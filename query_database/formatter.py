"""Format query results for MCP agent response."""

from __future__ import annotations

import json
from typing import Any


def format_query_result(result: dict[str, Any]) -> str:
    if result.get("mode") == "search":
        return json.dumps(result, ensure_ascii=False, indent=2)

    if result.get("check_mode") == "parseonly":
        return _format_parseonly_result(result)

    if result.get("resolved_as") == "object_summary" or "spec_version" in result or (
        not result.get("success") and result.get("error") in ("snippet_params_required", "object_not_found")
    ):
        from .bridges.summary_format import format_summary_result

        return format_summary_result(result)

    if not result.get("success"):
        lines = [f"[ERROR] {result.get('error', 'Unknown error')}"]
        if result.get("failed_batch_index"):
            lines.append(
                f"Failed batch: {result['failed_batch_index']}/{result.get('batch_count', '?')}"
            )
            if result.get("failed_batch_preview"):
                lines.append(f"Batch preview: {result['failed_batch_preview']}")
        if result.get("file_path"):
            lines.append(f"File: {result['file_path']}")
        if result.get("sql_file_path"):
            lines.append(f"SQL file: {result['sql_file_path']}")
        if result.get("query_type") is not None:
            lines.append(f"Query type: {result['query_type']}")
        if result.get("project_root"):
            lines.append(f"Project root: {result['project_root']}")
        if result.get("server"):
            lines.append(f"Server: {result['server']}")
        if result.get("database"):
            lines.append(f"Database: {result['database']}")
        for w in result.get("warnings") or []:
            lines.append(f"[WARNING] {w}")
        return "\n".join(lines)

    query_type = result.get("query_type", 1)
    script_text = _extract_script_text(result)
    if script_text is not None:
        lines = [
            "[OK] Query executed",
            f"File: {result.get('file_path', '')}",
            f"Database: {result.get('database', '')} @ {result.get('server', '')}",
            f"DB type: {result.get('db_type', 'app')}",
            f"Query type: {query_type} ({result.get('query_label', '')})",
        ]
        if result.get("object_name"):
            lines.append(
                f"Object: {result['object_name']} "
                f"({result.get('object_type_desc') or result.get('object_type', '')})"
            )
        if result.get("resolved_as"):
            lines.append(f"Resolved as: {result['resolved_as']}")
        if result.get("project_root"):
            lines.append(f"Project root: {result['project_root']}")
        for w in result.get("warnings") or []:
            lines.append(f"[WARNING] {w}")
        lines.extend(
            [
                f"Execution time: {result.get('execution_time_ms', 0)} ms",
                "",
                "```sql",
                script_text.rstrip(),
                "```",
            ]
        )
        return "\n".join(lines)

    lines = [
        "[OK] Query executed",
        f"File: {result.get('file_path', '')}",
        f"Database: {result.get('database', '')} @ {result.get('server', '')}",
        f"DB type: {result.get('db_type', 'app')}",
        f"Query type: {query_type} ({result.get('query_label', '')})",
        f"Execution time: {result.get('execution_time_ms', 0)} ms",
        f"Total rows: {result.get('row_count', 0)}",
    ]
    if result.get("project_root"):
        lines.append(f"Project root: {result['project_root']}")
    if result.get("resolved_via"):
        lines.append(f"Resolved via: {result['resolved_via']}")
    for w in result.get("warnings") or []:
        lines.append(f"[WARNING] {w}")
    if result.get("batch_count"):
        lines.append(
            f"Batches: {result.get('batches_ok', 0)}/{result['batch_count']} OK"
        )

    if result.get("sql_file_path"):
        lines.insert(2, f"SQL file: {result['sql_file_path']}")

    if result.get("truncated"):
        lines.append(f"[WARNING] Kết quả bị cắt ở {result.get('max_rows', 0)} dòng")

    sql_messages = result.get("messages") or []
    if sql_messages:
        lines.append("")
        lines.append("--- SQL messages ---")
        for msg in sql_messages:
            lines.append(msg)

    for idx, rs in enumerate(result.get("result_sets", []), start=1):
        columns = rs.get("columns", [])
        rows = rs.get("rows", [])
        lines.append("")
        lines.append(f"--- Result set {idx} ({len(rows)} rows) ---")

        if not columns:
            lines.append("(no columns)")
            continue

        lines.append(" | ".join(columns))
        lines.append("-|-".join("-" * min(len(c), 20) for c in columns))

        # Không cắt cell trên cột definition (text/val/definition/...) hoặc
        # kết quả 1 cột ít dòng — agent cần full body (OBJECT_DEFINITION...).
        single_col = len(columns) <= 1
        few_rows = len(rows) <= 20
        def_col_idx = {
            i
            for i, c in enumerate(columns)
            if str(c).strip().lower() in _FULL_TEXT_COL_HINTS
        }
        for row in rows[:200]:
            cells = [
                _cell_text(
                    v,
                    allow_full=(single_col and few_rows) or i in def_col_idx,
                )
                for i, v in enumerate(row)
            ]
            lines.append(" | ".join(cells))

        if len(rows) > 200:
            lines.append(f"... ({len(rows) - 200} rows omitted in preview)")

    return "\n".join(lines)


