import json
from unittest.mock import patch

from app.graph.semantic_extractor import extract_semantic_graph


VALID_GRAPH = {
    "schema_version": 1,
    "nodes": [
        {"id": "water_vapor", "label": "Water vapor"},
        {"id": "droplets", "label": "Tiny droplets"},
    ],
    "edges": [
        {
            "source": "water_vapor",
            "target": "droplets",
            "relationship": "transforms",
        }
    ],
}


def mock_gemini_response(graph):
    client = patch("google.genai.Client").start()
    client.return_value.models.generate_content.return_value.text = json.dumps(
        graph
    )
    return client


def test_extracts_and_validates_a_semantic_graph(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client = mock_gemini_response(VALID_GRAPH)

    try:
        result = extract_semantic_graph(
            "Water vapor cools and forms tiny droplets."
        )

        assert result == VALID_GRAPH
        client.assert_called_once()
        client.return_value.models.generate_content.assert_called_once()
    finally:
        patch.stopall()


def test_returns_none_when_api_key_is_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert extract_semantic_graph(
        "Water vapor cools and forms tiny droplets."
    ) is None


def test_returns_none_for_empty_narration(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    with patch("google.genai.Client") as client:
        assert extract_semantic_graph("   ") is None
        client.assert_not_called()


def test_returns_none_for_invalid_json(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    with patch("google.genai.Client") as client:
        client.return_value.models.generate_content.return_value.text = (
            "This is not JSON"
        )

        assert extract_semantic_graph("Some narration.") is None


def test_returns_none_for_invalid_graph(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    invalid_graph = {
        "schema_version": 1,
        "nodes": [{"id": "water", "label": "Water"}],
        "edges": [
            {
                "source": "water",
                "target": "missing_node",
                "relationship": "causes",
            }
        ],
    }

    with patch("google.genai.Client") as client:
        client.return_value.models.generate_content.return_value.text = (
            json.dumps(invalid_graph)
        )

        assert extract_semantic_graph("Water causes something.") is None


def test_returns_none_when_gemini_fails(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    with patch("google.genai.Client", side_effect=RuntimeError("test error")):
        assert extract_semantic_graph("Some narration.") is None


def test_returns_none_when_gemini_finds_no_relationship(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    empty_graph = {
        "schema_version": 1,
        "nodes": [],
        "edges": [],
    }

    with patch("google.genai.Client") as client:
        client.return_value.models.generate_content.return_value.text = (
            json.dumps(empty_graph)
        )

        assert extract_semantic_graph("A general introductory sentence.") is None
