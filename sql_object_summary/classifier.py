"""Classifier for object kinds: infra vs system vs business vs view."""

from __future__ import annotations

import re
from typing import Literal

from sql_object_summary.options import (
    DEFAULT_INFRA_PATTERNS,
    DEFAULT_SYSTEM_PATTERNS,
    DEFAULT_BUSINESS_PATTERNS,
)


def classify_object(
    name: str,
    *,
    object_type: str = "PROCEDURE",
    infra_patterns: list[str] | None = None,
    system_patterns: list[str] | None = None,
    business_patterns: list[str] | None = None,
) -> Literal["infra", "system", "business", "view"]:
    """Classify an SQL object by its name and type.

    - If object_type == "VIEW" -> "view"
    - If matches system_patterns (sp_*, xp_*, fn_*) -> "system"
    - If matches infra_patterns (FastBusiness$*, ff_*, fsd_*) -> "infra"
    - Otherwise -> "business"
    """
    clean_type = object_type.upper().strip()
    if clean_type == "VIEW" or clean_type == "V":
        return "view"

    # Strip schema prefix if present (e.g. dbo.FastBusiness$Balance -> FastBusiness$Balance)
    bare_name = name.split(".", 1)[-1] if "." in name else name

    # 1. System objects (sp_executesql, sp_helptext, etc.)
    systems = system_patterns if system_patterns is not None else DEFAULT_SYSTEM_PATTERNS
    for pat in systems:
        if re.search(pat, bare_name, re.IGNORECASE):
            return "system"

    # 2. Infra objects (FastBusiness$*, ff_*, fsd_*)
    infras = infra_patterns if infra_patterns is not None else DEFAULT_INFRA_PATTERNS
    for pat in infras:
        if re.search(pat, bare_name, re.IGNORECASE):
            return "infra"

    return "business"
