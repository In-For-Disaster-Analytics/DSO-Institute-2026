"""Decision component extraction helpers."""

from __future__ import annotations

from copy import deepcopy

import pandas as pd

from semantic_bridge.constants import DEFAULT_COMPONENT_PATTERNS


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

