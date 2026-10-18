import json
import math
import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import requests
from dotenv import load_dotenv

from app.graph.state import VideoState

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ExplainerVideoAgent/0.1 (educational research prototype)"

# Research tuning. Each planned query costs one search plus one summary
# request per new article, so keep these modest.
MAX_PLANNED_QUERIES = 4        # planner queries used after the original topic
MAX_GAP_QUERIES = 2            # extra searches for uncovered key questions
INITIAL_SEARCH_LIMIT = 10      # results for the user's original topic
RELATED_SEARCH_LIMIT = 5       # results for each planned or gap query
MAX_JUDGED_CANDIDATES = 25     # candidates sent to the relevance judge

# Critic tuning: fraction of the planner's required concepts that the
# script must mention before it can be approved.
MIN_CONCEPT_COVERAGE = 0.75


JOINED_WORD_FIXES = {
    "conversionofenergy": "conversion of energy",
    "solarelectricity": "solar electricity",
    "understandingthe": "understanding the",
    "ofenergy": "of energy",
    "toa": "to a",
    "lightand": "light and",
    "suchas": "such as",
    "andresearch": "and research",
    "useto": "use to",
    "fromsunlight": "from sunlight",
    "sunlightinto": "sunlight into",
    "annualpower": "annual power",
    "solarpower": "solar power",
    "naturallycirculate": "naturally circulate",
    "intoelectricity": "into electricity",
    "fromthe": "from the",
    "forthe": "for the",
    "circuitand": "circuit and",
    "assolar": "as solar",
    "arebroadly": "are broadly",
    "tablewithout": "table without",
    "ofdata": "of data",
    "toquickly": "to quickly",
    "indexcan": "index can",
    "thespeed": "the speed",
    "storagespace": "storage space",
    "andsearch": "and search",
}


