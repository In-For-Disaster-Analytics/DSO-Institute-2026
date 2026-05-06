from __future__ import annotations

import pandas as pd

from semantic_bridge.constants import DEFAULT_DOMAIN_KEYWORDS
from semantic_bridge.export.reports import build_summary_report
from semantic_bridge.export.reports import write_report
from semantic_bridge.io.ckan import build_ckan_auth_header
from semantic_bridge.notebook.display import resolve_tutorial_dir
from semantic_bridge.text.preprocess import preprocess_text


def test_build_summary_report_and_write_report(tmp_path):
    report = build_summary_report(
        case_study_name="case-study",
        transcripts={"doc.txt": "hello"},
        n_topics=2,
        topic_mappings=[{"topic": "Topic 1", "keywords": "water, aquifer", "primary_domain": "Water Systems", "secondary_domain": None}],
        decision_components={"goals": [{"text": "protect homes"}], "objectives": [], "variables": [], "constraints": [], "indicators": []},
        unique_mappings=[
            {
                "natural_language_term": "groundwater",
                "scientific_variable": "groundwater_level",
                "standard_name": "depth_to_groundwater",
            }
        ],
        svo_df=pd.DataFrame([{"domain": "Hydrology"}]),
    )
    path = write_report(tmp_path, "case-study", report)

    assert "Semantic Bridge Analysis Report" in report
    assert path.read_text() == report


def test_library_modules_expose_expected_entry_points():
    assert callable(preprocess_text)
    assert callable(build_ckan_auth_header)
    assert isinstance(DEFAULT_DOMAIN_KEYWORDS, dict)
    assert callable(resolve_tutorial_dir)

