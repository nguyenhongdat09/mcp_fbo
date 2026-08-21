"""Preprocess T-SQL text before ANTLR parse."""

from __future__ import annotations


def preprocess_definition(text: str) -> str:
    """Remove GO batch separators; normalize newlines."""
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().upper() == "GO":
            continue
        lines.append(line.rstrip("\r"))
    return "\n".join(lines)
