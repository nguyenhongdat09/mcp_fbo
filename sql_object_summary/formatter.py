"""JSON schema formatter: transform dataclass models to pure JSON dictionary."""

from __future__ import annotations

from typing import Any
from sql_object_summary.models import SummaryResult, SnippetResult, ObjectSummary, CallGraph, Meta


def result_to_dict(result: SummaryResult | SnippetResult | dict) -> dict[str, Any]:
    """Convert SummaryResult or SnippetResult to pure JSON-serializable dict."""
    if isinstance(result, dict):
        return result

    if isinstance(result, SnippetResult):
        return {
            "success": result.success,
            "spec_version": result.spec_version,
            "object": result.object,
            "mode": result.mode,
            "snippets": [
                {
                    "id": s.id,
                    "match_reason": s.match_reason,
                    "line_start": s.line_start,
                    "line_end": s.line_end,
                    "sql": s.sql,
                }
                for s in result.snippets
            ],
            "total_lines": result.total_lines,
            "truncated": result.truncated,
            "meta": _meta_to_dict(result.meta),
        }

    if isinstance(result, SummaryResult):
        d: dict[str, Any] = {
            "success": result.success,
            "spec_version": result.spec_version,
            "object": result.object,
            "object_type": result.object_type,
            "mode": result.mode,
            "parse_status": result.parse_status,
            "line_count": result.line_count,
            "modify_date": result.modify_date,
            "database": result.database,
            "summary": _object_summary_to_dict(result.summary),
        }
        if result.call_graph is not None:
            d["call_graph"] = _call_graph_to_dict(result.call_graph)
        d["meta"] = _meta_to_dict(result.meta)
        return d

    return dict(result)


def _object_summary_to_dict(summary: ObjectSummary) -> dict[str, Any]:
    res_dict: dict[str, Any] = {
        "params": [
            {
                "name": p.name,
                "type": p.type,
                "default": p.default if (p.default is not None and p.default != "") else None,
                "is_output": p.is_output,
            }
            for p in summary.params
        ],
        "calls_direct": [
            {
                "name": c.name,
                "kind": c.kind,
                "expanded": c.expanded,
                **({"error": c.error} if c.error else {}),
            }
            for c in summary.calls_direct
        ],
        "calls_business": [
            {
                "name": c.name,
                "kind": c.kind,
                "expanded": c.expanded,
            }
            for c in summary.calls_business
        ],
        "tables_read": summary.tables_read,
        "tables_write": summary.tables_write,
        "temp_tables": summary.temp_tables,
        "variables_key": summary.variables_key,
        "result_sets": [
            {
                "ordinal": rs.ordinal,
                **({"hint": rs.hint} if rs.hint else {}),
                "confidence": rs.confidence,
                "columns_hint": rs.columns_hint,
            }
            for rs in summary.result_sets
        ],
        "signals": {
            "uses_partition_execute": summary.signals.uses_partition_execute,
            "uses_balance_helper": summary.signals.uses_balance_helper,
            "has_cursor": summary.signals.has_cursor,
            "has_while": summary.signals.has_while,
            "has_dynamic_sql": summary.signals.has_dynamic_sql,
            "has_try_catch": summary.signals.has_try_catch,
            "options_keys": summary.signals.options_keys,
            "uses_pivot_pattern": summary.signals.uses_pivot_pattern,
        },
        "param_effects": [
            {
                "param": pe.param,
                "role": pe.role,
                "effect": pe.effect,
                "confidence": pe.confidence,
                "evidence_lines": pe.evidence_lines,
            }
            for pe in summary.param_effects
            if pe.confidence != "low"
        ][:5],
        "zones_detected": summary.zones_detected,
    }

    if summary.logic_hints:
        res_dict["logic_hints"] = summary.logic_hints
    if summary.snippet_index:
        res_dict["snippet_index"] = summary.snippet_index

    return res_dict


def _call_graph_to_dict(cg: CallGraph) -> dict[str, Any]:
    nodes_dict: dict[str, Any] = {}
    for k, v in cg.nodes.items():
        node_entry: dict[str, Any] = {
            "kind": v.kind,
            "depth": v.depth,
            "expanded": v.expanded,
            "calls": v.calls,
        }
        if v.tables_read:
            node_entry["tables_read"] = v.tables_read
        if v.error:
            node_entry["error"] = v.error
        nodes_dict[k] = node_entry

    return {
        "root": cg.root,
        "max_depth_applied": cg.max_depth_applied,
        "total_objects_count": cg.total_objects_count,
        "truncated": cg.truncated,
        "truncated_objects": cg.truncated_objects,
        "nodes": nodes_dict,
        "execution_tree_shallow": cg.execution_tree_shallow,
        "impacted_tables": cg.impacted_tables,
        "called_by": cg.called_by,
    }


def _meta_to_dict(meta: Meta) -> dict[str, Any]:
    d: dict[str, Any] = {
        "file_path": meta.file_path,
        "project_root": meta.project_root,
        "cache_hit": meta.cache_hit,
        "parse_time_ms": meta.parse_time_ms,
        "objects_fetched": meta.objects_fetched,
        "estimated_full_chars": meta.estimated_full_chars,
        "estimated_tokens_saved": meta.estimated_tokens_saved,
        "warnings": meta.warnings,
    }
    if meta.timing:
        d["timing"] = meta.timing
    return d
