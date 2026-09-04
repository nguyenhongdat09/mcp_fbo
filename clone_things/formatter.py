"""JSON Formatter for clone_things tool."""

import json
from typing import Any


def format_clone_result(result: dict[str, Any]) -> str:
    """Serialize clone_things result dict to formatted JSON string."""
    return json.dumps(result, ensure_ascii=False, indent=2)
