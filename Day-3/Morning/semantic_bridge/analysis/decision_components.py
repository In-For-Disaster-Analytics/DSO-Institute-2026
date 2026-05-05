"""Decision component extraction helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from semantic_bridge.constants import DEFAULT_COMPONENT_PATTERNS
from semantic_bridge.constants import DEFAULT_COMPONENT_SEED_PHRASES


def _safe_similarity(candidate: Any, reference: Any) -> float:
    try:
        score = float(candidate.similarity(reference))
    except Exception:
        return 0.0
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return score


def _build_seed_docs(nlp: Any, component_seeds: dict[str, list[str]]) -> dict[str, list[Any]]:
    seed_docs: dict[str, list[Any]] = {component: [] for component in component_seeds}
    for component, seeds in component_seeds.items():
        for seed in seeds:
            try:
                seed_docs[component].append(nlp(seed))
            except Exception:
                continue
    return seed_docs


def extract_decision_components(
    documents,
    nlp,
    patterns: dict[str, list[str]] | None = None,
    component_seeds: dict[str, list[str]] | None = None,
    keyword_weight: float = 0.45,
    semantic_weight: float = 0.55,
):
    component_patterns = deepcopy(patterns or DEFAULT_COMPONENT_PATTERNS)
    component_seed_map = deepcopy(component_seeds or DEFAULT_COMPONENT_SEED_PHRASES)
    seed_docs = _build_seed_docs(nlp, component_seed_map)
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
                            semantic_score = 0.0
                            for seed_doc in seed_docs.get(comp_type, []):
                                semantic_score = max(semantic_score, _safe_similarity(chunk, seed_doc))
                            confidence = keyword_weight + (semantic_weight * semantic_score)
                            components[comp_type].append(
                                {
                                    "text": chunk.text,
                                    "source": doc_name,
                                    "context": sent.text[:100],
                                    "confidence": round(confidence, 4),
                                }
                            )

    for comp_type in components:
        best_by_text: dict[str, dict[str, Any]] = {}
        for item in components[comp_type]:
            existing = best_by_text.get(item["text"])
            if existing is None or item["confidence"] > existing["confidence"]:
                best_by_text[item["text"]] = item
        ranked = sorted(best_by_text.values(), key=lambda value: value["confidence"], reverse=True)
        components[comp_type] = ranked[:10]
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
