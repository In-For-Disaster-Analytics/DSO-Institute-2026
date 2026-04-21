from __future__ import annotations

from semantic_bridge.io import ckan


class DummyResponse:
    def __init__(self, payload=None, content: bytes = b"file-bytes"):
        self._payload = payload or {}
        self.content = content

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

