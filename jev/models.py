"""Data models cho Jev client."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JevAnswer:
    """Kết quả 1 question Choice từ Jev."""

    choice: str
    confidence: float
    probabilities: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
