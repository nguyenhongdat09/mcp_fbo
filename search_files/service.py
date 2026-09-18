"""Service implementation for search_files tool."""

from __future__ import annotations

import fnmatch
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from xml_fbograph.utils.any_path import project_switch_message, resolve_any_path


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


# Heuristic: pattern chứa metachar regex điển hình — | ( \b\d\s\w [class]
# {m,n} ^anchor $anchor. Chỉ dùng để WARN khi regex=false, không auto-promote
# (false-positive ở warn level là chấp nhận được — chỉ là hint).
_REGEX_LIKE_RE = re.compile(
    r"(\||\(|\\[bdswBDWS]|\[[^\]]*\]|\{[0-9,]+\}|\^[^ ]|\$)"
)


def _read_text_file(abs_file: str) -> str | None:
    """Đọc file text; None nếu binary thật hoặc lỗi. BOM check TRƯỚC binary check
    (UTF-16LE 'A'=41 00 → mọi file UTF-16 đều chứa \\x00 — không được coi là binary)."""
    from fastbusiness_mcp.utils.file_utils import decode_bytes, detect_bom_encoding

    with open(abs_file, "rb") as f_in:
        raw_bytes = f_in.read()
    if not raw_bytes:
        return ""
    if detect_bom_encoding(raw_bytes) is None and _is_binary(raw_bytes[:4096]):
        return None
    text, _enc = decode_bytes(raw_bytes)
    return text


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


def _definition_regexes(symbol: str) -> List[tuple[re.Pattern, str]]:
    """Build regexes tìm ĐỊNH NGHĨA symbol JS (escape ký tự đặc biệt như $)."""
    esc = re.escape(symbol)
    b = r"(?<![\w$])"
    return [
        (re.compile(b + r"function\s+" + esc + r"\s*\("), "function"),
        (re.compile(b + esc + r"\s*=\s*function\b"), "assign"),
        (re.compile(b + r"(?:var|let|const)\s+" + esc + r"\b"), "var"),
        (re.compile(b + r"window\." + esc + r"\s*="), "assign"),
        (re.compile(b + esc + r"\s*:\s*function\b"), "object_prop"),
        (re.compile(b + esc + r"\s*=\s*\{"), "var"),
        (re.compile(b + esc + r"\s*=\s*new\b"), "assign"),
    ]


