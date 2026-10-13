
from unittest.mock import patch

from app.graph.nodes import (
    clean_research_text,
    critic_node,
    gemini_relevance_filter,
    is_relevant_source,
    research_node,
)
from app.graph.workflow import build_graph


def test_solar_energy_relevance_excludes_solar_corona():
    topic = "How does solar energy work?"

    assert is_relevant_source(
        topic,
        "Solar energy",
        "Solar energy comes from the Sun.",
    )

    assert is_relevant_source(
        topic,
        "Solar panel",
        "Solar panels use photovoltaic cells to convert sunlight into electricity.",
    )

    assert not is_relevant_source(
        topic,
        "Solar corona",
        "The solar corona is the Sun's outer atmosphere, filled with plasma.",
    )



def initial_state(topic="How vaccines work"):
    return {
        "topic": topic,
        "research_notes": [],
        "research_sources": [],
        "script": "",
        "critique": "",
        "approved": False,
        "revision_count": 0,
    }


def test_graph_revises_and_approves_script():
    fake_research = {
        "research_notes": [
            "Solar energy: Solar energy comes from sunlight.",
            "Solar panel: Solar panels convert sunlight into electricity.",
        ],
        "research_sources": [
            {
                "title": "Solar energy",
                "url": "https://example.com/solar-energy",
                "summary": "Solar energy comes from sunlight.",
            },
            {
                "title": "Solar panel",
                "url": "https://example.com/solar-panel",
                "summary": "Solar panels convert sunlight into electricity.",
            },
        ],
    }

    with patch(
        "app.graph.workflow.research_node",
        return_value=fake_research,
    ):
        graph = build_graph()
        state = initial_state("How does solar energy work?")
        result = graph.invoke(state)

    assert result["approved"] is True
    assert result["revision_count"] == 0
    assert result["script"].startswith("Imagine")
    assert 80 <= len(result["script"].split()) <= 180
    assert "Basic quality checks passed" in result["critique"]


def test_research_returns_source_titles_urls_and_summaries():
    fake_sources = [
        {
            "title": "Solar energy",
            "url": "https://en.wikipedia.org/wiki/Solar_energy",
            "summary": "Solar energy comes from the Sun.",
        },
        {
            "title": "Solar power",
            "url": "https://en.wikipedia.org/wiki/Solar_power",
            "summary": "Solar power converts sunlight into useful energy.",
        },
    ]

    with patch("app.graph.nodes.requests.get") as mock_get:
        search_response = mock_get.return_value
        search_response.raise_for_status.return_value = None
        search_response.json.return_value = {
            "query": {
                "search": [
                    {"title": "Solar energy"},
                    {"title": "Solar power"},
                ]
            }
        }

        summary_response = mock_get.side_effect = [
            search_response,
            type(
                "Response",
                (),
                {
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {
                        "extract": fake_sources[0]["summary"],
                        "content_urls": {
                            "desktop": {
                                "page": fake_sources[0]["url"]
                            }
                        },
                    },
                },
            )(),
            type(
                "Response",
                (),
                {
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {
                        "extract": fake_sources[1]["summary"],
                        "content_urls": {
                            "desktop": {
                                "page": fake_sources[1]["url"]
                            }
                        },
                    },
                },
            )(),
        ]

        result = research_node({"topic": "solar energy"})

    assert len(result["research_sources"]) == 2
    assert len(result["research_notes"]) == 2
    assert result["research_sources"][0]["title"] == "Solar energy"
    assert result["research_sources"][0]["url"] == fake_sources[0]["url"]
    assert "Sun" in result["research_sources"][0]["summary"]


def test_research_rejects_empty_topic():
    try:
        research_node({"topic": "  "})
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected an empty topic to be rejected.")


def test_gemini_relevance_filter_returns_selected_sources(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    candidates = [
        {
            "title": "Solar energy",
            "url": "https://example.com/solar-energy",
            "summary": "Solar energy comes from sunlight.",
        },
        {
            "title": "Solar corona",
            "url": "https://example.com/solar-corona",
            "summary": "The corona is the Sun's outer atmosphere.",
        },
    ]

    with patch("google.genai.Client") as mock_client:
        mock_client.return_value.models.generate_content.return_value.text = (
            '{"relevant_indices": [0]}'
        )

        result = gemini_relevance_filter("solar energy", candidates)

    assert result == [candidates[0]]


def test_gemini_relevance_filter_accepts_no_relevant_sources(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    candidates = [
        {
            "title": "Solar corona",
            "url": "https://example.com/solar-corona",
            "summary": "The corona is the Sun's outer atmosphere.",
        },
    ]

    with patch("google.genai.Client") as mock_client:
        mock_client.return_value.models.generate_content.return_value.text = (
            '{"relevant_indices": []}'
        )

        result = gemini_relevance_filter("solar energy", candidates)

    assert result == []


def test_gemini_relevance_filter_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    candidates = [
        {
            "title": "Solar energy",
            "url": "https://example.com/solar-energy",
            "summary": "Solar energy comes from sunlight.",
        },
    ]

    with patch("google.genai.Client", side_effect=RuntimeError("API unavailable")):
        result = gemini_relevance_filter("solar energy", candidates)

    assert result is None


def test_clean_research_text_repairs_known_joined_words():
    text = (
        "The conversion ofenergy from sunlight toa useful form "
        "involves lightand heat, suchas electricity."
    )

    result = clean_research_text(text)

    assert "of energy" in result
    assert "to a useful" in result
    assert "light and heat" in result
    assert "such as electricity" in result


def test_clean_research_text_preserves_normal_words():
    text = "Today, the hotspot is inside the building."

    result = clean_research_text(text)

    assert result == text


def test_clean_research_text_repairs_into_electricity():
    text = "Solar power converts sunlight intoelectricity."
    result = clean_research_text(text)

    assert result == "Solar power converts sunlight into electricity."


def test_critic_rejects_script_that_is_too_short():
    state = initial_state()
    state["script"] = "Imagine a short explanation."
    state["research_sources"] = [
        {
            "title": "Test source",
            "url": "https://example.com/research",
            "summary": "A source about the topic.",
        }
    ]

    result = critic_node(state)

    assert result["approved"] is False
    assert "80–180 words" in result["critique"]


def test_critic_rejects_script_without_sources():
    state = initial_state()
    state["script"] = "Imagine " + "word " * 85
    state["research_sources"] = []

    result = critic_node(state)

    assert result["approved"] is False
    assert "research source is required" in result["critique"]


def test_critic_approves_script_meeting_basic_checks():
    state = initial_state()
    state["script"] = (
        "Imagine learning how a process works. "
        + "This explanation describes the main steps and ideas. " * 12
    )
    state["research_sources"] = [
        {
            "title": "Test source",
            "url": "https://example.com/research",
            "summary": "A source about the topic.",
        }
    ]

    result = critic_node(state)

    assert result["approved"] is True
    assert "Basic quality checks passed" in result["critique"]
    assert "Factual accuracy has not been independently verified." in result["critique"]



def test_clean_research_text_repairs_solar_summary_phrases():
    text = (
        "Solar power is the conversion ofenergy from sunlight into "
        "electricity. Systems focus sunlight toa hot spot. "
        "Solar energy uses lightand heat with technologies suchas "
        "solar electricity. The UK's annualpower generation is growing."
    )

    result = clean_research_text(text)

    assert "conversion of energy" in result
    assert "sunlight to a hot spot" in result
    assert "light and heat" in result
    assert "such as solar electricity" in result
    assert "annual power generation" in result
