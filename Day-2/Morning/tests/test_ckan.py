from __future__ import annotations

import json
from pathlib import Path

from semantic_bridge.io import ckan


class DummyResponse:
    def __init__(self, payload=None, content: bytes = b"file-bytes", status_code: int = 200, text: str = ""):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_build_ckan_auth_header_api_token():
    assert ckan.build_ckan_auth_header(auth_mode="api_token", api_token=" token ") == "token"


def test_build_ckan_auth_header_tapis_password(monkeypatch):
    monkeypatch.setattr(ckan, "get_tapis_token", lambda username, password, tapis_url: "abc123")

    header = ckan.build_ckan_auth_header(auth_mode="tapis_password", username="user", password="secret")

    assert header == "Bearer abc123"


def test_fetch_ckan_dataset_returns_result(monkeypatch):
    def fake_get(url, params, headers, timeout):
        assert url.endswith("/api/3/action/package_show")
        assert params == {"id": "dataset-name"}
        assert headers == {"Authorization": "Bearer abc"}
        assert timeout == 60
        return DummyResponse({"success": True, "result": {"name": "dataset-name"}})

    monkeypatch.setattr(ckan.requests, "get", fake_get)

    result = ckan.fetch_ckan_dataset("https://example.com", "dataset-name", auth_header="Bearer abc")

    assert result == {"name": "dataset-name"}


