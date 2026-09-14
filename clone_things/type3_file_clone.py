"""Module handling clone_things type=3 (file clone between projects).

Copies files (relative, list, glob, presets) from project_source to project_target.
Defaults to dry-run (execute=False).
Defaults to no overwrite (overwrite=False) for existing files, prompting user confirmation.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from find_connect_by_path.path_resolver import get_project_root_from_path

logger = logging.getLogger("clone_things.type3")

# Whitelist preset definitions
PRESETS: dict[str, list[str]] = {
    "mail": [
        "bin/fsdMail.dll",
        "bin/callMailXS.dll",
        "bin/clsFileUpload.dll",
        "bin/zcCallMail.dll",
        "Main/Uploads/AjaxWeb.aspx",
        "Main/Uploads/AjaxWeb_Core.aspx",
        "ClientScript/jAjax.js",
    ],
}

HASH_MAX_BYTES = 32 * 1024 * 1024  # 32 MB


def coerce_bool(val: Any) -> bool:
    """Coerce boolean from string, int, or bool."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    return False


def to_posix(path_str: str | Path) -> str:
    """Convert path to forward slash POSIX style."""
    return str(path_str).replace("\\", "/")


def resolve_project_root(path_str: str) -> str | None:
    """
    Resolve project root using get_project_root_from_path with fallback.

    Fallback: if get_project_root_from_path returns None and path is an existing
    directory, return resolved directory path (essential for pytest tmp_path).
    """
    if not path_str or not str(path_str).strip():
        return None

    try:
        resolved_root = get_project_root_from_path(path_str)
        if resolved_root:
            return to_posix(Path(resolved_root).resolve())

        p = Path(path_str).resolve()
        if p.is_dir():
            return to_posix(p)
    except Exception as e:
        logger.warning("Error resolving project root for %s: %e", path_str, e)

    return None


def calculate_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def expand_object_tokens(
    object_str: str,
    root_source: str,
) -> tuple[list[str] | None, str | None, list[str]]:
    """
    Parse and expand object tokens token-first.

    Returns:
        (unique_relative_paths, error_code, warnings)
    """
    warnings: list[str] = []
    if not object_str or not str(object_str).strip():
        return None, "invalid_object", warnings

    # 1. Split tokens by ',', ';', or '\n'
    raw_tokens = []
    for line in str(object_str).splitlines():
        for semi in line.split(";"):
            for part in semi.split(","):
                token = part.strip()
                if token:
                    raw_tokens.append(token)

    if not raw_tokens:
        return None, "invalid_object", warnings

    expanded_paths: list[str] = []
    root_src_path = Path(root_source).resolve()

    single_token_candidate_unknown: str | None = None
    has_any_valid_path = False

    for token in raw_tokens:
        # a. Explicit preset prefix: preset:<name>
        if token.lower().startswith("preset:"):
            preset_name = token[len("preset:") :].strip().lower()
            if preset_name in PRESETS:
                expanded_paths.extend(PRESETS[preset_name])
                has_any_valid_path = True
            else:
                return None, "unknown_preset", warnings
            continue

        # b. Registered preset name alone (e.g. 'mail')
        if token.lower() in PRESETS:
            expanded_paths.extend(PRESETS[token.lower()])
            has_any_valid_path = True
            continue

        # c. Glob pattern: contains * or ?
        if "*" in token or "?" in token:
            norm_pat = token.replace("\\", "/").lstrip("/")
            # Check for path escape in glob
            if ".." in norm_pat.split("/"):
                return None, "path_outside_project", warnings

            try:
                matched_files = [
                    f
                    for f in root_src_path.glob(norm_pat)
                    if f.is_file()
                ]
                if not matched_files:
                    warnings.append(f"no_files_matched_glob: {token}")
                for mf in matched_files:
                    try:
                        rel = mf.relative_to(root_src_path).as_posix()
                        expanded_paths.append(rel)
                        has_any_valid_path = True
                    except ValueError:
                        return None, "path_outside_project", warnings
            except Exception as e:
                warnings.append(f"glob_error for '{token}': {e}")
            continue

        # d. Relative / absolute path or single word check
        norm_token = token.replace("\\", "/").strip()

        # Check path escape
        parts = norm_token.split("/")
        if ".." in parts:
            return None, "path_outside_project", warnings

        token_path = Path(token)
        if token_path.is_absolute():
            try:
                rel = token_path.resolve().relative_to(root_src_path).as_posix()
                expanded_paths.append(rel)
                has_any_valid_path = True
                continue
            except ValueError:
                return None, "path_outside_project", warnings

        # Single word check: no slash, no file extension
        has_slash = "/" in norm_token
        has_ext = bool(token_path.suffix)

        if not has_slash and not has_ext:
            # Check if exists on source disk
            candidate_file = root_src_path / norm_token
            if candidate_file.exists():
                expanded_paths.append(norm_token)
                has_any_valid_path = True
            else:
                single_token_candidate_unknown = token
            continue

        # Normal relative path
        rel = norm_token.lstrip("/")
        expanded_paths.append(rel)
        has_any_valid_path = True

    # If single token candidate unknown was encountered and no other valid path found
    if single_token_candidate_unknown and not has_any_valid_path:
        return None, "unknown_preset", warnings

    # Deduplicate preserving order
    seen: set[str] = set()
    unique_paths: list[str] = []
    for p in expanded_paths:
        norm_p = to_posix(p).lstrip("/")
        if norm_p and norm_p not in seen:
            seen.add(norm_p)
            unique_paths.append(norm_p)

    if not unique_paths:
        if single_token_candidate_unknown:
            return None, "unknown_preset", warnings
        return None, "invalid_object", warnings

    return unique_paths, None, warnings


