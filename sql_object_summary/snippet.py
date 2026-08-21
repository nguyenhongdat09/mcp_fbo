"""Extract SQL snippets based on keywords and FBO structural zones."""

from __future__ import annotations

import re
from sql_object_summary.models import SnippetResult, SnippetItem, Meta


def extract_snippet(
    definition: str,
    *,
    object_name: str = "",
    keywords: list[str] | None = None,
    zones: list[str] | None = None,
    max_lines: int = 120,
) -> SnippetResult:
    """Extract code snippets from SQL definition text."""
    lines = definition.splitlines()
    total_file_lines = len(lines)

    snippets: list[SnippetItem] = []
    matched_ranges: list[tuple[int, int, str]] = []

    # 1. Extract by zones
    if zones:
        for z in zones:
            ranges = _find_zone_ranges(lines, z)
            for start, end in ranges:
                matched_ranges.append((start, end, f"zone:{z}"))

    # 2. Extract by keywords
    if keywords:
        for kw in keywords:
            kw_clean = kw.strip()
            if not kw_clean:
                continue
            for idx, line in enumerate(lines):
                if re.search(re.escape(kw_clean), line, re.IGNORECASE):
                    start = _expand_start(lines, idx, context=8)
                    end = _expand_end(lines, idx, context=8)
                    matched_ranges.append((start, end, f"keyword:{kw_clean}"))

    # 3. Merge overlapping ranges
    merged = _merge_ranges(matched_ranges)

    total_snippet_lines = 0
    truncated = False

    for i, (start, end, reason) in enumerate(merged, start=1):
        block_lines = lines[start : end + 1]
        line_count = len(block_lines)

        if total_snippet_lines + line_count > max_lines:
            # Cut off at max_lines
            allowed = max(0, max_lines - total_snippet_lines)
            if allowed > 0:
                block_lines = block_lines[:allowed]
                snippets.append(
                    SnippetItem(
                        id=f"s{i}",
                        match_reason=reason,
                        line_start=start + 1,
                        line_end=start + allowed,
                        sql="\n".join(block_lines),
                    )
                )
                total_snippet_lines += allowed
            truncated = True
            break

        snippets.append(
            SnippetItem(
                id=f"s{i}",
                match_reason=reason,
                line_start=start + 1,
                line_end=end + 1,
                sql="\n".join(block_lines),
            )
        )
        total_snippet_lines += line_count

    warnings = []
    if not snippets:
        warnings.append("no_snippet_matches")

    return SnippetResult(
        success=True,
        spec_version="1.0",
        object=object_name,
        mode="snippet",
        snippets=snippets,
        total_lines=total_snippet_lines,
        truncated=truncated,
        meta=Meta(estimated_full_chars=len(definition), warnings=warnings),
    )


def _find_zone_ranges(lines: list[str], zone: str) -> list[tuple[int, int]]:
    z = zone.lower()
    ranges: list[tuple[int, int]] = []

    if z == "header" or z == "params":
        # First 30 lines or up to AS
        for i, line in enumerate(lines[:60]):
            if re.match(r"^\s*AS\b", line, re.IGNORECASE):
                ranges.append((0, i))
                break
        if not ranges:
            ranges.append((0, min(len(lines) - 1, 30)))

    elif z == "cursor":
        for i, line in enumerate(lines):
            if "DECLARE" in line.upper() and "CURSOR" in line.upper():
                ranges.append((max(0, i - 2), min(len(lines) - 1, i + 35)))

    elif z == "pivot":
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["#pivot", "xpivot", "xsearch", "npivot"]):
                ranges.append((max(0, i - 5), min(len(lines) - 1, i + 30)))

    elif z == "result_set":
        # Find last SELECT statement
        for i in range(len(lines) - 1, -1, -1):
            if re.match(r"^\s*SELECT\b", lines[i], re.IGNORECASE) and "INTO" not in lines[i].upper():
                ranges.append((max(0, i - 2), min(len(lines) - 1, i + 25)))
                break

    return ranges


def _expand_start(lines: list[str], idx: int, context: int = 8) -> int:
    start = max(0, idx - context)
    # Lùi về comment separator hoặc BEGIN nếu gần
    for i in range(idx, start, -1):
        if lines[i].strip().startswith("-- ===") or lines[i].strip().startswith("/*"):
            return i
    return start


def _expand_end(lines: list[str], idx: int, context: int = 8) -> int:
    end = min(len(lines) - 1, idx + context)
    # Tiến tới END nếu gần
    for i in range(idx, end):
        if lines[i].strip().upper() == "END":
            return i
    return end


def _merge_ranges(ranges: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    if not ranges:
        return []

    # Sort by start line
    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    merged: list[tuple[int, int, str]] = []

    cur_start, cur_end, cur_reason = sorted_ranges[0]

    for start, end, reason in sorted_ranges[1:]:
        if start <= cur_end + 3:  # Overlap or very close (within 3 lines)
            cur_end = max(cur_end, end)
            if reason not in cur_reason:
                cur_reason = f"{cur_reason} + {reason}"
        else:
            merged.append((cur_start, cur_end, cur_reason))
            cur_start, cur_end, cur_reason = start, end, reason

    merged.append((cur_start, cur_end, cur_reason))
    return merged
