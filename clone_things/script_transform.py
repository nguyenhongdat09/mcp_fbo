"""SQL script transformation and wrapping utilities for clone_things."""

from __future__ import annotations

import re


def wrap_check_exists(
    script: str,
    clean_name: str,
    schema: str = "dbo",
    obj_type: str = "",
    type_desc: str = "",
) -> str:
    """Wrap SQL object definition with check exists logic to ensure idempotent execution."""
    clean_script = script.strip()
    if not clean_script:
        return ""

    schema_clean = (schema or "dbo").strip()
    obj_clean = clean_name.strip()
    full_name = f"[{schema_clean}].[{obj_clean}]"

    t_desc = (type_desc or "").upper()
    o_type = (obj_type or "").upper()

    # 1. USER_TABLE: IF NOT EXISTS (...) BEGIN ... END
    if o_type == "U" or t_desc == "USER_TABLE" or "TABLE" in t_desc:
        inner = clean_script
        # If already has IF NOT EXISTS wrapper, extract inner DDL
        if re.search(r"IF\s+NOT\s+EXISTS", inner, re.IGNORECASE):
            begin_match = re.search(r"\bBEGIN\b", inner, re.IGNORECASE)
            end_match = list(re.finditer(r"\bEND\b", inner, re.IGNORECASE))
            if begin_match and end_match:
                inner = inner[begin_match.end():end_match[-1].start()].strip()

        # Strip all GO statements: GO is a batch separator and CANNOT be inside BEGIN ... END
        clean_ddl = re.sub(r"^\s*GO\s*(?:;)?\s*$", "", inner, flags=re.MULTILINE | re.IGNORECASE).strip()
        clean_ddl = re.sub(r"\n{3,}", "\n\n", clean_ddl)

        return (
            f"IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'{full_name}') AND type = N'U')\n"
            f"BEGIN\n"
            f"{clean_ddl}\n"
            f"END"
        )

    # 2. STORED PROCEDURE
    if o_type == "P" or "PROCEDURE" in t_desc:
        inner = clean_script
        inner = re.sub(rf"IF\s+OBJECT_ID\([^)]+\)\s+IS\s+NOT\s+NULL\s+DROP\s+PROCEDURE\s+[^;\n]+(?:;)?(?:\s*GO)?", "", inner, flags=re.DOTALL | re.IGNORECASE).strip()
        inner = re.sub(r"^\s*GO\s*(?:;)?\s*$", "", inner, flags=re.MULTILINE | re.IGNORECASE).strip()
        return (
            f"IF OBJECT_ID(N'{full_name}', N'P') IS NOT NULL\n"
            f"    DROP PROCEDURE {full_name}\n"
            f"GO\n"
            f"{inner}"
        )

    # 3. FUNCTION
    if o_type in ("FN", "IF", "TF") or "FUNCTION" in t_desc:
        inner = clean_script
        inner = re.sub(rf"IF\s+OBJECT_ID\([^)]+\)\s+IS\s+NOT\s+NULL\s+DROP\s+FUNCTION\s+[^;\n]+(?:;)?(?:\s*GO)?", "", inner, flags=re.DOTALL | re.IGNORECASE).strip()
        inner = re.sub(r"^\s*GO\s*(?:;)?\s*$", "", inner, flags=re.MULTILINE | re.IGNORECASE).strip()
        return (
            f"IF OBJECT_ID(N'{full_name}') IS NOT NULL\n"
            f"    DROP FUNCTION {full_name}\n"
            f"GO\n"
            f"{inner}"
        )

    # 4. VIEW
    if o_type == "V" or "VIEW" in t_desc:
        inner = clean_script
        inner = re.sub(rf"IF\s+OBJECT_ID\([^)]+\)\s+IS\s+NOT\s+NULL\s+DROP\s+VIEW\s+[^;\n]+(?:;)?(?:\s*GO)?", "", inner, flags=re.DOTALL | re.IGNORECASE).strip()
        inner = re.sub(r"^\s*GO\s*(?:;)?\s*$", "", inner, flags=re.MULTILINE | re.IGNORECASE).strip()
        return (
            f"IF OBJECT_ID(N'{full_name}', N'V') IS NOT NULL\n"
            f"    DROP VIEW {full_name}\n"
            f"GO\n"
            f"{inner}"
        )

    return clean_script


def transform_create_to_alter(script: str) -> str:
    """
    Transform CREATE PROCEDURE/PROC/FUNCTION/VIEW statement to ALTER.
    Strips any leading DROP statements.
    Preserves CREATE OR ALTER, already ALTER, and CREATE TABLE.
    """
    if not script:
        return ""
    # Strip any leading IF OBJECT_ID(...) DROP ... GO
    clean_script = re.sub(
        r"(?is)^\s*IF\s+OBJECT_ID\([^)]+\)\s+IS\s+NOT\s+NULL\s+DROP\s+(?:PROC(?:EDURE)?|FUNCTION|VIEW)\s+[^;\n]+(?:;)?(?:\s*GO)?\s*",
        "",
        script,
    ).strip()
    pat = r"(?im)^(\s*)CREATE(\s+)(?!OR\s+ALTER\b)(PROC(?:EDURE)?|FUNCTION|VIEW)\b"
    return re.sub(pat, r"\1ALTER\2\3", clean_script, count=1)
