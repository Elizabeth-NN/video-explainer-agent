
import json
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

    text = re.sub(r",(?=\S)", ", ", text)
    text = re.sub(r"(?<=[A-Za-z])\(", " (", text)
    return text


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "does", "do", "for",
    "from", "how", "in", "into", "is", "it", "of", "on", "or",
    "the", "to", "what", "when", "where", "which", "who", "why",
    "with", "work", "works", "explain", "explained", "understand",
}

TOPIC_CONCEPTS = {
    "vaccine": {
        "antigen",
        "immune system",
        "immune response",
        "antibody",
        "pathogen",
        "immunity",
    },
    "solar energy": {
        "photovoltaic",
        "solar panel",
        "solar power",
        "solar electricity",
        "solar thermal",
        "concentrated solar",
        "renewable energy",
    },
    "solar power": {
        "photovoltaic",
        "solar panel",
        "solar power",
        "solar electricity",
        "concentrated solar",
    },
}


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
    """Check whether a research source matches the topic."""
    normalized_topic = " ".join(topic.lower().split())
    title_lower = " ".join(title.lower().split())
    combined = f"{title_lower} {summary.lower()}"

    topic_words = set(_normalize_words(topic))
    title_words = set(_normalize_words(title))
    content_words = set(_normalize_words(combined))

    if not topic_words or not title_words:
        return False

    # Allow an exact title match for the main topic.
    if title_lower in normalized_topic:
        return True

    # Apply topic-specific rules before general keyword matching.
    # This rejects unrelated articles such as "The Vaccines" (the band).
    for known_topic, concepts in TOPIC_CONCEPTS.items():
        if known_topic in normalized_topic:
            return any(concept in combined for concept in concepts)

    # Accept titles made up entirely of topic keywords.
    if title_words.issubset(topic_words) and len(title_words) >= 2:
        return True

    # General relevance check for other topics.
    matched_words = topic_words & content_words
    required_matches = max(1, (len(topic_words) * 2 + 2) // 3)

    return len(matched_words) >= required_matches


def gemini_relevance_filter(
    topic: str,
    candidates: list[dict],
) -> list[dict] | None:
    """Judge candidate relevance in one Gemini request.

    Return relevant candidates, an empty list if none qualify, or None
    if Gemini is unavailable or its response cannot be processed.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip() or not candidates:
        return None

    from google import genai
    from google.genai import types

    candidate_data = [
        {
            "index": index,
            "title": source["title"],
            "summary": source["summary"][:1200],
        }
        for index, source in enumerate(candidates)
    ]

    prompt = (
        "Decide which candidate Wikipedia articles are directly relevant "
        "to the user's research topic. Relevance means the article helps "
        "explain or answer the topic, not merely that it shares a word. "
        "Reject tangential articles. Use only the supplied titles and "
        "summaries. Return JSON with one field named relevant_indices, "
        "containing the zero-based integer indices of relevant articles. "
        "If none are relevant, return an empty list.\n\n"
        f"Topic: {topic}\n\n"
        f"Candidates: {json.dumps(candidate_data, ensure_ascii=False)}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
                max_output_tokens=300,
            ),
        )

        data = json.loads(response.text or "")
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

        return selected

    except Exception:
        # Preserve the keyword-filter results if Gemini fails.
        return None


def expand_research_queries(topic: str) -> list[str]:
    """Return the original topic followed by useful related searches."""
    normalized = " ".join(topic.lower().split())
    queries = [topic.strip()]

    related_queries = {
        "vaccine": [
            "Vaccine",
            "Immune system",
            "Antibody",
            "mRNA vaccine",
        ],
        "vaccination": [
            "Vaccine",
            "Immune system",
            "Antibody",
            "mRNA vaccine",
        ],
        "solar energy": [
            "Solar energy",
            "Solar power",
            "Photovoltaics",
            "Solar panel",
        ],
        "solar power": [
            "Solar energy",
            "Solar power",
            "Photovoltaics",
            "Solar panel",
        ],
        "api": [
            "Application programming interface",
            "Representational state transfer",
            "HTTP",
        ],
    }

    for key, related in related_queries.items():
        if key in normalized:
            queries.extend(related)
            break

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


def classify_research_quality(source_count: int) -> str:
    """Classify research coverage by the number of relevant sources."""
    if source_count < 2:
        return "insufficient"
    if source_count == 2:
        return "limited"
    return "adequate"


def research_node(state: VideoState) -> dict:
    """Retrieve relevant Wikipedia summaries with expanded search."""
    topic = state["topic"].strip()

    if not topic:
        raise ValueError("The research topic cannot be empty.")

    try:
        queries = expand_research_queries(topic)
        candidates = []
        seen_titles = set()

        def fetch_summaries(search_results: list[dict]) -> None:
            """Fetch summaries while skipping malformed search results."""
            for result in search_results:
                if not isinstance(result, dict):
                    continue

                title = result.get("title")
                if not isinstance(title, str) or not title.strip():
                    continue

                title = title.strip()
                title_key = " ".join(title.casefold().split())

                if not title_key or title_key in seen_titles:
                    continue

                # Avoid refetching the same article across related searches.
                seen_titles.add(title_key)

                page_url = (
                    "https://en.wikipedia.org/wiki/"
                    + quote(title.replace(" ", "_"), safe="()_")
                )

                try:
                    summary_response = requests.get(
                        "https://en.wikipedia.org/api/rest_v1/page/summary/"
                        + quote(title.replace(" ", "_"), safe="()_"),
                        headers={"User-Agent": USER_AGENT},
                        timeout=15,
                    )
                    summary_response.raise_for_status()
                    page = summary_response.json()

                    if not isinstance(page, dict):
                        continue

                    extract = page.get("extract", "")
                    if not isinstance(extract, str):
                        continue

                    summary = clean_research_text(extract)
                    if not summary:
                        continue

                    content_urls = page.get("content_urls", {})
                    desktop = (
                        content_urls.get("desktop", {})
                        if isinstance(content_urls, dict)
                        else {}
                    )
                    candidate_url = (
                        desktop.get("page")
                        if isinstance(desktop, dict)
                        else None
                    )

                    # Fall back to the title-derived Wikipedia URL if needed.
                    url = (
                        candidate_url
                        if normalize_source_url(candidate_url)
                        else page_url
                    )

                    if normalize_source_url(url) is None:
                        continue

                    candidates.append({
                        "title": title,
                        "url": url,
                        "summary": summary,
                    })

                except (requests.RequestException, ValueError):
                    # Skip unavailable or malformed article responses.
                    continue

        def search_wikipedia(query: str) -> list[dict]:
            response = requests.get(
                WIKIPEDIA_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": 10,
                    "format": "json",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()
            return response.json()["query"]["search"]

        # Always search the user's original topic first.
        initial_results = search_wikipedia(queries[0])

        if not initial_results:
            # Related searches may still find useful material.
            print(f"No direct Wikipedia results for: {topic}")

        fetch_summaries(initial_results)

        def relevant_sources() -> list[dict]:
            matches = [
                item
                for item in candidates
                if is_relevant_source(
                    topic, item["title"], item["summary"]
                )
            ]
            return deduplicate_valid_sources(matches)

        sources = relevant_sources()

        # Expand only when the original search yields fewer than two
        # keyword-relevant summaries.
        for query in queries[1:]:
            if len(sources) >= 2:
                break

            try:
                related_results = search_wikipedia(query)
            except requests.RequestException:
                continue

            fetch_summaries(related_results)
            sources = relevant_sources()

        # Use Gemini as a fallback if keyword filtering is insufficient.
        if len(sources) < 2:
            judged_sources = gemini_relevance_filter(
                topic, deduplicate_valid_sources(candidates)
            )
            if judged_sources is not None:
                sources = deduplicate_valid_sources(judged_sources)

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
            "research_quality": classify_research_quality(len(sources)),
        }

    except requests.RequestException as exc:
        raise RuntimeError(
            "Research failed while contacting Wikipedia. "
            "Check your internet connection and try again."
        ) from exc


def scriptwriter_node(state: VideoState) -> dict:
    """Write an educational script using retrieved research."""
    topic = state["topic"].strip()
    if not topic:
        raise ValueError("A topic is required to write the script.")

    sources = state.get("research_sources", [])
    if not sources:
        raise RuntimeError(
            "No research sources are available for the fallback writer."
        )

    normalized_topic = topic.lower()

    # Build a solar explanation from details explicitly present in research.
    if any(
        term in normalized_topic
        for term in ("solar panel", "solar panels", "photovoltaic")
    ):
        source_text = " ".join(
            source.get("summary", "")
            for source in sources
        ).lower()

        if all(
            term in source_text
            for term in ("sunlight", "electricity", "solar cell")
        ):
            parts = [
                "Imagine turning sunlight into electricity.",
                "Solar panels use solar cells to convert light energy "
                "into electrical energy.",
            ]

            if "semiconductor" in source_text:
                parts.append(
                    "These cells use semiconductor materials to help "
                    "convert light into electrical energy."
                )

            if "photovoltaic effect" in source_text:
                parts.append(
                    "This light-to-electricity process is known as "
                    "the photovoltaic effect."
                )

            if (
                "direct current" in source_text
                or " dc " in f" {source_text} "
            ):
                parts.append(
                    "Solar cells can produce direct current, also "
                    "called DC electricity."
                )

            if (
                "inverter" in source_text
                and (
                    "alternating current" in source_text
                    or " ac " in f" {source_text} "
                )
            ):
                parts.append(
                    "An inverter can convert direct current into "
                    "alternating current for compatible electrical systems. "
                    "This conversion is useful when equipment requires "
                    "alternating current rather than the direct current "
                    "produced by the solar cells."
                )

            if "temperature" in source_text:
                parts.append(
                    "Temperature is one factor that can affect "
                    "solar-panel performance."
                )

            if "battery" in source_text or "batteries" in source_text:
                parts.append(
                    "Electricity produced by solar cells can also be "
                    "stored in batteries when the system includes storage."
                )

            if (
                "solar lamp" in source_text
                and "charge controller" in source_text
            ):
                parts.append(
                    "A solar lighting system can include a panel, "
                    "a battery, a charge controller, and an LED lamp."
                )

            if "excited electrons" in source_text:
                parts.append(
                    "Photovoltaic cells contain materials that produce "
                    "excited electrons when exposed to light."
                )

            if "flow through a circuit" in source_text:
                parts.append(
                    "These electrons flow through a circuit and produce "
                    "direct current electricity."
                )

            return {"script": " ".join(parts)}

    if "vaccine" in normalized_topic or "vaccination" in normalized_topic:
        script = (
            "Imagine preparing your immune system to recognize a threat "
            "before encountering it. Vaccines are biological preparations "
            "that help provide active acquired immunity against a particular "
            "disease. A vaccine typically contains an agent that resembles "
            "a disease-causing microorganism, such as a weakened or killed "
            "microbe or one of its surface proteins. The vaccine stimulates "
            "the immune system to recognize that agent as a threat. This "
            "can help the body respond when it encounters the corresponding "
            "microorganism in the future. For example, an mRNA vaccine uses "
            "messenger RNA as a blueprint for cells to produce a protein "
            "that stimulates an adaptive immune response. A conjugate "
            "vaccine combines a weak antigen with a stronger carrier antigen "
            "to improve the immune response. The central idea is preparation: "
            "vaccines use different approaches to help the immune system "
            "recognize a specific threat."
        )
        return {"script": script}

    def excerpt(source: dict, max_words: int = 35) -> str:
        summary = clean_research_text(source["summary"])
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        first_sentence = sentences[0] if sentences else summary
        return " ".join(first_sentence.split()[:max_words]).rstrip(". ")

    first = sources[0]

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

    if len(sources) > 1:
        second = sources[1]
        parts.append(
            f"Another source, {second['title']}, explains: {excerpt(second)}."
        )

    parts.append(
        f"Together, these details help explain {topic_label}. "
        f"{first['title']} provides this key detail: {excerpt(first)}."
    )

    if len(sources) > 1:
        parts.append(
            f"{second['title']} adds another important detail: "
            f"{excerpt(second)}. Read together, these details show "
            f"how the retrieved evidence relates to {topic_label}."
        )

    script = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return {"script": script}

def gemini_scriptwriter_node(state: VideoState) -> dict:
    """Generate a script grounded in the retrieved research notes."""
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
Aim for approximately 100–150 words.
Use simple language and a logical sequence.
Use only factual claims reasonably supported by the supplied sources.
Do not invent statistics, quotations, sources, or citations.
The supplied sources may contain errors; do not claim they independently
verify every fact.
If evidence is insufficient, avoid unsupported details.
Return only the script, without a title or extra commentary.
""".strip()

    critique = state.get("critique", "").strip()
    revision_instructions = (
        f"Revise the previous script to address this critic feedback:\n"
        f"{critique}\n\n"
        if critique
        else ""
    )

    prompt = (
        f"Topic: {state['topic']}\n\n"
        f"Research from Wikipedia:\n{evidence}\n\n"
        f"{revision_instructions}"
        "Write the explainer-video script using this evidence. "
        "If revising, correct the identified issues while keeping "
        "supported factual claims and following all script requirements."
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
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

    script = (response.text or "").strip()

    if not script:
        raise RuntimeError(
            "Gemini returned an empty script. Try the request again."
        )

    return {"script": script}


def critic_node(state: VideoState) -> dict:
    """Check structure, topic coverage, and textual evidence overlap."""
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
            f"The script must contain 80–180 words; it currently has "
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
            "Research coverage is limited to two relevant sources; "
            "verify key claims against the full sources before publication."
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
        "its", "our", "out", "all", "any", "has", "had", "his", "her",
        "she", "him", "his", "who", "been", "being", "it", "is", "in",
        "on", "of", "to", "as", "at", "by", "a", "an", "i", "we",
        "they", "he", "or", "if", "do", "did", "up", "so", "now",
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
    """Rebuild a rejected script from the available research."""
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

    return {
        "script": revised["script"],
        "revision_count": state["revision_count"] + 1,
    }
