"""API chính: file_path + entity names → nội dung hoặc path entity (lxml, không cần .exe)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .entity_cache import normalize_entity_name
from .facade import resolve_entities


_config: dict | None = None


def set_config(config: dict | None) -> None:
    global _config
    _config = config


def normalize_modes(mode: str | list[str] | None) -> set[str]:
    """Chuẩn hóa mode MCP → {'content'} và/hoặc {'path'}."""
    if mode is None:
        return {"content"}

    items = [mode] if isinstance(mode, str) else list(mode)
    result: set[str] = set()
    for item in items:
        value = (item or "").strip().lower()
        if value in ("content", "0"):
            result.add("content")
        elif value in ("path", "1"):
            result.add("path")
    return result or {"content"}


def _entity_to_content_dict(record: dict) -> dict[str, Any]:
    content = record.get("value") or ""
    if not content and record.get("sourceFile"):
        from .entity_resolver import read_file_content
        content = read_file_content(record.get("sourceFile")) or ""
    return {
        "name": record.get("name"),
        "found": True,
        "content": content,
    }


def _entity_to_path_dict(record: dict) -> dict[str, Any]:
    declared_in_file = record.get("declaredInFile") or record.get("sourceFile") or ""
    declared_line = record.get("line") or -1
    source_file = record.get("sourceFile") or ""
    
    watch_set = set()
    if declared_in_file:
        watch_set.add(declared_in_file)
    if source_file:
        watch_set.add(source_file)
        
    return {
        "name": record.get("name"),
        "found": bool(declared_in_file),
        "source_file": source_file,
        "line": declared_line,
        "declared_in_file": declared_in_file,
        "declared_line": declared_line,
        "system_file": record.get("systemUrl") or "",
        "watch_files": list(watch_set),
    }


def get_xml_entities(
    file_path: str,
    entities: list[str] | None = None,
    *,
    mode: str | list[str] | None = "content",
    force_reload: bool = False,
    list_all: bool = False,
    config: dict | None = None,
) -> dict[str, Any]:
    """
    Đọc XML entity trực tiếp bằng lxml (parse DTD + external .ent).

    Args:
        file_path: Đường dẫn file XML (.xml, .f, ...)
        entities: Danh sách tên entity (có hoặc không có &...;)
        mode: "content" (mode 0), "path" (mode 1), hoặc ["content", "path"]
        force_reload: Bỏ cache parse trong memory và parse lại
        list_all: Chỉ trả danh sách tên entity (chỉ mode content)
        config: Giữ để tương thích MCP (không còn dùng ReadXML.exe)
    """
    _ = config if config is not None else _config
    modes = normalize_modes(mode)
    want_content = "content" in modes
    want_path = "path" in modes

    file_path = str(file_path or "").strip()
    if not file_path:
        return {"success": False, "error": "file_path is required"}

    xml_path = Path(file_path)
    if not xml_path.is_file():
        return {"success": False, "error": f"File không tồn tại: {file_path}", "file_path": file_path}

    if list_all and not want_content:
        return {
            "success": False,
            "error": "list_all chỉ dùng với mode=content",
            "file_path": file_path,
        }

    if want_path and not entities:
        return {
            "success": False,
            "error": "mode=path cần truyền entities (array tên entity)",
            "file_path": file_path,
        }

    if not list_all and not entities and want_content and not want_path:
        return {
            "success": False,
            "error": "Cần truyền entities (array) hoặc list_all=true",
            "file_path": file_path,
        }

    requested = entities or []
    normalized_names = [normalize_entity_name(raw_name) for raw_name in requested]
    normalized_names = [name for name in normalized_names if name]

    try:
        res = resolve_entities(str(xml_path), force_reload=force_reload)
        all_entities = {}
        for name, ent in res["system_entities"].items():
            ent_copy = ent.copy()
            ent_copy["name"] = name
            all_entities[name] = ent_copy
    except Exception as exc:
        return {
            "success": False,
            "error": f"Lỗi parse XML entity: {exc}",
            "file_path": file_path,
            "mode": sorted(modes),
        }

    base_result: dict[str, Any] = {
        "success": True,
        "file_path": file_path,
        "mode": sorted(modes),
        "reloaded": force_reload,
        "entity_count": len(all_entities),
    }

    if want_content:
        if list_all:
            base_result["list_all"] = True
            base_result["entity_names"] = list(all_entities.keys())
            if not want_path:
                return base_result

        if normalized_names:
            content_results: list[dict[str, Any]] = []
            for norm in normalized_names:
                hit = all_entities.get(norm)
                if hit:
                    content_results.append(_entity_to_content_dict(hit))
                else:
                    content_results.append(
                        {
                            "name": norm,
                            "found": False,
                            "content": "",
                            "hint": "Entity không có trong DTD của file XML.",
                        }
                    )
            base_result["entities"] = content_results

    if want_path:
        path_results: list[dict[str, Any]] = []
        for norm in normalized_names:
            hit = all_entities.get(norm)
            if hit:
                path_results.append(_entity_to_path_dict(hit))
            else:
                path_results.append(
                    {
                        "name": norm,
                        "found": False,
                        "source_file": "",
                        "line": -1,
                        "hint": "Entity không có trong DTD của file XML.",
                    }
                )
        base_result["entity_paths"] = path_results

    return base_result
