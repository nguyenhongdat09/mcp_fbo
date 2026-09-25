"""tool_help — route step -> task_type bằng Jev, trả usage card tĩnh.

Nguyên tắc: Jev chỉ classify task_type (Choice, criteria=null + catalog
trong state). Param giá trị (path/pattern/symbol) agent tự điền theo card.
Mọi exception bắt chặt — tool này là cứu cánh, không được crash.
"""
from __future__ import annotations

import logging

from .cards import (REQUIREMENT_TYPE_CATALOG, TASK_TYPE_CATALOG,
                    TASK_TYPES, TOOL_PARAM_EXAMPLES, card_for,
                    template_block)
from .formatter import dumps
from .keywords import keyword_route

logger = logging.getLogger(__name__)

ALT_PROB_MIN = 0.2          # sàn tuyệt đối cho candidate
NO_MATCH_PROB = 0.9         # no_match >=90% -> "agent tự xử lý step này"

_AGENT_CONTEXT = (
    "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; "
    "data = SQL Server. MCP tools available."
)


def _normalize_steps(steps: tuple) -> list[str]:
    if len(steps) == 1 and isinstance(steps[0], (list, tuple)):
        steps = tuple(steps[0])
    return [str(s).strip() for s in steps if str(s).strip()]


def _build_questions(steps: list[str],
                     task_requirement: str = "") -> dict:
    criteria = {k: None for k in TASK_TYPE_CATALOG}
    questions = {
        f"step{i}_tool": {
            "type": "choice",
            "instructions": (
                f"Which task type best describes this step: '{s}'? "
                "Type meanings are in state.task_type_catalog."
            ),
            "criteria": criteria,
        }
        for i, s in enumerate(steps, 1)
    }
    if task_requirement:
        questions["requirement_type"] = {
            "type": "choice",
            "instructions": (
                "Classify the user requirement in state.task_requirement "
                "into ONE requirement type. IMPORTANT: template types "
                "(category_*, report_*, voucher) are ONLY for requests "
                "that CREATE a brand-new screen/report/category from "
                "scratch. If the request edits/modifies/fixes/queries "
                "something that already exists, or intent is ambiguous, "
                "choose 'none' with high probability. Type meanings are "
                "in state.requirement_type_catalog."
            ),
            "criteria": {k: None for k in REQUIREMENT_TYPE_CATALOG},
        }
    return questions


def _requirement_result(answer: dict) -> dict:
    choice = str(answer.get("choice") or "")
    probs = answer.get("probabilities") or {}
    top = max(probs.values()) if probs else 0
    cutoff = max(ALT_PROB_MIN, top * 0.5)
    cands = [{"task_type": k, "confidence_to_use_top": i}
             for i, (k, v) in enumerate(
                 sorted(probs.items(), key=lambda x: -x[1]), 1)
             if v >= cutoff and k in REQUIREMENT_TYPE_CATALOG]
    out = {"type": choice,
           "confidence_to_use_top": max(len(cands), 1)}
    tpl = template_block(choice)
    if tpl:
        out["template"] = tpl
    elif choice and choice != "none":
        out["note"] = (f"loại '{choice}' chưa có template mẫu — agent tự "
                       "tìm file tương tự trong project rồi dùng "
                       "clone_things type=3 (suite Old->New) để copy/đổi "
                       "tên, sửa nội dung tay")
    alts = [c for c in cands if c["task_type"] != choice]
    if alts:
        out["alternatives"] = alts
    return out


def _candidates(probs: dict) -> list[dict]:
    """Candidate cạnh tranh: p >= max(20%, top_prob/2).

    Top-1 áp đảo (68/29) -> chỉ còn 1 candidate -> confidence_to_use_top=1.
    Phân tán (28/24/22) -> cả 3 cùng cạnh tranh -> =3."""
    if not probs:
        return []
    top = max(probs.values())
    cutoff = max(ALT_PROB_MIN, top * 0.5)
    out = []
    for k, v in sorted(probs.items(), key=lambda x: -x[1]):
        if v >= cutoff and k in TASK_TYPES:
            out.append({"task_type": k, "tool": TASK_TYPES[k]["tool"],
                        "probability": round(v, 3)})
    return out


