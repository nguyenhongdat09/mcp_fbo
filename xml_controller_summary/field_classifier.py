"""Classifier to convert raw XML field definitions into concise FieldSummary items."""

from __future__ import annotations

import re
from typing import Literal
from xml_controller_summary.models import FieldSummary
from xml_controller_summary.extract import RawField

_ONCHANGE_RE = re.compile(
    r"(?:onchange|onclick)\s*=\s*[\"']\s*([a-zA-Z0-9_$]+)\s*\(",
    re.IGNORECASE,
)

_NUMBER_TYPES = {
    "decimal", "int16", "int32", "int64", "byte", "double", "single",
    "numeric", "money", "smallmoney", "bigint", "int", "smallint", "tinyint", "float", "real",
}


def map_field_type(attrs: dict[str, str], items_attrs: dict[str, str]) -> Literal["char", "number", "checkbox", "date"]:
    """Map XML field attributes to one of 4 bucket types: char, number, checkbox, date."""
    items_style = (items_attrs.get("style") or "").strip().lower()
    if items_style == "checkbox":
        return "checkbox"

    raw_type = (attrs.get("type") or "").strip()
    tl = raw_type.lower()

    if tl in {"checkbox", "boolean"}:
        return "checkbox"
    if "date" in tl or tl == "smalldatetime" or tl == "datetime2":
        return "date"
    if tl in _NUMBER_TYPES:
        return "number"

    return "char"


def extract_lookup(items_attrs: dict[str, str]) -> str | None:
    """Extract lookup controller reference from items element."""
    controller = (items_attrs.get("controller") or "").strip()
    return controller if controller else None


def extract_onchange(client_script: str) -> str | None:
    """Extract onchange handler function name from clientScript CDATA."""
    if not client_script:
        return None
    m = _ONCHANGE_RE.search(client_script)
    return m.group(1) if m else None


def classify_field(raw: RawField) -> FieldSummary:
    """Convert a single RawField into a FieldSummary."""
    f_type = map_field_type(raw.attrs, raw.items_attrs)
    lookup = extract_lookup(raw.items_attrs)
    onchange = extract_onchange(raw.client_script)

    hidden_val = raw.attrs.get("hidden")
    hidden: bool | None = None
    if hidden_val is not None:
        hidden = hidden_val.lower() == "true"

    allow_nulls_val = raw.attrs.get("allowNulls")
    allow_nulls: bool | None = None
    if allow_nulls_val is not None:
        allow_nulls = allow_nulls_val.lower() == "true"

    return FieldSummary(
        name=raw.name,
        type=f_type,
        lookup=lookup,
        onchange=onchange,
        hidden=hidden,
        allowNulls=allow_nulls,
    )


def classify_fields(raw_fields: list[RawField]) -> list[FieldSummary]:
    """Convert a list of RawFields preserving XML appearance order and merging duplicates by name."""
    fields_by_name: dict[str, FieldSummary] = {}

    for rf in raw_fields:
        curr = classify_field(rf)
        key = curr.name.lower()
        if key not in fields_by_name:
            fields_by_name[key] = curr
        else:
            existing = fields_by_name[key]
            # Merge lookup
            if not existing.lookup and curr.lookup:
                existing.lookup = curr.lookup
            # Merge onchange
            if not existing.onchange and curr.onchange:
                existing.onchange = curr.onchange
            # Merge allowNulls (stricter False takes precedence)
            if curr.allowNulls is False or existing.allowNulls is False:
                existing.allowNulls = False
            elif existing.allowNulls is None and curr.allowNulls is not None:
                existing.allowNulls = curr.allowNulls
            # Merge hidden
            if existing.hidden is None and curr.hidden is not None:
                existing.hidden = curr.hidden
            # Merge type (if existing was generic char and current is more specific)
            if existing.type == "char" and curr.type != "char":
                existing.type = curr.type

    return list(fields_by_name.values())
