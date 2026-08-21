"""2-tier parameter effects detector for FastBusiness FBO SQL procedures."""

from __future__ import annotations

import re
from sql_object_summary.models import ParamEffect, ParamInfo

SPECIFIC_PARAM_RULES = [
    {
        "param": r"^@\w+_yn$",
        "patterns": [
            r"@\w+_yn\s*=",
            r"@\w+_yn\s*=\s*'1'",
            r"@\w+_yn\s*=\s*'0'",
        ],
        "role": "branching",
        "effect": "Toggles business feature / data creation / optional processing (Yes/No)",
        "confidence": "high",
    },
    {
        "param": r"^@form$",
        "patterns": [
            r"@form\s*=",
            r"dmctns",
            r"bcnsky",
            r"glns",
        ],
        "role": "branching",
        "effect": "Selects report form template / chỉ tiêu structure (dmctns, bcnsky)",
        "confidence": "high",
    },
    {
        "param": r"^@mau_bc$",
        "patterns": [
            r"@mau_bc\s*=",
            r"bcnsky",
            r"glns",
            r"#pivot",
            r"xpivot",
        ],
        "role": "branching",
        "effect": "Controls report template / layout / pivot or NS structure",
        "confidence": "high",
    },
    {
        "param": r"^@ma_vv$",
        "patterns": [
            r"@ma_vv\s*=",
            r"dmvv",
            r"#dmvv",
            r"JobCalcXStruct",
        ],
        "role": "filter",
        "effect": "Filters by job/project (vụ việc / dự án)",
        "confidence": "medium",
    },
    {
        "param": r"^@kieu_xem$",
        "patterns": [r"@kieu_xem\s*="],
        "role": "branching",
        "effect": "Controls view mode / report display type",
        "confidence": "medium",
    },
    {
        "param": r"^@(loai|source|phan_loai|ticket|Type|Action|status|kieu_\w+|kieu)$",
        "patterns": [r"@(loai|source|phan_loai|ticket|Type|Action|status|kieu_\w+|kieu)\s*="],
        "role": "branching",
        "effect": "Controls business processing mode / transaction category",
        "confidence": "medium",
    },
    {
        "param": r"^@Status$",
        "patterns": [
            r"@Status\s*=\s*'1'",
            r"@Status\s*=\s*'0'",
            r"DATEADD\s*\(\s*day\s*,\s*1",
        ],
        "role": "branching",
        "effect": "Affects period boundary / ngay_tu (+1 day when '1')",
        "confidence": "medium",
    },
    {
        "param": r"^@Language$",
        "patterns": [r"@Language\s*=\s*'[VE]'", r"ten_\w+2"],
        "role": "branching",
        "effect": "Selects Vietnamese vs English field aliases / column headers",
        "confidence": "high",
    },
    {
        "param": r"^@Admin$",
        "patterns": [r"@Admin\s*=\s*1", r"@Admin\s*=\s*0"],
        "role": "branching",
        "effect": "Bypasses or enforces user rights / data security filters",
        "confidence": "high",
    },
]

INFRA_PARAMS = {"@UserID", "@Admin", "@Language", "@SysDB", "@sysDatabaseName", "@cLan"}


def detect_param_effects(
    source_lines: list[str],
    declared_params: list[ParamInfo],
) -> list[ParamEffect]:
    """Detect parameter effects using 2-tier analysis:

    Tier 1 (Generic): Scans for @param inside IF, CASE WHEN, WHERE, WHILE blocks.
    Tier 2 (Specific): Applies domain-specific rules for known FBO parameters.
    """
    param_names = [p.name for p in declared_params]
    effects_map: dict[str, ParamEffect] = {}

    # Join lines for regex search with line mapping
    full_text = "\n".join(source_lines)

    # 1. Tier 2: Check specific domain rules first
    for rule in SPECIFIC_PARAM_RULES:
        rule_pat = re.compile(rule["param"], re.IGNORECASE)
        for p_name in param_names:
            if rule_pat.match(p_name):
                evidence_lines = []
                matched = False
                for sub_pat in rule["patterns"]:
                    for idx, line in enumerate(source_lines, start=1):
                        if re.search(sub_pat, line, re.IGNORECASE):
                            matched = True
                            if idx not in evidence_lines:
                                evidence_lines.append(idx)
                if matched:
                    effects_map[p_name] = ParamEffect(
                        param=p_name,
                        role=rule["role"],
                        effect=rule["effect"],
                        confidence=rule["confidence"],
                        evidence_lines=evidence_lines[:5],
                    )

    # 2. Tier 1: Generic detector for any remaining params
    for p_name in param_names:
        if p_name in effects_map:
            continue

        esc_param = re.escape(p_name)
        branch_pat = re.compile(rf"\b(IF|CASE|WHEN)\b[^\n;]*?{esc_param}", re.IGNORECASE)
        where_pat = re.compile(rf"\b(WHERE|HAVING)\b[^\n;]*?{esc_param}", re.IGNORECASE)
        while_pat = re.compile(rf"\b(WHILE)\b[^\n;]*?{esc_param}", re.IGNORECASE)

        evidence_lines = []
        role = None

        for idx, line in enumerate(source_lines, start=1):
            if while_pat.search(line):
                role = "loop_bound"
                evidence_lines.append(idx)
            elif branch_pat.search(line):
                if not role:
                    role = "branching"
                evidence_lines.append(idx)
            elif where_pat.search(line):
                if not role:
                    role = "filter"
                evidence_lines.append(idx)

        if role and evidence_lines:
            # Only record if we have meaningful evidence
            conf = "medium" if len(evidence_lines) >= 2 else "low"
            if conf != "low":
                effects_map[p_name] = ParamEffect(
                    param=p_name,
                    role=role,
                    effect=f"Parameter {p_name} used in {role} logic",
                    confidence=conf,
                    evidence_lines=evidence_lines[:5],
                )

    # Return only medium and high confidence effects
    filtered = [e for e in effects_map.values() if e.confidence in ("medium", "high")]

    # Priority sorting: Business params before Infra params (@Admin, @Language), High before Medium
    def _effect_sort_key(e: ParamEffect) -> tuple[int, int, int, str]:
        is_infra = 1 if e.param in INFRA_PARAMS else 0
        conf_score = 0 if e.confidence == "high" else 1
        is_generic_tier1 = 1 if (e.effect.startswith("Parameter ") and "used in" in e.effect) else 0
        return (is_infra, conf_score, is_generic_tier1, e.param)

    filtered.sort(key=_effect_sort_key)
    return filtered[:5]
