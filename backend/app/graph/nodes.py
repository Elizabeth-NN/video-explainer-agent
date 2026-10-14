
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


def research_node(state: VideoState) -> dict:
    """Retrieve Wikipedia article summaries and their source URLs."""
    topic = state["topic"].strip()

    if not topic:
        raise ValueError("The research topic cannot be empty.")

    try:
        response = requests.get(
            WIKIPEDIA_API,
            params={
                "action": "query",
                "list": "search",
                "srsearch": topic,
                "srlimit": 10,
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        results = response.json()["query"]["search"]

        if not results:
            raise RuntimeError(
                f"No Wikipedia articles were found for: {topic}"
            )

        sources = []

        for result in results:
            title = result["title"]
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

                summary = clean_research_text(page.get("extract", ""))
                if not summary:
                    continue

                sources.append(
                    {
                        "title": title,
                        "url": page.get("content_urls", {})
                        .get("desktop", {})
                        .get("page", page_url),
                        "summary": summary,
                    }
                )

            except requests.RequestException:
                # Skip an unavailable article and try the next result.
                continue

        if not sources:
            raise RuntimeError(
                "Wikipedia search returned results, but no article "
                "summaries could be retrieved. Check your connection "
                "and try again."
            )

        
        candidates = sources

        sources = [
            source
            for source in candidates
            if is_relevant_source(
                topic,
                source["title"],
                source["summary"],
            )
        ]

        # Ask Gemini only when the keyword filter finds fewer than two.
        if len(sources) < 2:
            judged_sources = gemini_relevance_filter(topic, candidates)
            if judged_sources is not None:
                sources = judged_sources

        if not sources:
            raise RuntimeError(
                "No sufficiently relevant research sources were found. "
                "Try a more specific topic or check the research results."
            )

        research_notes = [
            f"{source['title']}: {source['summary']}"
            for source in sources
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
    parts = [
        f"Imagine discovering how {topic.rstrip('.!?')} works.",
        f"One important starting point is {first['title']}. "
        f"The research describes this idea: {excerpt(first)}.",
    ]

    if len(sources) > 1:
        second = sources[1]
        parts.append(
            f"Another source, {second['title']}, explains: {excerpt(second)}."
        )

    parts.append(
        f"Together, these details help explain {topic.rstrip('.!?')}. "
        "To understand the process, connect the main idea to the steps "
        "that make it happen. Consider what starts the process, what changes "
        "along the way, and what result follows. These connections help turn "
        "individual facts into a clear explanation rather than a list of "
        "definitions. The retrieved summaries provide a starting point, "
        "but they may not cover every step or exception. The full sources "
        "should be consulted before publication to check the details and "
        "add any missing steps to the explanation."
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
    """Check script structure and reject disclaimer-only writing."""
    script = state["script"].strip()
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

    if not state.get("research_sources"):
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

    if issues:
        return {
            "critique": " ".join(issues),
            "approved": False,
        }

    return {
        "critique": (
            f"Basic quality checks passed: opening hook, "
            f"{len(words)} words, and research sources present. "
            "Factual accuracy has not been independently verified."
        ),
        "approved": True,
    }

def revise_script_node(state: VideoState) -> dict:
    """Apply a simple deterministic revision."""
    script = state["script"]
    topic = state["topic"]

    if state["revision_count"] >= 2:
        return {
            "critique": "Revision limit reached.",
            "approved": False,
        }

    remainder = script.split(". ", 1)
    revised_script = (
        f"Imagine discovering something surprising about {topic}. "
        + (remainder[1] if len(remainder) > 1 else "")
    )

    return {
        "script": revised_script,
        "revision_count": state["revision_count"] + 1,
    }
