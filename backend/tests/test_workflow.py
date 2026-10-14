
from unittest.mock import patch

from app.graph.nodes import (
    clean_research_text,
    critic_node,
    gemini_relevance_filter,
    is_relevant_source,
    research_node,
    revise_script_node,
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




def test_vaccine_relevance_excludes_unrelated_music_band():
    topic = "How vaccines work"

    assert is_relevant_source(
        topic,
        "Vaccine",
        "Vaccines stimulate the immune system to recognize antigens "
        "and develop immunity.",
    )
    assert not is_relevant_source(
        topic,
        "The Vaccines",
        "The Vaccines are an English indie rock band formed in London.",
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
    assert "Structural and evidence-overlap checks passed" in result["critique"]


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
    state = initial_state(topic="How a process works")
    state["script"] = (
        "Imagine learning how a process works. "
        + "This explanation describes the main steps and ideas. " * 12
    )
    state["research_sources"] = [
        {
            "title": "Process explanation",
            "url": "https://example.com/research",
            "summary": (
                "This explanation describes the main steps and ideas. "
                "Learning how a process works involves understanding "
                "the steps and ideas."
            ),
        }
    ]

    result = critic_node(state)

    assert result["approved"] is True
    assert "evidence-overlap checks passed" in result["critique"]
    assert "factual accuracy has not been independently verified" in (
        result["critique"]
    )


def test_critic_rejects_script_with_unsupported_sentence():
    state = initial_state(topic="How vaccines work")
    state["script"] = (
        "Imagine learning how vaccines work. "
        + "Vaccines help the immune system recognize specific pathogens. " * 9
        + "Purple elephants operate invisible underwater computers while astronauts bake imaginary cakes on Mars."
    )
    state["research_sources"] = [
        {
            "title": "Vaccine",
            "url": "https://example.com/vaccine",
            "summary": (
                "Vaccines help the immune system recognize pathogens. "
                "The immune system can develop a response to infection."
            ),
        }
    ]

    result = critic_node(state)

    assert result["approved"] is False
    assert "limited word overlap" in result["critique"]



def test_revision_rebuilds_script_from_research():
    state = initial_state(topic="How vaccines work")
    state["script"] = (
        "Imagine learning about vaccines. "
        + "Purple elephants operate invisible underwater computers. " * 5
    )
    state["research_sources"] = [
        {
            "title": "Vaccine",
            "url": "https://example.com/vaccine",
            "summary": (
                "Vaccines help the immune system recognize pathogens. "
                "The immune system can develop a response to infection."
            ),
        }
    ]

    result = revise_script_node(state)

    assert result["revision_count"] == 1
    assert result["script"].startswith("Imagine")
    assert "Purple elephants" not in result["script"]
    assert "immune system" in result["script"]


def test_revision_respects_revision_limit():
    state = initial_state()
    state["revision_count"] = 2
    state["script"] = "Original script"

    result = revise_script_node(state)

    assert result["approved"] is False
    assert result["critique"] == "Revision limit reached."
    assert "script" not in result
    assert result["revision_count"] == 2


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

def test_expand_research_queries_for_vaccines():
    from app.graph.nodes import expand_research_queries

    queries = expand_research_queries("How vaccines work")

    assert queries[0] == "How vaccines work"
    assert "Vaccine" in queries
    assert "Immune system" in queries
    assert "mRNA vaccine" in queries


def test_expand_research_queries_for_solar_energy():
    from app.graph.nodes import expand_research_queries

    queries = expand_research_queries("How does solar energy work?")

    assert queries[0] == "How does solar energy work?"
    assert "Solar power" in queries
    assert "Photovoltaics" in queries
    assert "Solar panel" in queries


def test_expand_research_queries_deduplicates_and_preserves_order():
    from app.graph.nodes import expand_research_queries

    queries = expand_research_queries("Vaccine")

    assert queries[0] == "Vaccine"
    assert len(queries) == len({query.casefold() for query in queries})


def test_expand_research_queries_keeps_unknown_topics():
    from app.graph.nodes import expand_research_queries

    assert expand_research_queries("How volcanoes erupt") == [
        "How volcanoes erupt"
    ]


def test_research_expands_queries_when_sources_are_insufficient(monkeypatch):
    import requests
    from app.graph.nodes import research_node

    search_queries = []
    summary_titles = []

    def fake_get(url, **kwargs):
        if url == "https://en.wikipedia.org/w/api.php":
            query = kwargs["params"]["srsearch"]
            search_queries.append(query)

            if query == "How vaccines work":
                results = [{"title": "Unrelated Topic"}]
            elif query == "Vaccine":
                results = [
                    {"title": "Vaccine"},
                    {"title": "Immune system"},
                    {"title": "Vaccine"},
                ]
            else:
                results = []

            response = type("Response", (), {})()
            response.raise_for_status = lambda: None
            response.json = lambda: {"query": {"search": results}}
            return response

        title = url.rsplit("/", 1)[-1].replace("_", " ")
        summary_titles.append(title)

        summaries = {
            "Unrelated Topic": "An unrelated subject with no vaccine information.",
            "Vaccine": (
                "A vaccine trains the immune system to recognize "
                "a pathogen and can provide immune protection."
            ),
            "Immune system": (
                "The immune system protects the body from pathogens "
                "using immune cells and antibodies."
            ),
        }

        response = type("Response", (), {})()
        response.raise_for_status = lambda: None
        response.json = lambda: {
            "extract": summaries[title],
            "content_urls": {
                "desktop": {"page": f"https://en.wikipedia.org/wiki/{title}"}
            },
        }
        return response

    monkeypatch.setattr("app.graph.nodes.requests.get", fake_get)
    monkeypatch.setattr(
        "app.graph.nodes.gemini_relevance_filter",
        lambda topic, candidates: None,
    )

    result = research_node({"topic": "How vaccines work"})

    assert search_queries[:2] == ["How vaccines work", "Vaccine"]
    assert len(result["research_sources"]) >= 2

    source_titles = [item["title"] for item in result["research_sources"]]
    assert len(source_titles) == len(set(source_titles))
    assert "Vaccine" in source_titles
    assert "Immune system" in source_titles
