"""Lấy Map<entityName, content> đã resolve cho file XML.

Port tương đương getEntityContentsForDoc trong CheckLegacyEntity.js —
tái dùng find_entity_by_xml.entity_resolver (đã port sẵn FboEntParser).
"""

from __future__ import annotations

from typing import Dict

from find_entity_by_xml.entity_resolver import get_entities_for_file, read_file_content


def get_entity_contents(file_path: str) -> Dict[str, str]:
    """Dict<entityName, content>: SYSTEM entity -> đọc file nguồn, inline -> value.

    Entity SYSTEM trỏ file thiếu/đọc lỗi -> content '' (giống JS try/catch).
    """
    contents: Dict[str, str] = {}
    try:
        general_entities, _param, _mtimes = get_entities_for_file(file_path)
    except Exception:
        return contents

    for name, decl in (general_entities or {}).items():
        d = decl or {}
        if d.get("systemUrl"):
            try:
                contents[name] = read_file_content(str(d.get("sourceFile") or "")) or ""
            except Exception:
                contents[name] = ""
        else:
            contents[name] = d.get("value") or ""
    return contents
