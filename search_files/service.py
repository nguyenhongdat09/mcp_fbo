"""Service implementation for search_files tool."""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Dict, List


def _expand_brace_pattern(pattern: str) -> List[str]:
    """Expand pattern with braces like '*.{xml,js}' into ['*.xml', '*.js']."""
    match = re.search(r"\{([^}]+)\}", pattern)
    if not match:
        return [pattern]
    prefix = pattern[: match.start()]
    suffix = pattern[match.end() :]
    options = match.group(1).split(",")
    expanded = []
    for opt in options:
        sub = prefix + opt.strip() + suffix
        expanded.extend(_expand_brace_pattern(sub))
    return expanded


def _parse_globs(glob_str: str) -> List[str]:
    """Parse comma-separated glob string with brace expansion."""
    if not glob_str:
        return []
    expanded = _expand_brace_pattern(glob_str.strip())
    results = []
    for item in expanded:
        for part in item.split(","):
            p = part.strip()
            if p:
                results.append(p)
    return results


def _is_binary(chunk: bytes) -> bool:
    """Detect if chunk contains null bytes, indicating binary content."""
    return b"\x00" in chunk


def _matches_globs(rel_path: str, include_globs: List[str], exclude_globs: List[str]) -> bool:
    """Check if rel_path matches any include glob and no exclude glob."""
    basename = os.path.basename(rel_path)
    norm_rel = rel_path.replace("\\", "/").strip("/")
    parts = norm_rel.split("/")

    for pat in exclude_globs:
        p = pat.replace("\\", "/").strip("/")
        p_clean = p.replace("**/", "").replace("/**", "").strip("*")
        if p_clean and p_clean in parts:
            return False
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(norm_rel, pat):
            return False
        if pat.startswith("**/") and fnmatch.fnmatch(norm_rel, pat[3:]):
            return False

    if not include_globs or include_globs == ["*"]:
        return True

    for pat in include_globs:
        if fnmatch.fnmatch(basename, pat) or fnmatch.fnmatch(norm_rel, pat):
            return True
        if pat.startswith("**/") and fnmatch.fnmatch(norm_rel, pat[3:]):
            return True

    return False


