"""CKAN authentication and resource synchronization helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from semantic_bridge.io.documents import SUPPORTED_DOCUMENT_SUFFIXES, ensure_data_directory


DEFAULT_TAPIS_URL = "https://portals.tapis.io/v3/oauth2/tokens"


def get_tapis_token(username: str, password: str, *, tapis_url: str = DEFAULT_TAPIS_URL) -> str:
    response = requests.post(
        tapis_url,
        data={
            "username": username,
            "password": password,
            "grant_type": "password",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["result"]["access_token"]["access_token"]


def build_ckan_auth_header(
    *,
    auth_mode: str,
    api_token: str | None = None,
    username: str | None = None,
    password: str | None = None,
    tapis_url: str = DEFAULT_TAPIS_URL,
) -> str | None:
    normalized_mode = (auth_mode or "api_token").strip().lower()
    if normalized_mode == "api_token":
        token = (api_token or "").strip()
        return token or None
    if normalized_mode == "tapis_password":
        user = (username or "").strip()
        secret = password or ""
        if not user or not secret:
            raise ValueError("TACC username and password are required for CKAN tapis_password authentication.")
        return f"Bearer {get_tapis_token(user, secret, tapis_url=tapis_url)}"
    raise ValueError(f"Unsupported CKAN auth mode: {auth_mode}")


def auth_headers(auth_header: str | None = None) -> dict[str, str]:
    if not auth_header:
        return {}
    return {"Authorization": auth_header}


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
    if resource_url.startswith(("http://", "https://")):
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

