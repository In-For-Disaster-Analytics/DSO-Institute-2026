"""Notebook-friendly display helpers for the semantic bridge tutorial."""

from __future__ import annotations

from pathlib import Path

try:
    from IPython.display import Markdown, display
except ImportError:  # pragma: no cover - notebook-only enhancement
    Markdown = None
    display = None


def _render_markdown(text: str) -> None:
    if Markdown is not None and display is not None:
        display(Markdown(text))
    else:
        print(text)


def _escape(text: object) -> str:
    return str(text).replace("_", r"\_")


def resolve_tutorial_dir(
    anchor_filename: str = "semantic_bridge_cookbook.ipynb",
    relative_fallback: str = "DSO-Institute-2026/Day-3/Morning",
) -> Path:
    search_roots = [Path.cwd(), *Path.cwd().parents]
    for root in search_roots:
        if (root / anchor_filename).exists():
            return root
        fallback = root / relative_fallback
        if (fallback / anchor_filename).exists():
            return fallback
    raise FileNotFoundError(f"Could not locate {relative_fallback}")


def print_runtime_paths(tutorial_dir: Path, corpus_dir: Path, raw_dir: Path, cleaned_dir: Path, active_dir: Path) -> None:
    _render_markdown(
        "\n".join(
            [
                "**Runtime Paths**",
                f"- **Tutorial directory:** `{tutorial_dir}`",
                f"- **Corpus directory:** `{corpus_dir}`",
                f"- **Raw source directory:** `{raw_dir}`",
                f"- **Cleaned text directory:** `{cleaned_dir}`",
                f"- **Active input directory:** `{active_dir}`",
            ]
        )
    )


def print_document_list(documents: dict[str, str]) -> None:
    lines = [f"**Loaded Documents:** {len(documents)}"]
    lines.extend(f"- `{filename}`" for filename in documents)
    _render_markdown("\n".join(lines))


def print_document_previews(previews: list[dict[str, str]]) -> None:
    blocks = []
    for preview in previews:
        blocks.append(
            "\n".join(
                [
                    f"### `{_escape(preview['filename'])}`",
                    "```text",
                    preview["preview"],
                    "```",
                ]
            )
        )
    _render_markdown("\n\n".join(blocks))


def print_topic_parameters(n_topics: int, max_vocabulary: int, top_words_display: int) -> None:
    _render_markdown(
        "\n".join(
            [
                "**Topic Model Parameters**",
                f"- **Topics:** {n_topics}",
                f"- **Max vocabulary:** {max_vocabulary}",
                f"- **Display keywords per topic:** {top_words_display}",
            ]
        )
    )


def print_topic_discovery_summary(topics_info: dict[str, dict[str, object]], feature_names, top_words_display: int) -> None:
    lines = [
        "**Topic Discovery Summary**",
        f"- **Vocabulary size:** {len(feature_names)}",
        f"- **Topics discovered:** {len(topics_info)}",
    ]
    for topic_data in topics_info.values():
        lines.append(f"\n### {_escape(topic_data.get('human_label', topic_data['label']))}")
        if topic_data.get("description"):
            lines.append(f"*{topic_data['description']}*")
        lines.append(f"- **Keywords:** {', '.join(topic_data['keywords'][:top_words_display])}")
    _render_markdown("\n".join(lines))


def print_topic_label_comparison(
    baseline_topics_info: dict[str, dict[str, object]],
    relabeled_topics_info: dict[str, dict[str, object]],
    top_words_display: int,
) -> None:
    lines = ["## Topic Label Comparison"]
    for topic_id in baseline_topics_info:
        baseline_topic = baseline_topics_info[topic_id]
        relabeled_topic = relabeled_topics_info[topic_id]
        lines.extend(
            [
                f"\n### {_escape(topic_id)}",
                f"- **Baseline:** {baseline_topic['label']}",
                f"- **Human-readable:** {relabeled_topic.get('human_label', relabeled_topic['label'])}",
                f"- **Description:** {relabeled_topic.get('description', 'No description generated.')}",
                f"- **Keywords:** {', '.join(relabeled_topic['keywords'][:top_words_display])}",
            ]
        )
    _render_markdown("\n".join(lines))


def print_topic_query_recommendations(topic_query_recommendations: list[dict[str, object]]) -> None:
    lines = ["## Topic-to-MINT Query Recommendations"]
    for recommendation in topic_query_recommendations:
        lines.append(f"\n### {_escape(recommendation['label'])}")
        if recommendation.get("description"):
            lines.append(f"*{recommendation['description']}*")
        lines.append(f"- **Suggested MINT domains:** {', '.join(recommendation['query_domains']) or 'None'}")
        lines.append(f"- **Suggested MINT tags:** {', '.join(recommendation['query_tags']) or 'None'}")
    _render_markdown("\n".join(lines))


def print_science_backbone(science_backbone: dict[str, list[str]]) -> None:
    lines = ["## Science Backbone"]
    for domain, subdisciplines in science_backbone.items():
        lines.append(f"\n### {_escape(domain)}")
        for subdiscipline in subdisciplines:
            lines.append(f"- {subdiscipline}")
    _render_markdown("\n".join(lines))


def print_eto_query_recommendations(topic_query_recommendations: list[dict[str, object]]) -> None:
    lines = ["## ETO Map of Science Query Recommendations"]
    for recommendation in topic_query_recommendations:
        lines.append(f"\n### {_escape(recommendation['label'])}")
        if recommendation.get("description"):
            lines.append(f"*{recommendation['description']}*")
        lines.append(f"- **Suggested subjects:** {', '.join(recommendation['subjects']) or 'None'}")
        lines.append(f"- **List view URL:** `{recommendation['eto_list_url']}`")
        lines.append(f"- **Map view URL:** `{recommendation['eto_map_url']}`")
    _render_markdown("\n".join(lines))