def clean_research_text(text: str) -> str:
    """Repair known joined-word issues in retrieved research summaries."""
    text = re.sub(r"\s+", " ", text).strip()

    for joined, corrected in JOINED_WORD_FIXES.items():
        text = re.sub(
            rf"\b{re.escape(joined)}\b",
            corrected,
            text,
            flags=re.IGNORECASE,
        )

    # Only add a space after a comma before a letter, so numbers such as
    # "1,000" are left intact.
    text = re.sub(r",(?=[A-Za-z])", ", ", text)
    text = re.sub(r"(?<=[A-Za-z])\(", " (", text)
    return text


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "does", "do", "for",
    "from", "how", "in", "into", "is", "it", "of", "on", "or",
    "the", "to", "what", "when", "where", "which", "who", "why",
    "with", "work", "works", "explain", "explained", "understand",
}


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _gemini_json(prompt: str, max_output_tokens: int = 600) -> dict | None:
    """Run one JSON-mode Gemini request.

    Return the parsed JSON object, or None if Gemini is unavailable or
    its response cannot be processed. Callers must have a fallback.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
                max_output_tokens=max_output_tokens,
            ),
        )
        data = json.loads(response.text or "")
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _clean_str_list(value: object, limit: int) -> list[str]:
    """Return up to `limit` distinct, non-empty strings from a JSON value."""
    if not isinstance(value, list):
        return []

    cleaned = []
    seen = set()

    for item in value:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
        if len(cleaned) >= limit:
            break

    return cleaned


def _clean_concepts(value: object, limit: int = 6) -> list[dict]:
    """Validate planner output into [{"concept": str, "keywords": [str]}]."""
    if not isinstance(value, list):
        return []

    concepts = []

    for item in value:
        if not isinstance(item, dict):
            continue

        concept = item.get("concept")
        keywords = _clean_str_list(item.get("keywords"), 5)

        if not isinstance(concept, str) or not concept.strip() or not keywords:
            continue

        concepts.append({
            "concept": " ".join(concept.split()),
            "keywords": [keyword.lower() for keyword in keywords],
        })

        if len(concepts) >= limit:
            break

    return concepts


# ---------------------------------------------------------------------------
# Research planning
# ---------------------------------------------------------------------------

def plan_research(topic: str) -> dict:
    """Plan the research for any topic.

    Gemini suggests searches, questions, and concepts. It never supplies
    evidence; the research node retrieves and checks real sources.

    Falls back to a plan containing only the original topic.
    """
    topic = topic.strip()
    fallback = {
        "search_queries": [topic],
        "key_questions": [],
        "required_concepts": [],
    }

    prompt = (
        "You are planning research for a short explainer video. Suggest "
        "Wikipedia searches that would retrieve useful background, list "
        "the questions the video should answer, and list the concepts a "
        "script must cover. Do not answer the questions or state facts.\n\n"
        "Return JSON with exactly these fields:\n"
        "- search_queries: 3 to 5 Wikipedia article titles or short search "
        "phrases, covering different aspects of the topic. Be specific "
        "enough to avoid unrelated namesakes.\n"
        "- key_questions: 3 to 5 questions the explanation should answer.\n"
        "- required_concepts: 3 to 5 objects, each with a short "
        "\"concept\" description and a \"keywords\" list of 2 to 4 "
        "lowercase words or phrases (including common synonyms) that "
        "would likely appear in a script explaining that concept.\n\n"
        f"Topic: {topic}"
    )

    data = _gemini_json(prompt, max_output_tokens=800)
    if data is None:
        return fallback

    queries = _clean_str_list(data.get("search_queries"), MAX_PLANNED_QUERIES + 1)

    return {
        "search_queries": queries or [topic],
        "key_questions": _clean_str_list(data.get("key_questions"), 5),
        "required_concepts": _clean_concepts(data.get("required_concepts")),
    }


def expand_research_queries(
    topic: str,
    planned_queries: list[str] | None = None,
) -> list[str]:
    """Return the original topic followed by distinct planned searches."""
    queries = [topic.strip()]
    queries.extend(planned_queries or [])

    # Preserve order and remove duplicate queries.
    unique_queries = []
    seen = set()

    for query in queries:
        cleaned = query.strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            unique_queries.append(cleaned)
            seen.add(key)

    return unique_queries


# ---------------------------------------------------------------------------
# Source relevance
# ---------------------------------------------------------------------------

def _normalize_words(text: str) -> list[str]:
    """Normalize text into simple searchable word forms."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    normalized = []

    for word in words:
        # Basic plural handling: networks -> network, vaccines -> vaccine.
        if len(word) > 4 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]

        if word not in STOP_WORDS:
            normalized.append(word)

    return normalized


