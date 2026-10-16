"""Dựng request Jev (state + questions) cho tool_help — nguồn DUY NHẤT.

Service, eval harness (scratch/jev_eval.py) và dump payload đều gọi
``build_jev_request`` để eval đo đúng request production.

Style:
- ``v1`` (mặc định hiện tại): catalog mô tả nằm trong ``state``,
  ``criteria`` = {option: null}, instructions trỏ "meanings: state.x".
- ``v2`` (theo docs TypeSafe): mô tả option nằm THẲNG trong ``criteria``
  dạng object ``{what, signals, not_for}``; state chỉ còn context chung;
  text step nằm trong instructions của chính question (không question nào
  phải đọc các step khác). Bật bằng config ``jev.prompt_style: v2`` sau khi
  ``jev_eval.py --steps-set`` cho thấy không tụt.
"""
from __future__ import annotations

import re

from .cards import (REQUIREMENT_TYPE_CATALOG, TASK_TYPE_CATALOG)

AGENT_CONTEXT = (
    "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; "
    "data = SQL Server. MCP tools available."
)

_REQ_RULES_V1 = (
    "Classify state.task_requirement into ONE "
    "requirement_type. template types (category_*/report_*/"
    "voucher) ONLY for create-from-scratch. EXCEPTION: "
    "retrieve_flow_* also fits ADDING lay du lieu onto an "
    "existing voucher (creates new {X}Filter/{X}MultiForm/"
    "{X}MultiGrid/{X}Lookup); popup_* fits ADDING a button popping "
    "a {X}Filter form onto existing Dir/Grid (pick voucher -> "
    "popup_lookup_*, input params -> popup_input_form). voucher_* "
    "by UR signals: "
    "duyet/phe duyet/trinh duyet->approval; ngoai te/ma_nt/"
    "ty gia/nguyen te->currency; both->voucher_approval_"
    "currency; UR says khong/none->no_* variant; signals "
    "unstated->'voucher'. edits/fixes/queries on existing "
    "targets or ambiguous->'none' high probability. "
    "meanings: state.requirement_type_catalog"
)

_REQ_RULES_V2 = [
    "template types (category_*/report_*/voucher*) ONLY for creating a "
    "new screen/report from scratch",
    "EXCEPTION: retrieve_flow_* also fits ADDING lay du lieu onto an "
    "existing voucher (new {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup)",
    "EXCEPTION: popup_* fits ADDING a button popping a {X}Filter form "
    "onto existing Dir/Grid: pick voucher -> popup_lookup_*, input "
    "params -> popup_input_form",
    "voucher_* by signals: duyet/phe duyet/trinh duyet -> approval; "
    "ngoai te/ma_nt/ty gia/nguyen te -> currency; both -> "
    "voucher_approval_currency; UR says khong -> no_* variant; signals "
    "unstated -> voucher",
    "edits/fixes/queries on existing targets or ambiguous -> none",
]

# Step chỉ nói tới file .sql (không .xml) → loại các option chỉ dành cho
# XML controller khỏi criteria của step đó (lọc bằng code, không hỏi Jev).
_XML_ONLY_TYPES = ("entity_content", "entity_path", "entity_list",
                   "entity_check", "diff_xml", "find_by_title")
_SQL_FILE_RE = re.compile(r"\.sql\b", re.IGNORECASE)
_XML_FILE_RE = re.compile(r"\.xml\b|controller|\bDir/|\bGrid/|\bFilter/",
                          re.IGNORECASE)


