"""Regex extraction when parsing controller scripts and SQL fragments."""

from __future__ import annotations

import re

JS_FUNCTION_RE = re.compile(r"\bfunction\s+([a-zA-Z0-9_$]+)\s*\(", re.IGNORECASE)
JS_DIR_REQUEST_RE = re.compile(r"\brequest\s*\(\s*['\"]([A-Za-z_][\w$]*)['\"]", re.IGNORECASE)
JS_GRID_REQUEST_RE = re.compile(r"\brequest\s*\(\s*[^,'\"]+,\s*['\"]([A-Za-z_][\w$]*)['\"]", re.IGNORECASE)

JS_GRID_REQUEST_CALL_RE = re.compile(r"\bgrid\.request\b", re.IGNORECASE)
JS_G_REQUEST_CALL_RE = re.compile(r"\bg\.request\b", re.IGNORECASE)
JS_PARENT_REQUEST_RE = re.compile(r"\bparentform\.request\b", re.IGNORECASE)
JS_F_REQUEST_RE = re.compile(r"\bf\.request\b", re.IGNORECASE)
JS_SHOW_FORM_RE = re.compile(r"\bg\.showForm\b", re.IGNORECASE)
JS_EXEC_EXPR_RE = re.compile(r"\bexecuteExpression\b", re.IGNORECASE)
JS_MESSAGE_SHOW_RE = re.compile(r"\$message\.show\b", re.IGNORECASE)

SQL_TABLE_RE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO)\s+([a-zA-Z0-9_#$@\[\].]+)",
    re.IGNORECASE,
)
SQL_EXEC_RE = re.compile(r"\b(?:EXEC|EXECUTE)\s+([a-zA-Z0-9_#$@\[\].]+)", re.IGNORECASE)

_DB_PREFIX_RE = re.compile(r"^@@(?:sys|app)DatabaseName\.+", re.IGNORECASE)

_NOISE_TOKENS = {
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "select", "where", "from", "join", "insert", "update", "delete", "set", "values",
    "table", "exec", "execute", "begin", "end", "with", "as", "into", "on", "null",
}

COLUMN_DENYLIST = {
    "stt_rec", "stt_rec0", "stt_rec1", "line_nbr", "status",
    "datetime0", "datetime2", "user_id0", "user_id2", "ma_dvcs",
    "so_ct", "ngay_ct", "ma_kh", "tk", "ma_nt", "ty_gia", "dien_giai",
    "ma_vt", "so_luong", "gia", "tien", "thue", "ma_thue", "status2",
}

SQL_TYPE_NOISE = {
    "nvarchar", "varchar", "nchar", "char", "int", "bigint", "smallint",
    "tinyint", "bit", "decimal", "numeric", "money", "smallmoney",
    "float", "real", "datetime", "smalldatetime", "date", "time",
    "uniqueidentifier", "xml", "text", "ntext", "image", "sysname",
}


def clean_table_name(raw_name: str) -> str:
    """Clean table or proc name by stripping brackets, schema prefix, and FBO db variable prefixes."""
    if not raw_name:
        return ""
    name = raw_name.strip("[]\"'").strip()
    if _DB_PREFIX_RE.match(name):
        name = _DB_PREFIX_RE.sub("", name).strip("[]\"'").strip()
    if name.lower().startswith("dbo."):
        name = name[4:].strip("[]\"'").strip()
    return name


def is_plausible_table_name(raw_name: str) -> bool:
    """Validate if an extracted name is a plausible table/view identifier."""
    if not raw_name:
        return False
    name = clean_table_name(raw_name)
    low = name.lower()
    if not name or low in _NOISE_TOKENS or low in COLUMN_DENYLIST or low in SQL_TYPE_NOISE:
        return False
    if low.startswith("#") or low.startswith("@"):
        return False
    if low.startswith("information_schema") or low.startswith("sys.") or low == "sys":
        return False
    return True


def is_plausible_proc_name(raw_name: str) -> bool:
    """Validate if an extracted name is a plausible stored procedure identifier."""
    if not raw_name:
        return False
    name = clean_table_name(raw_name)
    low = name.lower()
    if not name or low in _NOISE_TOKENS or low in COLUMN_DENYLIST or low in SQL_TYPE_NOISE:
        return False
    if low.startswith("#") or low.startswith("@"):
        return False
    if low == "sp_executesql":
        return True
    if low.startswith("information_schema") or low.startswith("sys.") or low == "sys":
        return False
    return True


def fallback_extract_js(source: str) -> tuple[set[str], set[str], set[str]]:
    """Extract functions, whitelist calls, and request_actions from JS source using regex."""
    funcs = set(JS_FUNCTION_RE.findall(source))
    actions = set(JS_DIR_REQUEST_RE.findall(source)).union(set(JS_GRID_REQUEST_RE.findall(source)))
    calls = set()

    if JS_GRID_REQUEST_CALL_RE.search(source):
        calls.add("o.grid.request")
    elif JS_G_REQUEST_CALL_RE.search(source):
        calls.add("g.request")
    elif JS_PARENT_REQUEST_RE.search(source):
        calls.add("o.parentForm.request")
    elif JS_F_REQUEST_RE.search(source) or JS_DIR_REQUEST_RE.search(source):
        calls.add("f.request")

    if JS_SHOW_FORM_RE.search(source):
        calls.add("g.showForm")

    if JS_EXEC_EXPR_RE.search(source):
        calls.add("f.executeExpression")

    if JS_MESSAGE_SHOW_RE.search(source):
        calls.add("$message.show")

    return funcs, calls, actions


def fallback_extract_sql(source: str) -> tuple[list[str], list[str], set[str]]:
    """Extract tables, procs, and signals from SQL source using fast regex."""
    tables_dict: dict[str, str] = {}
    procs_dict: dict[str, str] = {}
    signals: set[str] = set()

    for match in SQL_TABLE_RE.finditer(source):
        raw = match.group(1)
        if is_plausible_table_name(raw):
            clean = clean_table_name(raw)
            if clean.lower() not in tables_dict:
                tables_dict[clean.lower()] = clean

    for match in SQL_EXEC_RE.finditer(source):
        raw = match.group(1)
        if is_plausible_proc_name(raw):
            clean = clean_table_name(raw)
            if clean.lower() not in procs_dict:
                procs_dict[clean.lower()] = clean

    low_src = source.lower()
    if "$partition$" in low_src or "@@prime$partition" in low_src or "$$" in low_src:
        signals.add("partition")
    if "sp_executesql" in low_src or "exec(" in low_src:
        signals.add("dynamic_sql")
    if "cursor" in low_src:
        signals.add("cursor")

    return list(tables_dict.values()), list(procs_dict.values()), signals
