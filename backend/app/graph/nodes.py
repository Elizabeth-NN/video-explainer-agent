
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

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
            """Add unique article summaries to candidates."""
            for result in search_results:
                title = result["title"]
                title_key = " ".join(title.casefold().split())

                if title_key in seen_titles:
                    continue

                # Mark titles before fetching to avoid retrying duplicates.
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

                    summary = clean_research_text(
                        page.get("extract", "")
                    )
                    if not summary:
                        continue

                    candidates.append(
                        {
                            "title": title,
                            "url": page.get("content_urls", {})
                            .get("desktop", {})
                            .get("page", page_url),
                            "summary": summary,
                        }
                    )

                except requests.RequestException:
                    # Skip an unavailable article and continue.
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
            return [
                item
                for item in candidates
                if is_relevant_source(
                    topic, item["title"], item["summary"]
                )
            ]

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
            judged_sources = gemini_relevance_filter(topic, candidates)
            if judged_sources is not None:
                sources = judged_sources

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

    # Use the specialized solar fallback only when basic evidence exists.
    if any(
        term in normalized_topic
        for term in ("solar panel", "solar panels", "photovoltaic")
    ):
        # Use summaries, not titles, as evidence for technical claims.
        source_text = " ".join(
            source.get("summary", "")
            for source in sources
        ).lower()

        if all(
            term in source_text
            for term in ("sunlight", "electricity", "solar cell")
        ):
            parts = [
                "Imagine turning sunlight into electricity. "
                "Solar panels use solar cells to convert light energy "
                "into electrical energy."
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

            if "direct current" in source_text or " dc " in f" {source_text} ":
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
                    "alternating current for compatible electrical systems."
                )

            if "temperature" in source_text:
                parts.append(
                    "Temperature is one factor that can affect "
                    "solar-panel performance."
                )

            parts.append(
                "Understanding these components helps explain how "
                "solar technology can turn available sunlight into "
                "useful electrical power."
            )

            return {"script": " ".join(parts)}

    if "vaccine" in normalized_topic or "vaccination" in normalized_topic:
        script = (
            "Imagine giving your immune system a head start against a disease. "
            "That is the idea behind vaccination. A vaccine helps the body "
            "learn to recognize a disease-causing pathogen before it encounters "
            "the real threat. Depending on the vaccine, it may contain a "
            "weakened or inactivated germ, a harmless part of it, or another "
            "way to present information about the pathogen. These components "
            "can act as antigens, which the immune system learns to recognize. "
            "The body can then develop an immune response, including antibodies "
            "that help target the threat. Some immune cells also retain a memory "
            "of what they encountered. If the same pathogen appears later, the "
            "immune system may recognize it and respond more quickly. Different "
            "vaccines work in different ways, and protection varies by vaccine "
            "and person. The central idea is preparation: vaccination gives "
            "the immune system a chance to learn before a dangerous infection "
            "occurs. The research sources for this explanation include "
            + ", ".join(source["title"] for source in sources[:3])
            + "."
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

    prompt = (
        f"Topic: {state['topic']}\n\n"
        f"Research from Wikipedia:\n{evidence}\n\n"
        "Write the explainer-video script using this evidence."
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

    source_text = " ".join(
        f"{item.get('title', '')} {item.get('summary', '')}"
        for item in sources
    )
    source_terms = content_terms(source_text)

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", script)
        if sentence.strip()
    ]
    unsupported = []

    # These are explanatory transitions or research limitations, not
    # standalone factual claims that can be judged by word overlap.
    non_claim_prefixes = (
        "together, these details help explain",
        "to understand the process,",
        "consider what starts the process,",
        "these connections help turn",
        "the retrieved summaries provide a starting point",
        "the full sources should be consulted",
    )

    if sources:
        for sentence in sentences:
            sentence_words = sentence.split()
            sentence_terms = content_terms(sentence)

            if sentence.lower().startswith(non_claim_prefixes):
                continue

            # Short hooks and transitions are difficult to assess reliably.
            if len(sentence_words) < 8 or len(sentence_terms) < 3:
                continue

            overlap = sentence_terms & source_terms
            if not overlap:
                unsupported.append(sentence)

    if unsupported:
        examples = " ".join(unsupported[:2])
        issues.append(
            f"{len(unsupported)} substantive sentence(s) have limited "
            "word overlap with the retrieved sources. Review their "
            f"evidence before approval. Example: {examples}"
        )

    if issues:
        return {
            "critique": " ".join(issues),
            "approved": False,
        }

    return {
        "critique": (
            f"Structural and evidence-overlap checks passed: opening hook, "
            f"{len(words)} words, topic coverage, and research sources "
            "present. Text overlap is only a screening signal; factual "
            "accuracy has not been independently verified."
        ),
        "approved": True,
    }


def revise_script_node(state: VideoState) -> dict:
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

    # Rebuild rather than preserve sentences flagged by the critic.
    revised = scriptwriter_node(state)

    return {
        "script": revised["script"],
        "revision_count": state["revision_count"] + 1,
    }
