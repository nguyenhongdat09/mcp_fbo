"""Name normalization, parsing, and filtering helpers for clone_things."""

from __future__ import annotations

import re
from typing import Any

DEFAULT_EXTRA_EXCLUDES = [
    r"^sp_",
    r"^xp_",
    r"^sys\.",
    r"^sp_executesql$",
]

# Tên extract nhầm từ SQL / catalog SQL Server — không phải object FBO cần clone
SYSTEM_NOISE_NAMES = frozenset(
    {
        "tempdb",
        "master",
        "msdb",
        "model",
        "systypes",
        "sysobjects",
        "syscolumns",
        "sysusers",
        "sysindexes",
        "syscomments",
        "sysdepends",
        "sysconstraints",
        "information_schema",
    }
)


def is_system_noise_name(clean_name: str) -> bool:
    name = (clean_name or "").strip().lower()
    if not name:
        return False
    if name in SYSTEM_NOISE_NAMES:
        return True
    for pat in DEFAULT_EXTRA_EXCLUDES:
        if re.search(pat, name, re.IGNORECASE):
            return True
    return False


def normalize_fbo_db_table(raw: str) -> str:
    """d91$@@prime$partition$current -> d91$; c91$$$partition$current -> c91$"""
    s = (raw or "").strip()
    if not s:
        return s
    cleaned = re.sub(r"(\$)?(?:\$\$|@@).+$", r"\1", s).strip()
    return cleaned or s


def to_partition_structure_name(clean_name: str) -> str:
    """
    Map FBO partition names to the structure table (*$000000).

    - m41$        → m41$000000   (template từ XML/summary)
    - m41$202601  → m41$000000   (bảng kỳ — clone theo cấu trúc, không clone từng kỳ)
    - m41$000000  → m41$000000
    - dmkh        → dmkh         (không đụng)
    """
    name = (clean_name or "").strip()
    if not name or "$" not in name:
        return name

    # Đã là bảng cấu trúc
    if re.search(r"\$000000$", name, re.IGNORECASE):
        return name

    # m41$202601 / r00$000001 → giữ prefix tới $ rồi gắn 000000
    m = re.match(r"^(.+\$)\d+$", name)
    if m:
        return f"{m.group(1)}000000"

    # m41$ / r00$ (kết thúc bằng $) → nối 000000
    if name.endswith("$"):
        return f"{name}000000"

    return name


def normalize_object_name(name: str, default_schema: str = "dbo") -> tuple[str, str, str]:
    """
    Split name into (schema, clean_name, visited_key).
    visited_key is always '<schema_lower>.<clean_name_lower>'.
    Partition templates được map sang *$000000 trước khi tạo visited_key.
    """
    cleaned = str(name).strip().strip("'\"[]")
    if "." in cleaned:
        parts = cleaned.split(".", 1)
        schema = parts[0].strip().strip("'\"[]") or default_schema
        clean_name = parts[1].strip().strip("'\"[]")
    else:
        schema = default_schema
        clean_name = cleaned

    clean_name = to_partition_structure_name(clean_name)
    visited_key = f"{schema.lower()}.{clean_name.lower()}"
    return schema, clean_name, visited_key


def is_excluded(name: str, exclude_patterns: list[str]) -> bool:
    """Check if object name matches any exclude regex."""
    clean = name.split(".")[-1].strip()
    for pat in exclude_patterns:
        if re.search(pat, clean, re.IGNORECASE) or re.search(pat, name, re.IGNORECASE):
            return True
    return False


def parse_object_list(raw_object: str, default_schema: str = "dbo") -> list[str]:
    """Parse comma/semicolon/newline separated SQL object names, deduping preserving order."""
    parts = re.split(r"[,;\n]+", str(raw_object or ""))
    res: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = part.strip().strip("'\"")
        if not cleaned:
            continue
        item_schema, item_clean_name, visited_key = normalize_object_name(cleaned, default_schema)
        formatted_name = f"{item_schema}.{item_clean_name}"
        if visited_key not in seen:
            seen.add(visited_key)
            res.append(formatted_name)
    return res


MODE_GET_TOKEN_MAP: dict[str, list[str]] = {
    "proc": ["proc"],
    "procedure": ["proc"],
    "procedures": ["proc"],
    "p": ["proc"],
    "func": ["func"],
    "function": ["func"],
    "functions": ["func"],
    "fn": ["func"],
    "view": ["view"],
    "views": ["view"],
    "v": ["view"],
    "table": ["table"],
    "tables": ["table"],
    "tbl": ["table"],
    "u": ["table"],
    "full": ["proc", "func", "view", "table"],
    "all": ["proc", "func", "view", "table"],
    "*": ["proc", "func", "view", "table"],
}


def parse_mode_get(raw_mode: str | None) -> tuple[list[str], list[str]]:
    """
    Parse mode_get string into normalized list of kinds and warnings for unknown tokens.
    Returns (kinds, warnings).
    """
    raw = (raw_mode or "").strip()
    if not raw:
        return ["proc"], []

    tokens = re.split(r"[,;]+", raw)
    kinds: list[str] = []
    warnings: list[str] = []

    for tok in tokens:
        t = tok.strip().lower()
        if not t:
            continue
        mapped = MODE_GET_TOKEN_MAP.get(t)
        if mapped:
            for k in mapped:
                if k not in kinds:
                    kinds.append(k)
        else:
            warnings.append(f"unknown_mode_get_token: {tok.strip()}")

    return kinds, warnings


def parse_mode_recursion(raw_rec: str | int | None) -> tuple[int | None, str | None]:
    """
    Parse mode_recursion value (0/1).
    Returns (recursion_int, error_message).
    """
    if raw_rec is None:
        return 0, None
    s = str(raw_rec).strip().lower()
    if s in ("0", ""):
        return 0, None
    if s == "1":
        return 1, None
    return None, f"invalid_mode_recursion: expected '0' or '1', got '{raw_rec}'"


def parse_mode_read(raw_mode_read: Any) -> tuple[int | None, str | None]:
    """
    Normalize and validate mode_read parameter for type=1:
    - 0: paste into file (legacy behavior)
    - 1: summary / analyze (default, no file created)
    - 3: full SQL body in JSON (mode_recursion=0, seed count <= max_full_objects)
    """
    if raw_mode_read is None:
        return 1, None
    if isinstance(raw_mode_read, int) and not isinstance(raw_mode_read, bool):
        if raw_mode_read in (0, 1, 3):
            return raw_mode_read, None
        return None, f"invalid_mode_read: expected 0, 1, or 3, got {raw_mode_read}"
    s = str(raw_mode_read).strip()
    if s == "0":
        return 0, None
    if s == "1":
        return 1, None
    if s == "3":
        return 3, None
    return None, f"invalid_mode_read: expected 0, 1, or 3, got '{raw_mode_read}'"