def is_relevant_source(topic: str, title: str, summary: str) -> bool:
    """Deterministic keyword baseline for source relevance.

    This is the fallback when Gemini is unavailable. It cannot tell
    namesakes apart (economic versus cosmic inflation, for instance),
    which is why semantic ranking is the primary filter.
    """
    normalized_topic = " ".join(topic.lower().split())
    title_lower = " ".join(title.lower().split())
    combined = f"{title_lower} {summary.lower()}"

    topic_words = set(_normalize_words(topic))
    title_words = set(_normalize_words(title))
    content_words = set(_normalize_words(combined))

    if not topic_words or not title_words:
        return False

    # Allow an exact title match.
    if title_lower in normalized_topic:
        return True

    # Accept titles made up entirely of topic keywords.
    if title_words.issubset(topic_words) and len(title_words) >= 2:
        return True

    # General relevance check.
    matched_words = topic_words & content_words
    required_matches = max(1, (len(topic_words) * 2 + 2) // 3)

    return len(matched_words) >= required_matches


def gemini_relevance_filter(
    topic: str,
    candidates: list[dict],
    key_questions: list[str] | None = None,
) -> tuple[list[dict], set[int]] | None:
    """Judge candidate relevance and key-question coverage in one request.

    Return (relevant candidates, indices of key questions that the
    relevant candidates help answer), or None if Gemini is unavailable
    or its response cannot be processed.
    """
    if not candidates:
        return None

    key_questions = key_questions or []

    candidate_data = [
        {
            "index": index,
            "title": source["title"],
            "summary": source["summary"][:1200],
        }
        for index, source in enumerate(candidates)
    ]
    question_data = [
        {"index": index, "question": question}
        for index, question in enumerate(key_questions)
    ]

    prompt = (
        "Decide which candidate Wikipedia articles are directly relevant "
        "to the user's research topic. Relevance means the article "
        "substantively helps explain or answer the topic, not merely that "
        "it shares a word or is a different subject with the same name. "
        "Reject tangential articles and namesakes. Prefer articles that "
        "use different terminology but explain the same subject. Use only "
        "the supplied titles and summaries.\n\n"
        "Return JSON with two fields:\n"
        "- relevant_indices: zero-based indices of relevant articles "
        "(an empty list if none are relevant).\n"
        "- covered_question_indices: zero-based indices of the key "
        "questions that the relevant articles' summaries help answer "
        "(an empty list if there are no key questions).\n\n"
        f"Topic: {topic}\n\n"
        f"Key questions: {json.dumps(question_data, ensure_ascii=False)}\n\n"
        f"Candidates: {json.dumps(candidate_data, ensure_ascii=False)}"
    )

    data = _gemini_json(prompt, max_output_tokens=400)
    if data is None:
        return None

    indices = data.get("relevant_indices")
    if not isinstance(indices, list):
        return None

    selected = []
    seen = set()

    for index in indices:
        if (
            isinstance(index, int)
            and not isinstance(index, bool)
            and 0 <= index < len(candidates)
            and index not in seen
        ):
            selected.append(candidates[index])
            seen.add(index)

    covered = set()
    raw_covered = data.get("covered_question_indices")

    if isinstance(raw_covered, list) and selected:
        for index in raw_covered:
            if (
                isinstance(index, int)
                and not isinstance(index, bool)
                and 0 <= index < len(key_questions)
            ):
                covered.add(index)

    return selected, covered


# ---------------------------------------------------------------------------
# Source cleaning and quality
# ---------------------------------------------------------------------------

def normalize_source_url(value: object) -> str | None:
    """Return a normalized HTTP(S) URL for safe source deduplication."""
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = urlsplit(value.strip())
        scheme = parsed.scheme.casefold()
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None

    if scheme not in {"http", "https"} or not hostname:
        return None

    hostname = hostname.casefold()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    netloc = hostname
    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"

    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def deduplicate_valid_sources(sources: list[dict]) -> list[dict]:
    """Keep only usable sources with distinct titles, URLs, and summaries."""
    unique = []
    seen_titles = set()
    seen_urls = set()
    seen_summaries = set()

    for source in sources:
        if not isinstance(source, dict):
            continue

        title = source.get("title")
        summary = source.get("summary")
        url = source.get("url")

        if not isinstance(title, str) or not isinstance(summary, str):
            continue

        title = title.strip()
        summary = summary.strip()
        normalized_url = normalize_source_url(url)

        if not title or not summary or normalized_url is None:
            continue

        title_key = " ".join(title.casefold().split())
        summary_key = " ".join(summary.casefold().split())

        if (
            title_key in seen_titles
            or normalized_url in seen_urls
            or summary_key in seen_summaries
        ):
            continue

        seen_titles.add(title_key)
        seen_urls.add(normalized_url)
        seen_summaries.add(summary_key)

        unique.append({
            "title": title,
            "url": url.strip(),
            "summary": summary,
        })

    return unique


def classify_research_quality(
    source_count: int,
    key_question_count: int = 0,
    covered_question_count: int | None = None,
) -> str:
    """Classify research coverage.

    Source count sets the baseline. When the planner supplied key
    questions and coverage was judged, poor coverage can downgrade
    "adequate" to "limited". Coverage never upgrades a rating, and
    this function never manufactures evidence.
    """
    if source_count < 2:
        return "insufficient"

    quality = "limited" if source_count == 2 else "adequate"

    if (
        quality == "adequate"
        and key_question_count > 0
        and covered_question_count is not None
        and covered_question_count / key_question_count < 0.5
    ):
        quality = "limited"

    return quality


# ---------------------------------------------------------------------------
# Wikipedia retrieval
# ---------------------------------------------------------------------------

def search_wikipedia(query: str, limit: int = 10) -> list[dict]:
    """Search Wikipedia and return raw search results."""
    response = requests.get(
        WIKIPEDIA_API,
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["query"]["search"]


def fetch_candidate(title: str) -> dict | None:
    """Fetch one article summary, or None if it is unusable."""
    slug = quote(title.replace(" ", "_"), safe="()_")
    page_url = "https://en.wikipedia.org/wiki/" + slug

    try:
        response = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + slug,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        page = response.json()
    except (requests.RequestException, ValueError):
        # Skip unavailable or malformed article responses.
        return None

    if not isinstance(page, dict):
        return None

    extract = page.get("extract", "")
    if not isinstance(extract, str):
        return None

    summary = clean_research_text(extract)
    if not summary:
        return None

    content_urls = page.get("content_urls", {})
    desktop = (
        content_urls.get("desktop", {})
        if isinstance(content_urls, dict)
        else {}
    )
    candidate_url = desktop.get("page") if isinstance(desktop, dict) else None

    # Fall back to the title-derived Wikipedia URL if needed.
    url = candidate_url if normalize_source_url(candidate_url) else page_url

    if normalize_source_url(url) is None:
        return None

    return {"title": title, "url": url, "summary": summary}


def evaluate_sources(
    topic: str,
    candidates: list[dict],
    key_questions: list[str],
) -> tuple[list[dict], set[int] | None]:
    """Select relevant sources and report which key questions they cover.

    Gemini's semantic judgment is preferred. If it is unavailable, fall
    back to the keyword baseline; coverage is then unknown (None).
    """
    deduped = deduplicate_valid_sources(candidates)[:MAX_JUDGED_CANDIDATES]

    judged = gemini_relevance_filter(topic, deduped, key_questions)
    if judged is not None:
        selected, covered = judged
        return deduplicate_valid_sources(selected), covered

    baseline = [
        item
        for item in deduped
        if is_relevant_source(topic, item["title"], item["summary"])
    ]
    return deduplicate_valid_sources(baseline), None


def research_node(state: VideoState) -> dict:
    """Retrieve relevant Wikipedia summaries using planned, iterative search."""
    topic = state["topic"].strip()

    if not topic:
        raise ValueError("The research topic cannot be empty.")

    try:
        plan = plan_research(topic)
        key_questions = plan["key_questions"]
        queries = expand_research_queries(topic, plan["search_queries"])

        candidates: list[dict] = []
        seen_titles: set[str] = set()

        def add_candidates(search_results: list[dict]) -> None:
            """Fetch summaries, skipping malformed or repeated results."""
            for result in search_results:
                if not isinstance(result, dict):
                    continue

                title = result.get("title")
                if not isinstance(title, str) or not title.strip():
                    continue

                title = title.strip()
                title_key = " ".join(title.casefold().split())

                # Avoid refetching the same article across searches.
                if not title_key or title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                candidate = fetch_candidate(title)
                if candidate is not None:
                    candidates.append(candidate)

        def run_searches(search_queries: list[str], limit: int) -> None:
            for query in search_queries:
                try:
                    add_candidates(search_wikipedia(query, limit))
                except (requests.RequestException, KeyError, ValueError):
                    continue

        # Always search the user's original topic first, and let a
        # failure here surface as a research error.
        initial_results = search_wikipedia(queries[0], INITIAL_SEARCH_LIMIT)

        if not initial_results:
            # Related searches may still find useful material.
            print(f"No direct Wikipedia results for: {topic}")

        add_candidates(initial_results)

        # Planned searches add other aspects of the topic.
        run_searches(queries[1:MAX_PLANNED_QUERIES + 1], RELATED_SEARCH_LIMIT)

        sources, covered = evaluate_sources(topic, candidates, key_questions)

        # Evidence-driven follow-up: search for key questions that the
        # current sources do not appear to answer, then re-evaluate once.
        if covered is not None and key_questions:
            missing = [
                question
                for index, question in enumerate(key_questions)
                if index not in covered
            ]
            if missing:
                before = len(candidates)
                run_searches(missing[:MAX_GAP_QUERIES], RELATED_SEARCH_LIMIT)

                if len(candidates) > before:
                    sources, covered = evaluate_sources(
                        topic, candidates, key_questions
                    )

        if not candidates:
            raise RuntimeError(
                "Wikipedia search returned no usable article summaries. "
                "Check your connection and try again."
            )

        if not sources:
            raise RuntimeError(
                "No sufficiently relevant research sources were found. "
                "Try a more specific topic or check the research results."
            )

        research_notes = [
            f"{item['title']}: {item['summary']}"
            for item in sources
        ]

        return {
            "research_notes": research_notes,
            "research_sources": sources,
            "research_quality": classify_research_quality(
                len(sources),
                len(key_questions),
                len(covered) if covered is not None else None,
            ),
            "key_questions": key_questions,
            "required_concepts": plan["required_concepts"],
        }

    except requests.RequestException as exc:
        raise RuntimeError(
            "Research failed while contacting Wikipedia. "
            "Check your internet connection and try again."
        ) from exc


# ---------------------------------------------------------------------------
# Script writing
# ---------------------------------------------------------------------------

def scriptwriter_node(state: VideoState) -> dict:
    """Deterministic, topic-agnostic fallback writer.

    It quotes the opening sentence of the first sources. It is used when
    Gemini is unavailable and makes no topic-specific claims.
    """
    topic = state["topic"].strip()
    if not topic:
        raise ValueError("A topic is required to write the script.")

    sources = state.get("research_sources", [])
    if not sources:
        raise RuntimeError(
            "No research sources are available for the fallback writer."
        )

    def excerpt(source: dict, max_words: int = 35) -> str:
        summary = clean_research_text(source["summary"])
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        first_sentence = sentences[0] if sentences else summary
        return " ".join(first_sentence.split()[:max_words]).rstrip(". ")

    first = sources[0]
    second = sources[1] if len(sources) > 1 else None

    # Turn question-style topics into natural phrases for the script.
    topic_label = topic.rstrip(".!?").strip()
    topic_label = re.sub(
        r"^(how does|how do|how is|how are|how can|what is|what are)\s+",
        "",
        topic_label,
        flags=re.IGNORECASE,
    )
    topic_label = re.sub(
        r"\s+work(s)?$",
        "",
        topic_label,
        flags=re.IGNORECASE,
    ).strip()

    parts = [
        f"Imagine exploring {topic_label} and discovering how it works.",
        f"One important starting point is {first['title']}. "
        f"The research describes this idea: {excerpt(first)}.",
    ]

    if second is not None:
        parts.append(
            f"Another source, {second['title']}, explains: {excerpt(second)}."
        )

    parts.append(
        f"Together, these details help explain {topic_label}. "
        f"{first['title']} provides this key detail: {excerpt(first)}."
    )

    if second is not None:
        parts.append(
            f"{second['title']} adds another important detail: "
            f"{excerpt(second)}. Read together, these details show "
            f"how the retrieved evidence relates to {topic_label}."
        )

    script = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return {"script": script}


def gemini_scriptwriter_node(state: VideoState) -> dict:
    """Generate a script grounded in the retrieved research.

    This is the general writing path. It works for any topic by
    following the supplied evidence, key questions, and required
    concepts rather than topic-specific templates.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    if not api_key or not api_key.strip():
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to backend/.env."
        )

    from google import genai
    from google.genai import types

    sources = state.get("research_sources", [])
    evidence = "\n\n".join(
        f"Source: {source['title']}\n"
        f"URL: {source['url']}\n"
        f"Summary: {source['summary']}"
        for source in sources
    )

    if not evidence:
        raise RuntimeError(
            "No research sources are available. "
            "Run the research node before generating a script."
        )

    system_instruction = """
You are an explainer-video scriptwriter.

Write an engaging, clear script for a general audience.
Start with a curiosity-driven hook beginning with "Imagine".
Aim for approximately 100-150 words.
Use simple language and a logical sequence that follows the evidence.
Use only factual claims reasonably supported by the supplied sources.
Do not invent statistics, quotations, sources, or citations.
The supplied sources may contain errors; do not claim they independently
verify every fact.
If evidence is insufficient, avoid unsupported details rather than
filling gaps from memory.
Check the final script for missing spaces between words, accidental
joined words, duplicated words, and awkward sentence boundaries.
Use normal punctuation and a space between every separate word.
Before returning, reread the complete script for formatting errors.
For evidence screening, write each factual sentence using key terms and
relationships explicitly present in at least one supplied source summary.
Prefer clear, close paraphrases over broad analogies or decorative claims.
Do not present an analogy as a factual claim about the topic.
When critic feedback identifies limited word overlap, rewrite the flagged
sentence using supported source wording or remove it; do not merely swap
synonyms or repeat the same claim in different words.
Avoid concluding restatements that introduce new claims.
When revising, address each critic issue without inventing evidence.
Return JSON with two fields: "script" (the script text only, with no
title or commentary) and "sources_used" (the titles of the supplied
sources the script relies on).
""".strip()

    key_questions = state.get("key_questions") or []
    required_concepts = state.get("required_concepts") or []
    critique = (state.get("critique") or "").strip()
    previous_script = (state.get("script") or "").strip()

    planning_context = ""
    if key_questions:
        planning_context += (
            "Questions the script should answer where the sources "
            "support an answer:\n"
            + "\n".join(f"- {question}" for question in key_questions)
            + "\n\n"
        )
    if required_concepts:
        planning_context += (
            "Concepts the script should explain where the sources "
            "support them:\n"
            + "\n".join(
                f"- {item['concept']} "
                f"(related terms: {', '.join(item['keywords'])})"
                for item in required_concepts
            )
            + "\n\n"
        )

    if critique and previous_script:
        revision_instructions = (
            "Revise the previous script below to address the critic "
            "feedback. Keep supported claims and change only what the "
            "feedback requires.\n\n"
            f"Previous script:\n{previous_script}\n\n"
            f"Critic feedback:\n{critique}\n\n"
            "For each sentence flagged for limited word overlap, either "
            "rewrite it using wording and concepts traceable to one "
            "supplied source summary, or remove it. Do not preserve a "
            "flagged analogy by merely changing its wording. Keep the "
            "opening beginning with Imagine, but make the hook itself "
            "evidence-aligned. Do not add unsupported replacement claims."
            "\n\n"
        )
    elif critique:
        revision_instructions = (
            f"Address this critic feedback:\n{critique}\n\n"
        )
    else:
        revision_instructions = ""

    prompt = (
        f"Topic: {state['topic']}\n\n"
        f"{planning_context}"
        f"Research from Wikipedia:\n{evidence}\n\n"
        f"{revision_instructions}"
        "Write the explainer-video script using this evidence, following "
        "all script requirements."
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.4,
                max_output_tokens=1200,
            ),
        )
    except Exception as exc:
        raise RuntimeError(
            "Gemini script generation failed. Check your API key, "
            "model availability, internet connection, and API quota. "
            f"Details: {exc}"
        ) from exc

    raw_text = (response.text or "").strip()
    script = ""
    sources_used: list[str] = []

    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            script_value = data.get("script")
            if isinstance(script_value, str):
                script = script_value.strip()
            sources_used = _clean_str_list(data.get("sources_used"), 10)
    except ValueError:
        # Fall back to treating the response as plain script text.
        script = raw_text

    if not script:
        raise RuntimeError(
            "Gemini returned an empty script. Try the request again."
        )

    # Keep only citations that match supplied sources.
    known_titles = {source["title"].casefold(): source["title"] for source in sources}
    script_sources = [
        known_titles[title.casefold()]
        for title in sources_used
        if title.casefold() in known_titles
    ]

    return {
        "script": clean_research_text(script),
        "script_sources": script_sources,
    }


def grounded_scriptwriter_node(state: VideoState) -> dict:
    """General writer: Gemini first, deterministic fallback if it fails.

    Use this as the workflow's writer (and as the `writer` passed to
    revise_script_node) so a missing key or API error does not stop the
    workflow.
    """
    try:
        return gemini_scriptwriter_node(state)
    except RuntimeError as exc:
        print(f"Gemini writer unavailable, using fallback writer: {exc}")
        return scriptwriter_node(state)


# ---------------------------------------------------------------------------
# Critic
# ---------------------------------------------------------------------------

def critic_node(state: VideoState) -> dict:
    """Check structure, topic coverage, concept coverage, and evidence overlap."""
    script = state["script"].strip()
    topic = state["topic"].strip()
    words = script.split()
    issues = []

    if not script.startswith("Imagine"):
        issues.append(
            "Start with a curiosity-driven hook beginning with 'Imagine'."
        )

    if not 80 <= len(words) <= 180:
        issues.append(
            f"The script must contain 80-180 words; it currently has "
            f"{len(words)}."
        )

    sources = state.get("research_sources", [])
    research_quality = state.get("research_quality", "unknown")
    research_warning = ""

    if research_quality == "insufficient":
        issues.append(
            "Research coverage is insufficient: fewer than two relevant "
            "sources are available. Additional research is required "
            "before this script can be approved."
        )
    elif research_quality == "limited":
        research_warning = (
            "Research coverage is limited; verify key claims against "
            "the full sources before publication."
        )

    if not sources:
        issues.append(
            "At least one research source is required before approval."
        )

    if len(words) < 10:
        issues.append(
            "The script needs enough meaningful content to explain the topic."
        )

    lower_script = script.lower()
    disclaimer_phrases = (
        "the source summary identifies",
        "we should distinguish what the sources state",
        "together, these sources provide a starting point",
        "research summaries help guide the explanation",
        "not proof that every detail has been independently verified",
    )
    if any(phrase in lower_script for phrase in disclaimer_phrases):
        issues.append(
            "Replace research disclaimers with a substantive explanation "
            "of the topic."
        )

    stopwords = {
        "about", "after", "again", "also", "and", "are", "because",
        "before", "being", "between", "but", "can", "could", "does",
        "each", "for", "from", "have", "into", "its", "just", "like",
        "more", "most", "not", "often", "only", "other", "over", "some",
        "such", "than", "that", "the", "their", "them", "then", "there",
        "these", "they", "this", "those", "through", "under", "using",
        "very", "was", "were", "what", "when", "where", "which", "while",
        "with", "would", "your", "you", "how", "why", "who", "will",
        "our", "out", "all", "any", "has", "had", "his", "her",
        "she", "him", "been", "it", "is", "in",
        "on", "of", "to", "as", "at", "by", "a", "an", "i", "we",
        "he", "or", "if", "do", "did", "up", "so", "now",
        "imagine", "explanation", "explains", "explain",
    }

    def content_terms(text: str) -> set[str]:
        terms = set()
        for word in re.findall(r"[a-zA-Z]{3,}", text.lower()):
            if word in stopwords:
                continue
            # Normalize common plurals for simple word matching.
            if len(word) > 4 and word.endswith("s"):
                word = word[:-1]
            terms.add(word)
        return terms

    topic_terms = content_terms(topic)
    script_terms = content_terms(script)

    if topic_terms and not (topic_terms & script_terms):
        issues.append(
            "The script does not clearly cover the requested topic."
        )

    # Per-video learning objectives come from the research plan, not from
    # topic-specific branches. A concept counts as covered when any of its
    # keywords appears in the script.
    required_concepts = state.get("required_concepts") or []
    if required_concepts:
        missing_concepts = [
            item["concept"]
            for item in required_concepts
            if not any(keyword in lower_script for keyword in item["keywords"])
        ]
        covered_count = len(required_concepts) - len(missing_concepts)
        needed = math.ceil(len(required_concepts) * MIN_CONCEPT_COVERAGE)

        if covered_count < needed:
            issues.append(
                "The script does not yet explain these planned concepts: "
                + "; ".join(missing_concepts)
                + ". Cover them only where the sources support them."
            )

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", script)
        if sentence.strip()
    ]
    unsupported = []
    weak_claims = []
    supported_count = 0

    # These are explanatory transitions, not standalone factual claims.
    non_claim_prefixes = (
        "together, these details help explain",
        "to understand the process,",
        "consider what starts the process,",
        "these connections help turn",
        "the retrieved summaries provide a starting point",
        "the full sources should be consulted",
        "read together, these details show how the retrieved evidence relates to",
    )

    # Compare each claim with each source separately. This prevents
    # unrelated terms spread across sources from inflating support.
    if sources:
        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_terms = content_terms(sentence)

            if sentence.lower().startswith(non_claim_prefixes):
                continue

            # Short hooks and transitions are difficult to assess reliably.
            if len(sentence_words) < 8 or len(sentence_terms) < 3:
                continue

            best_overlap = 0
            best_ratio = 0.0

            for source in sources:
                source_terms_for_claim = content_terms(
                    f"{source.get('title', '')} "
                    f"{source.get('summary', '')}"
                )
                overlap = sentence_terms & source_terms_for_claim
                ratio = len(overlap) / len(sentence_terms)

                if (ratio, len(overlap)) > (best_ratio, best_overlap):
                    best_ratio = ratio
                    best_overlap = len(overlap)

            if best_overlap >= 2 and best_ratio >= 0.35:
                supported_count += 1
            elif best_overlap >= 2 and best_ratio >= 0.15:
                weak_claims.append(sentence)
            else:
                unsupported.append(sentence)

    evidence_warning = ""
    if weak_claims:
        examples = " ".join(weak_claims[:2])
        evidence_warning = (
            f"Evidence review required: {len(weak_claims)} substantive "
            "sentence(s) have weak source matches. This may reflect "
            "paraphrasing or missing evidence; it is not proof the claims "
            f"are false. Example: {examples}"
        )

    if unsupported:
        examples = " ".join(unsupported[:2])
        issues.append(
            f"{len(unsupported)} substantive sentence(s) have limited "
            "word overlap with any individual source. Their evidence "
            "could not be matched reliably; revise or verify them before "
            f"approval. Example: {examples}"
        )

    if issues:
        critique = " ".join(issues)
        if research_warning:
            critique = f"{critique} {research_warning}"
        if evidence_warning:
            critique = f"{critique} {evidence_warning}"
        return {
            "critique": critique,
            "approved": False,
        }

    critique = (
        f"Structural and evidence-overlap checks passed: opening hook, "
        f"{len(words)} words, topic coverage, and research sources "
        "present. Text overlap is only a screening signal; factual "
        "accuracy has not been independently verified."
    )
    critique += (
        f" Evidence screening: {supported_count} supported match(es), "
        f"{len(weak_claims)} weak match(es), "
        f"{len(unsupported)} unsupported match(es)."
    )
    if evidence_warning:
        critique = f"{critique} {evidence_warning}"
    if research_warning:
        critique = f"{critique} {research_warning}"

    return {
        "critique": critique,
        "approved": True,
    }


def revise_script_node(state: VideoState, writer=None) -> dict:
    """Rewrite a rejected script, giving the writer the critic's feedback."""
    if state["revision_count"] >= 2:
        return {
            "critique": "Revision limit reached.",
            "approved": False,
            "revision_count": state["revision_count"],
        }

    if not state.get("research_sources"):
        return {
            "critique": "Cannot revise without research sources.",
            "approved": False,
        }

    # Use the workflow's selected writer; retain deterministic default
    # behavior for direct calls and existing tests.
    selected_writer = writer or scriptwriter_node
    revised = selected_writer(state)

    result = {
        "script": revised["script"],
        "revision_count": state["revision_count"] + 1,
    }

    if "script_sources" in revised:
        result["script_sources"] = revised["script_sources"]

    return result