"""Notebook-friendly display helpers for the semantic bridge tutorial."""

from __future__ import annotations

from pathlib import Path


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
    print(f"Tutorial directory: {tutorial_dir}")
    print(f"Corpus directory: {corpus_dir}")
    print(f"Raw source directory: {raw_dir}")
    print(f"Cleaned text directory: {cleaned_dir}")
    print(f"Active input directory: {active_dir}")


def print_document_list(documents: dict[str, str]) -> None:
    print(f"Loaded {len(documents)} documents:")
    for filename in documents:
        print(f"  - {filename}")


def print_document_previews(previews: list[dict[str, str]]) -> None:
    for preview in previews:
        print(f"\n{preview['filename']}")
        print("-" * len(preview["filename"]))
        print(preview["preview"])


def print_topic_parameters(n_topics: int, max_vocabulary: int, top_words_display: int) -> None:
    print("Topic model parameters")
    print(f"  Topics: {n_topics}")
    print(f"  Max vocabulary: {max_vocabulary}")
    print(f"  Display keywords per topic: {top_words_display}")


def print_topic_discovery_summary(topics_info: dict[str, dict[str, object]], feature_names, top_words_display: int) -> None:
    print(f"Vocabulary size: {len(feature_names)}")
    print(f"Topics discovered: {len(topics_info)}")
    for topic_data in topics_info.values():
        print(f"\n{topic_data.get('human_label', topic_data['label'])}")
        if topic_data.get("description"):
            print(f"  Description: {topic_data['description']}")
        print(f"  Keywords: {', '.join(topic_data['keywords'][:top_words_display])}")


def print_topic_label_comparison(
    baseline_topics_info: dict[str, dict[str, object]],
    relabeled_topics_info: dict[str, dict[str, object]],
    top_words_display: int,
) -> None:
    print("Topic label comparison")
    print("=" * 80)
    for topic_id in baseline_topics_info:
        baseline_topic = baseline_topics_info[topic_id]
        relabeled_topic = relabeled_topics_info[topic_id]
        print(f"\n{topic_id}")
        print(f"  Baseline: {baseline_topic['label']}")
        print(f"  Human-readable: {relabeled_topic.get('human_label', relabeled_topic['label'])}")
        print(f"  Description: {relabeled_topic.get('description', 'No description generated.')}")
        print(f"  Keywords: {', '.join(relabeled_topic['keywords'][:top_words_display])}")
    print("=" * 80)


def print_topic_query_recommendations(topic_query_recommendations: list[dict[str, object]]) -> None:
    print("Topic-to-MINT query recommendations")
    print("=" * 80)
    for recommendation in topic_query_recommendations:
        print(f"\n{recommendation['label']}")
        if recommendation.get("description"):
            print(f"  Description: {recommendation['description']}")
        print(f"  Suggested MINT domains: {', '.join(recommendation['query_domains']) or 'None'}")
        print(f"  Suggested MINT tags: {', '.join(recommendation['query_tags']) or 'None'}")
        for idx, model in enumerate(recommendation["recommended_models"], start=1):
            print(f"  {idx}. {model['label']} [{model['type']}]")
            if model.get("categories"):
                print(f"     Categories: {', '.join(model['categories'])}")
            if model.get("keywords"):
                print(f"     Tags: {', '.join(model['keywords'][:5])}")
    print("=" * 80)


def print_science_backbone(science_backbone: dict[str, list[str]]) -> None:
    print("Science backbone")
    for domain, subdisciplines in science_backbone.items():
        print(f"\n{domain}")
        for subdiscipline in subdisciplines:
            print(f"  - {subdiscipline}")


def print_topic_mappings(topic_mappings: list[dict[str, object]]) -> None:
    print("Topic-to-domain mappings")
    for mapping in topic_mappings:
        print(f"\n{mapping['topic']}")
        print(f"  Keywords: {mapping['keywords']}")
        print(f"  Primary domain: {mapping['primary_domain']}")
        if mapping.get("secondary_domain"):
            print(f"  Secondary domain: {mapping['secondary_domain']}")


def print_decision_components(decision_components: dict[str, list[dict[str, str]]], preview_limit: int = 5) -> None:
    print("Decision components")
    for component_type, items in decision_components.items():
        print(f"\n{component_type.title()} ({len(items)} found)")
        for index, item in enumerate(items[:preview_limit], start=1):
            print(f"  {index}. {item['text']} [{item['source']}]")


def print_svo_vocabulary_preview(svo_vocabulary: dict[str, dict[str, object]], source: str, preview_limit: int = 10) -> None:
    print(f"SVO vocabulary source: {source}")
    print(f"Variables available: {len(svo_vocabulary)}")
    for svo_name, svo_info in list(svo_vocabulary.items())[:preview_limit]:
        print(f"\n{svo_name}")
        print(f"  Label: {svo_info.get('label', svo_name)}")
        print(f"  Standard: {svo_info['standard_name']}")
        print(f"  Units: {svo_info['units']}")
        print(f"  Domain: {svo_info['domain']}")


def print_svo_mapping_summary(unique_mappings: list[dict[str, str]], preview_limit: int = 6) -> None:
    print(f"Semantic links created: {len(unique_mappings)}")
    for index, mapping in enumerate(unique_mappings[:preview_limit], start=1):
        print(f"\n{index}. '{mapping['natural_language_term']}' -> {mapping['scientific_variable']}")
        print(f"   Standard: {mapping['standard_name']}")
        print(f"   Units: {mapping['units']}")
        print(f"   Domain: {mapping['domain']}")
        print(f"   Data source: {mapping['data_source']}")


def print_svo_model_recommendations(model_recommendations_df) -> None:
    if model_recommendations_df.empty:
        print("No matching MINT models were found for the current SVO mappings.")
        return
    print(f"SVO-to-model recommendations: {len(model_recommendations_df)}")
    for scientific_variable, group in model_recommendations_df.groupby("scientific_variable"):
        print(f"\n{scientific_variable}")
        for _, rec in group.sort_values("rank").iterrows():
            print(f"  {int(rec['rank'])}. {rec['recommended_model']} [{rec['model_type']}]")
            if rec["model_categories"]:
                print(f"     Categories: {rec['model_categories']}")
            if rec["model_description"]:
                print(f"     Why: {rec['model_description'][:180]}")


def print_domain_counts(domain_counts: dict[str, int]) -> None:
    print(f"Domains covered: {len(domain_counts)}")
    for domain, count in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True):
        print(f"  {domain}: {count}")


def print_export_summary(
    transcripts: dict[str, str],
    n_topics: int,
    topic_mappings: list[dict[str, object]],
    decision_components: dict[str, list[dict[str, str]]],
    unique_mappings: list[dict[str, str]],
    output_files: dict[str, Path],
    report_path: Path,
) -> None:
    print("Semantic bridge analysis complete")
    print(f"  Documents analyzed: {len(transcripts)}")
    print(f"  Topics identified: {n_topics}")
    print(f"  Scientific domains: {len(set(m['primary_domain'] for m in topic_mappings))}")
    print(f"  Decision components: {sum(len(v) for v in decision_components.values())}")
    print(f"  Scientific variables: {len(set(m['scientific_variable'] for m in unique_mappings))}")
    print("  Output files:")
    for path in output_files.values():
        print(f"    - {path.name}")
    print(f"    - {report_path.name}")


def print_report_preview(summary: str, report_path: Path, preview_chars: int = 1000) -> None:
    print("Report preview")
    print(summary[:preview_chars])
    print("\n...")
    print(f"Full report: {report_path}")
