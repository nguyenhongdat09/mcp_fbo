"""Formatter for summary_object MCP tool output string (Markdown format)."""

from __future__ import annotations

import json
from typing import Any


def format_summary_result(result: dict[str, Any]) -> str:
    """Format dictionary result into clean Markdown for MCP client."""
    if not result.get("success", False):
        err = result.get("error", "error")
        msg = result.get("message", "Unknown error")
        return f"[ERROR] {msg}\nError code: {err}"

    mode = result.get("mode", "summary")
    obj_name = result.get("object", "unknown")
    obj_type = result.get("object_type", "OBJECT")
    db = result.get("database", "")
    parse_status = result.get("parse_status", "ok")
    cache_hit = result.get("meta", {}).get("cache_hit", False)

    cache_label = "hit" if cache_hit else "miss"
    db_label = f" @ {db}" if db else ""

    header_lines = [
        "[OK] summary_object",
        f"Object: {obj_name} ({obj_type})",
        f"Mode: {mode}",
    ]
    if db:
        header_lines.append(f"Database: {db}")
    if parse_status:
        header_lines.append(f"Parse: {parse_status}")
    header_lines.append(f"Cache: {cache_label}")

    header = "\n".join(header_lines)
    json_str = json.dumps(result, ensure_ascii=False, indent=2)

    return f"{header}\n\n```json\n{json_str}\n```"