def _step_result_jev(step: str, answer: dict, cfg: dict) -> dict:
    choice = str(answer.get("choice") or "")
    probs = answer.get("probabilities") or {}
    cands = _candidates(probs)
    # confidence_to_use_top = số candidate cạnh tranh = "đáp án nằm trong
    # top-N": 1 = dùng top-1 luôn; 2/3/... = xem thêm alternatives.
    base = {"step": step, "task_type": choice,
            "confidence_to_use_top": max(len(cands), 1)}

    if choice == "no_match" and probs.get("no_match", 0) >= NO_MATCH_PROB:
        base["note"] = ("không có tool phù hợp — agent tự xử lý step này "
                        "(viết file tay / thao tác web / hỏi user)")
        return base

    card = card_for(choice)
    if card is None:
        # choice lạ hoặc no_match yếu -> keyword fallback riêng step này
        return _step_result_keyword(step)

    base.update(card)
    # Alternatives = các candidate cạnh tranh còn lại, full card như top-1;
    # confidence_to_use_top = thứ hạng của option đó trong top-N
    alts = []
    for rank, c in enumerate(cands, 1):
        if c["task_type"] == choice:
            continue
        alt = {"task_type": c["task_type"],
               "confidence_to_use_top": rank}
        alt_card = card_for(c["task_type"])
        if alt_card:
            alt.update(alt_card)   # tool, call, required_params, pitfalls
        else:
            alt["tool"] = c["tool"]
        alts.append(alt)
    if alts:
        base["alternatives"] = alts
    return base


def _step_result_keyword(step: str) -> dict:
    tt = keyword_route(step)
    if tt is None or card_for(tt) is None:
        return {"step": step, "task_type": "no_match",
                "note": "không có tool phù hợp — agent tự xử lý step này"}
    out = {"step": step, "task_type": tt, "router": "keyword"}
    out.update(card_for(tt))
    return out


def tool_help(*steps, context: dict | None = None,
              jev_config: dict | None = None) -> str:
    """Route các bước plan -> tool + call template + pitfalls.

    Trả JSON: {"router": "jev|keyword", "steps": [per-step result],
               "jev_usage": {...}}
    """
    steps = _normalize_steps(steps)
    try:
        if not steps:
            return dumps({"router": "none", "steps": [],
                          "error": "steps rỗng — truyền các bước plan, "
                                   "không truyền raw UR"})

        task_requirement = ""
        if context and context.get("task_requirement"):
            task_requirement = context["task_requirement"]

        state = {
            "agent_context": _AGENT_CONTEXT,
            "task_type_catalog": TASK_TYPE_CATALOG,
            "steps": steps,
        }
        if task_requirement:
            state["task_requirement"] = task_requirement
            state["requirement_type_catalog"] = REQUIREMENT_TYPE_CATALOG

        res = {"ok": False}
        if jev_config:
            try:
                from jev import ask_jev
                res = ask_jev(jev_config, state,
                              _build_questions(steps, task_requirement))
            except Exception as e:
                res = {"ok": False, "error": "jev_exception",
                       "detail": str(e)}

        out_steps: list[dict] = []
        usage = res.get("usage") or {}
        answers = res.get("answers") or {}

        if res.get("ok"):
            for i, s in enumerate(steps, 1):
                ans = answers.get(f"step{i}_tool") or {}
                out_steps.append(_step_result_jev(s, ans, jev_config))
            router = "jev"
        else:
            logger.warning(f"tool_help: Jev fail "
                           f"({res.get('error')}: {res.get('detail')}) "
                           f"-> keyword fallback")
            out_steps = [_step_result_keyword(s) for s in steps]
            router = "keyword"

        used = {s.get("tool") for s in out_steps} - {None}
        param_examples = {t: TOOL_PARAM_EXAMPLES[t]
                          for t in used if t in TOOL_PARAM_EXAMPLES}
        if param_examples:
            param_examples = {
                "_note": ("CHỈ LÀ VÍ DỤ format giá trị — thay mọi path "
                          "\\\\172.168.5.14\\...\\SP2264 bằng path project "
                          "HIỆN TẠI của user; đừng copy nguyên địa chỉ/tên "
                          "file trong ví dụ"),
                **param_examples}
        payload = {"router": router, "steps": out_steps,
                   "param_examples": param_examples,
                   "jev_usage": usage}
        req_ans = answers.get("requirement_type")
        if task_requirement and res.get("ok") and req_ans:
            payload["requirement"] = _requirement_result(req_ans)
        return dumps(payload)
    except Exception as e:  # tuyệt đối không crash
        logger.exception("tool_help error")
        return dumps({"router": "error", "steps": [
            {"step": s, "task_type": "no_match",
             "note": f"tool_help lỗi: {e} — agent tự xử lý"}
            for s in steps]})