def search_files(
    root: str,
    pattern: str = "",
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
    mode: str = "content",
    symbol: str = "",
    reference_file: str = "",
    include_definitions: bool = True,
    on_progress: Any = None,
    time_budget_seconds: float = 45.0,
    max_candidates: int = 30000,
) -> Dict[str, Any]:
    """
    Search text in files under a directory (local or UNC).

    Denies reading *.f files, skips binary files.
    Sorts candidates with priority to avoid missing matches before hitting max_files quota.
    mode: 'content' (grep thường) | 'definition' (tìm nơi định nghĩa symbol) | 'files_only' (chỉ list candidate).
    root nhận path bất kỳ: abs dir, abs file (search đúng file đó), hoặc relative
    (resolve qua reference_file / sticky project context).
    """
    warnings: List[str] = []
    regex_hint = False
    mode_norm = (mode or "content").strip().lower()
    if mode_norm not in {"content", "definition", "files_only", "references"}:
        return {
            "success": False,
            "error_code": "invalid_mode",
            "message": "mode phai la 'content', 'definition', 'files_only' hoac 'references'",
            "warnings": warnings,
        }

    if not root or not str(root).strip():
        return {
            "success": False,
            "error_code": "invalid_root",
            "message": "root is required",
            "warnings": warnings,
        }

    resolved = resolve_any_path(root, reference_file)
    if not resolved.ok:
        err = dict(resolved.error or {})
        err.setdefault("success", False)
        err.setdefault("project_root", resolved.project_root)
        err.setdefault("resolved_via", resolved.resolved_via)
        err["warnings"] = warnings
        return err

    # Sticky context visibility — echo project đã resolve + cảnh báo khi context trôi
    _switch_warn = project_switch_message(resolved.switched_from, resolved.project_root)
    if _switch_warn:
        warnings.append(_switch_warn)

    def _ctx(d: Dict[str, Any]) -> Dict[str, Any]:
        d.setdefault("project_root", resolved.project_root)
        d.setdefault("resolved_via", resolved.resolved_via)
        if regex_hint:
            d["regex_hint"] = True
        return d

    single_file: Path | None = None
    if resolved.kind == "file":
        single_file = Path(resolved.abs_path)
        root_path = single_file.parent
    else:
        root_path = Path(resolved.abs_path)

    if mode_norm == "content" and not pattern:
        return _ctx({
            "success": False,
            "error_code": "invalid_pattern",
            "message": "pattern is required",
            "warnings": warnings,
        })

    if mode_norm in ("definition", "references") and not (symbol or "").strip():
        return _ctx({
            "success": False,
            "error_code": "invalid_symbol",
            "message": "symbol is required when mode='definition'/'references'",
            "warnings": warnings,
        })

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
            return _ctx({
                "success": False,
                "error_code": "invalid_regex",
                "message": f"Invalid regular expression '{pattern}': {e}",
                "warnings": warnings,
            })
    else:
        needle = pattern if case_sensitive else pattern.lower()
        # Hint DX: pattern trông giống regex nhưng đang literal-search → warn,
        # KHÔNG auto-promote (literal semantics giữ nguyên).
        if mode_norm == "content" and pattern and _REGEX_LIKE_RE.search(pattern):
            regex_hint = True
            warnings.append(
                f"pattern_looks_like_regex: '{pattern}' chứa metachar regex "
                "nhưng đang literal-search (regex=false). Nếu ý đồ là regex "
                "→ gọi lại với regex=true."
            )

    # --- time budget + progress plumbing (UNC crawl có thể vượt client timeout) ---
    t0 = time.monotonic()
    deadline = t0 + time_budget_seconds if time_budget_seconds and time_budget_seconds > 0 else None
    timed_out = False

    def _report(done: int, total: int, msg: str = "") -> None:
        if on_progress:
            try:
                on_progress(done, total, msg)
            except Exception:
                pass

    def _deadline_hit() -> bool:
        return deadline is not None and time.monotonic() > deadline

    # Tên thư mục có thể prune khỏi os.walk: chỉ từ exclude glob dạng '**/<name>/**' hoặc '**/<name>'
    pruned_dir_names = set()
    for pat in exc_patterns:
        p = pat.replace("\\", "/").strip("/")
        m_dir = re.fullmatch(r"\*\*/([^/*?]+)(?:/\*\*)?", p)
        if m_dir:
            pruned_dir_names.add(m_dir.group(1).lower())

    # 1. Collect all candidates matching globs and not *.f
    candidates: List[tuple[str, str]] = []  # (rel_path, abs_file)
    enum_capped = False
    dirs_walked = 0
    if single_file is not None:
        # root là 1 file: search đúng file đó, bỏ glob (vẫn cấm *.f)
        if not single_file.name.lower().endswith(".f"):
            candidates.append((single_file.name, str(single_file)))
    else:
        if recursive:
            walker = os.walk(str(root_path))
            for dirpath, dirnames, filenames in walker:
                dirs_walked += 1
                if pruned_dir_names:
                    dirnames[:] = [
                        d for d in dirnames if d.lower() not in pruned_dir_names
                    ]
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
                        if len(candidates) >= max_candidates:
                            enum_capped = True
                            break
                if enum_capped or _deadline_hit():
                    break
                if dirs_walked % 50 == 0:
                    _report(dirs_walked, 0, f"Dang liet ke thu muc... ({len(candidates)} candidates)")
        else:
            try:
                entries = list(os.scandir(str(root_path)))
                walker = [(str(root_path), [], [e.name for e in entries if e.is_file()])]
            except Exception as e:
                return _ctx({
                    "success": False,
                    "error_code": "scan_error",
                    "message": str(e),
                    "warnings": warnings,
                })

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
                        if len(candidates) >= max_candidates:
                            enum_capped = True
                            break

    timed_out = timed_out or (deadline is not None and time.monotonic() > deadline)
    if timed_out:
        warnings.append(
            f"Enumeration dung som do time_budget_seconds={time_budget_seconds} "
            f"(dirs_walked={dirs_walked}, candidates={len(candidates)}). "
            "Ket qua PARTIAL — hep root hoac include_glob."
        )
    if enum_capped:
        warnings.append(
            f"Enumeration dung o max_candidates={max_candidates} "
            f"(dirs_walked={dirs_walked}). Ket qua PARTIAL — hep root/include_glob."
        )

    files_candidate = len(candidates)

    # 2. Priority sort candidates
    if prefer_name_match:
        sort_pattern = symbol if mode_norm in ("definition", "references") and symbol else pattern
        if regex and mode_norm == "content":
            tokens = re.findall(r"[a-zA-Z0-9_]+", sort_pattern)
            pattern_sub = tokens[0].lower() if tokens else ""
        else:
            pattern_sub = sort_pattern if case_sensitive else sort_pattern.lower()

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

    root_display = str(root_path).replace("\\", "/")

    # --- mode=files_only: chỉ list candidates, KHÔNG đọc nội dung ---
    if mode_norm == "files_only":
        max_list = 2000
        files = [rel for rel, _ in candidates]
        truncated = len(files) > max_list
        if truncated:
            files = files[:max_list]
            warnings.append(
                f"files list capped at {max_list} (files_candidate={files_candidate})"
            )
        return _ctx({
            "success": True,
            "mode": "files_only",
            "root": root_display,
            "files": files,
            "files_scanned": 0,
            "files_candidate": files_candidate,
            "truncated": truncated,
            "timed_out": timed_out,
            "warnings": warnings,
        })

    # --- mode=definition: tìm nơi ĐỊNH NGHĨA symbol JS ---
    if mode_norm == "definition":
        sym = symbol.strip()
        def_res = _definition_regexes(sym)
        definitions: List[Dict[str, Any]] = []
        usage_lines = 0
        usage_files = 0
        files_scanned = 0
        truncated = False

        for rel_path, abs_file in candidates:
            if files_scanned >= max_files or _deadline_hit():
                truncated = True
                break
            try:
                text = _read_text_file(abs_file)
                if text is None:
                    continue
                files_scanned += 1
                if files_scanned % 10 == 0:
                    _report(files_scanned, min(files_candidate, max_files), "Dang quet noi dung...")
                file_used = False
                for idx, line in enumerate(text.splitlines(), 1):
                    if sym in line:
                        usage_lines += 1
                        file_used = True
                    for rx, kind in def_res:
                        if rx.search(line):
                            preview = line.strip()
                            if len(preview) > 300:
                                preview = preview[:300] + "..."
                            definitions.append(
                                {
                                    "path": rel_path,
                                    "line": idx,
                                    "preview": preview,
                                    "kind": kind,
                                }
                            )
                            break
                if file_used:
                    usage_files += 1
            except Exception as ex:
                warnings.append(f"Error reading {rel_path}: {ex}")

        not_opened = max(0, files_candidate - files_scanned)
        if truncated and _deadline_hit():
            warnings.append(
                f"Dung som do time_budget_seconds={time_budget_seconds} sau {files_scanned} files "
                f"({not_opened} candidates chua mo). Ket qua PARTIAL — hep root/include_glob."
            )
        elif truncated:
            warnings.append(
                f"Reached max_files ({files_scanned}); {not_opened} candidates not opened "
                f"(files_candidate={files_candidate}). Narrow root/include_glob or raise max_files."
            )
        definition_found = bool(definitions)
        if not definition_found and truncated:
            warnings.append(
                f"Không kết luận symbol chưa định nghĩa — {not_opened} candidates chưa mở. "
                "Hẹp root/include_glob."
            )

        return _ctx({
            "success": True,
            "mode": "definition",
            "root": root_display,
            "symbol": sym,
            "definitions": definitions,
            "definition_found": definition_found,
            "usage_hint": f"{usage_lines} dòng usage ở {usage_files} file (mode='content' để xem)",
            "files_scanned": files_scanned,
            "files_candidate": files_candidate,
            "truncated": truncated,
            "timed_out": timed_out or _deadline_hit(),
            "warnings": warnings,
        })

    # --- mode=references: list usage file:line của symbol (phân biệt def vs usage) ---
    if mode_norm == "references":
        sym = symbol.strip()
        def_res = _definition_regexes(sym)
        definitions: List[Dict[str, Any]] = []
        usages: List[Dict[str, Any]] = []
        files_scanned = 0
        truncated = False
        truncated_reason: str | None = None

        for rel_path, abs_file in candidates:
            if files_scanned >= max_files:
                truncated = True
                truncated_reason = "max_files"
                break
            if _deadline_hit():
                truncated = True
                truncated_reason = "time_budget"
                break
            try:
                text = _read_text_file(abs_file)
                if text is None:
                    continue
                files_scanned += 1
                if files_scanned % 10 == 0:
                    _report(files_scanned, min(files_candidate, max_files), "Dang quet noi dung...")
                file_matches_count = 0
                for idx, line in enumerate(text.splitlines(), 1):
                    if sym not in line:
                        continue
                    kind = None
                    for rx, k in def_res:
                        if rx.search(line):
                            kind = k
                            break
                    preview = line.strip()
                    if len(preview) > 300:
                        preview = preview[:300] + "..."
                    if kind is not None:
                        definitions.append(
                            {
                                "path": rel_path,
                                "line": idx,
                                "preview": preview,
                                "kind": kind,
                            }
                        )
                    else:
                        usages.append(
                            {
                                "path": rel_path,
                                "line": idx,
                                "preview": preview,
                                "is_definition": False,
                            }
                        )
                    file_matches_count += 1
                    if len(usages) + len(definitions) >= max_total_matches:
                        truncated = True
                        truncated_reason = "max_total_matches"
                        break
                    if file_matches_count >= max_matches_per_file:
                        break
                if truncated:
                    break
            except Exception as ex:
                warnings.append(f"Error reading {rel_path}: {ex}")

        if truncated and truncated_reason == "max_files":
            not_opened = max(0, files_candidate - files_scanned)
            warnings.append(
                f"Reached max_files ({files_scanned}); {not_opened} candidates not opened "
                f"(files_candidate={files_candidate}). Narrow root/include_glob or raise max_files. "
                "Không kết luận ít usage khi truncated."
            )
        elif truncated and truncated_reason == "time_budget":
            warnings.append(
                f"Dung som do time_budget_seconds={time_budget_seconds} sau {files_scanned} files. "
                "Ket qua PARTIAL — hep root/include_glob."
            )
        elif truncated and truncated_reason == "max_total_matches":
            warnings.append(f"Reached max_total_matches limit ({max_total_matches})")

        result: Dict[str, Any] = {
            "success": True,
            "mode": "references",
            "root": root_display,
            "symbol": sym,
            "usages": usages,
            "usage_count": len(usages),
            "definition_count": len(definitions),
            "files_scanned": files_scanned,
            "files_candidate": files_candidate,
            "truncated": truncated,
            "timed_out": timed_out or _deadline_hit(),
            "warnings": warnings,
        }
        if include_definitions:
            result["definitions"] = definitions
        if truncated_reason:
            result["truncated_reason"] = truncated_reason
        return _ctx(result)

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
        if _deadline_hit():
            truncated = True
            truncated_reason = "time_budget"
            break

        # Read and search file
        try:
            text = _read_text_file(abs_file)
            if text is None:
                continue

            lines = text.splitlines()
            files_scanned += 1
            if files_scanned % 10 == 0:
                _report(files_scanned, min(files_candidate, max_files), "Dang quet noi dung...")
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
    elif truncated and truncated_reason == "time_budget":
        warnings.append(
            f"Dung som do time_budget_seconds={time_budget_seconds} sau {files_scanned} files. "
            "Ket qua PARTIAL — hep root/include_glob."
        )
    elif truncated and truncated_reason == "max_total_matches":
        warnings.append(f"Reached max_total_matches limit ({max_total_matches})")

    return _ctx({
        "success": True,
        "root": str(root_path).replace("\\", "/"),
        "pattern": pattern,
        "matches": matches,
        "files_scanned": files_scanned,
        "files_candidate": files_candidate,
        "total_matches": len(matches),
        "truncated": truncated,
        "truncated_reason": truncated_reason,
        "timed_out": timed_out or _deadline_hit(),
        "warnings": warnings,
    })