def test_ckan_action_post_surfaces_http_error_payload(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return DummyResponse(
            payload={"success": False, "error": {"name": ["That URL is already in use."]}},
            status_code=409,
            text="conflict",
        )

    monkeypatch.setattr(ckan.requests, "post", fake_post)

    try:
        ckan._ckan_action_post("https://example.com", "package_patch", {"id": "x"})
        assert False, "Expected ValueError"
    except ValueError as exc:
        message = str(exc)
        assert "HTTP 409" in message
        assert "That URL is already in use." in message


def test_sync_ckan_resources_to_directory_downloads_supported_files(monkeypatch, tmp_path):
    requested_urls = []

    def fake_get(url, headers, timeout):
        requested_urls.append((url, headers, timeout))
        return DummyResponse(content=b"alpha")

    monkeypatch.setattr(ckan.requests, "get", fake_get)
    dataset = {
        "resources": [
            {"name": "alpha.txt", "url": "/dataset/alpha.txt"},
            {"name": "ignore.csv", "url": "/dataset/ignore.csv"},
        ]
    }

    paths = ckan.sync_ckan_resources_to_directory(dataset, tmp_path, "https://example.com", auth_header="Bearer abc")

    assert [path.name for path in paths] == ["alpha.txt"]
    assert (tmp_path / "alpha.txt").read_bytes() == b"alpha"
    assert requested_urls == [("https://example.com/dataset/alpha.txt", {"Authorization": "Bearer abc"}, 120)]


def test_collect_pdf_resources(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "b.txt").write_text("b")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.pdf").write_bytes(b"c")

    pdfs = ckan.collect_pdf_resources(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in pdfs] == ["a.pdf", "nested/c.pdf"]


def test_build_ckan_registration_plan_with_llm_aggregates_tags(monkeypatch, tmp_path):
    pdf_a = tmp_path / "one.pdf"
    pdf_b = tmp_path / "two.pdf"
    pdf_a.write_bytes(b"1")
    pdf_b.write_bytes(b"2")

    def fake_extract(pdf_path: Path, **_kwargs):
        if pdf_path.name == "one.pdf":
            return {
                "resource_name": "one.pdf",
                "resource_title": "Shared Title",
                "resource_description": "Desc one",
                "resource_tags": ["groundwater", "subsidence", "groundwater"],
            }
        return {
            "resource_name": "two.pdf",
            "resource_title": "Shared Title",
            "resource_description": "Desc two",
            "resource_tags": ["flood", "groundwater"],
        }

    monkeypatch.setattr(ckan, "extract_ckan_resource_metadata_with_llm", fake_extract)

    plan = ckan.build_ckan_registration_plan_with_llm(
        [pdf_a, pdf_b],
        model="gpt-test",
        api_key="key",
        dataset_title="My Corpus",
    )

    assert plan["dataset_name"] == "my-corpus"
    assert plan["dataset_title"] == "My Corpus"
    assert [item["resource_name"] for item in plan["resources"]] == ["one.pdf", "two.pdf"]
    assert plan["resources"][0]["resource_title"] == "Shared Title (one)"
    assert plan["resources"][1]["resource_title"] == "Shared Title (two)"
    assert plan["resources"][0]["resource_tags"] == ["groundwater", "subsidence"]
    tag_names = [tag["name"] for tag in plan["dataset_tags"]]
    assert "groundwater" in tag_names
    assert "subsidence" in tag_names
    assert "flood" in tag_names
    assert "semantic-bridge" in tag_names


def test_create_or_update_ckan_dataset_creates_when_missing(monkeypatch):
    monkeypatch.setattr(ckan, "fetch_ckan_dataset", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("missing")))
    calls = []

    def fake_action(base_url, action, payload, auth_header=None, files=None, timeout=120):
        calls.append((base_url, action, payload, auth_header, files, timeout))
        return {"id": "dataset-id", "name": payload["name"]}

    monkeypatch.setattr(ckan, "_ckan_action_post", fake_action)

    dataset = ckan.create_or_update_ckan_dataset(
        "https://example.com",
        dataset_name="demo",
        dataset_title="Demo",
        dataset_notes="Notes",
        auth_header="Bearer abc",
        dataset_author="Author Name",
        dataset_author_email="author@example.com",
        dataset_maintainer="Maintainer Name",
        dataset_maintainer_email="maintainer@example.com",
        dataset_license_id="cc-by",
        dataset_url="https://example.com/source",
        dataset_version="2026.05",
        dataset_type="dataset",
        dataset_isopen=True,
        dataset_spatial='{"type":"Polygon","coordinates":[[[-1,1],[-1,2],[1,2],[1,1],[-1,1]]]}',
        temporal_coverage_start="2025-01-01",
        temporal_coverage_end="2025-12-31",
    )

    assert dataset["name"] == "demo"
    assert calls[0][1] == "package_create"
    assert calls[0][2]["name"] == "demo"
    assert calls[0][2]["author"] == "Author Name"
    assert calls[0][2]["author_email"] == "author@example.com"
    assert calls[0][2]["maintainer"] == "Maintainer Name"
    assert calls[0][2]["maintainer_email"] == "maintainer@example.com"
    assert calls[0][2]["license_id"] == "cc-by"
    assert calls[0][2]["url"] == "https://example.com/source"
    assert calls[0][2]["version"] == "2026.05"
    assert calls[0][2]["type"] == "dataset"
    assert calls[0][2]["isopen"] is True
    assert calls[0][2]["spatial"].startswith("{")
    assert calls[0][2]["temporal_coverage_start"] == "2025-01-01"
    assert calls[0][2]["temporal_coverage_end"] == "2025-12-31"


def test_create_or_update_ckan_dataset_updates_owner_org_with_dedicated_action(monkeypatch):
    monkeypatch.setattr(
        ckan,
        "fetch_ckan_dataset",
        lambda *_args, **_kwargs: {"id": "dataset-id", "name": "demo", "owner_org": "old-org"},
    )
    calls = []

    def fake_action(base_url, action, payload, auth_header=None, files=None, timeout=120):
        calls.append((action, payload))
        return {"id": payload.get("id", "dataset-id"), "name": "demo"}

    monkeypatch.setattr(ckan, "_ckan_action_post", fake_action)

    ckan.create_or_update_ckan_dataset(
        "https://example.com",
        dataset_name="demo",
        dataset_title="Demo",
        dataset_notes="Notes",
        owner_org="new-org",
    )

    assert calls[0][0] == "package_owner_org_update"
    assert calls[0][1] == {"id": "dataset-id", "organization_id": "new-org"}
    assert calls[1][0] == "package_patch"
    assert "owner_org" not in calls[1][1]


