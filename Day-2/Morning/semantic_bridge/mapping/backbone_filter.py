"""Human-readable helpers for filtering the full UCSD science backbone.

Why this exists
---------------
The full UCSD Map of Science is useful, but it is too broad for the Day 2
semantic bridge visualization. These helpers keep the workflow general:

    documents -> discovered topic keywords -> filtered UCSD science backbone

No groundwater-specific seed list is required. The notebook can still add a
small optional hint list later, but the default behavior is corpus-driven.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any, Iterable

import pandas as pd

from semantic_bridge.text.topics import topic_display_name


DEFAULT_STOPWORDS = {
    # English/function words
    "about", "above", "across", "after", "again", "against", "also", "among",
    "and", "are", "because", "been", "before", "being", "below", "between",
    "both", "but", "can", "could", "did", "does", "doing", "done", "during",
    "each", "few", "for", "from", "had", "has", "have", "having", "into",
    "its", "itself", "may", "more", "most", "not", "off", "our", "out",
    "over", "own", "same", "should", "such", "than", "that", "the", "their",
    "then", "there", "these", "they", "this", "those", "through", "under",
    "use", "used", "using", "was", "were", "when", "where", "which", "while",
    "with", "within", "would", "you", "your",
    # common paper/report words that should not drive science-domain filtering
    "abstract", "analysis", "approach", "article", "authors", "based", "case",
    "data", "dataset", "datasets", "document", "documents", "figure", "figures",
    "finding", "findings", "introduction", "method", "methods", "model",
    "models", "paper", "papers", "report", "reports", "research", "result",
    "results", "section", "study", "table", "tables", "text",
}


def clean_term(value: Any) -> str:
    """Normalize a word or phrase for matching."""
    text = " ".join(str(value).lower().replace("_", " ").split())
    text = re.sub(r"[^a-z0-9\- ]+", "", text)
    return text.strip()


def unique_in_order(values: Iterable[Any]) -> list[str]:
    """Return cleaned unique terms while keeping first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        term = clean_term(value)
        if not term or term in seen:
            continue
        seen.add(term)
        out.append(term)
    return out


def document_to_text(document: Any) -> str:
    """Extract text from the document shapes used in the Day 2 notebook."""
    if document is None:
        return ""

    if isinstance(document, str):
        return document

    if isinstance(document, dict):
        for key in ("text", "content", "page_content", "body", "raw_text"):
            value = document.get(key)
            if value:
                return str(value)
        return " ".join(str(value) for value in document.values() if value is not None)

    # LangChain-style objects and simple dataclasses often expose one of these.
    for attr in ("page_content", "text", "content", "body"):
        value = getattr(document, attr, None)
        if value:
            return str(value)

    return str(document)


def collect_topic_terms(topics_info: dict[str, dict[str, Any]] | None) -> list[str]:
    """Collect terms from discovered topics.

    This is the most important signal because it comes from the topic discovery
    stage rather than from hand-written domain hints.
    """
    if not topics_info:
        return []

    terms: list[str] = []
    for topic_id, topic_data in topics_info.items():
        terms.extend(topic_data.get("keywords", []) or [])
        terms.extend(topic_data.get("terms", []) or [])
        terms.append(topic_display_name(topic_data))
        terms.append(topic_id)

    return unique_in_order(terms)


