"""Shared helpers for the basic SDK flow tutorial."""

from __future__ import annotations

from typing import Any, Optional


def safe_items(page: Any) -> list[Any]:
    """Return pagination items when present, otherwise an empty list."""
    items = getattr(page, "items", None)
    return items if isinstance(items, list) else []


def safe_total(page: Any) -> int:
    """Return pagination total when present, fallback to current page length."""
    total = getattr(page, "total", None)
    if isinstance(total, int):
        return total
    return len(safe_items(page))


def pick_id(requested_id: Optional[int], items: list[Any]) -> Optional[int]:
    """Choose an explicit ID when provided, else use the first item's id."""
    if requested_id is not None:
        return requested_id
    if not items:
        return None
    return getattr(items[0], "id", None)
