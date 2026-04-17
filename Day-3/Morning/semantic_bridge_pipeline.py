"""Reusable helpers for the semantic bridge tutorial notebook."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote

import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
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

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency at runtime
    OpenAI = None

from semantic_bridge_defaults import (
    DEFAULT_COMPONENT_PATTERNS,
    DEFAULT_DOMAIN_KEYWORDS,
    DEFAULT_SCIENCE_BACKBONE,
    DEFAULT_SVO_VOCABULARY,
    SAMPLE_TRANSCRIPTS,
)
from semantic_bridge_ckan import auth_headers

SUPPORTED_DOCUMENT_SUFFIXES = {".txt", ".json", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


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
    for root in _document_roots(data_dir):
        for filepath in sorted(root.rglob("*")):
            if _is_hidden_path(filepath.relative_to(root)):
                continue
            if not filepath.is_file() or filepath.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
                continue
            if filepath.name in documents:
                continue
            try:
                documents[filepath.name] = load_document(filepath)
            except Exception as exc:
                print(f"Skipping {filepath.name}: {exc}")
    return documents


def fetch_ckan_dataset(
    base_url: str,
    dataset_name: str,
    auth_header: str | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    response = requests.get(
        f"{base_url.rstrip('/')}/api/3/action/package_show",
        params={"id": dataset_name},
        headers=auth_headers(auth_header),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise ValueError(f"CKAN package_show failed for {dataset_name}")
    return payload["result"]


def _resource_download_url(base_url: str, resource: dict[str, Any]) -> str:
    resource_url = resource.get("url", "")
    if resource_url.startswith("http://") or resource_url.startswith("https://"):
        return resource_url
    return f"{base_url.rstrip('/')}/{resource_url.lstrip('/')}"


def sync_ckan_resources_to_directory(
    dataset: dict[str, Any],
    target_dir: Path,
    base_url: str,
    auth_header: str | None = None,
    overwrite: bool = False,
    timeout: int = 120,
) -> list[Path]:
    ensure_data_directory(target_dir)
    headers = auth_headers(auth_header)

    downloaded_paths: list[Path] = []
    for resource in dataset.get("resources", []):
        resource_name = resource.get("name", "").strip()
        if not resource_name:
            continue
        suffix = Path(resource_name).suffix.lower()
        if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
            continue

        target_path = target_dir / resource_name
        if target_path.exists() and not overwrite:
            downloaded_paths.append(target_path)
            continue

        response = requests.get(
            _resource_download_url(base_url, resource),
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        target_path.write_bytes(response.content)
        downloaded_paths.append(target_path)

    return downloaded_paths


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


def topic_display_name(topic_info: dict[str, Any]) -> str:
    return topic_info.get("human_label") or topic_info["label"]


def _topic_context(
    topic_id: str,
    topic_info: dict[str, Any],
    doc_topic_dist,
    doc_names: list[str],
    documents: dict[str, str],
    top_document_count: int = 3,
    snippet_chars: int = 350,
) -> dict[str, Any]:
    topic_index = int(topic_id.split()[1]) - 1
    ranked_indices = doc_topic_dist[:, topic_index].argsort()[::-1][:top_document_count]
    top_documents = []
    for idx in ranked_indices:
        doc_name = doc_names[idx]
        snippet = documents[doc_name][:snippet_chars].replace("\n", " ").strip()
        top_documents.append(
            {
                "document": Path(doc_name).stem,
                "coverage": float(doc_topic_dist[idx, topic_index]),
                "snippet": snippet,
            }
        )
    return {
        "topic": topic_id,
        "keywords": topic_info["keywords"],
        "top_documents": top_documents,
    }


def _parse_json_response(content: str) -> dict[str, str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", cleaned)

    candidates = [cleaned]
    object_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if object_match:
        candidates.append(object_match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate, strict=False)
            return {
                "label": str(payload.get("label", "")).strip(),
                "description": str(payload.get("description", "")).strip(),
            }
        except json.JSONDecodeError:
            continue

    label_match = re.search(r'"label"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    description_match = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned, re.DOTALL)
    if label_match or description_match:
        return {
            "label": bytes((label_match.group(1) if label_match else ""), "utf-8").decode("unicode_escape").strip(),
            "description": bytes(
                (description_match.group(1) if description_match else ""),
                "utf-8",
            ).decode("unicode_escape").strip(),
        }

    # Final fallback: treat the response as plain text and preserve it as the description.
    one_line = " ".join(cleaned.split())
    return {
        "label": "",
        "description": one_line,
    }


def relabel_topics_with_llm(
    topics_info: dict[str, dict[str, Any]],
    doc_topic_dist,
    doc_names: list[str],
    documents: dict[str, str],
    model: str,
    api_key: str,
    base_url: str | None = None,
) -> dict[str, dict[str, Any]]:
    if OpenAI is None:
        raise RuntimeError("openai is not installed in this environment")
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    updated_topics = deepcopy(topics_info)

    for topic_id, topic_info in updated_topics.items():
        context = _topic_context(topic_id, topic_info, doc_topic_dist, doc_names, documents)
        prompt = (
            "You are helping label topic-model outputs for a tutorial notebook.\n"
            "Given topic keywords and short excerpts from high-coverage documents, "
            "write a concise, human-readable topic label and a one-sentence description.\n"
            "Return JSON with keys 'label' and 'description'.\n"
            "Keep the label under 6 words. Avoid repeating the raw keyword list."
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(context, indent=2),
                },
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_json_response(content)
        updated_topics[topic_id]["human_label"] = f"{topic_id}: {parsed['label']}" if parsed["label"] else topic_info["label"]
        updated_topics[topic_id]["description"] = parsed["description"]

    return updated_topics


def build_topic_summary(topics_info: dict[str, dict[str, object]], doc_topic_dist, top_words_display: int) -> pd.DataFrame:
    summary_data = []
    for topic_num, info in topics_info.items():
        topic_index = int(topic_num.split()[1]) - 1
        summary_data.append(
            {
                "Topic": topic_num,
                "Label": topic_display_name(info),
                "Description": info.get("description", ""),
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
        display_name = topic_display_name(topic_info)
        hover_text = [
            f"{display_name}<br>"
            f"Document: {doc}<br>"
            f"Proportion: {val:.1%}<br>"
            f"Keywords: {', '.join(topic_info['keywords'][:6])}"
            + (f"<br>Description: {topic_info['description']}" if topic_info.get("description") else "")
            for doc, val in zip(topic_df.index, topic_df[topic_num])
        ]
        fig.add_trace(
            go.Bar(
                name=display_name,
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


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.startswith("http"):
            normalized = unquote(normalized.rstrip("/").split("/")[-1])
        return [normalized]
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_coerce_string_list(item))
        return values
    if isinstance(value, dict):
        for key in ("label", "name", "value", "id"):
            nested = value.get(key)
            values = _coerce_string_list(nested)
            if values:
                return values
    return []


def _first_nonempty(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        values = _coerce_string_list(value)
        if values:
            return values[0]
    return ""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _humanize_identifier(text: str) -> str:
    cleaned = text.replace("_", " ").replace("~", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.isupper():
        return cleaned.title()
    return cleaned


def _infer_domain_from_standard_name(standard_name: str, description: str = "") -> str:
    reference_text = f"{standard_name} {description}".upper()
    domain_rules = [
        ("Hydrology", ["SURFACE WATER", "GROUNDWATER", "RIVER", "DISCHARGE", "RUNOFF", "STREAM", "AQUIFER"]),
        ("Atmospheric Science", ["ATMOSPHERE", "AIR", "HUMIDITY", "PRECIPITATION", "RAINFALL", "TEMPERATURE", "WIND"]),
        ("Soil Science", ["SOIL", "STOMATAL", "HYDRAULIC CONDUCTIVITY", "POROSITY", "FIELD CAPACITY"]),
        ("Agriculture", ["CROP", "BIOMASS", "GRAIN", "FORAGE", "PLANT", "HARVEST", "RESIDUE"]),
        ("Oceanography", ["SEA", "OCEAN", "TIDE", "SALINITY", "ESTUARY", "COASTAL"]),
        ("Ecology", ["VEGETATION", "CANOPY", "ROOT", "LEAF", "ECOSYSTEM"]),
        ("Land Systems", ["LAND", "AREA", "USE", "ALLOCATION"]),
    ]
    for domain, markers in domain_rules:
        if any(marker in reference_text for marker in markers):
            return domain
    return "General Science"


def _keyword_candidates(*values: str) -> list[str]:
    keywords = []
    seen = set()
    for value in values:
        if not value:
            continue
        for candidate in re.split(r"[,;/]|(?:\s+-\s+)", value):
            cleaned = " ".join(candidate.lower().replace("_", " ").split())
            if len(cleaned) < 3:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                keywords.append(cleaned)
            for token in cleaned.split():
                if len(token) >= 4 and token not in seen:
                    seen.add(token)
                    keywords.append(token)
    return keywords[:12]


def _normalize_mint_variable(record: dict[str, Any]) -> tuple[str, dict[str, object]]:
    long_name = _first_nonempty(record, "hasLongName", "long_name", "longName")
    short_name = _first_nonempty(record, "hasShortName", "short_name", "shortName")
    display_name = _first_nonempty(
        record,
        "hasLongName",
        "long_name",
        "longName",
        "label",
        "name",
        "variable_name",
        "variableName",
        "standard_variable",
        "standardVariable",
    )
    standard_name = _first_nonempty(
        record,
        "hasStandardVariable",
        "standard_name",
        "standardName",
        "standard_variable",
        "standardVariable",
        "ontology_name",
        "ontologyName",
    ) or display_name
    units = _first_nonempty(record, "usesUnit", "units", "unit", "unit_names", "unitNames") or "unknown"
    description = _first_nonempty(record, "description", "definition", "summary")
    domain = _first_nonempty(record, "domain", "category", "theme", "realm")
    aliases = (
        _coerce_string_list(record.get("aliases"))
        + _coerce_string_list(record.get("synonyms"))
        + _coerce_string_list(record.get("hasShortName"))
        + _coerce_string_list(record.get("label"))
    )
    key_name = _slugify(display_name or standard_name or _first_nonempty(record, "id", "@id") or "mint_variable")
    human_label = _humanize_identifier(display_name or standard_name or key_name)
    human_standard_name = _humanize_identifier(standard_name)
    inferred_domain = _infer_domain_from_standard_name(human_standard_name, description)
    keywords = _keyword_candidates(human_label, short_name, human_standard_name, description, *aliases)
    return key_name, {
        "standard_name": human_standard_name,
        "units": _humanize_identifier(units),
        "data_source": "MINT variablepresentations API",
        "keywords": keywords or [key_name.replace("_", " ")],
        "domain": domain or inferred_domain,
        "label": human_label,
        "description": description,
        "short_name": short_name,
        "mint_id": _first_nonempty(record, "id", "@id"),
    }


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "data", "variablepresentations", "variablePresentations"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def fetch_mint_svo_vocabulary(
    base_url: str,
    username: str = "mint@isi.edu",
    per_page: int = 200,
    max_pages: int = 3,
    timeout: int = 30,
) -> dict[str, dict[str, object]]:
    endpoint = f"{base_url.rstrip('/')}/variablepresentations"
    vocabulary = {}
    session = requests.Session()

    for page in range(1, max_pages + 1):
        response = session.get(
            endpoint,
            params={
                "username": username,
                "page": page,
                "per_page": per_page,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        records = _extract_records(response.json())
        if not records:
            break
        for record in records:
            key, normalized = _normalize_mint_variable(record)
            if key not in vocabulary:
                vocabulary[key] = normalized
        if len(records) < per_page:
            break

    if not vocabulary:
        raise RuntimeError("MINT variablepresentations returned no usable records")
    return vocabulary


def _extract_model_candidates(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "data", "models", "modelconfigurations", "modelConfigurations"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_mint_model_candidate(record: dict[str, Any], candidate_kind: str) -> dict[str, Any]:
    label = _first_nonempty(record, "label", "name") or _first_nonempty(record, "id", "@id")
    description = _first_nonempty(record, "description", "shortDescription", "hasPurpose")
    keywords = _coerce_string_list(record.get("keywords"))
    categories = _coerce_string_list(record.get("hasModelCategory"))
    inputs = _coerce_string_list(record.get("hasInput"))
    outputs = _coerce_string_list(record.get("hasOutput"))
    processes = _coerce_string_list(record.get("hasProcess"))
    text_parts = [label, description, *keywords, *categories, *inputs, *outputs, *processes]
    searchable_text = " ".join(_humanize_identifier(part) for part in text_parts if part).lower()
    return {
        "id": _first_nonempty(record, "id", "@id"),
        "label": label,
        "description": description,
        "keywords": keywords,
        "categories": categories,
        "inputs": inputs,
        "outputs": outputs,
        "processes": processes,
        "candidate_kind": candidate_kind,
        "searchable_text": searchable_text,
    }


def fetch_mint_model_candidates(
    base_url: str,
    username: str = "mint@isi.edu",
    per_page: int = 100,
    max_pages: int = 3,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    session = requests.Session()
    endpoints = [
        ("models", "Model"),
        ("modelconfigurations", "Model Configuration"),
    ]
    candidates = []
    seen_ids = set()

    for endpoint_name, candidate_kind in endpoints:
        endpoint = f"{base_url.rstrip('/')}/{endpoint_name}"
        for page in range(1, max_pages + 1):
            response = session.get(
                endpoint,
                params={
                    "username": username,
                    "page": page,
                    "per_page": per_page,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            records = _extract_model_candidates(response.json())
            if not records:
                break
            for record in records:
                normalized = _normalize_mint_model_candidate(record, candidate_kind)
                record_id = normalized["id"] or normalized["label"]
                if record_id in seen_ids:
                    continue
                seen_ids.add(record_id)
                candidates.append(normalized)
            if len(records) < per_page:
                break

    if not candidates:
        raise RuntimeError("MINT model catalog returned no usable model candidates")
    return candidates


def recommend_models_for_svo_mappings(
    unique_mappings: list[dict[str, str]],
    model_candidates: list[dict[str, Any]],
    recommendations_per_svo: int = 2,
) -> list[dict[str, str]]:
    grouped = {}
    for mapping in unique_mappings:
        grouped.setdefault(mapping["scientific_variable"], mapping)

    recommendations = []
    for scientific_variable, mapping in grouped.items():
        query_terms = {
            mapping["scientific_variable"].replace("_", " ").lower(),
            mapping["standard_name"].lower(),
            mapping["domain"].lower(),
            mapping["natural_language_term"].lower(),
        }
        query_terms.update(term for term in mapping["standard_name"].lower().split() if len(term) >= 4)
        scored = []
        for candidate in model_candidates:
            score = 0
            searchable_text = candidate["searchable_text"]
            for term in query_terms:
                if not term:
                    continue
                if term in searchable_text:
                    score += 3 if " " in term else 1
            if mapping["domain"].lower() in " ".join(candidate["categories"]).lower():
                score += 3
            if mapping["natural_language_term"].lower() in searchable_text:
                score += 2
            if score > 0:
                scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], item[1]["label"]))
        for rank, (score, candidate) in enumerate(scored[:recommendations_per_svo], start=1):
            recommendations.append(
                {
                    "scientific_variable": scientific_variable,
                    "standard_name": mapping["standard_name"],
                    "domain": mapping["domain"],
                    "recommended_model": candidate["label"],
                    "model_type": candidate["candidate_kind"],
                    "model_categories": ", ".join(candidate["categories"]),
                    "model_keywords": ", ".join(candidate["keywords"]),
                    "reason_score": score,
                    "model_description": candidate["description"],
                    "rank": rank,
                }
            )
    return recommendations


def recommend_mint_queries_for_topics(
    topics_info: dict[str, dict[str, Any]],
    model_candidates: list[dict[str, Any]],
    recommendations_per_topic: int = 2,
    tags_per_topic: int = 5,
) -> list[dict[str, Any]]:
    recommendations = []
    for topic_id, topic_info in topics_info.items():
        query_terms = set(topic_info["keywords"])
        query_terms.update(term for term in topic_display_name(topic_info).lower().replace(":", " ").split() if len(term) >= 4)
        query_terms.update(term for term in topic_info.get("description", "").lower().split() if len(term) >= 4)

        scored = []
        for candidate in model_candidates:
            score = 0
            searchable_text = candidate["searchable_text"]
            for term in query_terms:
                if not term:
                    continue
                if term in searchable_text:
                    score += 3 if " " in term else 1
            if topic_info.get("description"):
                score += sum(1 for word in topic_info["description"].lower().split() if len(word) >= 6 and word in searchable_text)
            if score > 0:
                scored.append((score, candidate))

        scored.sort(key=lambda item: (-item[0], item[1]["label"]))
        top_scored = scored[: max(recommendations_per_topic * 3, 6)]

        category_counts = Counter()
        keyword_counts = Counter()
        for score, candidate in top_scored:
            for category in candidate["categories"]:
                category_counts[_humanize_identifier(category)] += score
            for keyword in candidate["keywords"]:
                keyword_counts[_humanize_identifier(keyword)] += score

        top_models = scored[:recommendations_per_topic]
        recommendations.append(
            {
                "topic": topic_id,
                "label": topic_display_name(topic_info),
                "description": topic_info.get("description", ""),
                "query_domains": [name for name, _ in category_counts.most_common(3)],
                "query_tags": [name for name, _ in keyword_counts.most_common(tags_per_topic)],
                "recommended_models": [
                    {
                        "label": candidate["label"],
                        "type": candidate["candidate_kind"],
                        "categories": candidate["categories"],
                        "keywords": candidate["keywords"],
                        "description": candidate["description"],
                        "score": score,
                    }
                    for score, candidate in top_models
                ],
            }
        )
    return recommendations


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


def create_svo_mappings(
    documents: dict[str, str],
    svo_vocabulary: dict[str, dict[str, object]],
    min_keyword_words: int = 2,
    allow_single_word_keywords: set[str] | None = None,
) -> list[dict[str, str]]:
    mappings = []
    allowed_singletons = {keyword.strip().lower() for keyword in (allow_single_word_keywords or set()) if keyword.strip()}
    for doc_name, text in documents.items():
        text_lower = text.lower()
        for svo_name, svo_info in svo_vocabulary.items():
            for keyword in svo_info["keywords"]:
                normalized_keyword = " ".join(keyword.lower().split())
                keyword_word_count = len(normalized_keyword.split())
                if keyword_word_count < min_keyword_words and normalized_keyword not in allowed_singletons:
                    continue
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
