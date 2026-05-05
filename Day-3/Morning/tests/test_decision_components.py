from __future__ import annotations

from semantic_bridge.analysis.decision_components import component_counts
from semantic_bridge.analysis.decision_components import component_table
from semantic_bridge.analysis.decision_components import extract_decision_components


class FakeChunk:
    def __init__(self, text: str):
        self.text = text


class FakeChunkWithSimilarity(FakeChunk):
    def __init__(self, text: str, similarity_score: float):
        super().__init__(text)
        self.similarity_score = similarity_score

    def similarity(self, _other) -> float:
        return self.similarity_score


class FakeSentence:
    def __init__(self, text: str, noun_chunks: list[str]):
        self.text = text
        self.noun_chunks = [FakeChunk(chunk) for chunk in noun_chunks]


class FakeDoc:
    def __init__(self, sentences):
        self.sents = sentences


class FakeNLP:
    def __call__(self, text: str):
        return FakeDoc(
            [
                FakeSentence("Our goal is flood protection for downtown homes.", ["flood protection", "downtown homes"]),
                FakeSentence("The budget constraint limits major upgrades.", ["budget constraint", "major upgrades"]),
            ]
        )


class FakeSentenceWithSimilarity:
    def __init__(self, text: str, noun_chunks: list[tuple[str, float]]):
        self.text = text
        self.noun_chunks = [FakeChunkWithSimilarity(chunk, score) for chunk, score in noun_chunks]


class FakeNLPWithSimilarity:
    def __call__(self, text: str):
        if text in {
            "desired outcome",
            "long term target",
            "community protection goal",
            "specific measurable objective",
            "optimize system performance",
            "reduce negative impacts",
            "decision option",
            "management strategy choice",
            "implementation alternative",
            "budget limitation",
            "policy restriction",
            "feasibility boundary",
            "success metric",
            "performance indicator",
            "measurable signal",
        }:
            return object()
        return FakeDoc(
            [
                FakeSentenceWithSimilarity("Our goal includes flood protection.", [("flood protection", 0.1)]),
                FakeSentenceWithSimilarity("Our goal includes flood protection for residents.", [("flood protection", 0.9)]),
            ]
        )


def test_extract_decision_components_and_summaries():
    documents = {"doc.txt": "unused raw text"}
    components = extract_decision_components(documents, FakeNLP())

    assert "flood protection" in [item["text"] for item in components["goals"]]
    assert "budget constraint" in [item["text"] for item in components["constraints"]]
    assert component_counts(components)["goals"] == 2

    table = component_table(components)
    assert set(table.columns) == {"component_type", "text", "source", "context"}
    assert not table.empty


def test_extract_decision_components_prefers_highest_confidence_duplicate():
    documents = {"doc.txt": "unused raw text"}
    components = extract_decision_components(documents, FakeNLPWithSimilarity())
    goal_matches = [item for item in components["goals"] if item["text"] == "flood protection"]

    assert len(goal_matches) == 1
    assert goal_matches[0]["confidence"] == 0.945
