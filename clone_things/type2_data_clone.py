"""Type 2 workflow: clone table data — sinh DELETE FROM + INSERT INTO từng dòng.

Agent truyền ``table`` + ``where`` (vd. dmmagd / ma_ct = 'DDV'), tool đọc dòng từ
DB của ``project_source`` rồi ghi script vào file .sql để user sửa/F5.
"""

from __future__ import annotations

import logging
import re
import time
from decimal import Decimal
from typing import Any

from .file_manager import resolve_output_file, append_script_block

logger = logging.getLogger("clone_things.type2")

# Identifier SQL Server thường + tên FBO có '$' (m41$000000) / '#' temp / '@' đặc biệt
_IDENT_RE = re.compile(r"^[A-Za-z_#@$][A-Za-z0-9_@$#]*$")
_LEADING_WHERE_RE = re.compile(r"^\s*WHERE\b", re.IGNORECASE)

UNICODE_TYPES = {"nvarchar", "nchar", "ntext", "xml"}
CHAR_TYPES = {"varchar", "char", "text"}
NUMERIC_TYPES = {
    "int", "bigint", "smallint", "tinyint",
    "decimal", "numeric", "money", "smallmoney",
    "float", "real",
}
DATETIME_TYPES = {"datetime", "datetime2", "smalldatetime", "date", "time", "datetimeoffset"}
BINARY_TYPES = {"binary", "varbinary", "image"}
# Không insert được bằng literal / không cho insert: bỏ khỏi column list
SKIP_TYPES = {"timestamp", "rowversion", "sql_variant", "hierarchyid", "geography", "geometry"}

DEFAULT_DATA_MAX_ROWS = 1000


def _parse_table_name(raw: str, default_schema: str = "dbo") -> tuple[str | None, str | None]:
    """Parse 'dmmagd' / 'dbo.dmmagd' / '[dbo].[dmmagd]' → (schema, name). None nếu invalid."""
    cleaned = str(raw or "").strip().rstrip(";").strip()
    parts = [p.strip().strip("'\"").strip("[]") for p in cleaned.split(".")]
    parts = [p for p in parts if p]
    if not parts or len(parts) > 2:
        return None, None
    if len(parts) == 2:
        t_schema, t_name = parts
    else:
        t_schema, t_name = default_schema, parts[0]
    if not _IDENT_RE.match(t_schema) or not _IDENT_RE.match(t_name):
        return None, None
    return t_schema, t_name


def _clean_where(raw: str) -> str:
    """Bỏ keyword WHERE đầu (nếu agent truyền kèm) + trailing ';'."""
    s = str(raw or "").strip().rstrip(";").strip()
    s = _LEADING_WHERE_RE.sub("", s, count=1).strip()
    return s


def _qident(name: str) -> str:
    return f"[{str(name).replace(']', ']]')}]"


def _fetch_columns(parsed_conn: dict[str, Any], t_schema: str, t_name: str) -> list[dict[str, Any]] | None:
    """Lấy metadata cột từ sys.columns. None = query lỗi."""
    import clone_things.service as svc

    safe_schema = str(t_schema).replace("'", "''")
    safe_name = str(t_name).replace("'", "''")
    sql = f"""
SELECT c.column_id, c.name, ty.name AS type_name, c.is_identity, c.is_computed
FROM sys.columns c
JOIN sys.types ty ON ty.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID(QUOTENAME(N'{safe_schema}') + N'.' + QUOTENAME(N'{safe_name}'))
ORDER BY c.column_id
"""
    res = svc.execute_query(parsed_conn, sql, max_rows=1000)
    if not res.get("success"):
        return None
    rows = res.get("result_sets", [{}])[0].get("rows", [])
    cols: list[dict[str, Any]] = []
    for r in rows:
        cols.append(
            {
                "name": str(r[1]),
                "type": str(r[2] or "").lower(),
                "is_identity": bool(r[3]),
                "is_computed": bool(r[4]),
            }
        )
    return cols


def _select_expr(col: dict[str, Any]) -> str:
    """Expression trong SELECT — convert kiểu đặc biệt sang literal-friendly text."""
    q = _qident(col["name"])
    t = col["type"]
    if t in BINARY_TYPES:
        return f"CONVERT(VARCHAR(MAX), {q}, 1) AS {q}"          # '0x...'
    if t in DATETIME_TYPES:
        return f"CONVERT(VARCHAR(35), {q}, 121) AS {q}"         # 'YYYY-MM-DD HH:MM:SS.fff'
    return q


