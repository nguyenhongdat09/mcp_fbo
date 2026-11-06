"""Gán nguồn (file gốc hay entity) cho các hàm JS trong summary.

Đầu vào là vết entity thu được lúc flat XML: {tên entity: {source_file, line, raw}}.
Một hàm thuộc entity nào thì tên hàm đó được định nghĩa trong nội dung thô của entity đó.
Hàm không được định nghĩa trong entity nào được xem là của file gốc, kể cả hàm có tên
ghép từ entity khác (vd function insert$&Identity;Form), vì tên đã bung không xuất hiện
trong nội dung thô của bất kỳ entity nào.
"""

from __future__ import annotations

import os
import re
from typing import Any

ORIGINAL_FILE_LABEL = "Original File"


def _definition_regex(name: str) -> re.Pattern:
    """Regex nhận ra phần định nghĩa hàm: function X(, X = function, X: function."""
    n = re.escape(name)
    return re.compile(
        rf"(?:function\s+{n}\s*\(|(?<![\w$]){n}\s*[:=]\s*function\b)"
    )


_ENTITY_REF_RE = re.compile(r"(?:\]\]>)?&([\w.]+);(?:<!\[CDATA\[)?")
# Entity "mảnh tên" (vd Identity = PVTranImport, Tag = 71): ngắn, một dòng, không chứa mã hàm.
_FRAGMENT_MAX_LEN = 80


def _is_name_fragment(raw: str) -> bool:
    text = (raw or "").strip()
    return bool(text) and len(text) <= _FRAGMENT_MAX_LEN and "\n" not in text and "function" not in text


def _collapse_name_fragments(raw: str, entity_trace: dict[str, dict[str, Any]]) -> str:
    """Thay &Fragment; bằng giá trị của nó để các tên hàm ghép từ entity khớp được.

    Chỉ thay entity dạng mảnh tên. Entity chứa mã (vd entity lồng) giữ nguyên để hàm bên trong
    vẫn được gán cho entity con, không gán cho entity cha.
    """
    def _sub(match: re.Match) -> str:
        record = entity_trace.get(match.group(1))
        if record is not None and _is_name_fragment(record.get("raw") or ""):
            return (record.get("raw") or "").strip()
        return match.group(0)

    return _ENTITY_REF_RE.sub(_sub, raw or "")


def _short_path(path: str) -> str:
    """Đường dẫn rút gọn tính từ thư mục Controllers (nếu có), ngược lại lấy tên file."""
    if not path:
        return ""
    norm = path.replace("\\", "/")
    parts = norm.split("/")
    lowered = [p.lower() for p in parts]
    if "controllers" in lowered:
        idx = len(lowered) - 1 - lowered[::-1].index("controllers")
        rest = parts[idx + 1:]
        if rest:
            return "/".join(rest)
    return os.path.basename(norm)


def entity_label(name: str, record: dict[str, Any]) -> str:
    """Nhãn dạng '&Name; (Include/File.ent:126)'."""
    path = _short_path(record.get("source_file") or record.get("declared_in_file") or "")
    line = record.get("line") or 0
    where = f"{path}:{line}" if path and line else path
    return f"&{name}; ({where})" if where else f"&{name};"


def build_function_origins(
    functions: list[str],
    entity_trace: dict[str, dict[str, Any]] | None,
) -> dict[str, list[str]]:
    """Gom hàm theo nguồn: {'Original File': [...], '&Entity; (file:line)': [...]}.

    Hàm xuất hiện trong nhiều entity sẽ nằm ở mỗi entity đó. Thứ tự hàm giữ theo `functions`.
    """
    entity_trace = entity_trace or {}
    origins: dict[str, list[str]] = {}
    labels = {name: entity_label(name, rec) for name, rec in entity_trace.items()}
    searchable = {
        name: _collapse_name_fragments(rec.get("raw") or "", entity_trace)
        for name, rec in entity_trace.items()
    }

    for fn in functions:
        regex = _definition_regex(fn)
        owners = [name for name, text in searchable.items() if regex.search(text)]
        if not owners:
            origins.setdefault(ORIGINAL_FILE_LABEL, []).append(fn)
            continue
        for name in owners:
            origins.setdefault(labels[name], []).append(fn)

    # Original File luôn đứng đầu để dễ đọc.
    if ORIGINAL_FILE_LABEL in origins:
        ordered = {ORIGINAL_FILE_LABEL: origins.pop(ORIGINAL_FILE_LABEL)}
        ordered.update(origins)
        return ordered
    return origins
