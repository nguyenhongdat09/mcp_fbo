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

    # 1. USER_TABLE: IF NOT EXISTS (...) BEGIN <table/index DDL> END
    #    CREATE TRIGGER phải là statement đầu batch → tách theo GO TRƯỚC khi wrap,
    #    trigger segments emit sau END dưới dạng IF OBJECT_ID IS NULL EXEC(N'...').
    if o_type == "U" or t_desc == "USER_TABLE" or "TABLE" in t_desc:
        segments = [
            s.strip()
            for s in re.split(
                r"^\s*GO\s*(?:;)?\s*$", clean_script, flags=re.MULTILINE | re.IGNORECASE
            )
            if s.strip()
        ]
        table_segs: list[str] = []
        trigger_segs: list[str] = []
        for seg in segments:
            if re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\b", seg, re.IGNORECASE):
                trigger_segs.append(seg)
            else:
                table_segs.append(seg)

        first = table_segs[0] if table_segs else ""
        # If already has IF NOT EXISTS wrapper, extract inner DDL
        if re.search(r"IF\s+NOT\s+EXISTS", first, re.IGNORECASE):
            begin_match = re.search(r"\bBEGIN\b", first, re.IGNORECASE)
            end_match = list(re.finditer(r"\bEND\b", first, re.IGNORECASE))
            if begin_match and end_match:
                first = first[begin_match.end():end_match[-1].start()].strip()

        clean_ddl = "\n\n".join([first] + table_segs[1:]).strip()
        clean_ddl = re.sub(r"\n{3,}", "\n\n", clean_ddl)

        wrapped = (
            f"IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'{full_name}') AND type = N'U')\n"
            f"BEGIN\n"
            f"{clean_ddl}\n"
            f"END"
        )
        for seg in trigger_segs:
            wrapped += "\nGO\n" + _wrap_trigger_ddl(seg, schema_clean)
        return wrapped

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

    # 5. TRIGGER: DROP + GO + CREATE TRIGGER (trigger là statement đầu batch)
    if o_type == "TR" or "TRIGGER" in t_desc:
        inner = clean_script
        inner = re.sub(r"IF\s+OBJECT_ID\([^)]+\)\s+IS\s+NOT\s+NULL\s+DROP\s+TRIGGER\s+[^;\n]+(?:;)?(?:\s*GO)?", "", inner, flags=re.DOTALL | re.IGNORECASE).strip()
        inner = re.sub(r"^\s*GO\s*(?:;)?\s*$", "", inner, flags=re.MULTILINE | re.IGNORECASE).strip()
        return (
            f"IF OBJECT_ID(N'{full_name}', N'TR') IS NOT NULL\n"
            f"    DROP TRIGGER {full_name}\n"
            f"GO\n"
            f"{inner}"
        )

    return clean_script


def _wrap_trigger_ddl(trigger_sql: str, schema: str = "dbo") -> str:
    """Wrap 1 đoạn CREATE TRIGGER thành batch an toàn.

    CREATE TRIGGER bắt buộc là statement đầu batch → emit
    ``IF OBJECT_ID(...) IS NULL EXEC(N'<ddl>')`` (EXEC là statement đầu,
    body trigger nằm trong dynamic SQL nên hợp lệ). Không bắt được tên
    trigger → trả raw (vẫn là batch riêng sau GO).
    """
    if re.match(r"^\s*IF\s+OBJECT_ID\b", trigger_sql, re.IGNORECASE):
        return trigger_sql  # đã wrap (idempotent khi wrap_check_exists chạy 2 lần)
    m = re.search(
        r"\bCREATE\s+(?:OR\s+ALTER\s+)?TRIGGER\s+"
        r"(?:(?:\[(?P<qs>[^\]]+)\]|(?P<s>[\w$]+))\s*\.\s*)?"
        r"(?:\[(?P<qn>[^\]]+)\]|(?P<n>[\w$]+))",
        trigger_sql,
        re.IGNORECASE,
    )
    if not m:
        return trigger_sql
    trg_name = m.group("qn") or m.group("n") or ""
    trg_schema = m.group("qs") or m.group("s") or schema or "dbo"
    esc = trigger_sql.replace("'", "''")
    return (
        f"IF OBJECT_ID(N'[{trg_schema}].[{trg_name}]', N'TR') IS NULL\n"
        f"EXEC(N'{esc}')"
    )


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
