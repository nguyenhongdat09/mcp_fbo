"""Pure orchestration: analyze flat XML string into SummaryXmlResult."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Literal

from xml_controller_summary.models import (
    SummaryXmlResult,
    ControllerMeta,
    JsSummary,
    SqlSummary,
    SqlBlock,
    Meta,
)
from xml_controller_summary.extract import extract_controller_blocks, JsChunk, SqlChunk
from xml_controller_summary.fallback_regex import (
    fallback_extract_js,
    fallback_extract_sql,
    is_plausible_table_name,
    is_plausible_proc_name,
)
from xml_controller_summary.field_classifier import classify_fields
from xml_controller_summary.grid_formulas import (
    extract_g_a_formulas,
    extract_show_forms_and_related,
)

_VIEW_HEURISTIC_RE = re.compile(r"^(v20|v25|v30|zv|v\d{2}dm)[a-z0-9_]*", re.IGNORECASE)


def is_fbo_view(name: str) -> bool:
    """Check if table name is a genuine FBO category/view (not partition tables like v00$$...)."""
    low = name.lower()
    # Exclude partition tables like v00$$partition$current, v01$000000
    if "$partition$" in low or "$$" in low:
        return False
    if re.match(r"^v\d{2}\$", low) and "dm" not in low:
        return False
    return bool(_VIEW_HEURISTIC_RE.match(name))


def normalize_display_file_path(source_path: str) -> str:
    """Normalize file path to relative from Controllers/ (e.g. 'Dir\\SVTran.xml') to save tokens."""
    if not source_path:
        return "Unknown.xml"
    parts = Path(source_path).parts
    for i, p in enumerate(parts):
        if p.lower() == "controllers" and i + 1 < len(parts):
            return "\\".join(parts[i + 1:])
    return source_path.replace("/", "\\")


def infer_folder_type(source_path: str) -> str | None:
    """Infer controller folder_type (Dir, Grid, Filter, Report, etc.) from relative or absolute path."""
    if not source_path:
        return None
    parts = Path(source_path).parts
    for i, p in enumerate(parts):
        if p.lower() == "controllers" and i + 1 < len(parts):
            return parts[i + 1]
    # Fallback to direct parent folder name if match common FBO folder names
    if len(parts) >= 2:
        parent = parts[-2]
        if parent.lower() in {"dir", "grid", "filter", "report", "lookup", "custom"}:
            return parent
    return None


def analyze_js_chunks(chunks: list[JsChunk]) -> tuple[JsSummary, list[str]]:
    """High-performance extraction and summarization of all JS chunks in controller."""
    warnings: list[str] = []
    if not chunks:
        return JsSummary(parse_status="empty"), warnings

    sources = [c.source for c in chunks]
    full_source = "\n;\n".join(c.content for c in chunks if c.content)
    line_count = sum(c.content.count("\n") + 1 for c in chunks if c.content)

    if not full_source.strip():
        return JsSummary(parse_status="empty", sources=sources, line_count=line_count), warnings

    # Fast and robust extraction of functions, whitelist calls, and request actions
    fb_funcs, fb_calls, fb_actions = fallback_extract_js(full_source)

    status: Literal["ok", "partial", "failed", "empty"] = "ok" if fb_funcs else "empty"

    return (
        JsSummary(
            parse_status=status,
            sources=sources,
            functions=sorted(fb_funcs),
            calls=sorted(fb_calls),
            request_actions=sorted(fb_actions),
            line_count=line_count,
        ),
        warnings,
    )


def analyze_sql_chunks(chunks: list[SqlChunk]) -> tuple[SqlSummary, list[str]]:
    """High-performance extraction and summarization of all SQL chunks in controller."""
    warnings: list[str] = []
    if not chunks:
        return SqlSummary(parse_status="empty"), warnings

    blocks: list[SqlBlock] = []
    all_tables: dict[str, str] = {}
    all_procs: dict[str, str] = {}
    all_signals: set[str] = set()
    total_lines = 0

    for chunk in chunks:
        content = chunk.content or ""
        total_lines += content.count("\n") + 1 if content else 0

        blocks.append(
            SqlBlock(
                kind=chunk.kind,
                event=chunk.event,
                id=chunk.id,
                line=chunk.line,
                lang=chunk.lang,
            )
        )

        if chunk.has_ifdef:
            all_signals.add("fbo_ifdef")

        if not content.strip():
            continue

        # Fast and robust regex extraction for tables, procs, and signals
        fb_tables, fb_procs, fb_signals = fallback_extract_sql(content)
        for t in fb_tables:
            if is_plausible_table_name(t) and t.lower() not in all_tables:
                all_tables[t.lower()] = t

        for p in fb_procs:
            if is_plausible_proc_name(p) and p.lower() not in all_procs:
                all_procs[p.lower()] = p

        all_signals.update(fb_signals)

    tables_list = list(all_tables.values())
    procs_list = list(all_procs.values())
    views_list = [t for t in tables_list if is_fbo_view(t)]

    status: Literal["ok", "partial", "failed", "empty"] = "ok"
    if total_lines == 0:
        status = "empty"
    elif "fbo_ifdef" in all_signals or warnings:
        status = "partial"

    return (
        SqlSummary(
            parse_status=status,
            blocks=blocks,
            tables=tables_list,
            procs=procs_list,
            views=views_list,
            signals=sorted(all_signals),
            line_count=total_lines,
        ),
        warnings,
    )


def analyze_flat_xml(flat_text: str, *, source_path: str = "") -> SummaryXmlResult:
    """Pure analysis of flat XML content into SummaryXmlResult."""
    t0 = time.perf_counter()
    flat_len = len(flat_text)
    display_file = normalize_display_file_path(source_path)

    # Check for empty or unsupported encrypted content
    if not flat_text or not flat_text.strip():
        parse_ms = max(1, int((time.perf_counter() - t0) * 1000))
        return SummaryXmlResult(
            success=False,
            file=display_file,
            controller=ControllerMeta(folder_type=infer_folder_type(source_path)),
            js=JsSummary(parse_status="empty"),
            sql=SqlSummary(parse_status="empty"),
            fields=[],
            meta=Meta(
                flat_chars=flat_len,
                estimated_tokens_saved=0,
                skipped_encrypted_blocks=0,
                warnings=["empty_flat_xml"],
                parse_ms=parse_ms,
            ),
        )

    # Extract blocks
    extracted = extract_controller_blocks(flat_text)
    all_warnings = list(extracted.warnings)

    # Build ControllerMeta
    root_attrs = extracted.root_attrs
    controller_meta = ControllerMeta(
        folder_type=infer_folder_type(source_path),
        db_table=root_attrs.get("table"),
        code_field=root_attrs.get("code"),
        title_v=extracted.title_v,
        title_e=extracted.title_e,
        id=root_attrs.get("id"),
    )

    # Analyze JS
    js_summary, js_warns = analyze_js_chunks(extracted.js_chunks)
    all_warnings.extend(js_warns)

    # Extract g.$a formulas and g.showForm related controllers from JS
    full_js_source = "\n;\n".join(c.content for c in extracted.js_chunks if c.content)
    grid_formulas = extract_g_a_formulas(full_js_source) if full_js_source else None
    show_forms, related_controllers = (
        extract_show_forms_and_related(full_js_source) if full_js_source else ([], [])
    )

    # Analyze SQL
    sql_summary, sql_warns = analyze_sql_chunks(extracted.sql_chunks)
    all_warnings.extend(sql_warns)
    if extracted.skipped_encrypted_count > 0:
        if "encrypted_skipped" not in sql_summary.signals:
            sql_summary.signals.append("encrypted_skipped")

    if "checking_routed_to_sql" in all_warnings:
        if "checking_routed_to_sql" not in sql_summary.signals:
            sql_summary.signals.append("checking_routed_to_sql")

    sql_summary.signals.sort()

    # Classify and deduplicate fields
    fields_summary = classify_fields(extracted.fields)

    # Calculate token saving
    parse_ms = max(1, int((time.perf_counter() - t0) * 1000))
    # Approximation of json character size
    estimated_json_chars = (
        len(js_summary.functions) * 30
        + len(sql_summary.tables) * 20
        + len(fields_summary) * 40
        + 500
    )
    tokens_saved = max(0, (flat_len - estimated_json_chars) // 4)

    return SummaryXmlResult(
        success=True,
        file=display_file,
        controller=controller_meta,
        js=js_summary,
        sql=sql_summary,
        fields=fields_summary,
        meta=Meta(
            flat_chars=flat_len,
            estimated_tokens_saved=tokens_saved,
            skipped_encrypted_blocks=extracted.skipped_encrypted_count,
            warnings=all_warnings,
            parse_ms=parse_ms,
        ),
        grid_formulas=grid_formulas,
        show_forms=show_forms,
        related_controllers=related_controllers,
    )