def search_files(
    root: str,
    pattern: str,
    regex: bool = False,
    include_glob: str = "*.{xml,aspx,js,html,config,ent,txt,sql}",
    exclude_glob: str = "**/*.f,**/*.dll,**/*.pdb,**/bin/**",
    recursive: bool = True,
    case_sensitive: bool = False,
    max_files: int = 50,
    max_matches_per_file: int = 5,
    max_total_matches: int = 100,
    context_lines: int = 0,
    prefer_name_match: bool = True,
) -> Dict[str, Any]:
    """
    Search text in files under a directory (local or UNC).
    
    Denies reading *.f files, skips binary files.
    Sorts candidates with priority to avoid missing matches before hitting max_files quota.
    """
    warnings: List[str] = []
    if not root or not str(root).strip():
        return {
            "success": False,
            "error_code": "invalid_root",
            "message": "root is required",
            "warnings": warnings,
        }

    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        return {
            "success": False,
            "error_code": "root_not_found",
            "message": f"root directory not found or not a directory: {root}",
            "warnings": warnings,
        }

    if not pattern:
        return {
            "success": False,
            "error_code": "invalid_pattern",
            "message": "pattern is required",
            "warnings": warnings,
        }

    inc_patterns = _parse_globs(include_glob)
    exc_patterns = _parse_globs(exclude_glob)
    # Ensure *.f is excluded
    if not any(p.lower() == "*.f" for p in exc_patterns):
        exc_patterns.append("*.f")

    # Prepare searcher
    regex_compiled = None
    if regex:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex_compiled = re.compile(pattern, flags)
        except re.error as e:
            return {
                "success": False,
                "error_code": "invalid_regex",
                "message": f"Invalid regular expression '{pattern}': {e}",
                "warnings": warnings,
            }
    else:
        needle = pattern if case_sensitive else pattern.lower()

    # 1. Collect all candidates matching globs and not *.f
    candidates: List[tuple[str, str]] = []  # (rel_path, abs_file)
    if recursive:
        walker = os.walk(str(root_path))
    else:
        try:
            entries = list(os.scandir(str(root_path)))
            walker = [(str(root_path), [], [e.name for e in entries if e.is_file()])]
        except Exception as e:
            return {
                "success": False,
                "error_code": "scan_error",
                "message": str(e),
                "warnings": warnings,
            }

    for dirpath, _, filenames in walker:
        for fname in sorted(filenames):
            if fname.lower().endswith(".f"):
                continue

            abs_file = os.path.join(dirpath, fname)
            try:
                rel_path = os.path.relpath(abs_file, str(root_path)).replace("\\", "/")
            except Exception:
                rel_path = fname

            if _matches_globs(rel_path, inc_patterns, exc_patterns):
                candidates.append((rel_path, abs_file))

    files_candidate = len(candidates)

    # 2. Priority sort candidates
    if prefer_name_match:
        if regex:
            tokens = re.findall(r"[a-zA-Z0-9_]+", pattern)
            pattern_sub = tokens[0].lower() if tokens else ""
        else:
            pattern_sub = pattern if case_sensitive else pattern.lower()

        ext_priority = {
            ".js": 0,
            ".xml": 1,
            ".aspx": 2,
            ".html": 3,
            ".txt": 4,
            ".ent": 5,
            ".config": 6,
            ".sql": 10,
        }

        key_dirs = ["filter/", "grid/", "dir/", "clientscript/", "main/", "templates/"]

        def candidate_sort_key(item: tuple[str, str]) -> tuple:
            rel_p = item[0]
            check_rel = rel_p if case_sensitive else rel_p.lower()
            base = os.path.basename(check_rel)

            # Priority 0: Name / path match with pattern_sub
            if pattern_sub:
                if pattern_sub in base:
                    p0 = 0
                elif pattern_sub in check_rel:
                    p0 = 1
                else:
                    p0 = 2
            else:
                p0 = 2

            # Priority 1: High priority extensions
            ext = os.path.splitext(base)[1].lower()
            p1 = ext_priority.get(ext, 8)

            # Priority 2: Key directories & FastBusiness custom prefix (z*, zc*, zf*, zs*)
            p_in_key = 0 if any(kd in check_rel for kd in key_dirs) else 1
            p_custom = 0 if base.startswith(("z", "zc", "zf", "zs")) else 1
            p2 = 99
            for idx, kd in enumerate(key_dirs):
                if kd in check_rel:
                    p2 = idx
                    break

            # Priority 3: Alphabetical POSIX relative path
            return (p0, p1, p_in_key, p_custom, p2, rel_p.lower())

        candidates.sort(key=candidate_sort_key)
    else:
        candidates.sort(key=lambda item: item[0].lower())

    matches: List[Dict[str, Any]] = []
    files_scanned = 0
    truncated = False
    truncated_reason: str | None = None

    # 3. Search contents
    for rel_path, abs_file in candidates:
        if files_scanned >= max_files:
            truncated = True
            truncated_reason = "max_files"
            break

        # Read and search file
        try:
            with open(abs_file, "rb") as f_in:
                sample = f_in.read(4096)
                if _is_binary(sample):
                    continue
                f_in.seek(0)
                raw_bytes = f_in.read()

            # Decode
            text = None
            for enc in ("utf-8", "utf-8-sig", "cp1258"):
                try:
                    text = raw_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    pass
            if text is None:
                text = raw_bytes.decode("utf-8", errors="replace")

            lines = text.splitlines()
            files_scanned += 1
            file_matches_count = 0

            for idx, line in enumerate(lines, 1):
                matched = False
                if regex_compiled:
                    if regex_compiled.search(line):
                        matched = True
                else:
                    target_line = line if case_sensitive else line.lower()
                    if needle in target_line:
                        matched = True

                if matched:
                    preview = line.strip()
                    if len(preview) > 300:
                        preview = preview[:300] + "..."

                    match_item: Dict[str, Any] = {
                        "path": rel_path,
                        "line": idx,
                        "preview": preview,
                    }

                    if context_lines > 0:
                        start_ctx = max(0, idx - 1 - context_lines)
                        end_ctx = min(len(lines), idx + context_lines)
                        match_item["context"] = [
                            {"line": c_idx + 1, "text": lines[c_idx]}
                            for c_idx in range(start_ctx, end_ctx)
                        ]

                    matches.append(match_item)
                    file_matches_count += 1

                    if len(matches) >= max_total_matches:
                        truncated = True
                        truncated_reason = "max_total_matches"
                        break

                    if file_matches_count >= max_matches_per_file:
                        break

            if len(matches) >= max_total_matches:
                break

        except Exception as ex:
            warnings.append(f"Error reading {rel_path}: {ex}")

    if truncated and truncated_reason == "max_files":
        not_opened = max(0, files_candidate - files_scanned)
        warnings.append(
            f"Reached max_files ({files_scanned}); {not_opened} candidates not opened "
            f"(files_candidate={files_candidate}). Narrow root/include_glob or raise max_files."
        )
        if not matches:
            warnings.append(
                'No matches in scanned files; remaining candidates were not opened — '
                'do not conclude "not found" without narrowing root/glob or increasing max_files.'
            )
    elif truncated and truncated_reason == "max_total_matches":
        warnings.append(f"Reached max_total_matches limit ({max_total_matches})")

    return {
        "success": True,
        "root": str(root_path).replace("\\", "/"),
        "pattern": pattern,
        "matches": matches,
        "files_scanned": files_scanned,
        "files_candidate": files_candidate,
        "total_matches": len(matches),
        "truncated": truncated,
        "truncated_reason": truncated_reason,
        "warnings": warnings,
    }
