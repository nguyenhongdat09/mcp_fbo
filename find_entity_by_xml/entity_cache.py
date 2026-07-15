"""Helpers cho entity lookup."""

from __future__ import annotations


def normalize_entity_name(name: str) -> str:
    """Bỏ & đầu và ; cuối — giống EntityHoverProvider."""
    s = (name or "").strip()
    if s.startswith("&"):
        s = s[1:]
    if s.endswith(";"):
        s = s[:-1]
    return s


def find_entity(entities: list[dict[str, str]], entity_name: str) -> dict[str, str] | None:
    """Tìm entity theo Name trong list dict — dùng cho unit test."""
    target = normalize_entity_name(entity_name)
    if not target:
        return None
    for item in entities:
        if item.get("Name") == target:
            return item
    return None


def list_entity_names(entities: list[dict[str, str]]) -> list[str]:
    """Danh sách tên entity duy nhất, giữ thứ tự xuất hiện đầu tiên."""
    seen: set[str] = set()
    names: list[str] = []
    for item in entities:
        name = item.get("Name", "")
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
