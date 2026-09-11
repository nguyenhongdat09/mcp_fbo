"""Shared line diff engine using difflib for compare_things."""

from __future__ import annotations

import difflib
from typing import Callable, List, Optional, Tuple

from .models import ContentDiff, Hunk


def build_line_diff(
    lines_a: List[str],
    lines_b: List[str],
    context_lines: int = 3,
    max_preview_lines_per_hunk: int = 8,
    max_diff_lines: int = 200,
    max_hunks: int = 200,
    mode: str = "summary",
    is_sql: bool = False,
    file_label_a: str = "a",
    file_label_b: str = "b",
    extract_signals_fn: Optional[Callable[[List[str]], List[str]]] = None,
    include_unified_diff: bool = False,
    include_text_snippets: bool = False,
) -> ContentDiff:
    """
    Build ContentDiff and list of Hunk objects using SequenceMatcher.
    """
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
    grouped_opcodes = list(matcher.get_grouped_opcodes(n=max(0, context_lines)))

    total_hunk_count = len(grouped_opcodes)

    hunks: List[Hunk] = []
    total_added = 0
    total_removed = 0
    diff_truncated = False

    hunk_idx = 1
    for group in grouped_opcodes:
        if hunk_idx > max_hunks:
            diff_truncated = True
            break


        # Calculate line spans (1-based)
        i1 = group[0][1]
        i2 = group[-1][2]
        j1 = group[0][3]
        j2 = group[-1][4]

        # Calculate added / removed & change_type
        group_added = 0
        group_removed = 0
        has_insert = False
        has_delete = False
        has_replace = False

        preview_lines: List[str] = []

        for tag, a1, a2, b1, b2 in group:
            if tag == "replace":
                has_replace = True
                del_count = a2 - a1
                ins_count = b2 - b1
                group_removed += del_count
                group_added += ins_count
                for line in lines_a[a1:a2]:
                    if len(preview_lines) < max_preview_lines_per_hunk:
                        preview_lines.append(f"- {line}")
                for line in lines_b[b1:b2]:
                    if len(preview_lines) < max_preview_lines_per_hunk:
                        preview_lines.append(f"+ {line}")
            elif tag == "delete":
                has_delete = True
                group_removed += a2 - a1
                for line in lines_a[a1:a2]:
                    if len(preview_lines) < max_preview_lines_per_hunk:
                        preview_lines.append(f"- {line}")
            elif tag == "insert":
                has_insert = True
                group_added += b2 - b1
                for line in lines_b[b1:b2]:
                    if len(preview_lines) < max_preview_lines_per_hunk:
                        preview_lines.append(f"+ {line}")
            elif tag == "equal":
                # For context in preview, add if space permits
                for line in lines_a[a1:a2]:
                    if len(preview_lines) < max_preview_lines_per_hunk:
                        preview_lines.append(f"  {line}")

        total_added += group_added
        total_removed += group_removed

        if has_replace or (has_insert and has_delete):
            change_type = "replace"
        elif has_insert:
            change_type = "insert"
        elif has_delete:
            change_type = "delete"
        else:
            change_type = "replace"

        # Calculate changed range excluding leading/trailing context equal opcodes
        changed_opcodes = [op for op in group if op[0] != "equal"]
        if changed_opcodes:
            chg_i1 = changed_opcodes[0][1]
            chg_i2 = changed_opcodes[-1][2]
            chg_j1 = changed_opcodes[0][3]
            chg_j2 = changed_opcodes[-1][4]
        else:
            chg_i1 = group[0][1]
            chg_i2 = group[-1][2]
            chg_j1 = group[0][3]
            chg_j2 = group[-1][4]

        # Safe line indices for 1-based output
        if chg_i2 > chg_i1:
            a_start = chg_i1 + 1
            a_end = chg_i2
        else:
            a_start = max(1, chg_i1)
            a_end = a_start

        if chg_j2 > chg_j1:
            b_start = chg_j1 + 1
            b_end = chg_j2
        else:
            b_start = max(1, chg_j1)
            b_end = b_start

        # Signals in hunk
        signals: List[str] = []
        if extract_signals_fn:
            signals = extract_signals_fn(preview_lines)

        hunk = Hunk(
            id=hunk_idx,
            change_type=change_type,
            lines_added=group_added,
            lines_removed=group_removed,
            preview=preview_lines,
            signals_in_hunk=signals,
        )

        if is_sql:
            hunk.source_line_start = a_start
            hunk.source_line_end = a_end
            hunk.target_line_start = b_start
            hunk.target_line_end = b_end
        else:
            hunk.a_line_start = a_start
            hunk.a_line_end = a_end
            hunk.b_line_start = b_start
            hunk.b_line_end = b_end

        # Mode body: snippet around hunk (only if include_text_snippets is True)
        if mode == "body" and include_text_snippets:
            # Window around hunk
            win_a1 = max(0, i1 - context_lines)
            win_a2 = min(len(lines_a), i2 + context_lines)
            win_b1 = max(0, j1 - context_lines)
            win_b2 = min(len(lines_b), j2 + context_lines)

            snippet_a = "\n".join(lines_a[win_a1:win_a2])
            snippet_b = "\n".join(lines_b[win_b1:win_b2])

            # Truncate if very large
            if len(snippet_a) > 4096:
                snippet_a = snippet_a[:4096] + "\n... [truncated]"
                hunk.body_truncated = True
            if len(snippet_b) > 4096:
                snippet_b = snippet_b[:4096] + "\n... [truncated]"
                hunk.body_truncated = True

            if is_sql:
                hunk.body_source = snippet_a
                hunk.body_target = snippet_b
            else:
                hunk.body_a = snippet_a
                hunk.body_b = snippet_b

        hunks.append(hunk)
        hunk_idx += 1

    # Unified diff string: ONLY when include_unified_diff=True and mode in ("hunks", "body")
    unified_diff_str = ""
    if include_unified_diff and mode in ("hunks", "body"):
        udiff_gen = difflib.unified_diff(
            lines_a,
            lines_b,
            fromfile=file_label_a,
            tofile=file_label_b,
            n=context_lines,
            lineterm="",
        )
        udiff_lines: List[str] = []
        for line in udiff_gen:
            if len(udiff_lines) >= max_diff_lines:
                diff_truncated = True
                udiff_lines.append("... [diff truncated]")
                break
            udiff_lines.append(line)
        unified_diff_str = "\n".join(udiff_lines)

    content_diff = ContentDiff(
        lines_added=total_added,
        lines_removed=total_removed,
        hunk_count=total_hunk_count,
        hunks=hunks,
        diff_truncated=diff_truncated or (len(hunks) < total_hunk_count),
        unified_diff=unified_diff_str,
    )
    if is_sql:
        content_diff.lines_source = len(lines_a)
        content_diff.lines_target = len(lines_b)
    else:
        content_diff.lines_a = len(lines_a)
        content_diff.lines_b = len(lines_b)

    return content_diff