def test_create_or_update_ckan_dataset_does_not_update_owner_org_when_same_org_name(monkeypatch):
    monkeypatch.setattr(
        ckan,
        "fetch_ckan_dataset",
        lambda *_args, **_kwargs: {
            "id": "dataset-id",
            "name": "demo",
            "owner_org": "83b478ad-8a76-401e-a9dc-99ea990eb922",
            "organization": {"id": "83b478ad-8a76-401e-a9dc-99ea990eb922", "name": "arctic-infrastructure", "title": "Arctic Infrastructure"},
        },
    )
    calls = []

    def fake_action(base_url, action, payload, auth_header=None, files=None, timeout=120):
        calls.append((action, payload))
        return {"id": payload.get("id", "dataset-id"), "name": "demo"}

    monkeypatch.setattr(ckan, "_ckan_action_post", fake_action)

    ckan.create_or_update_ckan_dataset(
        "https://example.com",
        dataset_name="demo",
        dataset_title="Demo",
        dataset_notes="Notes",
        owner_org="Arctic Infrastructure",
    )

    assert [action for action, _payload in calls] == ["package_patch"]


def test_upload_pdf_resources_to_ckan_uses_create_and_update(monkeypatch, tmp_path):
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"a")
    pdf_b.write_bytes(b"b")
    dataset = {
        "id": "dataset-id",
        "name": "dataset-name",
        "resources": [{"id": "resource-a", "name": "a.pdf"}],
    }
    resource_plan = [
        {"resource_name": "a.pdf", "resource_title": "A", "resource_description": "desc a", "resource_tags": ["a"]},
        {"resource_name": "b.pdf", "resource_title": "B", "resource_description": "desc b", "resource_tags": ["b"]},
    ]
    actions = []

    def fake_action(base_url, action, payload, auth_header=None, files=None, timeout=120):
        actions.append(action)
        assert files is not None and "upload" in files
        return {"id": payload.get("id", "new-resource"), "name": payload["name"]}

    monkeypatch.setattr(ckan, "_ckan_action_post", fake_action)

    uploaded = ckan.upload_pdf_resources_to_ckan(
        "https://example.com",
        dataset=dataset,
        pdf_paths=[pdf_a, pdf_b],
        resource_plan=resource_plan,
        auth_header="Bearer abc",
    )

    assert [item["name"] for item in uploaded] == ["a.pdf", "b.pdf"]
    assert actions == ["resource_update", "resource_create"]


def test_propose_ckan_dataset_metadata_with_llm(monkeypatch):
    class _FakeMessage:
        def __init__(self, content):
            self.content = content

    class _FakeChoice:
        def __init__(self, content):
            self.message = _FakeMessage(content)

    class _FakeResponse:
        def __init__(self, content):
            self.choices = [_FakeChoice(content)]

    class _FakeCompletions:
        def create(self, **_kwargs):
            return _FakeResponse(
                '{"dataset_name":"groundwater-policy-corpus","dataset_title":"Groundwater Policy Corpus","dataset_notes":"Compiled policy and planning documents."}'
            )

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(ckan, "OpenAI", _FakeOpenAI)
    result = ckan.propose_ckan_dataset_metadata_with_llm(
        resource_plan=[
            {
                "resource_name": "alpha.pdf",
                "resource_title": "Alpha report",
                "resource_description": "Alpha description",
                "resource_tags": ["groundwater", "policy"],
            }
        ],
        model="gpt-test",
        api_key="key",
        preferred_dataset_name="subsidence-groundwater-semantic-bridge-corpus",
        preferred_dataset_title="Subsidence and Groundwater Semantic Bridge Corpus",
        preserve_preferred_values=True,
    )

    assert result["dataset_name"] == "subsidence-groundwater-semantic-bridge-corpus"
    assert result["dataset_title"] == "Subsidence and Groundwater Semantic Bridge Corpus"
    assert result["dataset_notes"] == "Compiled policy and planning documents."


