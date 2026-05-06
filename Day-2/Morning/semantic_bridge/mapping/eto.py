"""ETO query and export helpers."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode

import pandas as pd

from semantic_bridge.text.topics import topic_display_name


ETO_MAP_BASE_URL = "https://sciencemap.eto.tech/"


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        normalized = " ".join(str(value).split()).strip()
        if not normalized:
            continue
        marker = normalized.lower()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(normalized)
    return ordered


def _pick_existing_columns(columns: list[str], candidates: list[str]) -> list[str]:
    normalized_lookup = {column.lower(): column for column in columns}
    matched = []
    for candidate in candidates:
        column = normalized_lookup.get(candidate.lower())
        if column and column not in matched:
            matched.append(column)
    return matched


def _find_first_column(columns: list[str], candidates: list[str]) -> str | None:
    matches = _pick_existing_columns(columns, candidates)
    return matches[0] if matches else None


def _split_multivalue_cell(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"\s*[|;,]\s*|\s{2,}", text)
    cleaned = []
    for part in parts:
        normalized = " ".join(part.split()).strip()
        if normalized:
            cleaned.append(normalized)
    return _unique_preserve_order(cleaned)


def build_eto_map_url(
    subjects: list[str] | None = None,
    mode: str = "list",
    extra_params: dict[str, Any] | None = None,
) -> str:
    params: dict[str, Any] = {"mode": mode}
    if subjects:
        params["all_subjects"] = ", ".join(_unique_preserve_order(subjects))
    if extra_params:
        params.update({key: value for key, value in extra_params.items() if value not in (None, "")})
    return f"{ETO_MAP_BASE_URL}?{urlencode(params, doseq=True)}"


def recommend_eto_queries_for_topics(
    topics_info: dict[str, dict[str, Any]],
    keywords_per_topic: int = 3,
) -> list[dict[str, Any]]:
    recommendations = []
    for topic_id, topic_info in topics_info.items():
        subject_terms = _unique_preserve_order(topic_info.get("keywords", [])[:keywords_per_topic])
        recommendations.append(
            {
                "topic": topic_id,
                "label": topic_display_name(topic_info),
                "description": topic_info.get("description", ""),
                "subjects": subject_terms,
                "eto_list_url": build_eto_map_url(subject_terms, mode="list"),
                "eto_map_url": build_eto_map_url(subject_terms, mode="map"),
            }
        )
    return recommendations


def prepare_eto_query_exports(
    output_dir: Path,
    topics_info: dict[str, dict[str, Any]],
    keywords_per_topic: int = 3,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    eto_export_path = output_dir / "eto_map_export.csv"
    eto_query_export_path = output_dir / "eto_query_recommendations.csv"
    eto_topic_queries = recommend_eto_queries_for_topics(
        topics_info,
        keywords_per_topic=keywords_per_topic,
    )
    pd.DataFrame(eto_topic_queries).to_csv(eto_query_export_path, index=False)
    return {
        "eto_export_path": eto_export_path,
        "eto_query_export_path": eto_query_export_path,
        "eto_topic_queries": eto_topic_queries,
    }


def load_eto_cluster_export(csv_path: Path) -> pd.DataFrame:
    cluster_df = pd.read_csv(csv_path)
    cluster_df.columns = [str(column).strip() for column in cluster_df.columns]
    return cluster_df


def build_science_backbone_from_eto_export(cluster_df: pd.DataFrame) -> dict[str, list[str]]:
    if cluster_df.empty:
        return {}

    columns = list(cluster_df.columns)
    domain_column = _find_first_column(
        columns,
        ["top discipline", "discipline", "primary discipline", "research discipline"],
    )
    subdiscipline_columns = _pick_existing_columns(
        columns,
        ["top field", "field", "top subfield", "subfield", "top topic", "topic"],
    )
    if not domain_column:
        return {}

    backbone: dict[str, list[str]] = {}
    for _, row in cluster_df.iterrows():
        domain = str(row.get(domain_column, "")).strip()
        if not domain or domain.lower() == "nan":
            continue
        domain_subs = backbone.setdefault(domain, [])
        for column in subdiscipline_columns:
            for subdiscipline in _split_multivalue_cell(row.get(column)):
                if subdiscipline not in domain_subs:
                    domain_subs.append(subdiscipline)
    return backbone


def map_topics_to_eto_clusters(
    topics_info: dict[str, dict[str, Any]],
    cluster_df: pd.DataFrame,
    top_matches: int = 3,
) -> list[dict[str, Any]]:
    if cluster_df.empty:
        return []

    columns = list(cluster_df.columns)
    cluster_id_column = _find_first_column(columns, ["cluster id", "cluster_id", "id"])
    cluster_label_column = _find_first_column(columns, ["cluster name", "name", "label", "title"])
    primary_domain_column = _find_first_column(
        columns,
        ["top discipline", "discipline", "primary discipline", "research discipline"],
    )
    secondary_domain_column = _find_first_column(columns, ["top field", "field", "top subfield", "subfield"])
    searchable_columns = _pick_existing_columns(
        columns,
        [
            "cluster name",
            "name",
            "label",
            "title",
            "top discipline",
            "discipline",
            "top field",
            "field",
            "top subfield",
            "subfield",
            "top topic",
            "topic",
            "key concepts",
            "key subjects",
            "subjects",
        ],
    )
    if not searchable_columns:
        searchable_columns = columns[: min(len(columns), 8)]

    scored_rows = []
    for _, row in cluster_df.iterrows():
        searchable_text = " ".join(str(row.get(column, "")) for column in searchable_columns).lower()
        scored_rows.append((row, searchable_text))

    mappings = []
    for topic_id, topic_data in topics_info.items():
        query_terms = {
            keyword.lower()
            for keyword in topic_data.get("keywords", [])
            if isinstance(keyword, str) and keyword.strip()
        }
        for token in topic_display_name(topic_data).lower().replace(":", " ").split():
            if len(token) >= 4:
                query_terms.add(token)

        candidates = []
        for row, searchable_text in scored_rows:
            score = 0
            for term in query_terms:
                if term in searchable_text:
                    score += 3 if " " in term else 1
            if score > 0:
                candidates.append((score, row))

        candidates.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get(cluster_label_column, "")) if cluster_label_column else "",
            )
        )
        best_matches = candidates[:top_matches]
        primary_domain = (
            str(best_matches[0][1].get(primary_domain_column, "")).strip()
            if best_matches and primary_domain_column
            else "General"
        )
        secondary_domain = (
            str(best_matches[0][1].get(secondary_domain_column, "")).strip()
            if best_matches and secondary_domain_column
            else None
        )
        mappings.append(
            {
                "topic": topic_id,
                "topic_label": topic_display_name(topic_data),
                "keywords": ", ".join(topic_data.get("keywords", [])[:5]),
                "primary_domain": primary_domain or "General",
                "secondary_domain": secondary_domain or None,
                "eto_matches": [
                    {
                        "cluster_id": str(match_row.get(cluster_id_column, "")).strip() if cluster_id_column else "",
                        "cluster_name": str(match_row.get(cluster_label_column, "")).strip() if cluster_label_column else "",
                        "score": score,
                    }
                    for score, match_row in best_matches
                ],
            }
        )
    return mappings

