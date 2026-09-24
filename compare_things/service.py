"""Main service and router for compare_things."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .file_compare import compare_files

VALID_KINDS = {"sql", "table", "xml", "file", "folder"}
VALID_MODES = {"summary", "hunks", "body"}
VALID_DB_TYPES = {"app", "sys", "both"}


def _build_error(
    kind: str,
    error_code: str,
    error_msg: str,
    vi_msg: str,
    next_actions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "success": False,
        "kind": kind,
        "error_code": error_code,
        "error": error_msg,
        "summary": None,
        "compared": [],
        "message": vi_msg,
        "next_actions": next_actions or ["fix_paths"],
        "warnings": [],
    }


def compare_things(
    kind: str,
    project_source: str = "",
    project_target: str = "",
    object: str = "",
    seed: str = "",
    seed_mode: str = "contains",
    db_type: str = "app",
    mode: str = "summary",
    file_a: str = "",
    file_b: str = "",
    folder_a: str = "",
    folder_b: str = "",
    detail: bool = False,
    detail_status: str = "",
    include_compared: Optional[bool] = None,
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
    max_diff_lines: int = 200,
    max_objects: Optional[int] = None,
    recursive: bool = True,
    compare_content: bool = False,
    hash_max_bytes: int = 1048576,
    include_glob: str = "*",
    exclude_glob: str = "",
    name_compare: str = "case_insensitive",
    meta_tolerance_seconds: int = 0,
    context_lines: int = 3,
    schema: str = "dbo",
    xml_view: str = "original",
    include_unified_diff: bool = False,
    include_text_snippets: bool = False,
    max_hunks_summary: int = 5,
    max_hunks_detail: int = 30,
    inventory: bool = False,
    list_identical: bool = False,
    config: Optional[Dict[str, Any]] = None,
    on_progress: Optional[Any] = None,
) -> Dict[str, Any]:

    """
    Dispatcher and parameter validator for compare_things tool.
    - kind='file': So sánh 2 file bất kỳ trên đĩa (.xml, .ent, .txt, .sql, .js, .config...) TRỪ file .f mã hóa và .xsd.
    - kind='folder': Quét và so sánh thư mục (loại trừ *.f mã hóa và *.xsd).
    - kind='xml': Tiện ích so sánh controller XML relative dưới Controllers/ (không dùng cho .ent/.txt).
    - kind='sql', kind='table': So sánh procedure/function/view hoặc schema bảng giữa 2 database.
    """
    params = dict(locals())  # capture đúng signature — locals() sau này sẽ dính biến cục bộ

    # Sticky context visibility — nuôi context theo project/file đang thao tác
    # (bên B/target feed sau nên thắng) + echo project_root vào response.
    from xml_fbograph.utils.any_path import project_switch_message, resolve_any_path

    ctx_paths = {
        "file": (file_a, file_b),
        "folder": (folder_a, folder_b),
    }.get(kind.strip().lower() if kind else "", (project_source, project_target))
    ctx_root: Optional[str] = None
    ctx_switched_from: Optional[str] = None
    for _ctx_path in ctx_paths:
        if not _ctx_path or not str(_ctx_path).strip():
            continue
        _ctx_res = resolve_any_path(str(_ctx_path))
        if _ctx_res.ok and _ctx_res.project_root:
            if _ctx_res.switched_from and ctx_switched_from is None:
                ctx_switched_from = _ctx_res.switched_from
            ctx_root = _ctx_res.project_root
    _ctx_warn = project_switch_message(ctx_switched_from, ctx_root)

    result = _compare_things_impl(**params)
    if isinstance(result, dict):
        result.setdefault("project_root", ctx_root)
        if ctx_root:
            result.setdefault("resolved_via", "absolute")
        if _ctx_warn:
            warns = result.setdefault("warnings", [])
            if isinstance(warns, list):
                warns.append(_ctx_warn)
    return result


def _compare_things_impl(
    kind: str,
    project_source: str = "",
    project_target: str = "",
    object: str = "",
    seed: str = "",
    seed_mode: str = "contains",
    db_type: str = "app",
    mode: str = "summary",
    file_a: str = "",
    file_b: str = "",
    folder_a: str = "",
    folder_b: str = "",
    detail: bool = False,
    detail_status: str = "",
    include_compared: Optional[bool] = None,
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
    max_diff_lines: int = 200,
    max_objects: Optional[int] = None,
    recursive: bool = True,
    compare_content: bool = False,
    hash_max_bytes: int = 1048576,
    include_glob: str = "*",
    exclude_glob: str = "",
    name_compare: str = "case_insensitive",
    meta_tolerance_seconds: int = 0,
    context_lines: int = 3,
    schema: str = "dbo",
    xml_view: str = "original",
    include_unified_diff: bool = False,
    include_text_snippets: bool = False,
    max_hunks_summary: int = 5,
    max_hunks_detail: int = 30,
    inventory: bool = False,
    list_identical: bool = False,
    config: Optional[Dict[str, Any]] = None,
    on_progress: Optional[Any] = None,
) -> Dict[str, Any]:

    kind = (kind or "").strip().lower()
    if kind not in VALID_KINDS:
        return _build_error(
            kind=kind,
            error_code="invalid_kind",
            error_msg=f"Kind '{kind}' is not supported. Must be one of: {sorted(VALID_KINDS)}",
            vi_msg=f"Tham số kind '{kind}' không hợp lệ. Chỉ chấp nhận: sql, table, xml, file, folder.",
            next_actions=["fix_paths"],
        )

    mode = (mode or "summary").strip().lower()
    if mode not in VALID_MODES:
        return _build_error(
            kind=kind,
            error_code="invalid_mode",
            error_msg=f"Mode '{mode}' is not supported. Must be one of: {sorted(VALID_MODES)}",
            vi_msg=f"Tham số mode '{mode}' không hợp lệ. Chỉ chấp nhận: summary, hunks, body.",
            next_actions=["fix_paths"],
        )

    if max_diff_lines <= 0:
        return _build_error(
            kind=kind,
            error_code="invalid_limit",
            error_msg=f"max_diff_lines must be positive, got {max_diff_lines}",
            vi_msg="Tham số max_diff_lines phải lớn hơn 0.",
        )

    if max_objects is not None and max_objects <= 0:
        return _build_error(
            kind=kind,
            error_code="invalid_limit",
            error_msg=f"max_objects must be positive, got {max_objects}",
            vi_msg="Tham số max_objects phải lớn hơn 0.",
        )

    # Defaults for max_objects
    if max_objects is None:
        max_objects = 200 if kind == "folder" else 50

    # 1. Validation for kind=file
    if kind == "file":
        if not file_a:
            return _build_error(
                kind="file",
                error_code="invalid_file_a",
                error_msg="file_a is required for kind=file",
                vi_msg="Thiếu tham số file_a cho kind=file.",
            )
        if not file_b:
            return _build_error(
                kind="file",
                error_code="invalid_file_b",
                error_msg="file_b is required for kind=file",
                vi_msg="Thiếu tham số file_b cho kind=file.",
            )

        # Gate .f: CẤM so sánh file .f mã hóa FBO
        if file_a.strip().lower().endswith(".f") or file_b.strip().lower().endswith(".f"):
            f_path = file_a if file_a.strip().lower().endswith(".f") else file_b
            return _build_error(
                kind="file",
                error_code="unsupported_extension_f",
                error_msg=f"Cannot compare .f encrypted file: {f_path}",
                vi_msg=f"Không so sánh file đuôi .f (file mã hóa FBO): {f_path}. Tuyệt đối không chỉnh sửa hoặc giải mã file .f.",
                next_actions=["use_source_xml_instead", "fix_paths"],
            )

        # Gate .xsd: file schema/kiến trúc — không cần đọc/so sánh
        if file_a.strip().lower().endswith(".xsd") or file_b.strip().lower().endswith(".xsd"):
            x_path = file_a if file_a.strip().lower().endswith(".xsd") else file_b
            return _build_error(
                kind="file",
                error_code="unsupported_extension_xsd",
                error_msg=f"Cannot compare .xsd schema file: {x_path}",
                vi_msg=f"Không so sánh file đuôi .xsd (file schema/kiến trúc — không cần đọc): {x_path}.",
                next_actions=["fix_paths"],
            )

        pa = Path(file_a)
        pb = Path(file_b)
        if not pa.exists() or not pa.is_file():
            return _build_error(
                kind="file",
                error_code="file_not_found",
                error_msg=f"file_a does not exist or is not a file: {file_a}",
                vi_msg=f"Không tìm thấy file_a trên đĩa: {file_a}",
            )
        if not pb.exists() or not pb.is_file():
            return _build_error(
                kind="file",
                error_code="file_not_found",
                error_msg=f"file_b does not exist or is not a file: {file_b}",
                vi_msg=f"Không tìm thấy file_b trên đĩa: {file_b}",
            )

        if on_progress:
            on_progress(10, 100, f"Đang so sánh file: {pa.name}...")

        item = compare_files(
            file_a=str(pa.resolve()),
            file_b=str(pb.resolve()),
            ignore_line_endings=ignore_line_endings,
            ignore_whitespace=ignore_whitespace,
            mode=mode,
            max_diff_lines=max_diff_lines,
            context_lines=context_lines,
            include_unified_diff=include_unified_diff,
            include_text_snippets=include_text_snippets,
            max_hunks_summary=max_hunks_summary,
            max_hunks_detail=max_hunks_detail,
        )

        if on_progress:
            on_progress(100, 100, f"Hoàn tất so sánh file: {pa.name}.")

        name_a = pa.name
        name_b = pb.name
        prefix = f"So file B: {name_b} (đang sửa) với file A: {name_a} (nguồn clone):"

        # Build message
        meta_diff_keys = item.get("meta_diff", [])
        meta_suffix = f"; khác metadata: {', '.join(meta_diff_keys)}" if meta_diff_keys else ""

        if item["status"] == "identical":
            if item.get("only_line_ending_diff"):
                vi_msg = f"{prefix} Hai file có nội dung giống nhau, chỉ khác định dạng xuống dòng (CRLF/LF){meta_suffix}."
            elif item.get("diff_reason") == "bom":
                vi_msg = f"{prefix} Hai file có nội dung giống nhau sau khi normalize; khác BOM hoặc bytes gốc{meta_suffix}."
            elif item.get("diff_reason") == "whitespace":
                vi_msg = f"{prefix} Hai file có nội dung giống nhau sau khi bỏ qua khoảng trắng; bytes gốc khác nhau{meta_suffix}."
            elif item.get("content_same_bytes_differ"):
                vi_msg = f"{prefix} Hai file có nội dung giống nhau sau khi normalize; bytes gốc khác nhau{meta_suffix}."
            else:
                if meta_diff_keys:
                    vi_msg = f"{prefix} Hai file giống nhau về nội dung; khác metadata: {', '.join(meta_diff_keys)}."
                else:
                    vi_msg = f"{prefix} Hai file hoàn toàn giống nhau về nội dung và metadata."
        else:
            hunk_cnt = item.get("content", {}).get("hunk_count", 0)
            vi_msg = f"{prefix} Hai file khác nhau về nội dung ({hunk_cnt} vùng thay đổi; xem hunks ranges, không dán code){meta_suffix}."

        return {
            "success": True,
            "kind": "file",
            "role_a": "reference_clone_from",
            "role_b": "editing",
            "file_a": str(pa.resolve()),
            "file_b": str(pb.resolve()),
            "mode": mode,
            "summary": {
                "identical_content": item["identical_content"],
                "identical_meta": item["identical_meta"],
                "only_line_ending_diff": item["only_line_ending_diff"],
                "content_same_bytes_differ": item.get("content_same_bytes_differ", False),
                "status": item["status"],
            },
            "compared": [item],
            "message": vi_msg,
            "next_actions": item["next_actions"],
            "warnings": item.get("warnings", []),
            "error_code": None,
            "error": None,
        }


    # 2. Validation for kind=folder
    if kind == "folder":
        if inventory:
            target_folder = folder_a or folder_b
            if not target_folder:
                return _build_error(
                    kind="folder",
                    error_code="invalid_folder",
                    error_msg="folder_a or folder_b is required when inventory=true",
                    vi_msg="Thiếu tham số folder_a (hoặc folder_b) cho chế độ inventory.",
                )
            p_folder = Path(target_folder)
            if not p_folder.exists() or not p_folder.is_dir():
                return _build_error(
                    kind="folder",
                    error_code="folder_not_found",
                    error_msg=f"folder does not exist or is not a directory: {target_folder}",
                    vi_msg=f"Không tìm thấy thư mục: {target_folder}",
                )
            from .folder_compare import inventory_folder
            return inventory_folder(
                folder=str(p_folder.resolve()),
                recursive=recursive,
                include_glob=include_glob,
                exclude_glob=exclude_glob,
                name_compare=name_compare,
                max_objects=max_objects or 200,
                seed=seed or "",
                seed_mode=seed_mode,
            )

        if not folder_a:
            return _build_error(
                kind="folder",
                error_code="invalid_folder_a",
                error_msg="folder_a is required for kind=folder",
                vi_msg="Thiếu tham số folder_a cho kind=folder.",
            )
        if not folder_b:
            return _build_error(
                kind="folder",
                error_code="invalid_folder_b",
                error_msg="folder_b is required for kind=folder",
                vi_msg="Thiếu tham số folder_b cho kind=folder.",
            )
        pa = Path(folder_a)
        pb = Path(folder_b)
        if not pa.exists() or not pa.is_dir():
            return _build_error(
                kind="folder",
                error_code="folder_not_found",
                error_msg=f"folder_a does not exist or is not a directory: {folder_a}",
                vi_msg=f"Không tìm thấy thư mục folder_a: {folder_a}",
            )
        if not pb.exists() or not pb.is_dir():
            return _build_error(
                kind="folder",
                error_code="folder_not_found",
                error_msg=f"folder_b does not exist or is not a directory: {folder_b}",
                vi_msg=f"Không tìm thấy thư mục folder_b: {folder_b}",
            )

        from .folder_compare import compare_folders
        return compare_folders(
            folder_a=str(pa.resolve()),
            folder_b=str(pb.resolve()),
            seed=seed or "",
            seed_mode=seed_mode,
            recursive=recursive,
            compare_content=compare_content,
            hash_max_bytes=hash_max_bytes,
            include_glob=include_glob,
            exclude_glob=exclude_glob,
            name_compare=name_compare,
            meta_tolerance_seconds=meta_tolerance_seconds,
            max_objects=max_objects or 200,
            mode=mode,
            detail=detail,
            detail_status=detail_status,
            include_compared=include_compared,
            context_lines=context_lines,
            ignore_line_endings=ignore_line_endings,
            ignore_whitespace=ignore_whitespace,
            max_diff_lines=max_diff_lines,
            include_unified_diff=include_unified_diff,
            include_text_snippets=include_text_snippets,
            max_hunks_summary=max_hunks_summary,
            max_hunks_detail=max_hunks_detail,
            list_identical=list_identical,
            on_progress=on_progress,
        )

    # Common validation for sql, table, xml
    if not project_source:
        return _build_error(
            kind=kind,
            error_code="invalid_project_source",
            error_msg="project_source is required",
            vi_msg="Thiếu tham số project_source.",
        )
    if not project_target:
        return _build_error(
            kind=kind,
            error_code="invalid_project_target",
            error_msg="project_target is required",
            vi_msg="Thiếu tham số project_target.",
        )

    # 3. Validation for kind=sql
    if kind == "sql":
        db_type = (db_type or "app").strip().lower()
        if db_type not in VALID_DB_TYPES:
            return _build_error(
                kind="sql",
                error_code="invalid_db_type",
                error_msg=f"db_type '{db_type}' is invalid. Must be app, sys, or both",
                vi_msg=f"db_type '{db_type}' không hợp lệ. Chỉ chấp nhận: app, sys, both.",
            )
        if not object and not seed:
            return _build_error(
                kind="sql",
                error_code="invalid_object_or_seed",
                error_msg="Either object or seed must be provided for kind=sql",
                vi_msg="Phải cung cấp ít nhất tham số 'object' hoặc 'seed' cho kind=sql.",
            )

        from .sql_compare import compare_sql
        return compare_sql(
            project_source=project_source,
            project_target=project_target,
            object=object,
            seed=seed,
            db_type=db_type,
            schema=schema or "dbo",
            mode=mode,
            max_objects=max_objects,
            max_diff_lines=max_diff_lines,
            ignore_line_endings=ignore_line_endings,
            ignore_whitespace=ignore_whitespace,
            context_lines=context_lines,
            include_unified_diff=include_unified_diff,
            include_text_snippets=include_text_snippets,
            max_hunks_summary=max_hunks_summary,
            max_hunks_detail=max_hunks_detail,
            config=config,
            on_progress=on_progress,
        )

    # 4. Validation for kind=xml
    if kind == "xml":
        xml_view_clean = (xml_view or "original").strip().lower()
        if xml_view_clean == "raw":
            xml_view_clean = "original"
        elif xml_view_clean == "expanded":
            xml_view_clean = "flat"

        if xml_view_clean not in ("original", "flat"):
            return _build_error(
                kind="xml",
                error_code="invalid_xml_view",
                error_msg=f"xml_view '{xml_view}' is not supported. Must be 'original' (or 'raw') or 'flat' (or 'expanded').",
                vi_msg=f"Tham số xml_view '{xml_view}' không hợp lệ. Chỉ chấp nhận: original (hoặc raw), flat (hoặc expanded).",
                next_actions=["fix_paths"],
            )

        if not object and not seed:
            return _build_error(
                kind="xml",
                error_code="invalid_object",
                error_msg="Either object or seed is required for kind=xml (relative path(s) under Controllers/ or search seed)",
                vi_msg="Thiếu tham số object hoặc seed cho kind=xml.",
            )

        from .xml_compare import compare_xml
        return compare_xml(
            project_source=project_source,
            project_target=project_target,
            object=object or "",
            seed=seed or "",
            mode=mode,
            xml_view=xml_view_clean,
            ignore_line_endings=ignore_line_endings,
            ignore_whitespace=ignore_whitespace,
            max_diff_lines=max_diff_lines,
            context_lines=context_lines,
            include_unified_diff=include_unified_diff,
            include_text_snippets=include_text_snippets,
            max_hunks_summary=max_hunks_summary,
            max_hunks_detail=max_hunks_detail,
            max_objects=max_objects or 50,
            on_progress=on_progress,
        )


    # 5. Validation for kind=table
    if kind == "table":
        if not object:
            return _build_error(
                kind="table",
                error_code="invalid_object",
                error_msg="object is required for kind=table (table name(s))",
                vi_msg="Thiếu tham số object (danh sách tên bảng) cho kind=table.",
            )

        from .table_compare import compare_table
        return compare_table(
            project_source=project_source,
            project_target=project_target,
            object=object,
            db_type=db_type,
            schema=schema or "dbo",
            max_objects=max_objects,
            config=config,
            on_progress=on_progress,
        )

    return _build_error(kind=kind, error_code="unhandled", error_msg="Unhandled branch", vi_msg="Lỗi chưa xử lý.")
