"""Formatter to wrap summary_xml JSON dictionary in MCP markdown format."""

from __future__ import annotations

import json
from typing import Any


def format_summary_xml_result(result: dict[str, Any]) -> str:
    """Format summary_xml dictionary into markdown response string for MCP."""
    file_name = result.get("file", "Unknown.xml")
    js_status = result.get("js", {}).get("parse_status", "empty")
    sql_status = result.get("sql", {}).get("parse_status", "empty")
    field_count = len(result.get("fields") or [])

    json_body = json.dumps(result, ensure_ascii=False, indent=2)

    status_tag = "[OK]" if result.get("success", True) else "[ERROR]"

    return (
        f"{status_tag} read_local_file summary_xml\n"
        f"File: {file_name}\n"
        f"Parse JS: {js_status}\n"
        f"Parse SQL: {sql_status}\n"
        f"Fields: {field_count}\n\n"
        f"```json\n{json_body}\n```"
    )
