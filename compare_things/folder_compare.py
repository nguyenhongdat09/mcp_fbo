"""Folder comparison implementation for kind=folder."""

from __future__ import annotations

import datetime
import fnmatch
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .line_diff import build_line_diff
from .meta_stat import decode_bytes_with_fallback, is_binary_bytes
from .text_normalize import normalize_text_lines


def _matches_globs(path_str: str, include_globs: List[str], exclude_globs: List[str]) -> bool:
    """Check if path matches any include pattern and no exclude pattern."""
    basename = os.path.basename(path_str)
    # Check exclude
    for pat in exclude_globs:
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(path_str, pat):
            return False

    # Check include
    matched = False
    for pat in include_globs:
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(path_str, pat):
            matched = True
            break
    return matched


def _scan_folder(
    root_dir: str,
    recursive: bool,
    include_globs: List[str],
    exclude_globs: List[str],
    case_insensitive: bool,
    seed_keywords: Optional[List[str]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[str], int]:
    """
    Scan folder and collect map of norm_rel_path -> file_info.
    Returns (files_map, error_list, skipped_f_count)
    """
    root_path = Path(root_dir)
    files_map: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    skipped_f_count = 0

    if recursive:
        walker = os.walk(root_dir)
    else:
        try:
            entries = list(os.scandir(root_dir))
            walker = [(root_dir, [], [e.name for e in entries if e.is_file()])]
        except Exception as e:
            errors.append(f"scan_error: {e}")
            return {}, errors, 0

    for dirpath, _, filenames in walker:
        for fname in filenames:
            # Gate .f: file mã hóa FBO luôn bị bỏ qua, không tính vào missing/different
            if fname.lower().endswith(".f"):
                skipped_f_count += 1
                continue

            abs_p = os.path.join(dirpath, fname)
            try:
                rel_p = os.path.relpath(abs_p, root_dir).replace("\\", "/")
            except Exception:
                rel_p = fname

            if not _matches_globs(rel_p, include_globs, exclude_globs):
                continue

            if seed_keywords:
                rel_lower = rel_p.lower()
                if not any(kw in rel_lower for kw in seed_keywords):
                    continue

            norm_key = rel_p.lower() if case_insensitive else rel_p
            try:
                st = os.stat(abs_p)
                files_map[norm_key] = {
                    "relative_path": rel_p,
                    "abs_path": abs_p,
                    "size": st.st_size,
                    "created": datetime.datetime.fromtimestamp(st.st_ctime).isoformat(),
                    "modified": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(),
                    "ctime_raw": st.st_ctime,
                    "mtime_raw": st.st_mtime,
                }
            except Exception as ex:
                errors.append(f"{rel_p}: {ex}")

    return files_map, errors, skipped_f_count


def compare_folders(
    folder_a: str,
    folder_b: str,
    recursive: bool = True,
    compare_content: bool = False,
    hash_max_bytes: int = 1048576,
    include_glob: str = "*",
    exclude_glob: str = "",
    name_compare: str = "case_insensitive",
    meta_tolerance_seconds: int = 0,
    max_objects: int = 200,
    mode: str = "summary",
    seed: str = "",
    detail: bool = False,
    detail_status: str = "",
    include_compared: Optional[bool] = None,
    context_lines: int = 3,
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
    max_diff_lines: int = 200,
    include_unified_diff: bool = False,
    include_text_snippets: bool = False,
    max_hunks_summary: int = 5,
    max_hunks_detail: int = 30,
    on_progress: Optional[Any] = None,
) -> Dict[str, Any]:

    """
    Compare two directories (local or UNC).
    """
    if include_compared is not None:
        detail = include_compared

    if on_progress:
        on_progress(0, 100, "Đang quét danh mục file thư mục A và B...")

    import re
    seed_keywords = [k.strip().lower() for k in re.split(r"[,;\s]+", seed) if k.strip()] if seed else None

    case_insensitive = name_compare.lower() == "case_insensitive"
    inc_globs = [g.strip() for g in include_glob.split(",") if g.strip()] or ["*"]
    exc_globs = [g.strip() for g in exclude_glob.split(",") if g.strip()]
    if not any(g.lower() == "*.f" for g in exc_globs):
        exc_globs.append("*.f")

    files_a, errs_a, skipped_f_a = _scan_folder(folder_a, recursive, inc_globs, exc_globs, case_insensitive, seed_keywords=seed_keywords)
    files_b, errs_b, skipped_f_b = _scan_folder(folder_b, recursive, inc_globs, exc_globs, case_insensitive, seed_keywords=seed_keywords)
    skipped_f_total = skipped_f_a + skipped_f_b

    if on_progress:
        on_progress(10, 100, f"Đã quét xong: {len(files_a)} file ở A, {len(files_b)} file ở B.")

    all_errors = errs_a + errs_b
    keys_a = set(files_a.keys())
    keys_b = set(files_b.keys())

    missing_keys_b = sorted(list(keys_a - keys_b))  # Only in A
    missing_keys_a = sorted(list(keys_b - keys_a))  # Only in B
    common_keys = sorted(list(keys_a & keys_b))

    missing_on_b_names: List[str] = [files_a[k]["relative_path"] for k in missing_keys_b]
    missing_on_a_names: List[str] = [files_b[k]["relative_path"] for k in missing_keys_a]

    identical_count = 0
    different_meta_names: List[str] = []
    different_content_names: List[str] = []

    compared_items: List[Dict[str, Any]] = []

    # Process missing items
    for k in missing_keys_b:
        f = files_a[k]
        compared_items.append({
            "relative_path": f["relative_path"],
            "status": "missing_on_b",
            "a": {
                "size": f["size"],
                "created": f["created"],
                "modified": f["modified"],
            },
            "b": None,
            "next_actions": ["copy_missing_to_b"],
        })

    for k in missing_keys_a:
        f = files_b[k]
        compared_items.append({
            "relative_path": f["relative_path"],
            "status": "missing_on_a",
            "a": None,
            "b": {
                "size": f["size"],
                "created": f["created"],
                "modified": f["modified"],
            },
            "next_actions": ["copy_missing_to_a"],
        })

    # Process common items
    total_common = len(common_keys)
    for idx, k in enumerate(common_keys, 1):
        fa = files_a[k]
        fb = files_b[k]

        if on_progress and (idx % 10 == 0 or idx == total_common or idx == 1):
            pct = 10 + int(85 * idx / max(1, total_common))
            on_progress(pct, 100, f"Đang so sánh ({idx}/{total_common}): {fa['relative_path']}")

        meta_diff: List[str] = []
        if fa["size"] != fb["size"]:
            meta_diff.append("size")
        if abs(fa["mtime_raw"] - fb["mtime_raw"]) > meta_tolerance_seconds:
            meta_diff.append("modified")
        if abs(fa["ctime_raw"] - fb["ctime_raw"]) > meta_tolerance_seconds:
            meta_diff.append("created")

        content_diff_obj = None
        has_content_diff = False
        diff_reason = "none"
        sha256_a = None
        sha256_b = None
        is_bin_a = False
        is_bin_b = False

        if compare_content:
            if fa["size"] <= hash_max_bytes and fb["size"] <= hash_max_bytes:
                try:
                    with open(fa["abs_path"], "rb") as f_in:
                        bytes_a = f_in.read()
                    with open(fb["abs_path"], "rb") as f_in:
                        bytes_b = f_in.read()

                    sha256_a = hashlib.sha256(bytes_a).hexdigest()
                    sha256_b = hashlib.sha256(bytes_b).hexdigest()
                    if sha256_a != sha256_b:
                        meta_diff.append("sha256")
                        is_bin_a = is_binary_bytes(bytes_a)
                        is_bin_b = is_binary_bytes(bytes_b)

                        if is_bin_a or is_bin_b:
                            has_content_diff = True
                            diff_reason = "binary"
                        else:
                            text_a, _, _ = decode_bytes_with_fallback(bytes_a)
                            text_b, _, _ = decode_bytes_with_fallback(bytes_b)
                            lines_a = normalize_text_lines(
                                text_a,
                                ignore_line_endings=ignore_line_endings,
                                ignore_whitespace=ignore_whitespace,
                            )
                            lines_b = normalize_text_lines(
                                text_b,
                                ignore_line_endings=ignore_line_endings,
                                ignore_whitespace=ignore_whitespace,
                            )
                            if lines_a == lines_b:
                                has_content_diff = False
                                bom_a = bytes_a.startswith(b"\xef\xbb\xbf")
                                bom_b = bytes_b.startswith(b"\xef\xbb\xbf")
                                if bom_a != bom_b:
                                    diff_reason = "bom"
                                else:
                                    crlf_a = b"\r\n" in bytes_a
                                    crlf_b = b"\r\n" in bytes_b
                                    cr_a = b"\r" in bytes_a and not crlf_a
                                    cr_b = b"\r" in bytes_b and not crlf_b
                                    if crlf_a != crlf_b or cr_a != cr_b:
                                        diff_reason = "line_ending"
                                    elif ignore_whitespace:
                                        raw_a = normalize_text_lines(text_a, ignore_line_endings=True, ignore_whitespace=False)
                                        raw_b = normalize_text_lines(text_b, ignore_line_endings=True, ignore_whitespace=False)
                                        if raw_a != raw_b:
                                            diff_reason = "whitespace"
                                        else:
                                            diff_reason = "encoding_or_bytes"
                                    else:
                                        diff_reason = "encoding_or_bytes"
                            else:
                                has_content_diff = True
                                diff_reason = "text_lines"
                                content_diff_obj = build_line_diff(
                                    lines_a=lines_a,
                                    lines_b=lines_b,
                                    context_lines=context_lines,
                                    max_preview_lines_per_hunk=8,
                                    max_diff_lines=max_diff_lines,
                                    max_hunks=max_hunks_detail,
                                    mode=mode,
                                    is_sql=False,
                                    file_label_a=fa["relative_path"],
                                    file_label_b=fb["relative_path"],
                                    include_unified_diff=include_unified_diff,
                                    include_text_snippets=include_text_snippets,
                                )
                except Exception as ex:
                    all_errors.append(f"hash_error {fa['relative_path']}: {ex}")

        rel_name = fa["relative_path"]
        if has_content_diff:
            different_content_names.append(rel_name)
            item: Dict[str, Any] = {
                "relative_path": rel_name,
                "status": "different_content",
                "diff_reason": diff_reason,
                "meta_diff": meta_diff,
                "a": {
                    "size": fa["size"],
                    "sha256": sha256_a,
                    "created": fa["created"],
                    "modified": fa["modified"],
                    "is_binary": is_bin_a,
                },
                "b": {
                    "size": fb["size"],
                    "sha256": sha256_b,
                    "created": fb["created"],
                    "modified": fb["modified"],
                    "is_binary": is_bin_b,
                },
                "next_actions": ["investigate_version_dll"] if (is_bin_a or is_bin_b or rel_name.lower().endswith(".dll")) else ["review_hunks"],
            }
            if content_diff_obj:
                cap_hunks = max_hunks_summary if mode == "summary" else max_hunks_detail
                item["content"] = content_diff_obj.to_dict(
                    is_sql=False,
                    mode=mode,
                    max_hunks=cap_hunks,
                    include_text_snippets=include_text_snippets,
                    include_unified_diff=include_unified_diff,
                )
            compared_items.append(item)
        elif meta_diff:
            different_meta_names.append(rel_name)
            is_bin_or_dll = rel_name.lower().endswith(".dll") or is_bin_a or is_bin_b
            if is_bin_or_dll:
                meta_next_actions = ["investigate_version_dll"]
            elif diff_reason in ("bom", "line_ending", "whitespace", "encoding_or_bytes"):
                meta_next_actions = ["ignore_normalized_bytes_diff"]
            else:
                meta_next_actions = ["review_meta"]

            compared_items.append({
                "relative_path": rel_name,
                "status": "different_meta",
                "diff_reason": diff_reason,
                "meta_diff": meta_diff,
                "a": {
                    "size": fa["size"],
                    "created": fa["created"],
                    "modified": fa["modified"],
                    "sha256": sha256_a,
                    "is_binary": is_bin_a,
                },
                "b": {
                    "size": fb["size"],
                    "created": fb["created"],
                    "modified": fb["modified"],
                    "sha256": sha256_b,
                    "is_binary": is_bin_b,
                },
                "next_actions": meta_next_actions,
            })
        else:
            identical_count += 1

    # Decouple summary names from max_objects (summary names list must remain full)
    summary_limit = 5000
    truncated_summary_names = (
        len(missing_on_b_names) > summary_limit
        or len(missing_on_a_names) > summary_limit
        or len(different_meta_names) > summary_limit
        or len(different_content_names) > summary_limit
        or len(all_errors) > summary_limit
    )
    s_missing_b = missing_on_b_names[:summary_limit] if truncated_summary_names else missing_on_b_names
    s_missing_a = missing_on_a_names[:summary_limit] if truncated_summary_names else missing_on_a_names
    s_diff_meta = different_meta_names[:summary_limit] if truncated_summary_names else different_meta_names
    s_diff_content = different_content_names[:summary_limit] if truncated_summary_names else different_content_names
    s_errors = all_errors[:summary_limit] if len(all_errors) > summary_limit else all_errors

    # Handle detail and detail_status for compared_items
    if detail:
        allowed_statuses: Set[str] = set()
        if detail_status and detail_status.strip():
            allowed_statuses = {s.strip().lower() for s in detail_status.split(",") if s.strip()}

        if allowed_statuses:
            filtered_items = [it for it in compared_items if it.get("status", "").lower() in allowed_statuses]
        else:
            filtered_items = compared_items

        limit_obj = max_objects if (max_objects is not None and max_objects > 0) else 200
        truncated_compared = len(filtered_items) > limit_obj
        final_compared = filtered_items[:limit_obj] if truncated_compared else filtered_items
    else:
        truncated_compared = False
        final_compared = []

    truncated = truncated_compared or truncated_summary_names

    # Global next actions
    top_actions: List[str] = []
    if missing_on_b_names:
        top_actions.append("copy_missing_to_b")
    if missing_on_a_names:
        top_actions.append("copy_missing_to_a")
    if different_content_names:
        if any(not n.lower().endswith(".dll") for n in different_content_names):
            top_actions.append("review_hunks")
        if any(n.lower().endswith(".dll") for n in different_content_names):
            if "investigate_version_dll" not in top_actions:
                top_actions.append("investigate_version_dll")
    if any(n.lower().endswith(".dll") for n in different_meta_names):
        if "investigate_version_dll" not in top_actions:
            top_actions.append("investigate_version_dll")
    if not top_actions:
        top_actions = ["noop"]

    name_a = Path(folder_a).name or folder_a
    name_b = Path(folder_b).name or folder_b
    msg_parts = [f"So thư mục B: {name_b} (đang sửa) với thư mục A: {name_a} (nguồn clone):"]
    if missing_on_b_names:
        msg_parts.append(f"{name_b} thiếu {len(missing_on_b_names)} file,")
    if different_content_names:
        msg_parts.append(f"khác nội dung: {len(different_content_names)} file,")
    if different_meta_names:
        msg_parts.append(f"khác metadata: {len(different_meta_names)} file,")
    if missing_on_a_names:
        msg_parts.append(f"thiếu ở nguồn A: {len(missing_on_a_names)} file,")
    msg_parts.append(f"giống metadata: {identical_count} (ẩn).")
    message = " ".join(msg_parts)

    return {
        "success": True,
        "kind": "folder",
        "role_a": "reference_clone_from",
        "role_b": "editing",
        "folder_a": folder_a,
        "folder_b": folder_b,
        "mode": mode,
        "seed": seed,
        "detail": detail,
        "summary": {
            "files_a": len(files_a),
            "files_b": len(files_b),
            "missing_on_b": s_missing_b,
            "missing_on_a": s_missing_a,
            "identical_meta_count": identical_count,
            "omitted_identical_count": identical_count,
            "different_meta": s_diff_meta,
            "different_content": s_diff_content,
            "skipped_f_count": skipped_f_total,
            "errors": s_errors,
            "truncated": truncated,
            "truncated_compared": truncated_compared,
            "truncated_summary_names": truncated_summary_names,
        },
        "compared": final_compared,
        "message": message,
        "next_actions": top_actions,
        "warnings": all_errors,
        "error_code": None,
        "error": None,
    }