def _reformat_sql_datetime(s: str) -> str:
    """'2023-02-02 09:02:00.000' → '20230202 09:02:00' (giữ fraction/offset nếu có)."""
    s = str(s)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](.*))?$", s)
    if not m:
        return s  # time-only 'HH:MM:SS.f' hoặc format lạ → giữ nguyên
    out = m.group(1) + m.group(2) + m.group(3)
    rest = m.group(4) or ""
    if rest:
        m2 = re.match(r"^(\d{2}:\d{2}:\d{2})(?:\.(\d+))?(\s*[+-]\d{2}:\d{2})?$", rest)
        if m2:
            frac = (m2.group(2) or "").rstrip("0")
            out += " " + m2.group(1) + (f".{frac}" if frac else "") + (m2.group(3) or "")
        else:
            out += " " + rest
    return out


def _fmt_literal(value: Any, type_name: str) -> str:
    """Format 1 cell thành SQL literal."""
    if value is None:
        return "NULL"
    t = (type_name or "").lower()
    if t == "bit":
        return "1" if value in (True, 1, "1", "True", "true") else "0"
    if t in NUMERIC_TYPES:
        if isinstance(value, bool):
            return "1" if value else "0"
        s = str(value)
        if t not in ("float", "real") and ("e" in s.lower()):
            s = format(Decimal(s), "f")
        return s
    if t in DATETIME_TYPES:
        return "'" + _reformat_sql_datetime(str(value)).replace("'", "''") + "'"
    if t in BINARY_TYPES:
        return str(value)  # đã là '0x...' từ CONVERT
    if t in CHAR_TYPES or t == "uniqueidentifier":
        return "'" + str(value).replace("'", "''") + "'"
    # nvarchar/nchar/ntext/xml + fallback an toàn cho kiểu lạ
    return "N'" + str(value).replace("'", "''") + "'"


def _build_data_script(
    t_schema: str,
    t_name: str,
    where_clean: str,
    insert_cols: list[dict[str, Any]],
    rows: list[list[Any]],
) -> str:
    qname = f"{_qident(t_schema)}.{_qident(t_name)}"
    col_list = ", ".join(_qident(c["name"]) for c in insert_cols)
    lines = [f"DELETE FROM {qname} WHERE {where_clean}"]

    has_identity = any(c["is_identity"] for c in insert_cols)
    if has_identity and rows:
        lines.append(f"SET IDENTITY_INSERT {qname} ON")
    for row in rows:
        vals = ", ".join(_fmt_literal(v, c["type"]) for v, c in zip(row, insert_cols))
        lines.append(f"INSERT INTO {qname}({col_list}) VALUES({vals})")
    if has_identity and rows:
        lines.append(f"SET IDENTITY_INSERT {qname} OFF")
    if not rows:
        lines.append("-- (0 rows matched)")
    return "\n".join(lines)


def _err(code: str, message: str, warnings: list[str], **extra: Any) -> dict[str, Any]:
    res: dict[str, Any] = {
        "success": False,
        "spec_version": "1.0",
        "type": 2,
        "mode": "data_clone",
        "error_code": code,
        "message": message,
        "path_to_pasted": None,
        "warnings": warnings,
    }
    res.update(extra)
    return res


