"""Data models for sql_object_summary."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal, Optional


@dataclass
class ParamInfo:
    name: str
    type: str
    default: Optional[str] = None
    is_output: bool = False


@dataclass
class DirectCall:
    name: str
    kind: Literal["infra", "system", "business", "view"] = "business"
    expanded: bool = False
    error: Optional[str] = None


@dataclass
class ResultSetHint:
    ordinal: int
    hint: Optional[str] = None
    confidence: Literal["low", "medium", "high"] = "medium"
    columns_hint: list[str] = field(default_factory=list)


@dataclass
class Signals:
    uses_partition_execute: bool = False
    uses_balance_helper: bool = False
    has_cursor: bool = False
    has_while: bool = False
    has_dynamic_sql: bool = False
    has_try_catch: bool = False
    options_keys: list[str] = field(default_factory=list)
    uses_pivot_pattern: bool = False


@dataclass
class ParamEffect:
    param: str
    role: Literal["branching", "filter", "loop_bound", "calculation"] = "branching"
    effect: str = ""
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence_lines: list[int] = field(default_factory=list)


@dataclass
class ObjectSummary:
    params: list[ParamInfo] = field(default_factory=list)
    calls_direct: list[DirectCall] = field(default_factory=list)
    calls_business: list[DirectCall] = field(default_factory=list)
    tables_read: list[str] = field(default_factory=list)
    tables_write: list[str] = field(default_factory=list)
    temp_tables: list[str] = field(default_factory=list)
    variables_key: list[str] = field(default_factory=list)
    result_sets: list[ResultSetHint] = field(default_factory=list)
    signals: Signals = field(default_factory=Signals)
    param_effects: list[ParamEffect] = field(default_factory=list)
    zones_detected: list[str] = field(default_factory=list)
    snippet_index: dict[str, list[int]] = field(default_factory=dict)
    logic_hints: dict[str, Any] = field(default_factory=dict)


@dataclass
class CallGraphNode:
    kind: Literal["infra", "system", "business", "view"] = "business"
    depth: int = 0
    expanded: bool = False
    calls: list[str] = field(default_factory=list)
    tables_read: list[str] = field(default_factory=list)
    status: str = "ok"
    error: Optional[str] = None


@dataclass
class CallGraph:
    root: str
    max_depth_applied: int = 1
    total_objects_count: int = 1
    truncated: bool = False
    truncated_objects: list[str] = field(default_factory=list)
    nodes: dict[str, CallGraphNode] = field(default_factory=dict)
    execution_tree_shallow: dict[str, list[str]] = field(default_factory=dict)
    impacted_tables: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)


@dataclass
class Meta:
    file_path: str = ""
    project_root: str = ""
    cache_hit: bool = False
    parse_time_ms: int = 0
    objects_fetched: int = 1
    estimated_full_chars: int = 0
    estimated_tokens_saved: int = 0
    warnings: list[str] = field(default_factory=list)
    timing: dict[str, int] = field(default_factory=dict)


@dataclass
class SummaryResult:
    success: bool = True
    spec_version: str = "1.0"
    object: str = ""
    object_type: Literal["PROCEDURE", "FUNCTION", "VIEW"] = "PROCEDURE"
    mode: str = "summary"
    parse_status: Literal["ok", "partial", "failed"] = "ok"
    line_count: int = 0
    modify_date: Optional[str] = None
    database: str = ""
    summary: ObjectSummary = field(default_factory=ObjectSummary)
    call_graph: Optional[CallGraph] = None
    meta: Meta = field(default_factory=Meta)


@dataclass
class SnippetItem:
    id: str
    match_reason: str
    line_start: int
    line_end: int
    sql: str


@dataclass
class SnippetResult:
    success: bool = True
    spec_version: str = "1.0"
    object: str = ""
    mode: str = "snippet"
    snippets: list[SnippetItem] = field(default_factory=list)
    total_lines: int = 0
    truncated: bool = False
    meta: Meta = field(default_factory=Meta)
