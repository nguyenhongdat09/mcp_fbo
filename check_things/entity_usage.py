"""BFS entity đang dùng (transitive) — port get_transitively_used_entities
từ entityResolverChecking.js."""

from __future__ import annotations

import os
import re
from typing import Any

BUILTIN_GENERAL_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
_ENTITY_REF_RE = re.compile(r"&([A-Za-z_][\w.-]*);")
_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_DOCTYPE_RE = re.compile(r"<!DOCTYPE\s+[\s\S]*?\[([\s\S]*?)\]\s*>", re.IGNORECASE)


def _scan_refs(content: str, used: set[str], to_process: list[str]) -> None:
    for m in _ENTITY_REF_RE.finditer(content):
        name = m.group(1)
        if name not in BUILTIN_GENERAL_ENTITIES and name not in used:
            used.add(name)
            to_process.append(name)


def get_transitively_used_entities(
    main_file_path: str, general_entities: dict[str, Any] | None
) -> set[str]:
    """Tập tên entity được file chính dùng — kể cả refs nằm trong nội dung
    entity (SYSTEM file hoặc inline value), BFS. Entity refs trong block
    DOCTYPE/comment KHÔNG tính là usage."""
    from find_entity_by_xml.entity_resolver import read_file_content

    used: set[str] = set()
    to_process: list[str] = []

    content = read_file_content(main_file_path) or ""
    if content:
        m = _DOCTYPE_RE.search(content)
        if m:
            content = content[m.end() :]
        content = _COMMENT_RE.sub("", content)
        _scan_refs(content, used, to_process)

    processed: set[str] = set()
    while to_process:
        current = to_process.pop(0)
        if current in processed:
            continue
        processed.add(current)

        ent = (general_entities or {}).get(current)
        if not ent:
            continue

        sub_content = ""
        if ent.get("systemUrl") and ent.get("sourceFile"):
            src = ent["sourceFile"]
            try:
                if os.path.exists(src):
                    sub_content = read_file_content(src) or ""
            except Exception:
                sub_content = ""
        elif ent.get("value"):
            sub_content = ent["value"]

        if sub_content:
            sub_content = _COMMENT_RE.sub("", sub_content)
            _scan_refs(sub_content, used, to_process)

    return used
