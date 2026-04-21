from __future__ import annotations

from semantic_bridge.mapping.domains import default_science_backbone
from semantic_bridge.mapping.domains import map_topics_to_domains
from semantic_bridge.text.preprocess import preprocess_documents
from semantic_bridge.text.preprocess import preprocess_text
from semantic_bridge.text.topics import build_topic_summary
from semantic_bridge.text.topics import discover_topics


def test_preprocess_text_normalizes_and_applies_stopwords():
    result = preprocess_text("Rain, WATER, and soil 123", custom_stopwords={"and", "soil"})

    assert result == "rain water"


def test_preprocess_documents_preserves_document_order():
    processed_docs, doc_names = preprocess_documents({"a.txt": "One two", "b.txt": "Three four"})

    assert doc_names == ["a.txt", "b.txt"]
    assert processed_docs == ["one two", "three four"]


def test_discover_topics_and_map_to_domains():
    processed_docs = [
        "groundwater aquifer pumping water supply",
        "climate subsidence geology land surface",
        "groundwater wells aquifer hydrology",
    ]
    result = discover_topics(processed_docs, n_topics=2, max_vocabulary=20, topic_keyword_count=4)

    assert set(result) == {"vectorizer", "lda_model", "doc_topic_dist", "feature_names", "topics_info"}
    assert len(result["topics_info"]) == 2

    summary = build_topic_summary(result["topics_info"], result["doc_topic_dist"], top_words_display=3)
    assert list(summary.columns) == ["Topic", "Label", "Description", "Top Keywords", "Avg Coverage"]

    mappings = map_topics_to_domains(
        {
            "Topic 1": {"label": "Topic 1", "keywords": ["groundwater", "aquifer", "water"]},
            "Topic 2": {"label": "Topic 2", "keywords": ["climate", "subsidence", "geology"]},
        }
    )
    assert mappings[0]["primary_domain"] == "Water Systems"
    assert mappings[1]["primary_domain"] == "Earth and Environmental Change"


def test_default_science_backbone_returns_copy():
    backbone = default_science_backbone()
    backbone["Water Systems"].append("New Node")

    fresh = default_science_backbone()
    assert "New Node" not in fresh["Water Systems"]

