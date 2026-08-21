"""Data models for xml_controller_summary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SPEC_VERSION: str = "1.0"


@dataclass
class ControllerMeta:
    folder_type: str | None = None
    db_table: str | None = None
    code_field: str | None = None
    title_v: str | None = None
    title_e: str | None = None
    id: str | None = None


@dataclass
class JsSummary:
    parse_status: Literal["ok", "partial", "failed", "empty"] = "empty"
    sources: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    request_actions: list[str] = field(default_factory=list)
    line_count: int = 0


@dataclass
class SqlBlock:
    kind: Literal["command", "action", "query"]
    event: str | None = None
    id: str | None = None
    line: int = 0
    lang: Literal["sql", "js"] = "sql"


@dataclass
class SqlSummary:
    parse_status: Literal["ok", "partial", "failed", "empty"] = "empty"
    blocks: list[SqlBlock] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    procs: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    line_count: int = 0


@dataclass
class FieldSummary:
    name: str
    type: Literal["char", "number", "checkbox", "date"]
    lookup: str | None = None
    onchange: str | None = None
    hidden: bool | None = None
    allowNulls: bool | None = None


@dataclass
class GridFormulas:
    expressions: dict[str, str] = field(default_factory=dict)
    aggregates: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Meta:
    flat_chars: int = 0
    estimated_tokens_saved: int = 0
    skipped_encrypted_blocks: int = 0
    warnings: list[str] = field(default_factory=list)
    parse_ms: int = 0


@dataclass
class SummaryXmlResult:
    success: bool
    file: str
    controller: ControllerMeta
    js: JsSummary
    sql: SqlSummary
    fields: list[FieldSummary]
    meta: Meta
    grid_formulas: GridFormulas | None = None
    show_forms: list[str] = field(default_factory=list)
    related_controllers: list[str] = field(default_factory=list)
    mode: str = "summary"
    spec_version: str = "1.0"
