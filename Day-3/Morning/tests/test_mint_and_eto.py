from __future__ import annotations

import pandas as pd

from semantic_bridge.mapping.eto import build_eto_map_url
from semantic_bridge.mapping.eto import build_science_backbone_from_eto_export
from semantic_bridge.mapping.eto import map_topics_to_eto_clusters
from semantic_bridge.mapping.eto import recommend_eto_queries_for_topics
from semantic_bridge.mapping.mint import _extract_records
from semantic_bridge.mapping.mint import _normalize_mint_model_candidate
from semantic_bridge.mapping.mint import recommend_models_for_svo_mappings


def test_extract_records_handles_common_payload_shapes():
    payload = {"results": [{"id": "one"}, {"id": "two"}]}

    assert _extract_records(payload) == [{"id": "one"}, {"id": "two"}]


def test_normalize_mint_model_candidate_builds_searchable_text():
    candidate = _normalize_mint_model_candidate(
        {
            "id": "model-1",
            "label": "Groundwater Model",
            "description": "Hydrology analysis",
            "hasModelCategory": ["Hydrology"],
            "keywords": ["groundwater"],
        },
        "Model",
    )

    assert candidate["candidate_kind"] == "Model"
    assert "groundwater model" in candidate["searchable_text"]


def test_recommend_models_for_svo_mappings_ranks_relevant_candidates():
    mappings = [
        {
            "natural_language_term": "groundwater",
            "scientific_variable": "groundwater_level",
            "standard_name": "depth to groundwater",
            "units": "meters",
            "domain": "Hydrology",
            "data_source": "USGS",
        }
    ]
    model_candidates = [
        {
            "label": "Groundwater Flow Model",
            "candidate_kind": "Model",
            "categories": ["Hydrology"],
            "keywords": ["groundwater"],
            "description": "Simulates groundwater flow",
            "searchable_text": "groundwater flow hydrology depth to groundwater",
        },
        {
            "label": "Crop Yield Model",
            "candidate_kind": "Model",
            "categories": ["Agriculture"],
            "keywords": ["crop"],
            "description": "Agriculture",
            "searchable_text": "crop yield agriculture",
        },
    ]

    recommendations = recommend_models_for_svo_mappings(mappings, model_candidates, recommendations_per_svo=1)

    assert len(recommendations) == 1
    assert recommendations[0]["recommended_model"] == "Groundwater Flow Model"


def test_eto_helpers_build_urls_and_backbone():
    url = build_eto_map_url(["Hydrology", "Groundwater"], mode="map")
    assert "mode=map" in url
    assert "Hydrology%2C+Groundwater" in url

    cluster_df = pd.DataFrame(
        [
            {"Top Discipline": "Water Systems", "Top Field": "Groundwater", "Top Topic": "Aquifers"},
            {"Top Discipline": "Water Systems", "Top Field": "Hydrology", "Top Topic": "Runoff"},
        ]
    )
    backbone = build_science_backbone_from_eto_export(cluster_df)

    assert backbone["Water Systems"] == ["Groundwater", "Aquifers", "Hydrology", "Runoff"]


def test_map_topics_to_eto_clusters_matches_rows():
    cluster_df = pd.DataFrame(
        [
            {"Cluster ID": "1", "Cluster Name": "Groundwater Systems", "Top Discipline": "Water Systems", "Top Field": "Groundwater"},
            {"Cluster ID": "2", "Cluster Name": "Climate Change", "Top Discipline": "Earth and Environmental Change", "Top Field": "Climate Impacts"},
        ]
    )
    topics = {
        "Topic 1": {"label": "Topic 1: groundwater", "keywords": ["groundwater", "aquifer"]},
    }

    mappings = map_topics_to_eto_clusters(topics, cluster_df, top_matches=1)
    query_recommendations = recommend_eto_queries_for_topics(topics)

    assert mappings[0]["primary_domain"] == "Water Systems"
    assert mappings[0]["eto_matches"][0]["cluster_id"] == "1"
    assert query_recommendations[0]["subjects"] == ["groundwater", "aquifer"]

