from __future__ import annotations

import pandas as pd

from semantic_bridge.text import llm_labels


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def create(self, **_kwargs):
        return _FakeResponse('{"readable_text": "reduced groundwater pumping", "rationale": "normalized phrase"}')


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeOpenAIClient:
    def __init__(self, **_kwargs):
        self.chat = _FakeChat()


def test_improve_decision_component_readability_with_llm(monkeypatch):
    monkeypatch.setattr(llm_labels, "OpenAI", _FakeOpenAIClient)
    components_df = pd.DataFrame(
        [
            {
                "component_type": "goals",
                "text": "groundwater withdrawal",
                "source": "example.txt",
                "context": "The long-term goal is to reduce groundwater withdrawal.",
            }
        ]
    )

    improved_df = llm_labels.improve_decision_component_readability_with_llm(
        components_df=components_df,
        model="gpt-4o-mini",
        api_key="test-key",
    )

    assert "readable_text" in improved_df.columns
    assert "readable_rationale" in improved_df.columns
    assert improved_df.loc[0, "readable_text"] == "reduced groundwater pumping"
    assert improved_df.loc[0, "readable_rationale"] == "normalized phrase"
