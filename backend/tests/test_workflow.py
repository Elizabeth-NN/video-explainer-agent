
from unittest.mock import patch

from app.graph.nodes import research_node
from app.graph.workflow import build_graph

from app.graph.nodes import is_relevant_source


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
    graph = build_graph()

    result = graph.invoke(initial_state())

    assert result["approved"] is True
    assert result["revision_count"] == 1
    assert result["script"].startswith("Imagine")
    assert result["critique"] == (
        "The hook passed the demonstration quality check."
    )


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
