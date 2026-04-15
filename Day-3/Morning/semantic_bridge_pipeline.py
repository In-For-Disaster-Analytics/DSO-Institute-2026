"""Reusable helpers for the semantic bridge tutorial notebook."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from docx import Document
from nltk.tokenize import sent_tokenize
from PIL import Image
from pypdf import PdfReader
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    import pytesseract
except ImportError:  # pragma: no cover - optional dependency at runtime
    pytesseract = None

from semantic_bridge_defaults import (
    DEFAULT_COMPONENT_PATTERNS,
    DEFAULT_DOMAIN_KEYWORDS,
    DEFAULT_SCIENCE_BACKBONE,
    DEFAULT_SVO_VOCABULARY,
    SAMPLE_TRANSCRIPTS,
)


def ensure_data_directory(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def write_sample_documents(data_dir: Path, sample_transcripts: dict[str, str] | None = None) -> dict[str, str]:
    documents = sample_transcripts or SAMPLE_TRANSCRIPTS
    ensure_data_directory(data_dir)
    for filename, content in documents.items():
        (data_dir / filename).write_text(content.strip())
    return documents


def load_text_document(filepath: Path) -> str:
    return filepath.read_text()


def load_json_document(filepath: Path) -> str:
    payload = json.loads(filepath.read_text())
    if isinstance(payload, dict):
        for key in ("text", "content", "body", "description"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return json.dumps(payload, indent=2)


def load_docx_document(filepath: Path) -> str:
    document = Document(filepath)
    return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())


def load_pdf_document(filepath: Path) -> str:
    reader = PdfReader(str(filepath))
    page_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            page_text.append(text)
    return "\n".join(page_text)


def load_image_document(filepath: Path) -> str:
    if pytesseract is None:
        raise RuntimeError("pytesseract is not available for OCR image extraction")
    image = Image.open(filepath)
    return pytesseract.image_to_string(image)


def load_document(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if suffix == ".txt":
        return load_text_document(filepath)
    if suffix == ".json":
        return load_json_document(filepath)
    if suffix == ".docx":
        return load_docx_document(filepath)
    if suffix == ".pdf":
        return load_pdf_document(filepath)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return load_image_document(filepath)
    raise ValueError(f"Unsupported document type: {filepath.suffix}")


def _is_hidden_path(filepath: Path) -> bool:
    return any(part.startswith(".") for part in filepath.parts)


def _document_roots(data_dir: Path) -> list[Path]:
    preferred_roots = [data_dir / "cleaned", data_dir / "raw"]
    available_roots = [root for root in preferred_roots if root.exists() and root.is_dir()]
    return available_roots or [data_dir]


def load_documents(data_dir: Path) -> dict[str, str]:
    documents = {}
    supported_suffixes = {".txt", ".json", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    for root in _document_roots(data_dir):
        for filepath in sorted(root.rglob("*")):
            if _is_hidden_path(filepath.relative_to(root)):
                continue
            if not filepath.is_file() or filepath.suffix.lower() not in supported_suffixes:
                continue
            if filepath.name in documents:
                continue
            try:
                documents[filepath.name] = load_document(filepath)
            except Exception as exc:
                print(f"Skipping {filepath.name}: {exc}")
    return documents


def preview_documents(documents: dict[str, str], preview_chars: int = 200) -> list[dict[str, str]]:
    previews = []
    for filename, content in documents.items():
        preview = content[:preview_chars] + "..." if len(content) > preview_chars else content
        previews.append({"filename": filename, "preview": preview})
    return previews


def build_stats_table(documents: dict[str, str]) -> pd.DataFrame:
    stats = []
    for filename, content in documents.items():
        stats.append(
            {
                "File": filename,
                "Characters": len(content),
                "Words": len(content.split()),
                "Sentences": len(sent_tokenize(content)),
            }
        )
    return pd.DataFrame(stats)


def preprocess_text(text: str, custom_stopwords: set[str] | None = None) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    tokens = text.split()
    if custom_stopwords:
        normalized_stopwords = {word.strip().lower() for word in custom_stopwords if word.strip()}
        tokens = [token for token in tokens if token not in normalized_stopwords]
    return " ".join(tokens)


def preprocess_documents(
    documents: dict[str, str],
    custom_stopwords: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    doc_names = list(documents.keys())
    processed_docs = [preprocess_text(text, custom_stopwords=custom_stopwords) for text in documents.values()]
    return processed_docs, doc_names


def discover_topics(
    processed_docs: list[str],
    n_topics: int,
    max_vocabulary: int,
    topic_keyword_count: int = 8,
    custom_stopwords: set[str] | None = None,
) -> dict[str, object]:
    combined_stopwords = "english"
    if custom_stopwords:
        sklearn_stopwords = TfidfVectorizer(stop_words="english").get_stop_words()
        user_stopwords = {word.strip().lower() for word in custom_stopwords if word.strip()}
        combined_stopwords = sorted(sklearn_stopwords.union(user_stopwords))
    vectorizer = TfidfVectorizer(
        max_features=max_vocabulary,
        stop_words=combined_stopwords,
        ngram_range=(1, 2),
    )
    doc_term_matrix = vectorizer.fit_transform(processed_docs)
    feature_names = vectorizer.get_feature_names_out()

    lda_model = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20,
    )
    doc_topic_dist = lda_model.fit_transform(doc_term_matrix)

    topics_info = {}
    for idx, topic in enumerate(lda_model.components_):
        top_indices = topic.argsort()[-topic_keyword_count:][::-1]
        top_words = [feature_names[i] for i in top_indices]
        topic_id = f"Topic {idx + 1}"
        topics_info[topic_id] = {
            "label": f"{topic_id}: {', '.join(top_words[:3])}",
            "keywords": top_words,
        }

    return {
        "vectorizer": vectorizer,
        "lda_model": lda_model,
        "doc_topic_dist": doc_topic_dist,
        "feature_names": feature_names,
        "topics_info": topics_info,
    }


def build_topic_summary(topics_info: dict[str, dict[str, object]], doc_topic_dist, top_words_display: int) -> pd.DataFrame:
    summary_data = []
    for topic_num, info in topics_info.items():
        topic_index = int(topic_num.split()[1]) - 1
        summary_data.append(
            {
                "Topic": topic_num,
                "Top Keywords": ", ".join(info["keywords"][:top_words_display]),
                "Avg Coverage": f"{doc_topic_dist[:, topic_index].mean():.1%}",
            }
        )
    return pd.DataFrame(summary_data)


def plot_topic_distribution(
    doc_topic_dist,
    doc_names: list[str],
    topics_info: dict[str, dict[str, object]],
    n_topics: int,
) -> tuple[pd.DataFrame, go.Figure]:
    topic_df = pd.DataFrame(
        doc_topic_dist,
        columns=[f"Topic {i + 1}" for i in range(n_topics)],
        index=[Path(name).stem for name in doc_names],
    )

    fig = go.Figure()
    for topic_num in topic_df.columns:
        topic_info = topics_info[topic_num]
        hover_text = [
            f"{topic_info['label']}<br>"
            f"Document: {doc}<br>"
            f"Proportion: {val:.1%}<br>"
            f"Keywords: {', '.join(topic_info['keywords'][:6])}"
            for doc, val in zip(topic_df.index, topic_df[topic_num])
        ]
        fig.add_trace(
            go.Bar(
                name=topic_info["label"],
                x=topic_df.index,
                y=topic_df[topic_num],
                text=[f"{val:.1%}" for val in topic_df[topic_num]],
                textposition="auto",
                hovertext=hover_text,
                hoverinfo="text",
            )
        )

    fig.update_layout(
        title=f"Topic Distribution Across Documents ({n_topics} Topics)",
        xaxis_title="Document",
        yaxis_title="Topic Proportion",
        barmode="stack",
        height=500,
        legend=dict(
            title="Topics (hover for details)",
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
        ),
    )
    return topic_df, fig


def default_science_backbone() -> dict[str, list[str]]:
    return deepcopy(DEFAULT_SCIENCE_BACKBONE)


def default_svo_vocabulary() -> dict[str, dict[str, object]]:
    return deepcopy(DEFAULT_SVO_VOCABULARY)


def map_topics_to_domains(
    topics_info: dict[str, dict[str, object]],
    domain_keywords: dict[str, list[str]] | None = None,
) -> list[dict[str, object]]:
    keywords_by_domain = domain_keywords or DEFAULT_DOMAIN_KEYWORDS
    mappings = []
    for topic_id, topic_data in topics_info.items():
        topic_keywords = set(" ".join(topic_data["keywords"]).lower().split())
        domain_scores = {}
        for domain, keywords in keywords_by_domain.items():
            matches = topic_keywords.intersection(set(keywords))
            if matches:
                domain_scores[domain] = len(matches)
        relevant = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)[:2]
        mappings.append(
            {
                "topic": topic_id,
                "keywords": ", ".join(topic_data["keywords"][:5]),
                "primary_domain": relevant[0][0] if relevant else "General",
                "secondary_domain": relevant[1][0] if len(relevant) > 1 else None,
            }
        )
    return mappings


def create_network_figure(
    science_backbone: dict[str, list[str]],
    topic_mappings: list[dict[str, object]],
    case_study_name: str,
) -> tuple[nx.Graph, go.Figure]:
    graph = nx.Graph()
    for domain in science_backbone:
        graph.add_node(domain, node_type="domain")
    for domain, subs in science_backbone.items():
        for sub in subs:
            graph.add_node(sub, node_type="subdiscipline")
            graph.add_edge(domain, sub)
    for mapping in topic_mappings:
        topic = mapping["topic"]
        graph.add_node(topic, node_type="topic")
        graph.add_edge(mapping["primary_domain"], topic)

    pos = nx.spring_layout(graph, k=2, iterations=50, seed=42)

    edge_trace = go.Scatter(
        x=[],
        y=[],
        line=dict(width=0.5, color="#888"),
        hoverinfo="none",
        mode="lines",
    )
    for edge in graph.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace["x"] += (x0, x1, None)
        edge_trace["y"] += (y0, y1, None)

    colors = {"domain": "#FF6B6B", "subdiscipline": "#4ECDC4", "topic": "#FFE66D"}
    sizes = {"domain": 20, "subdiscipline": 15, "topic": 12}

    node_traces = []
    for node_type in ["domain", "subdiscipline", "topic"]:
        nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == node_type]
        node_traces.append(
            go.Scatter(
                x=[pos[n][0] for n in nodes],
                y=[pos[n][1] for n in nodes],
                mode="markers+text",
                text=nodes,
                textposition="top center",
                marker=dict(size=sizes[node_type], color=colors[node_type]),
                name=node_type.title(),
            )
        )

    fig = go.Figure(
        data=[edge_trace] + node_traces,
        layout=go.Layout(
            title=f"Science Backbone Network with Topics ({case_study_name})",
            showlegend=True,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=600,
        ),
    )
    return graph, fig


def extract_decision_components(documents, nlp, patterns: dict[str, list[str]] | None = None):
    component_patterns = deepcopy(patterns or DEFAULT_COMPONENT_PATTERNS)
    components = {
        "goals": [],
        "objectives": [],
        "variables": [],
        "constraints": [],
        "indicators": [],
    }

    for doc_name, text in documents.items():
        doc = nlp(text)
        for sent in doc.sents:
            sent_text = sent.text.lower()
            for comp_type, keywords in component_patterns.items():
                if any(keyword in sent_text for keyword in keywords):
                    for chunk in sent.noun_chunks:
                        if len(chunk.text.split()) >= 2:
                            components[comp_type].append(
                                {
                                    "text": chunk.text,
                                    "source": doc_name,
                                    "context": sent.text[:100],
                                }
                            )

    for comp_type in components:
        seen = set()
        unique = []
        for item in components[comp_type]:
            if item["text"] not in seen:
                seen.add(item["text"])
                unique.append(item)
        components[comp_type] = unique[:10]
    return components


def component_counts(decision_components: dict[str, list[dict[str, str]]]) -> dict[str, int]:
    return {key: len(value) for key, value in decision_components.items()}


def component_table(decision_components: dict[str, list[dict[str, str]]]) -> pd.DataFrame:
    rows = []
    for comp_type, items in decision_components.items():
        for item in items:
            rows.append(
                {
                    "component_type": comp_type,
                    "text": item["text"],
                    "source": item["source"],
                    "context": item["context"],
                }
            )
    return pd.DataFrame(rows)


def plot_component_distribution(component_counts_map: dict[str, int]) -> go.Figure:
    fig = go.Figure(
        [
            go.Bar(
                x=list(component_counts_map.keys()),
                y=list(component_counts_map.values()),
                text=list(component_counts_map.values()),
                textposition="auto",
                marker=dict(color=["#FF6B6B", "#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"]),
            )
        ]
    )
    fig.update_layout(
        title="Decision Components Identified",
        xaxis_title="Component Type",
        yaxis_title="Count",
        height=400,
    )
    return fig


def create_svo_mappings(documents: dict[str, str], svo_vocabulary: dict[str, dict[str, object]]) -> list[dict[str, str]]:
    mappings = []
    for doc_name, text in documents.items():
        text_lower = text.lower()
        for svo_name, svo_info in svo_vocabulary.items():
            for keyword in svo_info["keywords"]:
                if keyword in text_lower:
                    context = ""
                    for sentence in sent_tokenize(text):
                        if keyword in sentence.lower():
                            context = sentence
                            break
                    mappings.append(
                        {
                            "natural_language_term": keyword,
                            "scientific_variable": svo_name,
                            "standard_name": svo_info["standard_name"],
                            "units": svo_info["units"],
                            "domain": svo_info["domain"],
                            "data_source": svo_info["data_source"],
                            "source_document": doc_name,
                            "context": context[:150],
                        }
                    )
    return mappings


def deduplicate_svo_mappings(svo_mappings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique_mappings = []
    seen = set()
    for mapping in svo_mappings:
        key = (mapping["natural_language_term"], mapping["scientific_variable"])
        if key not in seen:
            seen.add(key)
            unique_mappings.append(mapping)
    return unique_mappings


def svo_table(unique_mappings: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(unique_mappings)


def plot_svo_sunburst(unique_mappings: list[dict[str, str]]) -> tuple[pd.DataFrame, go.Figure, dict[str, int]]:
    domain_counts = Counter(mapping["domain"] for mapping in unique_mappings)
    sunburst_data = []
    for mapping in unique_mappings:
        sunburst_data.append(
            {
                "labels": mapping["scientific_variable"],
                "parents": mapping["domain"],
                "values": 1,
            }
        )
    for domain, count in domain_counts.items():
        sunburst_data.append({"labels": domain, "parents": "", "values": count})
    df_sunburst = pd.DataFrame(sunburst_data)
    fig = px.sunburst(
        df_sunburst,
        names="labels",
        parents="parents",
        values="values",
        title="Scientific Variables by Domain",
        height=500,
    )
    return df_sunburst, fig, dict(domain_counts)


def write_outputs_table(output_dir: Path, case_study_name: str, topic_mappings, components_df, svo_df, network_fig, sunburst_fig):
    mapping_path = output_dir / f"{case_study_name}_topic_mappings.csv"
    components_path = output_dir / f"{case_study_name}_components.csv"
    svo_path = output_dir / f"{case_study_name}_svo_mappings.csv"
    network_path = output_dir / f"{case_study_name}_network.html"
    sunburst_path = output_dir / f"{case_study_name}_svo_sunburst.html"

    pd.DataFrame(topic_mappings).to_csv(mapping_path, index=False)
    components_df.to_csv(components_path, index=False)
    svo_df.to_csv(svo_path, index=False)
    network_fig.write_html(str(network_path))
    sunburst_fig.write_html(str(sunburst_path))

    return {
        "mapping_path": mapping_path,
        "components_path": components_path,
        "svo_path": svo_path,
        "network_path": network_path,
        "sunburst_path": sunburst_path,
    }


def build_summary_report(
    case_study_name: str,
    transcripts: dict[str, str],
    n_topics: int,
    topic_mappings: list[dict[str, object]],
    decision_components: dict[str, list[dict[str, str]]],
    unique_mappings: list[dict[str, str]],
    svo_df: pd.DataFrame,
) -> str:
    summary = f"""# Semantic Bridge Analysis Report

