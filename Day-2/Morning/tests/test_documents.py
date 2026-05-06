from __future__ import annotations

import json

from semantic_bridge.io.documents import load_documents
from semantic_bridge.io.documents import load_json_document
from semantic_bridge.io.documents import preview_documents


def test_load_json_document_prefers_text_fields(tmp_path):
    payload = {"content": "usable text", "other": 1}
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(payload))

    assert load_json_document(path) == "usable text"


def test_load_documents_prefers_cleaned_and_raw_and_skips_hidden(tmp_path):
    cleaned = tmp_path / "cleaned"
    raw = tmp_path / "raw"
    cleaned.mkdir()
    raw.mkdir()
    (cleaned / "alpha.txt").write_text("cleaned alpha")
    (raw / "alpha.txt").write_text("raw alpha should lose duplicate name")
    (raw / "beta.txt").write_text("raw beta")
    hidden_dir = cleaned / ".ipynb_checkpoints"
    hidden_dir.mkdir()
    (hidden_dir / "skip.txt").write_text("hidden")
    (tmp_path / "gamma.txt").write_text("base dir should be ignored when cleaned/raw exist")

    documents = load_documents(tmp_path)

    assert documents == {
        "alpha.txt": "cleaned alpha",
        "beta.txt": "raw beta",
    }


def test_preview_documents_truncates_content():
    previews = preview_documents({"doc.txt": "abcdefghij"}, preview_chars=5)

    assert previews == [{"filename": "doc.txt", "preview": "abcde..."}]

