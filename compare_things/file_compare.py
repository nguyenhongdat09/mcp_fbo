"""Comparison implementation for kind=file."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .line_diff import build_line_diff
from .meta_stat import get_file_meta_and_bytes
from .models import ContentDiff, FileMeta
from .text_normalize import normalize_text_lines


def compare_files(
    file_a: str,
    file_b: str,
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
    mode: str = "summary",
    max_diff_lines: int = 200,
    context_lines: int = 3,
    max_file_bytes: int = 10485760,
    include_unified_diff: bool = False,
    include_text_snippets: bool = False,
    max_hunks_summary: int = 5,
    max_hunks_detail: int = 30,
) -> Dict[str, Any]:

    """
    Compare two files on disk (local or UNC).
    Returns dict representing a compared item for kind=file.
    """
    # Gate .f: CẤM so sánh file .f mã hóa FBO, không đọc bytes hay diff text
    if file_a.strip().lower().endswith(".f") or file_b.strip().lower().endswith(".f"):
        f_path = file_a if file_a.strip().lower().endswith(".f") else file_b
        empty_content = ContentDiff(lines_a=0, lines_b=0, hunk_count=0, hunks=[])
        return {
            "status": "skipped_encrypted_ext",
            "error_code": "unsupported_extension_f",
            "error": f"Cannot compare .f encrypted file: {f_path}",
            "identical_content": False,
            "identical_meta": False,
            "only_line_ending_diff": False,
            "file_a": {"path": file_a},
            "file_b": {"path": file_b},
            "meta_diff": [],
            "content": empty_content.to_dict(is_sql=False, mode=mode),
            "next_actions": ["use_source_xml_instead", "fix_paths"],
            "warnings": [f"Skipped .f encrypted file: {f_path}"],
        }

    # Gate .xsd: file schema/kiến trúc — không cần đọc/diff
    if file_a.strip().lower().endswith(".xsd") or file_b.strip().lower().endswith(".xsd"):
        x_path = file_a if file_a.strip().lower().endswith(".xsd") else file_b
        empty_content = ContentDiff(lines_a=0, lines_b=0, hunk_count=0, hunks=[])
        return {
            "status": "skipped_unsupported_ext",
            "error_code": "unsupported_extension_xsd",
            "error": f"Cannot compare .xsd schema file: {x_path}",
            "identical_content": False,
            "identical_meta": False,
            "only_line_ending_diff": False,
            "file_a": {"path": file_a},
            "file_b": {"path": file_b},
            "meta_diff": [],
            "content": empty_content.to_dict(is_sql=False, mode=mode),
            "next_actions": ["fix_paths"],
            "warnings": [f"Skipped .xsd schema file: {x_path}"],
        }

    meta_a, bytes_a, text_a, warn_a = get_file_meta_and_bytes(file_a, max_file_bytes=max_file_bytes)
    meta_b, bytes_b, text_b, warn_b = get_file_meta_and_bytes(file_b, max_file_bytes=max_file_bytes)

    warnings: List[str] = []
    if warn_a:
        warnings.append(f"file_a: {warn_a}")
    if warn_b:
        warnings.append(f"file_b: {warn_b}")

    # Compute meta differences
    meta_diff: List[str] = []
    if meta_a.size != meta_b.size:
        meta_diff.append("size")
    if meta_a.modified != meta_b.modified:
        meta_diff.append("modified")
    if meta_a.created != meta_b.created:
        meta_diff.append("created")
    if meta_a.sha256 != meta_b.sha256:
        meta_diff.append("sha256")
    if meta_a.line_ending != meta_b.line_ending:
        meta_diff.append("line_ending")

    identical_meta = len(meta_diff) == 0

    # Binary check
    if meta_a.is_binary or meta_b.is_binary:
        identical_content = meta_a.sha256 == meta_b.sha256
        status = "identical" if identical_content else "different"
        next_actions = ["noop"] if identical_content else ["compare_binary_meta_only"]

        empty_content = ContentDiff(lines_a=0, lines_b=0, hunk_count=0, hunks=[])

        return {
            "status": status,
            "identical_content": identical_content,
            "identical_meta": identical_meta,
            "only_line_ending_diff": False,
            "diff_reason": "none" if identical_content else "binary",
            "file_a": meta_a.to_dict(),
            "file_b": meta_b.to_dict(),
            "meta_diff": meta_diff,
            "content": empty_content.to_dict(is_sql=False, mode=mode),
            "next_actions": next_actions,
            "warnings": warnings,
        }

    # Text comparison
    lines_a = normalize_text_lines(
        text_a or "",
        ignore_line_endings=ignore_line_endings,
        ignore_whitespace=ignore_whitespace,
    )
    lines_b = normalize_text_lines(
        text_b or "",
        ignore_line_endings=ignore_line_endings,
        ignore_whitespace=ignore_whitespace,
    )

    identical_content = lines_a == lines_b
    content_same_bytes_differ = identical_content and (meta_a.sha256 != meta_b.sha256)
    line_ending_diff = meta_a.line_ending != meta_b.line_ending
    bom_diff = (bytes_a.startswith(b"\xef\xbb\xbf") != bytes_b.startswith(b"\xef\xbb\xbf"))
    ws_diff = False
    if ignore_whitespace:
        raw_lines_a = normalize_text_lines(text_a or "", ignore_line_endings=True, ignore_whitespace=False)
        raw_lines_b = normalize_text_lines(text_b or "", ignore_line_endings=True, ignore_whitespace=False)
        ws_diff = raw_lines_a != raw_lines_b

    only_line_ending_diff = identical_content and line_ending_diff and not bom_diff and not ws_diff

    diff_reason = "none"
    if identical_content:
        if line_ending_diff and not bom_diff and not ws_diff:
            diff_reason = "line_ending"
        elif bom_diff:
            diff_reason = "bom"
        elif ws_diff:
            diff_reason = "whitespace"
        elif content_same_bytes_differ:
            diff_reason = "bytes"

    if identical_content:
        status = "identical"
        if only_line_ending_diff:
            next_actions = ["ignore_line_ending_only"]
        elif content_same_bytes_differ:
            next_actions = ["ignore_normalized_bytes_diff"]
        else:
            next_actions = ["noop"]

        content_diff = ContentDiff(
            lines_a=len(lines_a),
            lines_b=len(lines_b),
            lines_added=0,
            lines_removed=0,
            hunk_count=0,
            hunks=[],
            diff_truncated=False,
            unified_diff="",
        )
    else:
        status = "different"
        next_actions = ["review_hunks", "edit_target_file"]

        content_diff = build_line_diff(
            lines_a=lines_a,
            lines_b=lines_b,
            context_lines=context_lines,
            max_preview_lines_per_hunk=8,
            max_diff_lines=max_diff_lines,
            max_hunks=max_hunks_detail,
            mode=mode,
            is_sql=False,
            file_label_a=meta_a.path,
            file_label_b=meta_b.path,
            include_unified_diff=include_unified_diff,
            include_text_snippets=include_text_snippets,
        )

    cap_hunks = max_hunks_summary if mode == "summary" else max_hunks_detail
    content_dict = content_diff.to_dict(
        is_sql=False,
        mode=mode,
        max_hunks=cap_hunks,
        include_text_snippets=include_text_snippets,
        include_unified_diff=include_unified_diff,
    )

    return {
        "status": status,
        "identical_content": identical_content,
        "identical_meta": identical_meta,
        "only_line_ending_diff": only_line_ending_diff,
        "content_same_bytes_differ": content_same_bytes_differ,
        "diff_reason": diff_reason,
        "file_a": meta_a.to_dict(),
        "file_b": meta_b.to_dict(),
        "meta_diff": meta_diff,
        "content": content_dict,
        "next_actions": next_actions,
        "warnings": warnings,
    }

