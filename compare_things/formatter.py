"""JSON formatter for compare_things output."""

from __future__ import annotations

import json
from typing import Any, Dict


def format_compare_result(result: Dict[str, Any]) -> str:
    """Format comparison result dictionary as formatted JSON string."""
    return json.dumps(result, ensure_ascii=False, indent=2)
