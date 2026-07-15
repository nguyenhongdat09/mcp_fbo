"""Resolve SQL from query type and parameters."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

TABLE_OBJECT_TYPE = "U"
HELPTEXT_OBJECT_TYPES = frozenset({"P", "V", "FN", "TR", "IF", "TF", "FS", "FT"})

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9_$]+$")
_MAX_SQL_FILE_BYTES = 1024 * 1024  # 1 MB


def _module_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "queryDatabase"
    return Path(__file__).resolve().parent


_CONFIG_DIR = _module_dir()
_CONFIG_PATH = _CONFIG_DIR / "queries_config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def sanitize_sql_identifier(name: str) -> str:
    """Validate table/object name — alphanumeric, underscore, dollar only."""
    cleaned = name.strip().strip("'\"[]")
    if not cleaned or not _IDENTIFIER_RE.match(cleaned):
        raise ValueError(
            f"Tên không hợp lệ: {name!r}. "
            "Chỉ cho phép chữ, số, _ và $ (vd: dmkh, d91$, ff_GetStartDateOfCycle)."
        )
    return cleaned


def normalize_query_type(query_type: int) -> int:
    """Chuẩn hóa type: 0=object, 1=SQL inline, 2=đọc file .sql."""
    qt = int(query_type)
    if qt not in (0, 1, 2):
        raise ValueError(
            f"type không hợp lệ: {query_type}. "
            "0=object (tự nhận bảng/proc/view/function), "
            "1=SQL tự do inline, 2=đọc file .sql."
        )
    return qt


def read_sql_file(sql_file_path: str) -> tuple[str, str]:
    """
    Đọc nội dung file .sql để execute.

    Returns:
        (sql_content, label) — label dạng sql_file:E:\\path\\file.sql
    """
    if not sql_file_path or not str(sql_file_path).strip():
        raise ValueError("query là bắt buộc (đường dẫn file .sql).")

    path = Path(sql_file_path.strip())
    if path.suffix.lower() != ".sql":
        raise ValueError(
            f"File phải có đuôi .sql: {sql_file_path!r}. "
            "Ví dụ: E:\\SQL Temp\\tmsg.sql"
        )
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file SQL: {path}")

    size = path.stat().st_size
    if size > _MAX_SQL_FILE_BYTES:
        raise ValueError(
            f"File SQL quá lớn ({size} bytes, tối đa {_MAX_SQL_FILE_BYTES})."
        )
    if size == 0:
        raise ValueError(f"File SQL rỗng: {path}")

    raw = path.read_bytes()
    content: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "cp1252"):
        try:
            content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise ValueError(f"Không đọc được encoding file SQL: {path}")

    sql = content.strip()
    if not sql:
        raise ValueError(f"File SQL không có nội dung hợp lệ: {path}")

    resolved = str(path.resolve())
    return sql, f"sql_file:{resolved}"


def build_object_lookup_sql(object_name: str) -> str:
    """SQL tra cứu loại object trong sys.objects."""
    name = sanitize_sql_identifier(object_name)
    return f"SELECT type, type_desc FROM sys.objects WHERE name = N'{name}'"


def parse_object_lookup_result(result: dict) -> tuple[str, str] | None:
    """
    Parse kết quả lookup sys.objects.

    Returns:
        (type, type_desc) hoặc None nếu không tìm thấy.
    """
    result_sets = result.get("result_sets") or []
    if not result_sets:
        return None

    rs = result_sets[0]
    columns = [c.lower() for c in rs.get("columns", [])]
    rows = rs.get("rows") or []
    if not rows:
        return None

    row = rows[0]
    type_idx = columns.index("type") if "type" in columns else None
    desc_idx = columns.index("type_desc") if "type_desc" in columns else None
    if type_idx is None:
        return None

    obj_type = str(row[type_idx] or "").strip()
    type_desc = str(row[desc_idx] or "").strip() if desc_idx is not None else ""
    return obj_type, type_desc


def is_user_table(obj_type: str, type_desc: str) -> bool:
    return obj_type == TABLE_OBJECT_TYPE or type_desc.upper() == "USER_TABLE"


def should_use_helptext(obj_type: str, type_desc: str) -> bool:
    if is_user_table(obj_type, type_desc):
        return False
    if obj_type in HELPTEXT_OBJECT_TYPES:
        return True
    upper_desc = type_desc.upper()
    return any(
        token in upper_desc
        for token in (
            "PROCEDURE",
            "VIEW",
            "FUNCTION",
            "TRIGGER",
        )
    )


def resolve_table_schema_sql(table_name: str) -> tuple[str, str]:
    config = _load_config()
    type_cfg = config["templates"]["table_schema"]
    table = sanitize_sql_identifier(table_name)
    sql_file = _CONFIG_DIR / type_cfg["sql_file"]
    if not sql_file.is_file():
        raise FileNotFoundError(f"Không tìm thấy SQL template: {sql_file}")
    template = sql_file.read_text(encoding="utf-8")
    placeholder = type_cfg.get("placeholder", "{{table_name}}")
    sql = template.replace(placeholder, table)
    return sql, f"table_schema:{table}"


def resolve_object_definition_sql(object_name: str) -> tuple[str, str]:
    config = _load_config()
    type_cfg = config["templates"]["object_definition"]
    name = sanitize_sql_identifier(object_name)
    template = type_cfg["sql_template"]
    sql = template.replace("{{object_name}}", name)
    return sql, f"object_definition:{name}"


def resolve_object_sql(object_name: str, obj_type: str, type_desc: str) -> tuple[str, str, str]:
    """
    Chọn SQL theo loại object đã tra cứu.

    Returns:
        (sql, label, resolved_as) — resolved_as: table_schema | object_definition
    """
    if is_user_table(obj_type, type_desc):
        sql, label = resolve_table_schema_sql(object_name)
        return sql, label, "table_schema"

    if should_use_helptext(obj_type, type_desc):
        sql, label = resolve_object_definition_sql(object_name)
        return sql, label, "object_definition"

    raise ValueError(
        f"Object {object_name!r} có type={obj_type!r}, type_desc={type_desc!r} "
        "— không hỗ trợ (chỉ USER_TABLE, P, V, FN, TR và các function/proc/view tương tự)."
    )


def resolve_query(query_type: int, query: str) -> tuple[str, str]:
    """
    Build executable SQL từ type và query.

    type=0: chỉ dùng cho bước lookup object (service sẽ gọi resolve_object_sql sau).
    type=1: câu SQL tự do inline.
    type=2: đọc SQL từ file .sql (query = path file).

    Returns:
        (sql, description)
    """
    qt = normalize_query_type(query_type)

    if not query or not query.strip():
        raise ValueError("query là bắt buộc (tên object, câu SQL, hoặc path file .sql).")

    if qt == 0:
        name = sanitize_sql_identifier(query)
        return build_object_lookup_sql(name), f"object_lookup:{name}"

    if qt == 2:
        return read_sql_file(query)

    return query.strip(), "free_query"