## {case_study_name}

**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}

---

## Analysis Summary

- **Documents Analyzed:** {len(transcripts)}
- **Topics Identified:** {n_topics}
- **Scientific Domains:** {len(set(m['primary_domain'] for m in topic_mappings))}
- **Decision Components:** {sum(len(v) for v in decision_components.values())}
- **Scientific Variables:** {len(set(m['scientific_variable'] for m in unique_mappings))}

---

## Key Findings

### Topics Discovered

"""
    for mapping in topic_mappings:
        summary += f"""**{mapping['topic']}**
- Keywords: {mapping['keywords']}
- Primary Domain: {mapping['primary_domain']}
"""
        if mapping["secondary_domain"]:
            summary += f"- Secondary Domain: {mapping['secondary_domain']}\n"
        summary += "\n"

    summary += """---

### Scientific Domains Engaged

"""
    for domain, count in svo_df.groupby("domain").size().sort_values(ascending=False).items():
        summary += f"- **{domain}:** {count} variables\n"

    summary += """
---

### Decision Components Extracted

"""
    for comp_type, items in decision_components.items():
        if items:
            summary += f"\n**{comp_type.title()}** ({len(items)}): "
            summary += ", ".join([item["text"] for item in items[:3]])
            if len(items) > 3:
                summary += f" ... (+{len(items) - 3} more)"
            summary += "\n"

    summary += """
