
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
        "research_quality": "insufficient",
        "script": "",
        "critique": "",
        "approved": False,
        "revision_count": 0,
    }


def test_graph_revises_and_approves_script():
    fake_research = {
        "research_quality": "limited",
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



def test_research_deduplicates_identical_summaries(monkeypatch):
    from app.graph.nodes import research_node

    summaries = {
        "Solar energy": (
            "Solar energy comes from sunlight and is a form "
            "of renewable energy."
        ),
        "Solar power": (
            "Solar power converts sunlight into useful energy."
        ),
        "Solar energy overview": (
            "Solar energy comes from sunlight and is a form "
            "of renewable energy."
        ),
    }

    def fake_get(url, **kwargs):
        response = type("Response", (), {})()
        response.raise_for_status = lambda: None

        if url == "https://en.wikipedia.org/w/api.php":
            response.json = lambda: {
                "query": {
                    "search": [
                        {"title": "Solar energy"},
                        {"title": "Solar power"},
                        {"title": "Solar energy overview"},
                    ]
                }
            }
        else:
            title = url.rsplit("/", 1)[-1].replace("_", " ")
            response.json = lambda: {
                "extract": summaries[title],
                "content_urls": {
                    "desktop": {
                        "page": f"https://en.wikipedia.org/wiki/{title}"
                    }
                },
            }

        return response

    monkeypatch.setattr("app.graph.nodes.requests.get", fake_get)
    monkeypatch.setattr(
        "app.graph.nodes.gemini_relevance_filter",
        lambda topic, candidates: None,
    )

    result = research_node({"topic": "solar energy"})

    source_titles = [
        source["title"] for source in result["research_sources"]
    ]

    assert source_titles == ["Solar energy", "Solar power"]
    assert len(result["research_sources"]) == 2
    assert len(result["research_notes"]) == 2


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

    state["research_quality"] = "limited"
    state["research_sources"].append(
        state["research_sources"][0].copy()
    )

    result = critic_node(state)

    assert result["approved"] is True
    assert "evidence-overlap checks passed" in result["critique"]
    assert "factual accuracy has not been independently verified" in (
        result["critique"]
    )
    assert "Research coverage is limited" in result["critique"]


def test_critic_flags_creative_opening_hook_with_limited_overlap():
    state = initial_state(
        topic="How solar panels convert sunlight into electricity"
    )
    state["script"] = (
        "Imagine a world where your roof acts like a giant battery, "
        "turning pure sunshine into the power that runs your home. "
        + "Photovoltaic cells convert sunlight directly into electricity "
        "using semiconductor materials. " * 10
    )
    state["research_sources"] = [
        {
            "title": "Solar energy",
            "url": "https://example.com/solar-energy",
            "summary": (
                "Photovoltaic cells convert sunlight into electricity "
                "using semiconductor materials."
            ),
        }
    ]

    result = critic_node(state)

    assert result["approved"] is False
    assert "limited word overlap" in result["critique"]


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



def test_solar_fallback_writer_explains_conversion_process():
    from app.graph.nodes import scriptwriter_node

    state = initial_state(
        topic="How solar panels convert sunlight into electricity"
    )
    state["research_sources"] = [
        {
            "title": "Solar energy",
            "url": "https://example.com/solar-energy",
            "summary": (
                "Sunlight provides energy. Solar cells use semiconductor "
                "materials to convert sunlight into electricity through "
                "the photovoltaic effect. Temperature can affect "
                "solar-panel performance."
            ),
        },
        {
            "title": "Solar cell",
            "url": "https://example.com/solar-cell",
            "summary": (
                "A solar cell converts light into electricity. "
                "Solar cells produce direct current. An inverter can "
                "convert direct current into alternating current."
            ),
        },
    ]

    result = scriptwriter_node(state)
    script = result["script"].lower()

    assert result["script"].startswith("Imagine")
    assert "photovoltaic effect" in script
    assert "semiconductor" in script
    assert "inverter" in script
    assert 80 <= len(result["script"].split()) <= 180
    assert "retrieved summaries provide a starting point" not in script
    assert "should be consulted before publication" not in script



def test_solar_fallback_omits_unsupported_technical_claims():
    from app.graph.nodes import scriptwriter_node

    state = initial_state(
        topic="How solar panels convert sunlight into electricity"
    )
    state["research_sources"] = [
        {
            "title": "Solar energy basics",
            "url": "https://example.com/solar-basics",
            "summary": (
                "Sunlight provides energy. Solar cells convert sunlight "
                "into electricity."
            ),
        }
    ]

    script = scriptwriter_node(state)["script"].lower()

    assert "sunlight" in script
    assert "solar cells" in script
    assert "electricity" in script
    assert "semiconductor" not in script
    assert "photovoltaic effect" not in script
    assert "direct current" not in script
    assert "inverter" not in script
    assert "alternating current" not in script
    assert "temperature" not in script

def test_heart_fallback_explains_blood_flow_sequence():
    from app.graph.nodes import scriptwriter_node

    state = initial_state(topic="How the human heart pumps blood")
    state["research_sources"] = [
        {
            "title": "Anatomy of the human heart",
            "url": "https://example.com/heart-anatomy",
            "summary": (
                "The heart is a muscular organ situated in the mediastinum. "
                "It consists of four chambers and four valves. The right "
                "side receives de-oxygenated blood through the superior "
                "and inferior venae cavae and pumps blood to the lungs "
                "through the pulmonary artery. The left side receives "
                "saturated blood from the lungs."
            ),
        },
        {
            "title": "Heart",
            "url": "https://example.com/heart",
            "summary": (
                "The heart pumps blood through the blood vessels. "
                "Blood carries oxygen and nutrients to tissue and carries "
                "metabolic waste such as carbon dioxide to the lungs."
            ),
        },
    ]

    script = scriptwriter_node(state)["script"]
    lower = script.lower()

    assert script.startswith("Imagine")
    assert 80 <= len(script.split()) <= 180
    for term in (
        "right side",
        "venae cavae",
        "pulmonary artery",
        "lungs",
        "left side",
        "blood vessels",
    ):
        assert term in lower
    assert "another source" not in lower
    assert "retrieved evidence relates" not in lower


def test_generic_fallback_avoids_research_process_disclaimers():
    from app.graph.nodes import scriptwriter_node

    state = initial_state(topic="How a process works")
    state["research_sources"] = [
        {
            "title": "Process",
            "url": "https://example.com/process",
            "summary": (
                "A process has steps that lead to a result. "
                "Each step contributes to the final outcome."
            ),
        }
    ]

    script = scriptwriter_node(state)["script"].lower()

    assert "retrieved summaries provide a starting point" not in script
    assert "should be consulted before publication" not in script


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


def test_graph_stops_when_research_is_insufficient():
    fake_research = {
        "research_quality": "insufficient",
        "research_notes": [
            "Process explanation: This explains the main process steps."
        ],
        "research_sources": [
            {
                "title": "Process explanation",
                "url": "https://example.com/process",
                "summary": (
                    "This explanation describes the main steps and ideas. "
                    "Learning how a process works involves understanding "
                    "the steps and ideas."
                ),
            }
        ],
    }

    with (
        patch(
            "app.graph.workflow.research_node",
            return_value=fake_research,
        ),
        patch(
            "app.graph.workflow.revise_script_node",
            side_effect=AssertionError(
                "The graph must not revise with insufficient research."
            ),
        ),
    ):
        result = build_graph().invoke(
            initial_state("How a process works")
        )

    assert result["approved"] is False
    assert result["revision_count"] == 0
    assert "Research coverage is insufficient" in result["critique"]


def test_graph_approves_script_with_adequate_research():
    fake_research = {
        "research_quality": "adequate",
        "research_notes": [
            "Process explanation: This explains the main process steps."
        ],
        "research_sources": [
            {
                "title": "Process explanation",
                "url": "https://example.com/process",
                "summary": (
                    "This explanation describes the main steps and ideas. "
                    "Learning how a process works involves understanding "
                    "the steps and ideas."
                ),
            },
            {
                "title": "Process overview",
                "url": "https://example.com/overview",
                "summary": (
                    "This explanation describes the main steps and ideas. "
                    "Learning how a process works involves understanding "
                    "the steps and ideas."
                ),
            },
            {
                "title": "Process guide",
                "url": "https://example.com/guide",
                "summary": (
                    "This explanation describes the main steps and ideas. "
                    "Learning how a process works involves understanding "
                    "the steps and ideas."
                ),
            },
        ],
    }

    with patch(
        "app.graph.workflow.research_node",
        return_value=fake_research,
    ):
        result = build_graph().invoke(
            initial_state("How a process works")
        )

    assert result["approved"] is True
    assert result["revision_count"] == 0
    assert "Structural and evidence-overlap checks passed" in (
        result["critique"]
    )

def test_research_quality_classification():
    from app.graph.nodes import classify_research_quality

    assert classify_research_quality(0) == "insufficient"
    assert classify_research_quality(1) == "insufficient"
    assert classify_research_quality(2) == "limited"
    assert classify_research_quality(3) == "adequate"
    assert classify_research_quality(5) == "adequate"

def test_critic_rejects_insufficient_research_without_revision_loop():
    from app.graph.workflow import route_after_critique

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
    state["research_quality"] = "insufficient"

    result = critic_node(state)

    assert result["approved"] is False
    assert "Research coverage is insufficient" in result["critique"]

    routed_state = {**state, **result}
    assert route_after_critique(routed_state) == "insufficient_research"
    assert routed_state["revision_count"] == 0


def test_critic_approves_limited_research_with_warning():
    state = initial_state(topic="How a process works")
    state["script"] = (
        "Imagine learning how a process works. "
        + "This explanation describes the main steps and ideas. " * 12
    )
    source = {
        "title": "Process explanation",
        "url": "https://example.com/research",
        "summary": (
            "This explanation describes the main steps and ideas. "
            "Learning how a process works involves understanding "
            "the steps and ideas."
        ),
    }
    state["research_sources"] = [
        source.copy(),
        {
            "title": "Process overview",
            "url": "https://example.com/overview",
            "summary": source["summary"],
        },
    ]
    state["research_quality"] = "limited"

    result = critic_node(state)

    assert result["approved"] is True
    assert "Research coverage is limited" in result["critique"]


def test_source_validation_deduplicates_urls_and_rejects_malformed_entries():
    from app.graph.nodes import deduplicate_valid_sources

    sources = [
        {
            "title": "Solar energy",
            "url": "https://EXAMPLE.com/article/#Overview",
            "summary": "Solar energy comes from sunlight.",
        },
        {
            "title": "Solar article duplicate",
            "url": "https://example.com/article/",
            "summary": "A different summary for the same URL.",
        },
        {
            "title": "Invalid URL",
            "url": "javascript:alert(1)",
            "summary": "This should not count as research.",
        },
        {
            "title": "Missing summary",
            "url": "https://example.com/other",
            "summary": "   ",
        },
        None,
        {
            "title": "Distinct source",
            "url": "https://example.com/distinct",
            "summary": "A separate source provides distinct evidence.",
        },
        {
            "title": "Repeated evidence",
            "url": "https://example.com/another-page",
            "summary": "Solar energy comes from sunlight.",
        },
    ]

    result = deduplicate_valid_sources(sources)

    assert [source["title"] for source in result] == [
        "Solar energy",
        "Distinct source",
    ]
    assert len(result) == 2
    assert all(source["url"].startswith("https://") for source in result)


def test_vaccine_script_keeps_source_titles_out_of_narration():
    from app.graph.nodes import scriptwriter_node

    state = initial_state(topic="How vaccines work")
    state["research_sources"] = [
        {
            "title": "Vaccine",
            "url": "https://en.wikipedia.org/wiki/Vaccine",
            "summary": (
                "A vaccine helps the immune system recognize "
                "a disease-causing pathogen."
            ),
        },
        {
            "title": "Conjugate vaccine",
            "url": "https://en.wikipedia.org/wiki/Conjugate_vaccine",
            "summary": (
                "A conjugate vaccine combines antigens to "
                "produce a stronger immune response."
            ),
        },
    ]

    script = scriptwriter_node(state)["script"]

    assert "research sources for this explanation" not in script.lower()
    assert "Conjugate vaccine" not in script
    assert "The central idea is preparation" in script
    assert len(state["research_sources"]) == 2


def test_critic_flags_weak_claim_evidence():
    state = initial_state(topic="How a process works")
    state["research_quality"] = "adequate"
    state["script"] = (
        "Imagine learning how a process works. "
        + "This explanation describes the main steps and ideas. " * 12
        + "This process includes several complex mechanisms that "
        "influence the overall outcome."
    )
    state["research_sources"] = [
        {
            "title": "Process explanation",
            "url": "https://example.com/process",
            "summary": (
                "This explanation describes the main steps and ideas. "
                "Learning how a process works involves understanding "
                "the steps and ideas. The process has mechanisms."
            ),
        }
    ]

    result = critic_node(state)

    assert result["approved"] is True
    assert "Evidence screening:" in result["critique"]
    assert "weak source matches" in result["critique"]
    assert "not proof the claims are false" in result["critique"]


def test_critic_reports_supported_claim_matches():
    state = initial_state(topic="How a process works")
    state["research_quality"] = "adequate"
    state["script"] = (
        "Imagine learning how a process works. "
        + "This explanation describes the main steps and ideas. " * 12
    )
    state["research_sources"] = [
        {
            "title": "Process explanation",
            "url": "https://example.com/process",
            "summary": (
                "This explanation describes the main steps and ideas. "
                "Learning how a process works involves understanding "
                "the steps and ideas."
            ),
        }
    ]

    result = critic_node(state)

    assert result["approved"] is True
    assert "supported match(es)" in result["critique"]
    assert "0 unsupported match(es)" in result["critique"]


def test_llm_workflow_uses_selected_writer_for_revision():
    from unittest.mock import patch

    from app.graph.workflow import build_graph

    state = initial_state()
    state["topic"] = "How vaccines work"

    research_result = {
        "research_quality": "limited",
        "research_sources": [
            {
                "title": "Vaccine overview",
                "url": "https://example.com/vaccines",
                "summary": "Vaccines train the immune system to recognize pathogens.",
            }
        ],
        "research_notes": ["Vaccines help prepare the immune system."],
    }

    with (
        patch(
            "app.graph.workflow.research_node",
            return_value=research_result,
        ),
        patch(
            "app.graph.workflow.gemini_scriptwriter_node",
            side_effect=[
                {"script": "First draft."},
                {"script": "Revised draft."},
            ],
        ) as gemini_writer,
        patch(
            "app.graph.workflow.critic_node",
            side_effect=[
                {"approved": False, "critique": "Fix the first draft."},
                {"approved": True, "critique": "Approved."},
            ],
        ),
    ):
        result = build_graph(use_llm=True).invoke(state)

    assert gemini_writer.call_count == 2
    assert (
        gemini_writer.call_args_list[1].args[0]["critique"]
        == "Fix the first draft."
    )
    assert result["script"] == "Revised draft."
    assert result["revision_count"] == 1
    assert result["approved"] is True