def test_propose_ckan_dataset_metadata_with_llm_uses_llm_when_preferred_missing(monkeypatch):
    class _FakeMessage:
        def __init__(self, content):
            self.content = content

    class _FakeChoice:
        def __init__(self, content):
            self.message = _FakeMessage(content)

    class _FakeResponse:
        def __init__(self, content):
            self.choices = [_FakeChoice(content)]

    class _FakeCompletions:
        def create(self, **_kwargs):
            return _FakeResponse(
                '{"dataset_name":"groundwater-policy-corpus","dataset_title":"Groundwater Policy Corpus","dataset_notes":"Compiled policy and planning documents."}'
            )

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(ckan, "OpenAI", _FakeOpenAI)
    result = ckan.propose_ckan_dataset_metadata_with_llm(
        resource_plan=[
            {
                "resource_name": "alpha.pdf",
                "resource_title": "Alpha report",
                "resource_description": "Alpha description",
                "resource_tags": ["groundwater", "policy"],
            }
        ],
        model="gpt-test",
        api_key="key",
    )

    assert result["dataset_name"] == "groundwater-policy-corpus"
    assert result["dataset_title"] == "Groundwater Policy Corpus"
    assert result["dataset_notes"] == "Compiled policy and planning documents."


def test_propose_ckan_dataset_metadata_with_llm_prefers_llm_by_default(monkeypatch):
    class _FakeMessage:
        def __init__(self, content):
            self.content = content

    class _FakeChoice:
        def __init__(self, content):
            self.message = _FakeMessage(content)

    class _FakeResponse:
        def __init__(self, content):
            self.choices = [_FakeChoice(content)]

    class _FakeCompletions:
        def create(self, **_kwargs):
            return _FakeResponse(
                '{"dataset_name":"context-specific-corpus","dataset_title":"Context Specific Corpus","dataset_notes":"Context notes."}'
            )

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(ckan, "OpenAI", _FakeOpenAI)
    result = ckan.propose_ckan_dataset_metadata_with_llm(
        resource_plan=[
            {
                "resource_name": "alpha.pdf",
                "resource_title": "Alpha report",
                "resource_description": "Alpha description",
                "resource_tags": ["groundwater", "policy"],
            }
        ],
        model="gpt-test",
        api_key="key",
        preferred_dataset_name="subsidence-groundwater-semantic-bridge-corpus",
        preferred_dataset_title="Subsidence and Groundwater Semantic Bridge Corpus",
    )

    assert result["dataset_name"] == "context-specific-corpus"
    assert result["dataset_title"] == "Context Specific Corpus"
    assert result["dataset_notes"] == "Context notes."


def test_propose_ckan_dataset_metadata_with_llm_does_not_prime_preferred_values_when_unlocked(monkeypatch):
    captured_messages = {}

    class _FakeMessage:
        def __init__(self, content):
            self.content = content

    class _FakeChoice:
        def __init__(self, content):
            self.message = _FakeMessage(content)

    class _FakeResponse:
        def __init__(self, content):
            self.choices = [_FakeChoice(content)]

    class _FakeCompletions:
        def create(self, **kwargs):
            captured_messages["messages"] = kwargs["messages"]
            return _FakeResponse(
                '{"dataset_name":"context-specific-corpus","dataset_title":"Context Specific Corpus","dataset_notes":"Context notes."}'
            )

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, **_kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(ckan, "OpenAI", _FakeOpenAI)
    ckan.propose_ckan_dataset_metadata_with_llm(
        resource_plan=[
            {
                "resource_name": "alpha.pdf",
                "resource_title": "Alpha report",
                "resource_description": "Alpha description",
                "resource_tags": ["groundwater", "policy"],
            }
        ],
        model="gpt-test",
        api_key="key",
        preferred_dataset_name="subsidence-groundwater-semantic-bridge-corpus",
        preferred_dataset_title="Subsidence and Groundwater Semantic Bridge Corpus",
        preserve_preferred_values=False,
    )

    payload = json.loads(captured_messages["messages"][1]["content"])
    assert payload["preferred_dataset_name"] == ""
    assert payload["preferred_dataset_title"] == ""
