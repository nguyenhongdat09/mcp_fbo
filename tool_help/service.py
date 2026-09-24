"""tool_help — route step -> task_type bằng Jev, trả usage card tĩnh.

Nguyên tắc: Jev chỉ classify task_type (Choice, criteria=null + catalog
trong state). Param giá trị (path/pattern/symbol) agent tự điền theo card.
Mọi exception bắt chặt — tool này là cứu cánh, không được crash.
"""
from __future__ import annotations

import logging

from .cards import (TASK_TYPE_CATALOG, TASK_TYPES, TOOL_PARAM_EXAMPLES,
                    card_for)
from .formatter import dumps
from .keywords import keyword_route

logger = logging.getLogger(__name__)

ALT_PROB_MIN = 0.2          # option >20% đưa vào candidates/alternatives
NO_MATCH_PROB = 0.9         # no_match >=90% -> "agent tự xử lý step này"

_AGENT_CONTEXT = (
    "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; "
    "data = SQL Server. MCP tools available."
)


def _normalize_steps(steps: tuple) -> list[str]:
    if len(steps) == 1 and isinstance(steps[0], (list, tuple)):
        steps = tuple(steps[0])
    return [str(s).strip() for s in steps if str(s).strip()]


def _build_questions(steps: list[str]) -> dict:
    criteria = {k: None for k in TASK_TYPE_CATALOG}
    return {
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


def _candidates(probs: dict) -> list[dict]:
    return [
        {"task_type": k, "probability": round(v, 3)}
        for k, v in sorted(probs.items(), key=lambda x: -x[1])
        if v > ALT_PROB_MIN and k in TASK_TYPES
    ]


def _step_result_jev(step: str, answer: dict, cfg: dict) -> dict:
    choice = str(answer.get("choice") or "")
    conf = float(answer.get("confidence") or 0)
    probs = answer.get("probabilities") or {}
    cands = _candidates(probs)
    act = cfg.get("confidence_act", 0.7) if cfg else 0.7

    base = {"step": step, "task_type": choice, "confidence": round(conf, 3)}

    if choice == "no_match" and probs.get("no_match", 0) >= NO_MATCH_PROB:
        base["note"] = ("không có tool phù hợp — agent tự xử lý step này "
                        "(viết file tay / thao tác web / hỏi user)")
        return base

    card = card_for(choice)
    if card is None:
        # choice lạ hoặc no_match yếu -> keyword fallback riêng step này
        return _step_result_keyword(step)

    base.update(card)
    if conf < act and len(cands) > 1:
        base["alternatives"] = [c for c in cands
                                if c["task_type"] != choice]
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

        state = {
            "agent_context": _AGENT_CONTEXT,
            "task_type_catalog": TASK_TYPE_CATALOG,
            "steps": steps,
        }
        if context and context.get("task_requirement"):
            state["task_requirement"] = context["task_requirement"]

        res = {"ok": False}
        if jev_config:
            try:
                from jev import ask_jev
                res = ask_jev(jev_config, state, _build_questions(steps))
            except Exception as e:
                res = {"ok": False, "error": "jev_exception",
                       "detail": str(e)}

        out_steps: list[dict] = []
        usage = res.get("usage") or {}
        answers = res.get("answers") or {}

        if res.get("ok"):
            for i, s in enumerate(steps, 1):
                ans = answers.get(f"step{i}_tool") or {}
                r = _step_result_jev(s, ans, jev_config)
                r.setdefault("router", "jev")
                out_steps.append(r)
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
        return dumps({"router": router, "steps": out_steps,
                      "param_examples": param_examples,
                      "jev_usage": usage})
    except Exception as e:  # tuyệt đối không crash
        logger.exception("tool_help error")
        return dumps({"router": "error", "steps": [
            {"step": s, "task_type": "no_match",
             "note": f"tool_help lỗi: {e} — agent tự xử lý"}
            for s in steps]})
