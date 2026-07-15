"""API chính: file path + query → kết quả SQL."""

from __future__ import annotations

from .connection import get_connection_config
from .executor import DEFAULT_MAX_ROWS, execute_query
from .query_resolver import (
    normalize_query_type,
    parse_object_lookup_result,
    resolve_object_sql,
    resolve_query,
    sanitize_sql_identifier,
)


def query_database(
    file_path: str,
    query: str,
    db_type: str = "app",
    max_rows: int = DEFAULT_MAX_ROWS,
    query_type: int = 1,
) -> dict:
    """
    Resolve connection từ file path, chạy query, trả kết quả cho agent.

    Args:
        file_path: Path file trong project FBO (XML, SQL, ...)
        query: Tên object (type=0), câu SQL inline (type=1), hoặc path file .sql (type=2)
        db_type: app hoặc sys (default: app)
        max_rows: Giới hạn số dòng trả về (default: 20000)
        query_type: 0=object, 1=SQL inline (default), 2=đọc file .sql
    """
    if not file_path or not str(file_path).strip():
        return {"success": False, "error": "file_path is required"}
    if not query or not str(query).strip():
        return {"success": False, "error": "query is required"}

    try:
        qt = normalize_query_type(query_type)
    except ValueError as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    conn_result = get_connection_config(file_path, db_type)
    if not conn_result.get("success"):
        return conn_result

    parsed = conn_result["parsed"]

    if qt == 0:
        return _query_object(
            file_path=file_path,
            query=query,
            parsed=parsed,
            conn_result=conn_result,
            db_type=db_type,
            max_rows=max_rows,
            query_type=qt,
        )

    try:
        sql, label = resolve_query(qt, query)
    except (ValueError, FileNotFoundError) as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    extra: dict = {}
    if qt == 2:
        extra["sql_file_path"] = str(query).strip()

    query_result = execute_query(parsed, sql, max_rows=max_rows)
    return _attach_metadata(
        query_result,
        file_path=file_path,
        conn_result=conn_result,
        db_type=db_type,
        query_type=qt,
        query_label=label,
        original_query=query,
        **extra,
    )


def _query_object(
    *,
    file_path: str,
    query: str,
    parsed: dict,
    conn_result: dict,
    db_type: str,
    max_rows: int,
    query_type: int,
) -> dict:
    try:
        object_name = sanitize_sql_identifier(query)
        lookup_sql, lookup_label = resolve_query(0, query)
    except (ValueError, FileNotFoundError) as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    lookup_result = execute_query(parsed, lookup_sql, max_rows=10)
    if not lookup_result.get("success"):
        lookup_result["file_path"] = file_path
        lookup_result["query_type"] = query_type
        lookup_result["query_label"] = lookup_label
        lookup_result["original_query"] = query
        return lookup_result

    parsed_object = parse_object_lookup_result(lookup_result)
    if not parsed_object:
        return {
            "success": False,
            "error": f"Không tìm thấy object trong sys.objects: {object_name}",
            "file_path": file_path,
            "project_root": conn_result.get("project_root"),
            "web_config_path": conn_result.get("web_config_path"),
            "db_type": db_type,
            "query_type": query_type,
            "original_query": query,
        }

    obj_type, type_desc = parsed_object
    try:
        sql, label, resolved_as = resolve_object_sql(object_name, obj_type, type_desc)
    except (ValueError, FileNotFoundError) as exc:
        return {
            "success": False,
            "error": str(exc),
            "file_path": file_path,
            "object_name": object_name,
            "object_type": obj_type,
            "object_type_desc": type_desc,
            "query_type": query_type,
            "original_query": query,
        }

    query_result = execute_query(parsed, sql, max_rows=max_rows)
    query_result["object_name"] = object_name
    query_result["object_type"] = obj_type
    query_result["object_type_desc"] = type_desc
    query_result["resolved_as"] = resolved_as
    return _attach_metadata(
        query_result,
        file_path=file_path,
        conn_result=conn_result,
        db_type=db_type,
        query_type=query_type,
        query_label=label,
        original_query=query,
    )


def _attach_metadata(
    query_result: dict,
    *,
    file_path: str,
    conn_result: dict,
    db_type: str,
    query_type: int,
    query_label: str,
    original_query: str,
    **extra: object,
) -> dict:
    query_result["file_path"] = file_path
    query_result["project_root"] = conn_result.get("project_root")
    query_result["web_config_path"] = conn_result.get("web_config_path")
    query_result["db_type"] = db_type
    query_result["query_type"] = query_type
    query_result["query_label"] = query_label
    query_result["original_query"] = original_query
    query_result.update(extra)
    return query_result
