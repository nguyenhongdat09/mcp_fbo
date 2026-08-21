"""Configuration options and default regex patterns for object analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

DEFAULT_INFRA_PATTERNS = [
    r"^FastBusiness\$",
    r"^ff_",
    r"^fsd_",
]

DEFAULT_SYSTEM_PATTERNS = [
    r"^sp_",
    r"^xp_",
    r"^fn_",
]

DEFAULT_BUSINESS_PATTERNS = [
    r"^zc_",
    r"^rs_rpt",
    r"^rs_",
    r"^zcs?",
]

DEFAULT_EXCLUDE_LIKE = [
    r"^FastBusiness\$",
    r"^ff_",
    r"^fsd_",
]


@dataclass
class AnalyzeOptions:
    max_depth: int = 1
    max_objects: int = 30
    expand: list[str] = field(default_factory=list)
    exclude_like: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_LIKE))
    infra_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_INFRA_PATTERNS))
    system_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_SYSTEM_PATTERNS))
    business_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_BUSINESS_PATTERNS))
    include_called_by: bool = False
    max_snippet_lines: int = 120
    max_full_chars: int = 50000
    use_cache: bool = True

    def __post_init__(self):
        if self.exclude_like is None:
            self.exclude_like = list(DEFAULT_EXCLUDE_LIKE)
        if self.infra_patterns is None:
            self.infra_patterns = list(DEFAULT_INFRA_PATTERNS)
        if self.system_patterns is None:
            self.system_patterns = list(DEFAULT_SYSTEM_PATTERNS)
        if self.business_patterns is None:
            self.business_patterns = list(DEFAULT_BUSINESS_PATTERNS)
        if self.expand is None:
            self.expand = []