def execute_type2_data_clone(
    table: str,
    where: str,
    project_source: str,
    path_to_pasted: str,
    schema: str,
    db_type: str,
    open_file: bool,
    open_editor_cmd: str,
    clone_cfg: dict[str, Any],
    config: dict[str, Any],
    warnings: list[str],
    start_time: float,
) -> dict[str, Any]:
    """Clone data: DELETE FROM <table> WHERE <where> + INSERT INTO từng dòng ra file .sql."""
    import clone_things.service as svc

    t_schema, t_name = _parse_table_name(table, schema)
    if not t_name:
        logger.warning("Invalid table name for data clone: %s", table)
        return _err("invalid_table", f"table name không hợp lệ: {table}", warnings)

    where_clean = _clean_where(where)
    if not where_clean:
        return _err(
            "missing_where",
            "where is required for data clone (bắt buộc để sinh DELETE FROM ... WHERE ...)",
            warnings,
        )

    output_file, file_err = resolve_output_file(
        path_to_pasted, t_name, config, project_source=project_source
    )
    if file_err:
        msg = "Chưa cấu hình clone_things.sql_temp_folder hoặc thư mục không tồn tại."
        if file_err == "invalid_path_to_pasted":
            msg = "path_to_pasted không hợp lệ (phải là file .sql và thư mục cha phải tồn tại)."
        return _err(file_err, msg, warnings)

    source_dbs = svc.load_project_db_connections(project_source, warnings)
    if not source_dbs:
        return _err(
            "invalid_project_source",
            "Cannot resolve app/sys connection from project_source",
            warnings,
            path_to_pasted=output_file,
        )

    source_app_db = (source_dbs.get("app") or {}).get("database") or ""
    source_sys_db = (source_dbs.get("sys") or {}).get("database") or ""
    lookup_order: tuple[str, ...] = (
        ("sys", "app") if str(db_type).lower() == "sys" else svc.DB_LOOKUP_ORDER
    )

    exists, s_type, s_desc, s_db = svc.find_object_on_side(
        source_dbs, t_name, t_schema, order=lookup_order
    )
    full_name = f"{t_schema}.{t_name}"
    if not exists:
        return _err(
            "table_not_found",
            f"Table {full_name} không tồn tại trên app/sys DB của project_source",
            warnings,
            path_to_pasted=output_file,
        )
    if not (s_type.upper() == "U" or "TABLE" in (s_desc or "").upper()):
        return _err(
            "not_a_table",
            f"{full_name} là {s_desc or s_type}, không phải table — clone data chỉ hỗ trợ table",
            warnings,
            path_to_pasted=output_file,
        )

    fetch_db = s_db or "app"
    conn = source_dbs.get(fetch_db)
    cols = _fetch_columns(conn, t_schema, t_name)
    if cols is None:
        return _err(
            "query_failed",
            f"Không đọc được metadata cột của {full_name}",
            warnings,
            path_to_pasted=output_file,
        )

    insert_cols = [
        c for c in cols
        if not c["is_computed"] and c["type"] not in SKIP_TYPES
    ]
    skipped_cols = [
        f"{c['name']}({c['type'] or 'computed'})"
        for c in cols
        if c["is_computed"] or c["type"] in SKIP_TYPES
    ]
    if skipped_cols:
        warnings.append(f"columns_skipped: {', '.join(skipped_cols)} (computed/timestamp/unsupported)")
    if not insert_cols:
        return _err(
            "no_insertable_columns",
            f"{full_name} không có cột nào insert được (toàn computed/timestamp)",
            warnings,
            path_to_pasted=output_file,
        )

    select_exprs = ", ".join(_select_expr(c) for c in insert_cols)
    select_sql = (
        f"SELECT {select_exprs} FROM {_qident(t_schema)}.{_qident(t_name)} WHERE {where_clean}"
    )
    max_rows = int(clone_cfg.get("data_max_rows", DEFAULT_DATA_MAX_ROWS))
    res = svc.execute_query(conn, select_sql, max_rows=max_rows)
    if not res.get("success"):
        return _err(
            "query_failed",
            f"SELECT data lỗi: {res.get('error', 'unknown')}",
            warnings,
            path_to_pasted=output_file,
        )

    rows = res.get("result_sets", [{}])[0].get("rows", [])
    truncated = bool(res.get("truncated"))
    if truncated:
        warnings.append(
            f"truncated_max_rows: chỉ lấy {len(rows)}/{max_rows} dòng đầu — "
            f"WHERE khớp nhiều hơn, thu hẹp where hoặc tăng clone_things.data_max_rows"
        )

    script = _build_data_script(t_schema, t_name, where_clean, insert_cols, rows)
    where_label = re.sub(r"\s+", " ", where_clean)[:200]
    obj_label = f"{full_name} | where: {where_label}"

    line_start, line_end = append_script_block(
        output_file,
        script,
        obj_label,
        "DATA",
        db=fetch_db,
        app_db_name=source_app_db,
        sys_db_name=source_sys_db,
        header_tag="data_clone",
    )

    open_attempted = bool(open_file) and open_editor_cmd.lower() != "none"
    open_ok = False
    if open_attempted and output_file:
        open_ok, open_warn = svc.open_file_for_user(output_file, open_editor_cmd, open_file)
        if open_warn:
            warnings.append(open_warn)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    agent_msg = (
        f"Đã clone data {full_name} ({len(rows)} dòng) vào {output_file} "
        f"(dòng {line_start}–{line_end}): DELETE FROM + INSERT INTO. "
        f"Sửa giá trị trong file (vd. đổi mã) rồi user tự F5."
    )
    if truncated:
        agent_msg += f" Lưu ý truncated: chỉ {len(rows)} dòng đầu."
    if not rows:
        agent_msg += " WHERE không khớp dòng nào — file chỉ có DELETE."

    return {
        "success": True,
        "spec_version": "1.0",
        "type": 2,
        "mode": "data_clone",
        "object": full_name,
        "table": full_name,
        "where": where_clean,
        "db": fetch_db,
        "row_count": len(rows),
        "truncated": truncated,
        "max_rows": max_rows,
        "columns": len(insert_cols),
        "skipped_columns": skipped_cols,
        "identity_insert": any(c["is_identity"] for c in insert_cols),
        "project_source": str(project_source),
        "path_to_pasted": output_file,
        "line_start": line_start,
        "line_end": line_end,
        "warnings": warnings,
        "agent_message": agent_msg,
        "meta": {
            "execute_clone": False,
            "db_lookup_order": list(lookup_order),
            "open_file_attempted": open_attempted,
            "open_file_ok": open_ok,
            "elapsed_ms": elapsed_ms,
        },
    }
