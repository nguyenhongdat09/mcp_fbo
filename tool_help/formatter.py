"""Serialize response tool_help -> JSON compact."""
from __future__ import annotations

import json


def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1)