def print_topic_mappings(topic_mappings: list[dict[str, object]]) -> None:
    lines = ["## Topic-to-Domain Mappings"]
    for mapping in topic_mappings:
        lines.append(f"\n### {_escape(mapping.get('topic_label', mapping['topic']))}")
        lines.append(f"- **Keywords:** {mapping['keywords']}")
        lines.append(f"- **Primary domain:** {mapping['primary_domain']}")
        if mapping.get("secondary_domain"):
            lines.append(f"- **Secondary domain:** {mapping['secondary_domain']}")
        if mapping.get("eto_matches"):
            lines.append("- **ETO cluster matches:**")
            for match in mapping["eto_matches"]:
                cluster_id = match.get("cluster_id") or "unknown"
                cluster_name = match.get("cluster_name") or "Unnamed cluster"
                lines.append(f"  - `{cluster_id}`: {cluster_name} *(score={match['score']})*")
    _render_markdown("\n".join(lines))


def print_decision_components(decision_components: dict[str, list[dict[str, str]]], preview_limit: int = 5) -> None:
    lines = ["## Decision Components"]
    for component_type, items in decision_components.items():
        lines.append(f"\n### {component_type.title()} *({len(items)} found)*")
        for index, item in enumerate(items[:preview_limit], start=1):
            lines.append(f"{index}. {item['text']} *[{item['source']}]*")
    _render_markdown("\n".join(lines))


def print_svo_vocabulary_preview(svo_vocabulary: dict[str, dict[str, object]], source: str, preview_limit: int = 10) -> None:
    lines = [
        f"**SVO vocabulary source:** {source}",
        f"**Variables available:** {len(svo_vocabulary)}",
    ]
    for svo_name, svo_info in list(svo_vocabulary.items())[:preview_limit]:
        lines.extend(
            [
                f"\n### `{svo_name}`",
                f"- **Label:** {svo_info.get('label', svo_name)}",
                f"- **Standard:** {svo_info['standard_name']}",
                f"- **Units:** {svo_info['units']}",
                f"- **Domain:** {svo_info['domain']}",
            ]
        )
    _render_markdown("\n".join(lines))


def print_svo_mapping_summary(unique_mappings: list[dict[str, str]], preview_limit: int = 6) -> None:
    lines = [f"**Semantic links created:** {len(unique_mappings)}"]
    for index, mapping in enumerate(unique_mappings[:preview_limit], start=1):
        lines.extend(
            [
                f"\n### {index}. *'{mapping['natural_language_term']}'* -> `{mapping['scientific_variable']}`",
                f"- **Standard:** {mapping['standard_name']}",
                f"- **Units:** {mapping['units']}",
                f"- **Domain:** {mapping['domain']}",
                f"- **Data source:** {mapping['data_source']}",
            ]
        )
    _render_markdown("\n".join(lines))


def print_svo_model_recommendations(model_recommendations_df) -> None:
    if model_recommendations_df.empty:
        _render_markdown("*No matching MINT models were found for the current SVO mappings.*")
        return
    lines = [f"**SVO-to-model recommendations:** {len(model_recommendations_df)}"]
    for scientific_variable, group in model_recommendations_df.groupby("scientific_variable"):
        lines.append(f"\n### `{scientific_variable}`")
        for _, rec in group.sort_values("rank").iterrows():
            lines.append(f"- **{int(rec['rank'])}.** {rec['recommended_model']} *[{rec['model_type']}]*")
            if rec["model_categories"]:
                lines.append(f"  Categories: {rec['model_categories']}")
            if rec["model_description"]:
                lines.append(f"  Why: {rec['model_description'][:180]}")
    _render_markdown("\n".join(lines))


def print_domain_counts(domain_counts: dict[str, int]) -> None:
    lines = [f"**Domains covered:** {len(domain_counts)}"]
    for domain, count in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- **{domain}:** {count}")
    _render_markdown("\n".join(lines))


def print_export_summary(
    transcripts: dict[str, str],
    n_topics: int,
    topic_mappings: list[dict[str, object]],
    decision_components: dict[str, list[dict[str, str]]],
    unique_mappings: list[dict[str, str]],
    output_files: dict[str, Path],
    report_path: Path,
) -> None:
    lines = [
        "## Semantic Bridge Analysis Complete",
        f"- **Documents analyzed:** {len(transcripts)}",
        f"- **Topics identified:** {n_topics}",
        f"- **Scientific domains:** {len(set(m['primary_domain'] for m in topic_mappings))}",
        f"- **Decision components:** {sum(len(v) for v in decision_components.values())}",
        f"- **Scientific variables:** {len(set(m['scientific_variable'] for m in unique_mappings))}",
        "- **Output files:**",
    ]
    for path in output_files.values():
        lines.append(f"  - `{path.name}`")
    lines.append(f"  - `{report_path.name}`")
    _render_markdown("\n".join(lines))


def print_report_preview(summary: str, report_path: Path, preview_chars: int = 1000) -> None:
    _render_markdown(
        "\n".join(
            [
                "## Report Preview",
                "```text",
                summary[:preview_chars],
                "...",
                "```",
                f"**Full report:** `{report_path}`",
            ]
        )
    )

