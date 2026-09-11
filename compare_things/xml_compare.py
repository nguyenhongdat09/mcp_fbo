"""XML controller comparison implementation for kind=xml supporting original and flat views."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from find_connect_by_path.path_resolver import get_project_root_from_path
from find_entity_by_xml.facade import flat_xml
from xml_fbograph.utils.path_helper import resolve_controllers_dir

from .file_compare import compare_files
from .line_diff import build_line_diff
from .meta_stat import get_file_meta_and_bytes
from .models import ContentDiff
from .text_normalize import normalize_text_lines



def _resolve_controllers(project_path: str) -> Optional[Path]:
    """
    Resolve Controllers directory from project path.
    Tries root via get_project_root_from_path then resolve_controllers_dir.
    """
    root = get_project_root_from_path(project_path)
    if root:
        controllers = resolve_controllers_dir(root)
        if controllers and controllers.is_dir():
            return controllers

    controllers = resolve_controllers_dir(project_path)
    if controllers and controllers.is_dir():
        return controllers

    p = Path(project_path)
    direct = p / "App_Data" / "Controllers"
    if direct.is_dir():
        return direct
    if p.name.lower() == "controllers" and p.is_dir():
        return p

    return None


def _normalize_relative_xml(relative: str) -> str:
    """
    Normalize relative XML path:
    - Replace \\ with /
    - Strip leading / and \\
    - Strip App_Data/Controllers/ or Controllers/ prefix
    - Reject '..' path traversal
    """
    norm = relative.strip().lstrip("/\\").replace("\\", "/")
    segments = norm.split("/")
    if ".." in segments:
        raise ValueError(f"Path traversal '..' is not allowed: {relative}")

    if norm.lower().startswith("app_data/controllers/"):
        norm = norm[len("app_data/controllers/"):]
    elif norm.lower().startswith("controllers/"):
        norm = norm[len("controllers/"):]

    return norm


def scan_xml_seed_candidates(
    controllers_src: Optional[Path],
    controllers_tgt: Optional[Path],
    seed: str,
    max_objects: int = 50,
) -> Tuple[List[str], int, bool]:
    """
    Scan Controllers directories in project_source and project_target for XML files matching seed keywords.
    Matches keywords against normalized relative path and filename (case-insensitive).
    Excludes *.f files. Only includes *.xml files.
    Returns (candidate_relative_paths, total_hits_count, is_truncated).
    """
    keywords = [k.strip().lower() for k in re.split(r"[,;\s]+", seed) if k.strip()]
    if not keywords:
        return [], 0, False

    found_set: Set[str] = set()

    for controllers_dir in (controllers_src, controllers_tgt):
        if not controllers_dir or not controllers_dir.is_dir():
            continue
        for root, _, files in os.walk(controllers_dir):
            for file in files:
                f_lower = file.lower()
                if f_lower.endswith(".f"):
                    continue
                if not f_lower.endswith(".xml"):
                    continue
                full_path = Path(root) / file
                try:
                    rel_path = full_path.relative_to(controllers_dir)
                except ValueError:
                    continue
                rel_str = str(rel_path).replace("\\", "/")
                rel_lower = rel_str.lower()
                if any(kw in rel_lower for kw in keywords):
                    found_set.add(rel_str)

    sorted_candidates = sorted(found_set, key=lambda s: s.lower())
    total_hits = len(sorted_candidates)
    truncated = False
    if total_hits > max_objects:
        return sorted_candidates[:max_objects], total_hits, True
    return sorted_candidates, total_hits, False


def compare_xml(
    project_source: str,
    project_target: str,
    object: str = "",
    seed: str = "",
    mode: str = "summary",
    xml_view: str = "original",
    ignore_line_endings: bool = True,
    ignore_whitespace: bool = False,
    max_diff_lines: int = 200,
    context_lines: int = 3,
    include_unified_diff: bool = False,
    include_text_snippets: bool = False,
    max_hunks_summary: int = 5,
    max_hunks_detail: int = 30,
    max_objects: int = 50,
    on_progress: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Compare XML files across two FastBusiness projects.
    Supports xml_view="original" (raw file) and xml_view="flat" (expanded entities).
    Supports discovery via seed keywords across Controllers directories.
    """
    xml_view = (xml_view or "original").strip().lower()
    if xml_view in ("raw",):
        xml_view = "original"
    elif xml_view in ("expanded",):
        xml_view = "flat"

    controllers_src = _resolve_controllers(project_source)
    if not controllers_src:
        return {
            "success": False,
            "kind": "xml",
            "role_source": "reference_clone_from",
            "role_target": "editing",
            "project_source": project_source,
            "project_target": project_target,
            "xml_view": xml_view,
            "error_code": "controllers_not_found",
            "error": f"Controllers directory not found for project_source: {project_source}",
            "summary": None,
            "compared": [],
            "message": f"Không tìm thấy thư mục Controllers của project_source: {project_source}",
            "next_actions": ["fix_paths"],
            "warnings": [],
        }

    controllers_tgt = _resolve_controllers(project_target)
    if not controllers_tgt:
        return {
            "success": False,
            "kind": "xml",
            "role_source": "reference_clone_from",
            "role_target": "editing",
            "project_source": project_source,
            "project_target": project_target,
            "xml_view": xml_view,
            "error_code": "controllers_not_found",
            "error": f"Controllers directory not found for project_target: {project_target}",
            "summary": None,
            "compared": [],
            "message": f"Không tìm thấy thư mục Controllers của project_target: {project_target}",
            "next_actions": ["fix_paths"],
            "warnings": [],
        }

    # Parse objects and seed
    explicit_objects = [o.strip() for o in re.split(r"[,;]+", object or "") if o.strip()]
    seed_clean = (seed or "").strip()
    seed_candidates: List[str] = []
    seed_hits_total = 0
    seed_truncated = False

    if seed_clean:
        seed_candidates, seed_hits_total, seed_truncated = scan_xml_seed_candidates(
            controllers_src=controllers_src,
            controllers_tgt=controllers_tgt,
            seed=seed_clean,
            max_objects=max_objects,
        )

    combined_objects: List[str] = []
    seen: Set[str] = set()
    for obj in explicit_objects:
        k = obj.replace("\\", "/").lower()
        if k not in seen:
            seen.add(k)
            combined_objects.append(obj)
    for cand in seed_candidates:
        k = cand.replace("\\", "/").lower()
        if k not in seen:
            seen.add(k)
            combined_objects.append(cand)

    truncated = seed_truncated
    if len(combined_objects) > max_objects:
        raw_objects = combined_objects[:max_objects]
        truncated = True
    else:
        raw_objects = combined_objects

    if not raw_objects:
        if seed_clean:
            return {
                "success": False,
                "kind": "xml",
                "role_source": "reference_clone_from",
                "role_target": "editing",
                "project_source": project_source,
                "project_target": project_target,
                "xml_view": xml_view,
                "seed": seed_clean,
                "error_code": "no_matching_objects",
                "error": f"No XML controller files matched seed: '{seed_clean}'",
                "summary": None,
                "compared": [],
                "message": f"Không tìm thấy file XML nào khớp với seed '{seed_clean}' trong thư mục Controllers của cả hai dự án.",
                "next_actions": ["check_seed_spelling", "specify_object_path"],
                "warnings": [],
            }
        return {
            "success": False,
            "kind": "xml",
            "role_source": "reference_clone_from",
            "role_target": "editing",
            "project_source": project_source,
            "project_target": project_target,
            "xml_view": xml_view,
            "error_code": "invalid_object",
            "error": "object and seed parameters are both empty",
            "summary": None,
            "compared": [],
            "message": "Thiếu tham số object (relative path XML) hoặc seed cho kind=xml.",
            "next_actions": ["fix_paths"],
            "warnings": [],
        }

    compared_items: List[Dict[str, Any]] = []
    missing_on_target: List[str] = []
    missing_on_source: List[str] = []
    missing_both: List[str] = []
    identical_list: List[str] = []
    different_list: List[str] = []
    errors_list: List[str] = []
    warnings_list: List[str] = []

    total_raw = len(raw_objects)
    for idx, raw_rel in enumerate(raw_objects, 1):
        if on_progress:
            pct = int(100 * (idx - 1) / max(1, total_raw))
            on_progress(pct, 100, f"Đang so sánh XML ({idx}/{total_raw}): {raw_rel}")
        try:
            rel_norm = _normalize_relative_xml(raw_rel)
        except ValueError as e:
            return {
                "success": False,
                "kind": "xml",
                "xml_view": xml_view,
                "error_code": "invalid_object",
                "error": str(e),
                "summary": None,
                "compared": [],
                "message": f"Đường dẫn object không hợp lệ: {raw_rel} ({e})",
                "next_actions": ["fix_paths"],
                "warnings": [],
            }

        # Gate .f: CẤM so sánh file .f mã hóa
        if rel_norm.lower().endswith(".f"):
            return {
                "success": False,
                "kind": "xml",
                "xml_view": xml_view,
                "error_code": "unsupported_extension_f",
                "error": f"Cannot compare .f encrypted file: {raw_rel}",
                "summary": None,
                "compared": [],
                "message": f"Không so sánh file đuôi .f (file mã hóa FBO): {raw_rel}. Tuyệt đối không chỉnh sửa hoặc giải mã file .f.",
                "next_actions": ["use_source_xml_instead", "fix_paths"],
                "warnings": [],
            }

        # Gate .ent / .txt: P0 chỉ hỗ trợ XML controller cho kind=xml
        if rel_norm.lower().endswith((".ent", ".txt")):
            return {
                "success": False,
                "kind": "xml",
                "xml_view": xml_view,
                "error_code": "invalid_object",
                "error": f"kind='xml' only supports XML controller files. For '{raw_rel}', please use kind='file' with absolute/UNC paths or kind='folder' for Include directory.",
                "summary": None,
                "compared": [],
                "message": f"kind='xml' chỉ hỗ trợ file XML controller. Với file '{raw_rel}', vui lòng dùng kind='file' kèm đường dẫn tuyệt đối hoặc kind='folder' cho thư mục Include.",
                "next_actions": ["use_kind_file", "fix_paths"],
                "warnings": [],
            }

        path_src = controllers_src / rel_norm
        path_tgt = controllers_tgt / rel_norm

        src_exists = path_src.exists() and path_src.is_file()
        tgt_exists = path_tgt.exists() and path_tgt.is_file()

        if not src_exists and not tgt_exists:
            missing_both.append(rel_norm)
            compared_items.append({
                "relative_path": rel_norm,
                "path_source": str(path_src),
                "path_target": str(path_tgt),
                "xml_view": xml_view,
                "status": "missing_both",
                "error": "File not found on source nor target",
                "next_actions": ["investigate_object_name", "fix_paths"],
            })
            continue

        if src_exists and not tgt_exists:
            missing_on_target.append(rel_norm)
            compared_items.append({
                "relative_path": rel_norm,
                "path_source": str(path_src),
                "path_target": str(path_tgt),
                "xml_view": xml_view,
                "status": "missing_on_target",
                "next_actions": ["copy_missing_to_target"],
            })
            continue

        if not src_exists and tgt_exists:
            missing_on_source.append(rel_norm)
            compared_items.append({
                "relative_path": rel_norm,
                "path_source": str(path_src),
                "path_target": str(path_tgt),
                "xml_view": xml_view,
                "status": "missing_on_source",
                "next_actions": ["investigate_source"],
            })
            continue

        # Both exist
        if xml_view == "original":
            res_file = compare_files(
                file_a=str(path_src),
                file_b=str(path_tgt),
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
            content = res_file.get("content", {})
            content["line_basis"] = "original"


            item = {
                "relative_path": rel_norm,
                "path_source": str(path_src),
                "path_target": str(path_tgt),
                "xml_view": "original",
                **res_file,
                "content": content,
            }
            compared_items.append(item)

            if item["status"] == "identical":
                identical_list.append(rel_norm)
            else:
                different_list.append(rel_norm)

        else:
            # xml_view == "flat": expand entities
            meta_a, _, _, warn_a = get_file_meta_and_bytes(str(path_src))
            meta_b, _, _, warn_b = get_file_meta_and_bytes(str(path_tgt))

            meta_diff: List[str] = []
            if meta_a.size != meta_b.size:
                meta_diff.append("size")
            if meta_a.modified != meta_b.modified:
                meta_diff.append("modified")
            if meta_a.sha256 != meta_b.sha256:
                meta_diff.append("sha256")

            # Expand flat xml
            flat_text_a = ""
            flat_text_b = ""
            flat_failed = False
            flat_err = ""

            try:
                flat_text_a = flat_xml(str(path_src))
                flat_text_b = flat_xml(str(path_tgt))
            except Exception as ex:

                flat_failed = True
                flat_err = str(ex)

            if flat_failed or not flat_text_a or not flat_text_b:
                err_msg = f"flat_failed: {flat_err or 'unable to expand entities'}"
                errors_list.append(f"{rel_norm}: {err_msg}")
                warnings_list.append(f"{rel_norm}: {err_msg}")
                compared_items.append({
                    "relative_path": rel_norm,
                    "path_source": str(path_src),
                    "path_target": str(path_tgt),
                    "xml_view": "flat",
                    "status": "error",
                    "error": err_msg,
                    "message": err_msg,
                    "file_a": meta_a.to_dict(),
                    "file_b": meta_b.to_dict(),
                    "next_actions": ["retry_xml_view_original"],
                })
                continue

            lines_a = normalize_text_lines(
                flat_text_a,
                ignore_line_endings=ignore_line_endings,
                ignore_whitespace=ignore_whitespace,
            )
            lines_b = normalize_text_lines(
                flat_text_b,
                ignore_line_endings=ignore_line_endings,
                ignore_whitespace=ignore_whitespace,
            )

            identical_content = lines_a == lines_b

            if identical_content:
                status = "identical"
                identical_list.append(rel_norm)
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
                different_list.append(rel_norm)
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
                    file_label_a=f"{path_src} (flat)",
                    file_label_b=f"{path_tgt} (flat)",
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
            content_dict["line_basis"] = "flat"

            item = {
                "relative_path": rel_norm,
                "path_source": str(path_src),
                "path_target": str(path_tgt),
                "xml_view": "flat",
                "status": status,
                "identical_content": identical_content,
                "identical_meta": meta_a.sha256 == meta_b.sha256,
                "only_line_ending_diff": False,
                "file_a": meta_a.to_dict(),
                "file_b": meta_b.to_dict(),
                "meta_diff": meta_diff,
                "content": content_dict,
                "next_actions": next_actions,
            }
            compared_items.append(item)

    top_actions: List[str] = []
    if errors_list:
        top_actions.append("retry_xml_view_original")
    if missing_on_target:
        top_actions.append("copy_missing_to_target")
    if different_list:
        top_actions.append("review_hunks")
        top_actions.append("edit_target_file")
    if missing_on_source:
        top_actions.append("investigate_source")
    if missing_both:
        top_actions.append("investigate_object_name")
    if not top_actions:
        top_actions = ["noop"]

    if truncated:
        warnings_list.append(
            f"Số lượng file XML vượt quá max_objects ({max_objects}), đã giới hạn {len(raw_objects)} file để so sánh."
        )

    src_name = Path(project_source).name or project_source
    tgt_name = Path(project_target).name or project_target
    mode_label = "flat (đã expand entity)" if xml_view == "flat" else "original (file gốc)"
    msg_parts = []
    if seed_clean:
        msg_parts.append(f"Tìm thấy {seed_hits_total} file XML từ seed '{seed_clean}'.")
    msg_parts.append(f"So {tgt_name} (đang sửa) với {src_name} (nguồn clone) [{mode_label}]:")
    if missing_on_target:
        msg_parts.append(f"{tgt_name} thiếu {len(missing_on_target)} XML (cần copy/clone từ nguồn),")
    if different_list:
        msg_parts.append(f"{len(different_list)} XML khác nhau (xem hunks ranges, không dán code),")
    if identical_list:
        diff_meta_cnt = sum(1 for it in compared_items if it.get("status") == "identical" and it.get("meta_diff"))
        if diff_meta_cnt > 0:
            msg_parts.append(f"{len(identical_list)} giống nhau về nội dung ({diff_meta_cnt} file khác metadata),")
        else:
            msg_parts.append(f"{len(identical_list)} giống nhau hoàn toàn,")
    if missing_on_source:
        msg_parts.append(f"{len(missing_on_source)} thiếu trên nguồn ({src_name}),")
    if missing_both:
        msg_parts.append(f"{len(missing_both)} không tìm thấy trên cả hai bên.")
    message = " ".join(msg_parts).rstrip(",")

    summary_dict: Dict[str, Any] = {
        "missing_on_target": missing_on_target,
        "missing_on_source": missing_on_source,
        "missing_both": missing_both,
        "identical": identical_list,
        "different": different_list,
        "errors": errors_list,
        "truncated": truncated,
        "counts": {
            "missing_on_target": len(missing_on_target),
            "missing_on_source": len(missing_on_source),
            "missing_both": len(missing_both),
            "identical": len(identical_list),
            "different": len(different_list),
            "errors": len(errors_list),
        },
    }
    if seed_clean:
        summary_dict["seed_hits"] = seed_hits_total

    return {
        "success": True,
        "kind": "xml",
        "role_source": "reference_clone_from",
        "role_target": "editing",
        "project_source": project_source,
        "project_target": project_target,
        "xml_view": xml_view,
        "mode": mode,
        "seed": seed_clean if seed_clean else "",
        "summary": summary_dict,
        "compared": compared_items,
        "message": message,
        "next_actions": top_actions,
        "warnings": warnings_list,
        "error_code": None,
        "error": None,
    }