def collect_corpus_terms(
    documents: Iterable[Any] | None,
    *,
    top_n: int = 100,
    stopwords: set[str] | None = None,
) -> list[str]:
    """Extract high-frequency words and two-word phrases from the loaded corpus.

    This is intentionally simple and dependency-free. It gives the science
    backbone filter a general sense of what the documents are about without
    requiring another API/model call.
    """
    if documents is None:
        return []

    stop = stopwords or DEFAULT_STOPWORDS
    text = "\n".join(document_to_text(doc) for doc in documents).lower()
    tokens = re.findall(r"\b[a-z][a-z0-9\-]{2,}\b", text)
    tokens = [token for token in tokens if token not in stop and not token.isdigit()]

    unigram_counts = Counter(tokens)
    bigram_counts = Counter(
        f"{tokens[i]} {tokens[i + 1]}"
        for i in range(len(tokens) - 1)
        if tokens[i] not in stop and tokens[i + 1] not in stop
    )

    phrases = [term for term, _ in bigram_counts.most_common(max(10, top_n // 2))]
    words = [term for term, _ in unigram_counts.most_common(top_n)]
    return unique_in_order([*phrases, *words])[:top_n]


def collect_case_terms(
    *,
    topics_info: dict[str, dict[str, Any]] | None = None,
    documents: Iterable[Any] | None = None,
    extra_terms: Iterable[str] | None = None,
    max_corpus_terms: int = 100,
) -> dict[str, list[str]]:
    """Collect all terms used to filter the science backbone.

    The default is document-driven. ``extra_terms`` is optional and should only
    be used as a small hint list when the corpus is too sparse.
    """
    topic_terms = collect_topic_terms(topics_info)
    corpus_terms = collect_corpus_terms(documents, top_n=max_corpus_terms)
    hint_terms = unique_in_order(extra_terms or [])

    all_terms = unique_in_order([*topic_terms, *corpus_terms, *hint_terms])
    all_terms = [term for term in all_terms if len(term) > 2 and term not in DEFAULT_STOPWORDS]

    return {
        "topic_terms": topic_terms,
        "corpus_terms": corpus_terms,
        "extra_terms": hint_terms,
        "all_terms": all_terms,
    }


def node_search_text(domain: str, node: dict[str, Any]) -> str:
    """Build searchable text for one science-backbone domain."""
    values: list[Any] = [domain]
    values.extend(node.get("subdisciplines", []) or [])
    values.extend(node.get("terms", []) or [])
    values.extend(node.get("keywords", []) or [])
    return " | ".join(clean_term(value) for value in values if value is not None)


def score_domain(domain: str, node: dict[str, Any], case_terms: Iterable[str]) -> tuple[int, list[str]]:
    """Score one UCSD domain by counting case terms found in that domain node."""
    searchable = node_search_text(domain, node)
    matches = []
    for term in case_terms:
        term = clean_term(term)
        if len(term) <= 2:
            continue
        if term in searchable:
            matches.append(term)

    matches = unique_in_order(matches)
    return len(matches), matches


def filter_subdisciplines(
    subdisciplines: Iterable[str],
    case_terms: Iterable[str],
    *,
    keep_top_n: int = 30,
) -> list[str]:
    """Keep only subdisciplines that visibly match the case terms.

    If no subdiscipline labels match directly, keep a small readable sample so
    the domain is not empty.
    """
    terms = [clean_term(term) for term in case_terms if len(clean_term(term)) > 2]
    scored: list[tuple[int, str]] = []

    for sub in subdisciplines or []:
        sub_clean = clean_term(sub)
        score = sum(1 for term in terms if term in sub_clean or sub_clean in term)
        if score > 0:
            scored.append((score, str(sub)))

    if scored:
        scored.sort(key=lambda item: (-item[0], item[1].lower()))
        return [sub for _, sub in scored[:keep_top_n]]

    return list(subdisciplines or [])[: min(keep_top_n, 10)]


def filter_science_backbone_for_case(
    science_backbone: dict[str, dict[str, Any]],
    *,
    topics_info: dict[str, dict[str, Any]] | None = None,
    documents: Iterable[Any] | None = None,
    extra_terms: Iterable[str] | None = None,
    keep_top_domains: int = 6,
    keep_top_subdisciplines: int = 30,
    min_domain_score: int = 1,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Filter the full UCSD backbone down to the current document/case study.

    Returns ``(filtered_backbone, debug_info)``. The debug info is intentionally
    notebook-friendly so students can see why domains were kept.
    """
    term_groups = collect_case_terms(
        topics_info=topics_info,
        documents=documents,
        extra_terms=extra_terms,
    )
    case_terms = term_groups["all_terms"]

    scored_domains: list[tuple[int, str, dict[str, Any], list[str]]] = []
    for domain, node in science_backbone.items():
        score, matches = score_domain(domain, node, case_terms)
        if score >= min_domain_score:
            kept = deepcopy(node)
            kept["subdisciplines"] = filter_subdisciplines(
                kept.get("subdisciplines", []),
                case_terms,
                keep_top_n=keep_top_subdisciplines,
            )
            kept["filter_score"] = score
            kept["matched_filter_terms"] = matches
            kept["source"] = kept.get("source", "UCSD Map of Science")
            scored_domains.append((score, domain, kept, matches))

    scored_domains.sort(key=lambda item: (-item[0], item[1].lower()))
    if keep_top_domains:
        scored_domains = scored_domains[:keep_top_domains]

    filtered = {domain: node for score, domain, node, matches in scored_domains}
    debug = {
        **term_groups,
        "domain_scores": [
            {
                "domain": domain,
                "score": score,
                "matches": matches[:12],
                "kept_subdisciplines": len(node.get("subdisciplines", [])),
            }
            for score, domain, node, matches in scored_domains
        ],
    }
    return filtered, debug


def make_topic_mappings_from_backbone(
    topics_info: dict[str, dict[str, Any]],
    science_backbone: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map discovered topics to the filtered science backbone.

    This creates the ``topic_mappings`` variable expected by
    ``create_network_figure(science_backbone, topic_mappings, ...)``.
    """
    mappings: list[dict[str, Any]] = []

    for topic_id, topic_data in topics_info.items():
        topic_terms = collect_topic_terms({topic_id: topic_data})

        domain_hits = []
        for domain, node in science_backbone.items():
            score, matches = score_domain(domain, node, topic_terms)
            if score > 0:
                domain_hits.append((score, domain, matches))

        domain_hits.sort(key=lambda item: (-item[0], item[1].lower()))

        primary_domain = domain_hits[0][1] if domain_hits else "General"
        secondary_domain = domain_hits[1][1] if len(domain_hits) > 1 else None
        matched_terms = domain_hits[0][2] if domain_hits else []

        mappings.append(
            {
                "topic": topic_id,
                "topic_label": topic_display_name(topic_data),
                "keywords": ", ".join(topic_data.get("keywords", [])[:5]),
                "primary_domain": primary_domain,
                "secondary_domain": secondary_domain,
                "matched_terms": ", ".join(matched_terms[:10]),
                "mapping_score": domain_hits[0][0] if domain_hits else 0,
            }
        )

    return mappings


def topic_mappings_table(topic_mappings: list[dict[str, Any]]) -> pd.DataFrame:
    """Small display helper for notebooks."""
    columns = [
        "topic",
        "topic_label",
        "keywords",
        "primary_domain",
        "secondary_domain",
        "mapping_score",
        "matched_terms",
    ]
    return pd.DataFrame(topic_mappings).reindex(columns=columns)
