
import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from app.graph.state import VideoState

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ExplainerVideoAgent/0.1 (educational research prototype)"



import re

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "does", "do", "for",
    "from", "how", "in", "into", "is", "it", "of", "on", "or",
    "the", "to", "what", "when", "where", "which", "who", "why",
    "with", "work", "works", "explain", "explained", "understand",
}

TOPIC_CONCEPTS = {
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

    # Accept an exact match or a title made entirely of topic keywords.
    if title_words == topic_words:
        return True

    if title_words.issubset(topic_words) and len(title_words) >= 2:
        return True

    # Special handling prevents unrelated solar articles from passing.
    for known_topic, concepts in TOPIC_CONCEPTS.items():
        if known_topic in normalized_topic:
            return any(concept in combined for concept in concepts)

    # General relevance check for other topics.
    matched_words = topic_words & content_words
    required_matches = max(1, (len(topic_words) * 2 + 2) // 3)

    return len(matched_words) >= required_matches



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
                "srlimit": 3,
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

                summary = page.get("extract", "").strip()
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

        
        sources = [
            source
            for source in sources
            if is_relevant_source(
                topic,
                source["title"],
                source["summary"],
            )
        ]

        if not sources:
            raise RuntimeError(
                "No sufficiently relevant research sources were found. "
                "Try a more specific topic."
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
    """Generate a deterministic demonstration script for tests."""
    topic = state["topic"]
    script = (
        f"Today we will explore {topic} step by step. "
        "First, we will define the main idea and explain why it matters "
        "in everyday life. Next, we will look at the key parts of the "
        "process and how they work together. We will connect those parts "
        "to a simple example, so the explanation is easier to follow. "
        "We will also point out a common misunderstanding and clarify "
        "what the available research can and cannot tell us. "
        "By the end, you should be able to describe the basic idea, "
        "recognize its main steps, and ask better questions about the "
        "details. Remember, this overview is a starting point, not a "
        "substitute for checking reliable sources."
    )
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
    """Check basic script quality without making another API call."""
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
