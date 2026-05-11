from __future__ import annotations

import pandas as pd

from semantic_bridge.mapping.eto import build_eto_map_url
from semantic_bridge.mapping.eto import build_eto_science_backbone
from semantic_bridge.mapping.eto import build_science_backbone_from_eto_export
from semantic_bridge.mapping.eto import build_science_backbone_payload
from semantic_bridge.mapping.eto import map_keyword_groups_to_backbone
from semantic_bridge.mapping.eto import map_topics_to_eto_clusters
from semantic_bridge.mapping.eto import project_documents_onto_backbone
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


def test_normalize_model_configuration_prefers_model_name_over_variable_label():
    candidate = _normalize_mint_model_candidate(
        {
            "id": "https://w3id.org/okn/i/mint/config-1",
            "label": "groundwater_level",
            "hasModel": "https://w3id.org/okn/i/mint/CYCLES",
            "description": "Configuration for groundwater runs",
        },
        "Model Configuration",
    )

    assert candidate["label"] == "Cycles"
    assert candidate["model_name"] == "Cycles"


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


def test_recommend_models_for_svo_mappings_can_filter_to_selected_variables():
    mappings = [
        {
            "natural_language_term": "groundwater",
            "scientific_variable": "groundwater_level",
            "standard_name": "depth to groundwater",
            "units": "meters",
            "domain": "Hydrology",
            "data_source": "USGS",
        },
        {
            "natural_language_term": "rainfall",
            "scientific_variable": "precipitation",
            "standard_name": "rainfall rate",
            "units": "mm/hour",
            "domain": "Atmospheric Science",
            "data_source": "NOAA",
        },
    ]
    model_candidates = [
        {
            "label": "Groundwater Flow Model",
            "model_name": "Groundwater Flow Model",
            "candidate_kind": "Model",
            "categories": ["Hydrology"],
            "keywords": ["groundwater"],
            "description": "Simulates groundwater flow",
            "searchable_text": "groundwater flow hydrology depth to groundwater",
        },
        {
            "label": "Rainfall Runoff Model",
            "model_name": "Rainfall Runoff Model",
            "candidate_kind": "Model",
            "categories": ["Atmospheric Science"],
            "keywords": ["rainfall"],
            "description": "Simulates rainfall runoff",
            "searchable_text": "rainfall runoff atmospheric science rainfall rate",
        },
    ]

    recommendations = recommend_models_for_svo_mappings(
        mappings,
        model_candidates,
        recommendations_per_svo=1,
        scientific_variables=["groundwater_level"],
    )

    assert len(recommendations) == 1
    assert recommendations[0]["scientific_variable"] == "groundwater_level"


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


def test_rich_eto_backbone_handles_current_field_export_shape():
    cluster_df = pd.DataFrame(
        [
            {
                "Cluster ID": "10",
                "Cluster Title": "Groundwater compaction and aquifer systems",
                "Cluster Summary": "Studies of aquifer compaction and land subsidence.",
                "Most common research field": "earth science",
                "Cluster Size": "125",
            },
            {
                "Cluster ID": "11",
                "Cluster Title": "Neural machine translation",
                "Cluster Summary": "Computer science language modeling.",
                "Most common research field": "computer science",
                "Cluster Size": "90",
            },
        ]
    )

    backbone = build_eto_science_backbone(
        cluster_df,
        title_filter=["groundwater", "subsidence"],
        prefer_ucsd_fields=True,
    )
    payload = build_science_backbone_payload(
        eto_cluster_df=cluster_df,
        title_filter=["groundwater", "subsidence"],
    )

    assert list(backbone) == ["Earth Sciences"]
    assert backbone["Earth Sciences"]["metadata"]["n_clusters"] == 1
    assert "Groundwater compaction and aquifer systems" in backbone["Earth Sciences"]["subdisciplines"]
    assert "aquifer" in backbone["Earth Sciences"]["terms"]
    assert payload["selected_layer"] == "merged"
    assert "Earth Sciences" in payload["layers"]["merged"]


def test_keyword_group_mapping_and_overlay_projection_use_rich_backbone():
    backbone = {
        "Earth Sciences": {
            "subdisciplines": ["Hydrogeology"],
            "terms": ["groundwater", "aquifer", "subsidence"],
        },
        "Social Sciences": {
            "subdisciplines": ["Decision Science"],
            "terms": ["policy", "decision"],
        },
    }
    keyword_groups = {
        "groundwater": ["groundwater", "aquifer"],
        "policy": ["policy"],
    }
    documents = {
        "a.txt": "Groundwater and aquifer decline can cause subsidence.",
        "b.txt": "Policy decisions shape groundwater management.",
    }

    group_mappings = map_keyword_groups_to_backbone(keyword_groups, backbone)
    projection = project_documents_onto_backbone(documents, keyword_groups, group_mappings)

    assert group_mappings[0]["primary_domain"] == "Earth Sciences"
    assert projection["group_totals"].set_index("group").loc["groundwater", "count"] == 3
    assert projection["domain_totals"].iloc[0]["domain"] == "Earth Sciences"
