from app.graph.workflow import build_graph


def initial_state(topic="How vaccines work"):
    return {
        "topic": topic,
        "research_notes": [],
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


def test_graph_preserves_topic():
    graph = build_graph()

    result = graph.invoke(
        initial_state("How does photosynthesis work")
    )

    assert result["topic"] == "How does photosynthesis work"
    assert result["approved"] is True


def test_research_is_marked_as_placeholder():
    graph = build_graph()

    result = graph.invoke(initial_state())

    assert len(result["research_notes"]) == 1
    assert "not a verified fact" in result["research_notes"][0]
