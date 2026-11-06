"""Formatter kết quả acceptance_xml -> JSON string cho MCP response."""

from __future__ import annotations

import json
from typing import Any, Dict


def format_acceptance_result(result: Dict[str, Any]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False)
