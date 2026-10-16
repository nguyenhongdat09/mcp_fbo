"""Định tuyến 2 tầng (recipe "Hierarchical classification" của TypeSafe).

Thay vì 1 Choice phẳng 39 task_type (dễ nhầm cặp gần nhau như
read_summary/read_flat), mỗi step hỏi:
- tầng 1: Choice ``tool`` (8 tool + no_match);
- tầng 2: Choice task_type TRONG từng tool (chỉ tool có >= 2 task_type).
Mọi câu hỏi gửi cùng 1 request (song song). Code giữ beam K=3: chỉ xét
3 tool xác suất cao nhất; điểm path = p_tool × p_type. Confidence =
phán đoán yếu nhất (min confidence 2 tầng) — theo cookbook function calling.

Kết quả quy về dạng answer Choice phẳng ``{choice, probabilities,
confidence}`` để service xử lý y như routing flat.

Bật bằng config ``jev.routing: hierarchical``; chỉ đổi mặc định khi
``jev_eval.py --steps-set --routing hierarchical`` không tụt so với flat.
"""
from __future__ import annotations

from .cards import TASK_TYPES
from .request import TASK_CRITERIA_V2

BEAM_K = 3

TOOL_CRITERIA = {
    "read_local_file": {
        "what": "read ONE known file on disk (XML controller, .sql, .js, "
                "Report/Templates): overview, full, raw, a named region, "
                "or old_string before editing",
        "not_for": ["finding which file contains something (search_files)",
                    "DB objects (query_database)"]},
    "search_files": {
        "what": "find files/places in the project: by content string, by "
                "file name/glob, where a JS symbol is defined/used",
        "not_for": ["reading a known file (read_local_file)"]},
    "compare_things": {
        "what": "compare/diff two files, folders, XML controllers or DB "
                "schemas across projects; list a folder"},
    "clone_things": {
        "what": "copy/export things: proc/func/view to .sql (ALTER), "
                "table rows to script, files/controller suites, templates, "
                "save-as an existing function, new empty .sql file"},
    "query_database": {
        "what": "SQL Server: run SELECT/DML, inspect table schema or proc "
                "summary, search DB objects, run/check .sql file, balance "
                "procs, add field",
        "not_for": ["exporting proc source to a file (clone_things)"]},
    "get_xml_entities": {
        "what": "XML DOCTYPE entities: list, content, where declared, check "
                "undeclared/missing"},
    "search_qlyc": {
        "what": "search past user requests/tickets (QLYC) by description "
                "or ticket code"},
    "no_match": {
        "what": "no tool fits — manual work only (business reasoning, "
                "hand-writing content)"},
}


def _types_by_tool() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for k, v in TASK_TYPES.items():
        out.setdefault(v["tool"] or "no_match", []).append(k)
    return out


TYPES_BY_TOOL = _types_by_tool()


def build_hierarchical_questions(steps: list[str]) -> dict:
    qs: dict = {}
    for i, s in enumerate(steps, 1):
        qs[f"step{i}_toolpick"] = {
            "type": "choice",
            "instructions": {"question": "Which tool does this single plan "
                                         "step need?", "step": s},
            "criteria": TOOL_CRITERIA,
        }
        for tool, types in TYPES_BY_TOOL.items():
            if len(types) < 2:
                continue
            qs[f"step{i}_tt_{tool}"] = {
                "type": "choice",
                "instructions": {
                    "question": f"IF this step uses {tool}, which mode/"
                                "task_type fits?", "step": s},
                "criteria": {t: TASK_CRITERIA_V2.get(t) for t in types},
            }
    return qs


def resolve_hierarchical(answers: dict, i: int) -> dict:
    """→ {task_type, top3, confidence, probabilities} cho step i."""
    pick = answers.get(f"step{i}_toolpick") or {}
    tool_probs = pick.get("probabilities") or {}
    beam = sorted(tool_probs.items(), key=lambda x: -x[1])[:BEAM_K]
    paths: dict[str, float] = {}
    tt_conf: dict[str, float] = {}
    for tool, p_tool in beam:
        types = TYPES_BY_TOOL.get(tool) or []
        if len(types) == 1:
            paths[types[0]] = float(p_tool)
            continue
        ans = answers.get(f"step{i}_tt_{tool}") or {}
        tt_conf[tool] = float(ans.get("confidence") or 0.0)
        for t, p in (ans.get("probabilities") or {}).items():
            if t in TASK_TYPES:
                paths[t] = float(p_tool) * float(p)
    if not paths:
        return {"task_type": "?", "top3": [], "confidence": None,
                "probabilities": {}}
    ranked = sorted(paths.items(), key=lambda x: -x[1])
    best = ranked[0][0]
    best_tool = TASK_TYPES[best]["tool"] or "no_match"
    confs = [float(pick.get("confidence") or 0.0)]
    if best_tool in tt_conf:
        confs.append(tt_conf[best_tool])
    total = sum(paths.values()) or 1.0
    return {"task_type": best,
            "top3": [k for k, _ in ranked[:3]],
            "confidence": round(min(confs), 3),
            "probabilities": {k: round(v / total, 4) for k, v in ranked}}


def as_flat_answer(answers: dict, i: int) -> dict:
    """Quy kết quả 2 tầng về dạng answer Choice phẳng cho service."""
    r = resolve_hierarchical(answers, i)
    if r["task_type"] == "?":
        return {}
    return {"choice": r["task_type"], "probabilities": r["probabilities"],
            "confidence": r["confidence"], "router": "hierarchical"}
