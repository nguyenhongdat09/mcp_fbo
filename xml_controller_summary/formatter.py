"""Convert SummaryXmlResult into a clean, spec-compliant JSON dictionary."""

from __future__ import annotations

from typing import Any
from xml_controller_summary.models import SummaryXmlResult


def result_to_dict(result: SummaryXmlResult) -> dict[str, Any]:
    """Format SummaryXmlResult into a spec-compliant JSON dict without MCP markdown wrapping."""
    # Format controller metadata (always emit dict, properties can be None)
    controller_dict = {
        "folder_type": result.controller.folder_type,
        "db_table": result.controller.db_table,
        "code_field": result.controller.code_field,
        "title_v": result.controller.title_v,
        "title_e": result.controller.title_e,
        "id": result.controller.id,
    }

    # Format JS summary
    js_dict = {
        "parse_status": result.js.parse_status,
        "sources": result.js.sources,
        "functions": sorted(result.js.functions),
        "calls": sorted(result.js.calls),
        "request_actions": sorted(result.js.request_actions),
        "line_count": result.js.line_count,
    }

    # Format SQL summary
    blocks_list = []
    for b in result.sql.blocks:
        blocks_list.append({
            "kind": b.kind,
            "event": b.event,
            "id": b.id,
            "line": b.line,
            "lang": b.lang,
        })

    sql_dict = {
        "parse_status": result.sql.parse_status,
        "blocks": blocks_list,
        "tables": sorted(result.sql.tables),
        "procs": sorted(result.sql.procs),
        "views": sorted(result.sql.views),
        "signals": sorted(result.sql.signals),
        "line_count": result.sql.line_count,
    }

    # Format fields (omit optional keys if None to save tokens)
    fields_list = []
    for f in result.fields:
        f_dict: dict[str, Any] = {
            "name": f.name,
            "type": f.type,
        }
        if f.lookup is not None:
            f_dict["lookup"] = f.lookup
        if f.onchange is not None:
            f_dict["onchange"] = f.onchange
        if f.hidden is not None:
            f_dict["hidden"] = f.hidden
        if f.allowNulls is not None:
            f_dict["allowNulls"] = f.allowNulls
        fields_list.append(f_dict)

    # Format meta
    meta_dict = {
        "flat_chars": result.meta.flat_chars,
        "estimated_tokens_saved": result.meta.estimated_tokens_saved,
        "skipped_encrypted_blocks": result.meta.skipped_encrypted_blocks,
        "warnings": result.meta.warnings,
        "parse_ms": result.meta.parse_ms,
    }

    out: dict[str, Any] = {
        "success": result.success,
        "mode": result.mode,
        "spec_version": result.spec_version,
        "file": result.file,
        "controller": controller_dict,
        "js": js_dict,
        "sql": sql_dict,
        "fields": fields_list,
        "meta": meta_dict,
    }

    # Optional grid formulas (omit if empty)
    if result.grid_formulas and (result.grid_formulas.expressions or result.grid_formulas.aggregates):
        out["grid_formulas"] = {
            "expressions": result.grid_formulas.expressions,
            "aggregates": result.grid_formulas.aggregates,
        }

    # Optional show_forms and related_controllers (omit if empty)
    if result.show_forms:
        out["show_forms"] = result.show_forms

    if result.related_controllers:
        out["related_controllers"] = result.related_controllers

    return out