def _format_parseonly_result(result: dict[str, Any]) -> str:
    """Render kết quả query_type=3 (SET PARSEONLY) — KHÔNG qua nhánh
    success/error generic (mất errors[] → 'Unknown error')."""
    errors = result.get("errors") or []
    lines = []
    if result.get("success"):
        lines.append("[OK] Parse-only check PASSED — không có statement nào được execute")
    else:
        lines.append(f"[FAIL] Parse-only check — {len(errors)} batch có lỗi syntax")
    if not result.get("success") and result.get("error"):
        lines.append(f"Error: {result['error']}")
    if result.get("sql_file_path"):
        lines.append(f"SQL file: {result['sql_file_path']}")
    lines.append(
        f"Database: {result.get('database', '')} @ {result.get('server', '')}"
    )
    if result.get("project_root"):
        lines.append(f"Project root: {result['project_root']}")
    lines.append(
        f"Batches: {result.get('batches_ok', 0)}/{result.get('batch_count', 0)} parse OK"
    )
    for err in errors:
        lines.append("")
        lines.append(
            f"--- Batch {err.get('batch_index', '?')} — bắt đầu dòng file "
            f"{err.get('line_start', '?')} ---"
        )
        lines.append(str(err.get("message", "")))
        if err.get("batch_preview"):
            lines.append(f"Preview: {err['batch_preview']}")
    if result.get("scope_note"):
        lines.append("")
        lines.append(f"Note: {result['scope_note']}")
    for w in result.get("warnings") or []:
        lines.append(f"[WARNING] {w}")
    return "\n".join(lines)


# Tên cột gợi ý nội dung code/definition — không truncate trong preview.
_FULL_TEXT_COL_HINTS = frozenset(
    {"text", "val", "definition", "c", "ddl", "script", "sql", "query"}
)


def _cell_text(value: Any, allow_full: bool = False) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    if allow_full or len(text) <= 80:
        return text
    return text[:77] + f"… [+{len(text) - 77} chars]"


def _extract_script_text(result: dict[str, Any]) -> str | None:
    """Gộp kết quả schema bảng (cột val) hoặc sp_helptext thành script text."""
    resolved_as = result.get("resolved_as")
    if resolved_as not in ("table_schema", "object_definition"):
        return None

    result_sets = result.get("result_sets") or []
    if not result_sets:
        return None

    rs = result_sets[0]
    columns = [c.lower() for c in rs.get("columns", [])]
    rows = rs.get("rows", [])

    if resolved_as == "table_schema" and "val" in columns:
        col_idx = columns.index("val")
        parts = []
        for row in rows:
            if col_idx < len(row) and row[col_idx] is not None:
                parts.append(str(row[col_idx]))
        return "".join(parts) if parts else None

    if resolved_as == "object_definition":
        for name in ("text", "val"):
            if name in columns:
                col_idx = columns.index(name)
                parts = []
                for row in rows:
                    if col_idx < len(row) and row[col_idx] is not None:
                        parts.append(str(row[col_idx]))
                return "".join(parts) if parts else None

    return None
