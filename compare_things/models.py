"""Data models and type definitions for compare_things."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Hunk:

    id: int
    change_type: str  # "insert" | "delete" | "replace"
    a_line_start: Optional[int] = None
    a_line_end: Optional[int] = None
    b_line_start: Optional[int] = None
    b_line_end: Optional[int] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    target_line_start: Optional[int] = None
    target_line_end: Optional[int] = None
    lines_added: int = 0
    lines_removed: int = 0
    preview: List[str] = field(default_factory=list)
    signals_in_hunk: List[str] = field(default_factory=list)
    body_a: Optional[str] = None
    body_b: Optional[str] = None
    body_source: Optional[str] = None
    body_target: Optional[str] = None
    body_truncated: bool = False

    def to_dict(
        self,
        is_sql: bool = False,
        mode: str = "summary",
        include_text_snippets: bool = False,
    ) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "id": self.id,
            "change_type": self.change_type,
        }
        if is_sql:
            res["source_line_start"] = self.source_line_start
            res["source_line_end"] = self.source_line_end
            res["target_line_start"] = self.target_line_start
            res["target_line_end"] = self.target_line_end
        else:
            res["a_line_start"] = self.a_line_start
            res["a_line_end"] = self.a_line_end
            res["b_line_start"] = self.b_line_start
            res["b_line_end"] = self.b_line_end

        res["lines_added"] = self.lines_added
        res["lines_removed"] = self.lines_removed

        if self.signals_in_hunk:
            res["signals_in_hunk"] = self.signals_in_hunk

        # CẤM preview / code snippets mặc định! Chỉ bật khi include_text_snippets=True
        if include_text_snippets:
            res["preview"] = self.preview
            if mode == "body":
                if is_sql:
                    if self.body_source is not None:
                        res["body_source"] = self.body_source
                    if self.body_target is not None:
                        res["body_target"] = self.body_target
                else:
                    if self.body_a is not None:
                        res["body_a"] = self.body_a
                    if self.body_b is not None:
                        res["body_b"] = self.body_b
                if self.body_truncated:
                    res["body_truncated"] = True

        return res


@dataclass
class FileMeta:
    path: str
    exists: bool = False
    size: int = 0
    created: str = ""
    modified: str = ""
    sha256: str = ""
    encoding: str = ""
    line_ending: str = ""
    is_binary: bool = False

    def to_dict(self) -> Dict[str, Any]:
        # Slim format: bỏ các field thừa để tiết kiệm token
        return {
            "path": self.path,
            "size": self.size,
            "modified": self.modified,
            "sha256": self.sha256,
            "line_ending": self.line_ending,
            "is_binary": self.is_binary,
        }


@dataclass
class ContentDiff:
    lines_a: Optional[int] = None
    lines_b: Optional[int] = None
    lines_source: Optional[int] = None
    lines_target: Optional[int] = None
    lines_added: int = 0
    lines_removed: int = 0
    hunk_count: int = 0
    hunks: List[Hunk] = field(default_factory=list)
    diff_truncated: bool = False
    unified_diff: str = ""

    def to_dict(
        self,
        is_sql: bool = False,
        mode: str = "summary",
        max_hunks: Optional[int] = None,
        include_text_snippets: bool = False,
        include_unified_diff: bool = False,
    ) -> Dict[str, Any]:
        res: Dict[str, Any] = {}
        if is_sql:
            res["lines_source"] = self.lines_source
            res["lines_target"] = self.lines_target
        else:
            res["lines_a"] = self.lines_a
            res["lines_b"] = self.lines_b
        res["lines_added"] = self.lines_added
        res["lines_removed"] = self.lines_removed
        res["hunk_count"] = self.hunk_count

        # Giới hạn số lượng hunks trả về theo max_hunks
        returned_hunks = self.hunks
        if max_hunks is not None and len(returned_hunks) > max_hunks:
            returned_hunks = returned_hunks[:max_hunks]

        hunks_omitted = max(0, self.hunk_count - len(returned_hunks))

        res["hunks"] = [
            h.to_dict(is_sql=is_sql, mode=mode, include_text_snippets=include_text_snippets)
            for h in returned_hunks
        ]
        res["hunks_omitted"] = hunks_omitted
        res["diff_truncated"] = self.diff_truncated or (hunks_omitted > 0)

        # unified_diff: chỉ trả về khi include_unified_diff=True
        if include_unified_diff and self.unified_diff:
            res["unified_diff"] = self.unified_diff

        return res

