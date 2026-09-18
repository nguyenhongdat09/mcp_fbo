"""check_entities — port checkEntityErrors từ entityResolverChecking.js.

Kiểm tra 1 nhóm file XML FBO:
- SYSTEM entity trỏ file không tồn tại (missing_files / table1).
- &name; dùng (transitive) mà không khai báo trong DOCTYPE (undeclared_entities).
- source_roots: file/entity thiếu nhưng có sẵn ở project NGUỒN → status='ok' /
  source_index + source_label 'Nguồn N'.
"""

from __future__ import annotations

import os
from typing import Any

from .entity_usage import get_transitively_used_entities
from .file_resolver import resolve_checking_files
from .path_helper import (
    find_in_sources_by_relative,
    get_relative_after_project,
    get_xml_short_name,
    map_to_source,
    source_label_from_index,
)


def check_entities(
    file_paths: list[str] | None,
    source_roots: list[str] | None = None,
) -> dict[str, Any]:
    from find_entity_by_xml.entity_resolver import get_entities_for_file

    # Giữ nguyên slot nguồn (kể cả '') để source_index khớp label Nguồn 1/2/3
    roots = list(source_roots) if isinstance(source_roots, (list, tuple)) else []
    resolved = resolve_checking_files([p for p in (file_paths or []) if p])
    warnings: list[str] = list(resolved["warnings"])

    errors: list[dict[str, Any]] = []
    table1_missing: list[dict[str, Any]] = []
    table2_entities: list[dict[str, Any]] = []
    seen_missing: set[str] = set()
    seen_undeclared: set[str] = set()
    per_xml: dict[str, dict[str, Any]] = {}

    def ensure_bucket(xml_path: str, xml_short: str) -> dict[str, Any]:
        if xml_path not in per_xml:
            per_xml[xml_path] = {
                "xml_short": xml_short,
                "missing_count": 0,
                "undeclared_count": 0,
            }
        return per_xml[xml_path]

    def collect_missing(
        file_path: str,
        xml_short: str,
        entities_map: dict | None,
        is_parameter: bool,
        bucket: dict,
    ) -> None:
        for entity_name, ent in (entities_map or {}).items():
            if not ent or not ent.get("systemUrl"):
                continue
            missing_path = ent.get("sourceFile")
            if not missing_path or os.path.exists(missing_path):
                continue

            bucket["missing_count"] += 1
            key = os.path.normpath(missing_path).lower()
            if key in seen_missing:
                errors.append(
                    {
                        "type": "missing_file",
                        "message": f"Thiếu file SYSTEM: {missing_path}",
                        "xml_short": xml_short,
                        "xml_path": file_path,
                        "entity_name": entity_name,
                        "missing_path": missing_path,
                        "system_url": ent.get("systemUrl"),
                        "is_parameter": is_parameter,
                    }
                )
                continue
            seen_missing.add(key)

            rel_info = get_relative_after_project(missing_path)
            relative_path = rel_info["relative_path"] if rel_info else None
            source_index = None
            source_file_path = None
            if relative_path:
                found = find_in_sources_by_relative(roots, relative_path)
                if found:
                    source_index = found["source_index"]
                    source_file_path = found["source_file_path"]

            table1_missing.append(
                {
                    "xml_short": xml_short,
                    "xml_path": file_path,
                    "missing_path": missing_path,
                    "relative_path": relative_path or "",
                    "system_url": ent.get("systemUrl"),
                    "entity_name": entity_name,
                    "is_parameter": is_parameter,
                    "source_index": source_index,
                    "source_label": source_label_from_index(source_index),
                    "source_file_path": source_file_path,
                }
            )
            errors.append(
                {
                    "type": "missing_file",
                    "message": f"Thiếu file SYSTEM: {missing_path}",
                    "xml_short": xml_short,
                    "xml_path": file_path,
                    "entity_name": entity_name,
                    "missing_path": missing_path,
                    "system_url": ent.get("systemUrl"),
                    "is_parameter": is_parameter,
                }
            )

    def scan_undeclared(
        file_path: str,
        xml_short: str,
        general_entities: dict | None,
        bucket: dict,
    ) -> None:
        used_entities = get_transitively_used_entities(file_path, general_entities)

        for entity_name in sorted(used_entities):
            if general_entities and entity_name in general_entities:
                continue
            dedupe_key = os.path.normpath(file_path).lower() + "|" + entity_name
            if dedupe_key in seen_undeclared:
                continue
            seen_undeclared.add(dedupe_key)

            status = "missing"
            source_index = None
            decl_file = None
            decl_line = None
            decl_is_system = False
            decl_system_file = None

            rel_info = get_relative_after_project(file_path)
            if rel_info and roots:
                for i, root in enumerate(roots):
                    if not root:
                        continue
                    source_xml = map_to_source(root, rel_info["relative_path"])
                    # relative_path là .f nhưng source chứa .xml → fallback
                    if not os.path.exists(source_xml) and source_xml.lower().endswith(".f"):
                        fallback_xml = source_xml[:-2] + ".xml"
                        if os.path.exists(fallback_xml):
                            source_xml = fallback_xml
                    if not os.path.exists(source_xml):
                        continue
                    try:
                        entities_on_source, _p, _mt = get_entities_for_file(source_xml)
                    except Exception:
                        continue
                    ent = (entities_on_source or {}).get(entity_name)
                    if not ent:
                        continue

                    status = "ok"
                    source_index = i
                    decl_is_system = bool(ent.get("systemUrl") and ent.get("sourceFile"))
                    decl_system_file = ent.get("sourceFile") if decl_is_system else None

                    if ent.get("declaredInFile") and (ent.get("line") or 0) > 0:
                        decl_file = ent["declaredInFile"]
                        decl_line = ent["line"]
                    elif (
                        decl_is_system
                        and ent.get("sourceFile")
                        and os.path.exists(ent["sourceFile"])
                    ):
                        decl_file = ent["sourceFile"]
                        decl_line = 1
                    else:
                        decl_file = source_xml
                        decl_line = ent.get("line") or 1
                    break

            table2_entities.append(
                {
                    "xml_short": xml_short,
                    "xml_path": file_path,
                    "entity_name": entity_name,
                    "status": status,
                    "source_index": source_index,
                    "source_label": (
                        source_label_from_index(source_index)
                        if status == "ok"
                        else "Không tìm thấy"
                    ),
                    "decl_file": decl_file,
                    "decl_line": decl_line,
                    "decl_is_system": decl_is_system,
                    "decl_system_file": decl_system_file,
                }
            )
            bucket["undeclared_count"] += 1
            errors.append(
                {
                    "type": "undeclared_entity",
                    "message": f"Entity chưa khai báo: &{entity_name};",
                    "xml_short": xml_short,
                    "xml_path": file_path,
                    "entity_name": entity_name,
                }
            )

    def check_one_file(file_path: str) -> None:
        xml_short = get_xml_short_name(file_path)
        bucket = ensure_bucket(file_path, xml_short)

        if not os.path.exists(file_path):
            # File chọn không tồn tại: đưa vào table1 để summary phản ánh đúng
            key = os.path.normpath(file_path).lower()
            if key not in seen_missing:
                seen_missing.add(key)
                table1_missing.append(
                    {
                        "xml_short": xml_short,
                        "xml_path": file_path,
                        "missing_path": file_path,
                        "relative_path": "",
                        "system_url": "",
                        "entity_name": "",
                        "is_parameter": False,
                        "source_index": None,
                        "source_label": "Không tìm thấy",
                        "source_file_path": None,
                    }
                )
            errors.append(
                {
                    "type": "missing_file",
                    "message": f"File chọn không tồn tại: {file_path}",
                    "xml_short": xml_short,
                    "xml_path": file_path,
                    "missing_path": file_path,
                }
            )
            bucket["missing_count"] += 1
            return

        try:
            general_entities, parameter_entities, _mt = get_entities_for_file(file_path)
        except Exception as exc:
            warnings.append(
                f"file_parse_error: '{file_path}': {exc} (file .f mã hóa / XML hỏng?)"
            )
            return

        collect_missing(file_path, xml_short, general_entities, False, bucket)
        collect_missing(file_path, xml_short, parameter_entities, True, bucket)
        scan_undeclared(file_path, xml_short, general_entities, bucket)

    for fp in resolved["xml_files"]:
        check_one_file(fp)

    table3_xml_errors = [
        {
            "xml_short": info["xml_short"],
            "xml_path": xml_path,
            "missing_count": info["missing_count"],
            "undeclared_count": info["undeclared_count"],
        }
        for xml_path, info in per_xml.items()
        if info["missing_count"] > 0 or info["undeclared_count"] > 0
    ]

    missing_count = len(table1_missing)
    undeclared_count = len(table2_entities)
    all_missing_have_source = (
        True
        if missing_count == 0
        else all(r["source_index"] is not None for r in table1_missing)
    )
    any_missing_has_source = any(
        r["source_index"] is not None for r in table1_missing
    )

    return {
        "success": True,
        "checked_files": resolved["xml_files"],
        "skipped_files": resolved["skipped_files"],
        "errors": errors,
        "missing_files": table1_missing,
        "undeclared_entities": table2_entities,
        "per_xml_summary": table3_xml_errors,
        "warnings": warnings,
        "summary": {
            "total": missing_count + undeclared_count,
            "missing_count": missing_count,
            "undeclared_count": undeclared_count,
            "all_missing_have_source": all_missing_have_source,
            "any_missing_has_source": any_missing_has_source,
        },
    }