---

## Outputs Generated

The following files have been created in the `outputs/` directory:

1. **Topic Mappings:** Links discovered topics to scientific domains
2. **Decision Components:** Extracted goals, objectives, variables, constraints, and indicators
3. **SVO Mappings:** Semantic links between natural language and scientific variables
4. **Network Visualization:** Interactive visualization of the science backbone
5. **Analysis Report:** This comprehensive summary document

---

## Next Steps

1. **Validate results** with domain experts and stakeholders
2. **Refine vocabularies** (`science_backbone` and `svo_vocabulary`) based on feedback
3. **Integrate** with computational models and decision support systems
4. **Iterate** the analysis with additional documents or refined parameters
5. **Deploy** as part of a larger decision pathways workflow
"""
    return summary


def write_report(output_dir: Path, case_study_name: str, summary: str) -> Path:
    report_path = output_dir / f"{case_study_name}_report.md"
    report_path.write_text(summary)
    return report_path


def build_quick_reference(
    transcripts: dict[str, str],
    n_topics: int,
    topic_mappings: list[dict[str, object]],
    decision_components: dict[str, list[dict[str, str]]],
    svo_vocabulary: dict[str, dict[str, object]],
    unique_mappings: list[dict[str, str]],
    output_files: dict[str, Path],
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Analysis Component": [
                "Input Documents",
                "Topics Discovered",
                "Scientific Domains",
                "Decision Components",
                "Scientific Variables",
                "Semantic Links",
            ],
            "Count": [
                len(transcripts),
                n_topics,
                len(set(m["primary_domain"] for m in topic_mappings)),
                sum(len(v) for v in decision_components.values()),
                len(svo_vocabulary),
                len(unique_mappings),
            ],
            "Output File": [
                "N/A",
                output_files["mapping_path"].name,
                output_files["network_path"].name,
                output_files["components_path"].name,
                output_files["svo_path"].name,
                output_files["svo_path"].name,
            ],
        }
    )
