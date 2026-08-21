"""API chính: file path + query → kết quả SQL."""

from __future__ import annotations

from .connection import get_connection_config
from .executor import DEFAULT_MAX_ROWS, execute_query
from .query_resolver import (
    is_user_table,
    normalize_query_type,
    parse_object_lookup_result,
    resolve_object_sql,
    resolve_query,
)
from .bridges.summary_bridge import resolve_object_ref


def query_database(
    file_path: str,
    query: str,
    db_type: str = "app",
    max_rows: int = DEFAULT_MAX_ROWS,
    query_type: int = 1,
    mode: str = "summary",
    schema: str = "dbo",
    max_depth: int = 1,
    max_objects: int = 30,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    include_called_by: bool = False,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    max_snippet_lines: int = 120,
    max_full_chars: int = 50000,
    use_cache: bool = True,
    fetcher_override: object = None,
    **extra_kwargs: object,
) -> dict:
    """
    Resolve connection từ file path, chạy query, trả kết quả cho agent.

    Args:
        file_path: Path file trong project FBO (XML, SQL, ...)
        query: Tên object (type=0), câu SQL inline (type=1), hoặc path file .sql (type=2)
        db_type: app hoặc sys (default: app)
        max_rows: Giới hạn số dòng trả về (default: 20000)
        query_type: 0=object, 1=SQL inline (default), 2=đọc file .sql
        mode: summary | snippet | full (khi query_type=0 với proc/view/func)
        schema: Schema mặc định (default: dbo)
        max_depth: Độ sâu call graph (default: 1)
        max_objects: Giới hạn số object đệ quy (default: 30)
        expand: Danh sách infra object cần bung thêm 1 cấp
        exclude_like: Pattern loại trừ khỏi call graph
        include_called_by: Có lấy inbound references không
        keywords: Từ khóa trích xuất snippet
        zones: Vùng cấu trúc cần lấy snippet
        max_snippet_lines: Giới hạn dòng snippet
        max_full_chars: Giới hạn ký tự mode full
        use_cache: Dùng cache in-memory thread-safe
        fetcher_override: Override fetcher cho unit test
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
            mode=mode,
            schema=schema,
            max_depth=max_depth,
            max_objects=max_objects,
            expand=expand,
            exclude_like=exclude_like,
            include_called_by=include_called_by,
            keywords=keywords,
            zones=zones,
            max_snippet_lines=max_snippet_lines,
            max_full_chars=max_full_chars,
            use_cache=use_cache,
            fetcher_override=fetcher_override,
            **extra_kwargs,
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
    mode: str = "summary",
    schema: str = "dbo",
    max_depth: int = 1,
    max_objects: int = 30,
    expand: list[str] | None = None,
    exclude_like: list[str] | None = None,
    include_called_by: bool = False,
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    max_snippet_lines: int = 120,
    max_full_chars: int = 50000,
    use_cache: bool = True,
    fetcher_override: object = None,
    **extra_kwargs: object,
) -> dict:
    try:
        resolved_schema, clean_object_name = resolve_object_ref(query, schema=schema)
        lookup_sql = f"SELECT type, type_desc FROM sys.objects WHERE name = N'{clean_object_name}'"
    except (ValueError, FileNotFoundError) as exc:
        return {"success": False, "error": str(exc), "file_path": file_path}

    lookup_result = execute_query(parsed, lookup_sql, max_rows=10)
    if not lookup_result.get("success"):
        lookup_result["file_path"] = file_path
        lookup_result["query_type"] = query_type
        lookup_result["query_label"] = f"object_lookup:{clean_object_name}"
        lookup_result["original_query"] = query
        return lookup_result

    parsed_object = parse_object_lookup_result(lookup_result)
    if not parsed_object:
        return {
            "success": False,
            "error": f"Không tìm thấy object trong sys.objects: {clean_object_name}",
            "file_path": file_path,
            "project_root": conn_result.get("project_root"),
            "web_config_path": conn_result.get("web_config_path"),
            "db_type": db_type,
            "query_type": query_type,
            "original_query": query,
        }

    obj_type, type_desc = parsed_object

    # Nếu là Bảng (Table) -> Thực thi script schema bảng (CREATE TABLE + Index + Constraint)
    if is_user_table(obj_type, type_desc):
        try:
            sql, label, resolved_as = resolve_object_sql(clean_object_name, obj_type, type_desc)
        except (ValueError, FileNotFoundError) as exc:
            return {
                "success": False,
                "error": str(exc),
                "file_path": file_path,
                "object_name": clean_object_name,
                "object_type": obj_type,
                "object_type_desc": type_desc,
                "query_type": query_type,
                "original_query": query,
            }

        query_result = execute_query(parsed, sql, max_rows=max_rows)
        query_result["object_name"] = clean_object_name
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

    # Nếu là Stored Procedure, Function, View, Trigger... -> Nhúng gọi summary_object
    from .bridges.summary_bridge import summary_object

    summary_result = summary_object(
        file_path=file_path,
        object_name=query,
        mode=mode,
        db_type=db_type,
        schema=resolved_schema,
        max_depth=max_depth,
        max_objects=max_objects,
        expand=expand,
        exclude_like=exclude_like,
        include_called_by=include_called_by,
        keywords=keywords,
        zones=zones,
        max_snippet_lines=max_snippet_lines,
        max_full_chars=max_full_chars,
        use_cache=use_cache,
        fetcher_override=fetcher_override,
        **extra_kwargs,
    )
    summary_result["file_path"] = file_path
    summary_result["project_root"] = conn_result.get("project_root")
    summary_result["web_config_path"] = conn_result.get("web_config_path")
    summary_result["db_type"] = db_type
    summary_result["query_type"] = query_type
    summary_result["query_label"] = f"object_summary:{clean_object_name}"
    summary_result["original_query"] = query
    summary_result["resolved_as"] = "object_summary"
    if "object_name" not in summary_result:
        summary_result["object_name"] = clean_object_name
    if "object_type" not in summary_result:
        summary_result["object_type"] = obj_type
    summary_result["object_type_desc"] = type_desc
    return summary_result


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