# ---------------------------------------------------------------- v2 criteria
def structure_desc(text) -> object:
    """Tách jev_desc telegraphic → ``{what, signals, not_for}``.

    jev_desc viết theo convention ``<what>; signals:<...>; not:<a (x), b>``
    (xem docstring cards.py) nên tách được tự động — giữ 1 nguồn mô tả,
    không viết tay lại 56 entry.
    """
    if not isinstance(text, str):
        return text
    parts = [p.strip() for p in re.split(r";\s*(?=signals:|not:)", text)]
    out: dict = {"what": parts[0]}
    for p in parts[1:]:
        if p.startswith("signals:"):
            out["signals"] = p[len("signals:"):].strip()
        elif p.startswith("not:"):
            out["not_for"] = [s.strip() for s in
                              re.split(r",\s*(?![^()]*\))",
                                       p[len("not:"):]) if s.strip()]
    return out if len(out) > 1 else parts[0]


def _req_entry_v2(v) -> object:
    if isinstance(v, dict):
        entry = structure_desc(v.get("desc", ""))
        entry = dict(entry) if isinstance(entry, dict) else {"what": entry}
        if v.get("examples"):
            entry["examples"] = v["examples"]
        return entry
    return structure_desc(v)


TASK_CRITERIA_V2 = {k: structure_desc(v) for k, v in TASK_TYPE_CATALOG.items()}
REQ_CRITERIA_V2 = {k: _req_entry_v2(v)
                   for k, v in REQUIREMENT_TYPE_CATALOG.items()}


def step_criteria_v2(step: str) -> dict:
    """Criteria cho 1 step — bỏ option XML-only khi step chỉ nói về .sql."""
    if _SQL_FILE_RE.search(step) and not _XML_FILE_RE.search(step):
        return {k: v for k, v in TASK_CRITERIA_V2.items()
                if k not in _XML_ONLY_TYPES}
    return TASK_CRITERIA_V2


# ------------------------------------------------------------------ builders
def build_questions_v1(steps: list[str], task_requirement: str = "") -> dict:
    criteria = {k: None for k in TASK_TYPE_CATALOG}
    questions = {
        f"step{i}_tool": {
            "type": "choice",
            "instructions": (
                f"task_type for step '{s}'? "
                "meanings: state.task_type_catalog"
            ),
            "criteria": criteria,
        }
        for i, s in enumerate(steps, 1)
    }
    if task_requirement:
        questions["requirement_type"] = {
            "type": "choice",
            "instructions": _REQ_RULES_V1,
            "criteria": {k: None for k in REQUIREMENT_TYPE_CATALOG},
        }
    return questions


def build_questions_v2(steps: list[str], task_requirement: str = "") -> dict:
    questions = {
        f"step{i}_tool": {
            "type": "choice",
            "instructions": {
                "question": "Which task_type (tool + mode) best fits this "
                            "single plan step?",
                "step": s,
            },
            "criteria": step_criteria_v2(s),
        }
        for i, s in enumerate(steps, 1)
    }
    if task_requirement:
        questions["requirement_type"] = {
            "type": "choice",
            "instructions": {
                "question": "Classify `task_requirement` into ONE "
                            "requirement_type",
                "rules": _REQ_RULES_V2,
            },
            "criteria": REQ_CRITERIA_V2,
        }
    return questions


def build_jev_request(steps: list[str], task_requirement: str = "",
                      context: dict | None = None,
                      style: str = "v1") -> tuple[dict, dict]:
    """→ (state, questions) cho câu hỏi routing chính."""
    context = context or {}
    if style == "v2":
        state: dict = {"agent_context": AGENT_CONTEXT}
        if task_requirement:
            state["task_requirement"] = task_requirement
        ctx = {k: context[k] for k in ("path", "ext", "db")
               if context.get(k)}
        if ctx:
            state["context"] = ctx
        return state, build_questions_v2(steps, task_requirement)

    state = {
        "agent_context": AGENT_CONTEXT,
        "task_type_catalog": TASK_TYPE_CATALOG,
        "steps": steps,
    }
    if task_requirement:
        state["task_requirement"] = task_requirement
        state["requirement_type_catalog"] = REQUIREMENT_TYPE_CATALOG
    questions = build_questions_v1(steps, task_requirement)
    return state, questions
