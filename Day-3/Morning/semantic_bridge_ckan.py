"""Shared CKAN authentication helpers for the semantic bridge tutorial."""

from __future__ import annotations

from typing import Any

import requests


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
