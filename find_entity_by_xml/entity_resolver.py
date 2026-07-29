"""
entity_resolver.py
Ported from entityResolver.js. Resolves FBO XML entities using FboEntParser.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .fbo_ent_parser import FboEntParser

# (normalized_path) -> (mtime, generalEntities, parameterEntities, overriddenEntities, fileMtimes)
_cache: dict[str, dict[str, Any]] = {}
_file_content_cache: dict[str, dict[str, Any]] = {}
MAX_FILE_CACHE_SIZE = 50


def uri_to_path(url: str) -> Path:
    if url.startswith("file:"):
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        if parsed.netloc:
            return Path(f"\\\\{parsed.netloc}{parsed.path}").resolve()
        else:
            path = parsed.path
            if path.startswith("/") and len(path) > 2 and path[2] == ":":
                path = path[1:]
            return Path(path).resolve()

    clean_url = url.replace("\\", "/")
    if len(clean_url) > 1 and clean_url[1] == ":":
        return Path(clean_url).resolve()
    return Path(url)


def read_file_content(file_path: str | Path) -> str | None:
    path_obj = Path(file_path)
    norm = str(path_obj.resolve()).lower()

    try:
        stat = path_obj.stat()
        mtime = stat.st_mtime
    except Exception:
        mtime = 0

    cached = _file_content_cache.get(norm)
    if cached and cached["mtime"] == mtime:
        # Move to end (LRU simulate)
        val = _file_content_cache.pop(norm)
        _file_content_cache[norm] = val
        return val["content"]

    try:
        raw_bytes = path_obj.read_bytes()
    except Exception:
        return None

    content = ""
    if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
        content = raw_bytes.decode("utf-16", errors="ignore")
    elif raw_bytes.startswith(b"\xef\xbb\xbf"):
        content = raw_bytes.decode("utf-8-sig", errors="ignore")
    else:
        try:
            content = raw_bytes.decode("utf-8")
            if "\x00" in content:
                content = raw_bytes.decode("utf-16", errors="ignore")
        except UnicodeDecodeError:
            try:
                content = raw_bytes.decode("utf-16", errors="ignore")
            except Exception:
                content = raw_bytes.decode("utf-8", errors="ignore")

    _file_content_cache[norm] = {"content": content, "mtime": mtime}
    if len(_file_content_cache) > MAX_FILE_CACHE_SIZE:
        oldest_key = next(iter(_file_content_cache))
        del _file_content_cache[oldest_key]

    return content


def get_file_mtime(file_path: str | Path) -> float:
    try:
        return Path(file_path).stat().st_mtime
    except Exception:
        return 0


def resolve_fbo_xml_entities(
    main_xml_path: str | Path,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], Dict[str, float]]:
    main_xml_path = Path(main_xml_path).resolve()
    main_xml_dir = main_xml_path.parent

    general_entities: dict[str, Any] = {}
    parameter_entities: dict[str, Any] = {}
    overridden_entities: list[dict[str, Any]] = []
    file_mtimes: dict[str, float] = {}

    def read_and_record_file(file_path: str) -> str | None:
        p = Path(file_path).resolve()
        norm = str(p).lower()
        file_mtimes[norm] = get_file_mtime(p)
        return read_file_content(p)

    def record_file_mtime(file_path: str) -> None:
        p = Path(file_path).resolve()
        norm = str(p).lower()
        file_mtimes[norm] = get_file_mtime(p)

    def resolve_path(current_file_path: str, target_url: str) -> str:
        clean_url = target_url.replace("\\", "/")
        if clean_url.startswith("file:///"):
            clean_url = clean_url[8:]
        elif clean_url.startswith("file:/"):
            clean_url = clean_url[6:]

        is_absolute = Path(clean_url).is_absolute() or (len(clean_url) > 1 and clean_url[1] == ":")
        if is_absolute:
            target_path = Path(clean_url).resolve()
        else:
            target_path = (Path(current_file_path).parent / clean_url).resolve()

        return str(target_path)

    parser = FboEntParser(
        read_file_fn=read_and_record_file,
        resolve_path_fn=resolve_path,
        record_file_mtime_fn=record_file_mtime,
    )

    if main_xml_path.exists():
        xml_content = read_and_record_file(str(main_xml_path))
        if xml_content:
            doctype_match = re.search(r"<!DOCTYPE\s+\w+[\s\S]*?\[([\s\S]*?)\]\s*>", xml_content, re.IGNORECASE)
            if doctype_match:
                dtd_block = doctype_match.group(1)
                prefix_match = re.search(r"<!DOCTYPE\s+\w+[\s\S]*?\[", xml_content, re.IGNORECASE)
                prefix = prefix_match.group(0) if prefix_match else ""

                parent_lines_before = xml_content[: doctype_match.start()].count("\n")
                prefix_lines = prefix.count("\n")
                dtd_line_offset = parent_lines_before + prefix_lines

                res = parser.parse_content(
                    dtd_block,
                    str(main_xml_path),
                    dtd_line_offset,
                    seed_params=parameter_entities,
                    seed_general=general_entities,
                    seed_overridden=overridden_entities,
                )

                general_entities.update(res["generalEntities"])
                parameter_entities.update(res["paramEntities"])
                overridden_entities.clear()
                overridden_entities.extend(res["overriddenEntities"])

    return general_entities, parameter_entities, overridden_entities, file_mtimes


def get_entities_for_file(
    file_path: str | Path, force_reload: bool = False, target_entity: str | None = None
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, float]]:
    p = Path(file_path).resolve()
    norm = str(p).lower()
    
    import time

    cached = _cache.get(norm)
    if not force_reload and cached:
        now = time.time()
        # Debounce stat if checked recently (< 1.0 second)
        if cached.get("last_checked") and now - cached["last_checked"] < 1.0:
            return (
                cached["generalEntities"],
                cached.get("parameterEntities", {}),
                cached.get("fileMtimes", {}),
            )
            
        is_valid = True
        if cached.get("fileMtimes"):
            for dep_path, old_mtime in cached["fileMtimes"].items():
                if get_file_mtime(dep_path) != old_mtime:
                    is_valid = False
                    _file_content_cache.pop(dep_path.lower(), None)
                    break
        if is_valid:
            cached["last_checked"] = now
            return (
                cached["generalEntities"],
                cached.get("parameterEntities", {}),
                cached.get("fileMtimes", {}),
            )
        else:
            del _cache[norm]
            _file_content_cache.pop(norm, None)

    general_entities, parameter_entities, overridden_entities, file_mtimes = resolve_fbo_xml_entities(p)

    _cache[norm] = {
        "generalEntities": general_entities,
        "parameterEntities": parameter_entities,
        "fileMtimes": file_mtimes,
        "overriddenEntities": overridden_entities,
        "last_checked": time.time(),
    }

    return general_entities, parameter_entities, file_mtimes


def clear_cache() -> None:
    _cache.clear()
    _file_content_cache.clear()