def run_type3_file_clone(
    object: str,
    project_source: str,
    project_target: str,
    execute: Any = False,
    overwrite: Any = False,
    warnings: list[str] | None = None,
    start_time: float | None = None,
) -> dict[str, Any]:
    """Execute type=3 file clone flow."""
    if warnings is None:
        warnings = []
    if start_time is None:
        start_time = time.perf_counter()

    exec_coerced = coerce_bool(execute)
    overwrite_coerced = coerce_bool(overwrite)

    # 1. Validation
    if not object or not str(object).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_object",
            "message": "object is required",
            "warnings": warnings,
        }

    if not project_source or not str(project_source).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_source",
            "message": "project_source is required",
            "warnings": warnings,
        }

    if not project_target or not str(project_target).strip():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_target",
            "message": "project_target is required when type=3",
            "warnings": warnings,
        }

    # Verify project paths are absolute
    if not Path(project_source).is_absolute():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_source",
            "message": "project_source must be an absolute path",
            "warnings": warnings,
        }

    if not Path(project_target).is_absolute():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_target",
            "message": "project_target must be an absolute path",
            "warnings": warnings,
        }

    # 2. Resolve roots
    root_src = resolve_project_root(project_source)
    if not root_src or not Path(root_src).exists():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_source",
            "message": f"Cannot resolve or find project_source root: {project_source}",
            "warnings": warnings,
        }

    root_tgt = resolve_project_root(project_target)
    if not root_tgt or not Path(root_tgt).exists():
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": "invalid_project_target",
            "message": f"Cannot resolve or find project_target root: {project_target}",
            "warnings": warnings,
        }

    root_src_path = Path(root_src)
    root_tgt_path = Path(root_tgt)

    # 3. Expand object tokens
    relative_paths, err_code, exp_warnings = expand_object_tokens(object, root_src)
    warnings.extend(exp_warnings)

    if err_code:
        return {
            "success": False,
            "spec_version": "1.0",
            "type": 3,
            "error_code": err_code,
            "message": f"Failed to expand object: {err_code}",
            "warnings": warnings,
        }

    assert relative_paths is not None

    planned: list[dict[str, Any]] = []
    will_copy: list[str] = []
    exists_on_target: list[dict[str, Any]] = []
    skipped_exists: list[str] = []
    skipped_denied: list[str] = []
    missing_on_source: list[str] = []
    copied: list[str] = []
    failed: list[dict[str, Any]] = []

    # 4. Plan and inspect each file
    for rel in relative_paths:
        src_file = root_src_path / rel
        tgt_file = root_tgt_path / rel

        # Check deny rule (*.f)
        if rel.lower().endswith(".f") or fnmatch.fnmatch(rel.lower(), "*.f"):
            planned_item = {
                "relative": rel,
                "status": "denied",
                "size_source": src_file.stat().st_size if src_file.is_file() else None,
                "size_target": tgt_file.stat().st_size if tgt_file.is_file() else None,
                "hash_source": None,
                "hash_target": None,
            }
            planned.append(planned_item)
            skipped_denied.append(rel)
            continue

        # Check source existence
        if not src_file.is_file():
            planned_item = {
                "relative": rel,
                "status": "missing_on_source",
                "size_source": None,
                "size_target": tgt_file.stat().st_size if tgt_file.is_file() else None,
                "hash_source": None,
                "hash_target": None,
            }
            planned.append(planned_item)
            missing_on_source.append(rel)
            continue

        # Source exists
        src_stat = src_file.stat()
        size_src = src_stat.st_size
        mtime_src = src_stat.st_mtime
        hash_src: str | None = None

        if size_src <= HASH_MAX_BYTES:
            try:
                hash_src = calculate_sha256(src_file)
            except Exception as e:
                warnings.append(f"hash_source_error for {rel}: {e}")
        else:
            warnings.append(
                f"hash_skipped_large_file: {rel} ({size_src} bytes > {HASH_MAX_BYTES})"
            )

        # Check target existence
        if not tgt_file.is_file():
            planned_item = {
                "relative": rel,
                "status": "missing_on_target",
                "size_source": size_src,
                "size_target": None,
                "hash_source": hash_src,
                "hash_target": None,
            }
            planned.append(planned_item)
            will_copy.append(rel)

            # Copy missing_on_target if execute=True
            if exec_coerced:
                try:
                    tgt_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, tgt_file)
                    copied.append(rel)
                except Exception as e:
                    failed.append({"relative": rel, "error": str(e)})
            continue

        # Target exists: determine content same vs different
        tgt_stat = tgt_file.stat()
        size_tgt = tgt_stat.st_size
        mtime_tgt = tgt_stat.st_mtime
        hash_tgt: str | None = None
        content_diff: str = "different"

        if size_src <= HASH_MAX_BYTES and size_tgt <= HASH_MAX_BYTES:
            try:
                hash_tgt = calculate_sha256(tgt_file)
                content_diff = "same" if (hash_src and hash_tgt and hash_src == hash_tgt) else "different"
            except Exception as e:
                warnings.append(f"hash_target_error for {rel}: {e}")
        else:
            # Large file (>32MB): compare size and mtime difference < 1s
            if size_src == size_tgt and abs(mtime_src - mtime_tgt) < 1.0:
                content_diff = "same"
            else:
                content_diff = "different"

        planned_item = {
            "relative": rel,
            "status": "exists_on_target",
            "content": content_diff,
            "size_source": size_src,
            "size_target": size_tgt,
            "hash_source": hash_src,
            "hash_target": hash_tgt,
        }
        planned.append(planned_item)

        exist_info = {
            "relative": rel,
            "content": content_diff,
            "size_source": size_src,
            "size_target": size_tgt,
        }
        exists_on_target.append(exist_info)

        if overwrite_coerced:
            # Overwrite allowed!
            will_copy.append(rel)
            if exec_coerced:
                try:
                    tgt_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, tgt_file)
                    copied.append(rel)
                except Exception as e:
                    failed.append({"relative": rel, "error": str(e)})
        else:
            # Overwrite forbidden by default
            skipped_exists.append(rel)

    # 5. User prompt and Agent messages
    needs_user_confirm = bool(exists_on_target and not overwrite_coerced)

    if needs_user_confirm:
        diff_summaries = [f"{it['relative']} (content={it['content']})" for it in exists_on_target]
        user_prompt = (
            f"Các file sau ĐÃ CÓ trên project đích (không tự ghi đè): "
            f"{', '.join(diff_summaries)}. Bạn có muốn ghi đè không? Nếu có, Agent gọi lại "
            f"clone_things type=3 với execute=true và overwrite=true (object có thể chỉ các path được chọn)."
        )
        agent_message = (
            "Dry-run/execute xong phần thiếu. Có file đã tồn tại → PHẢI hỏi user trước khi overwrite=true. Không tự đè."
        )
    else:
        user_prompt = ""
        if not exec_coerced:
            agent_message = (
                f"Dry-run type=3: {len(will_copy)} file planned. Gọi lại execute=true sau khi user xác nhận."
            )
        else:
            agent_message = (
                f"Execute type=3 hoàn tất: {len(copied)} file copied, {len(failed)} failed."
            )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return {
        "success": True,
        "spec_version": "1.0",
        "type": 3,
        "mode": "file_clone",
        "project_source": root_src,
        "project_target": root_tgt,
        "object": object,
        "execute": exec_coerced,
        "overwrite": overwrite_coerced,
        "needs_user_confirm": needs_user_confirm,
        "planned": planned,
        "will_copy": will_copy,
        "exists_on_target": exists_on_target,
        "copied": copied,
        "skipped_exists": skipped_exists,
        "skipped_denied": skipped_denied,
        "missing_on_source": missing_on_source,
        "failed": failed,
        "warnings": warnings,
        "user_prompt": user_prompt,
        "agent_message": agent_message,
        "meta": {
            "execute": exec_coerced,
            "overwrite": overwrite_coerced,
            "file_count": len(planned),
            "hash_max_bytes": HASH_MAX_BYTES,
            "elapsed_ms": elapsed_ms,
        },
    }
