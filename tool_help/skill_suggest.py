"""Gợi ý skill FBO bằng Jev — recipe "Skill suggestion" của TypeSafe.

Bài toán: agent hay quên load skill FBO đúng (hoặc load thừa). Cookbook
TypeSafe đo được giảm ~2.3× load sai, ~2.4× load thừa với 2 request:

1. (trong CÙNG call routing) 3 Noul **gate** — UR có cần skill không —
   + 1 Choice trên toàn bộ catalog skill (criteria = description).
   gate = mean(act, procedure, 1 - prose); < GATE_MIN → không gợi ý.
2. (call riêng, chỉ khi gate qua) rerank top-3: Choice trên description +
   700 ký tự đầu body, + 1 Noul "skill này làm đúng việc được yêu cầu?"
   mỗi candidate; giữ fit >= FIT_MIN (tối đa MAX_SKILLS).

Regex ``skill_hints.py`` vẫn chạy song song làm fallback / bổ sung.
Catalog: ``skill_catalog.json`` (sinh bằng scripts/build_skill_catalog.py).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GATE_MIN = 0.30
# Cookbook dùng 0.30; đo thật trên UR FBO: fit 0.37 là nhiễu (excel-mcp cho
# "báo cáo tạo mẫu"), skill đúng đều >= 0.8 → 0.5.
FIT_MIN = 0.5
TOP_K = 3
MAX_SKILLS = 2
_DESC_CAP = 400

_CATALOG_PATH = Path(__file__).with_name("skill_catalog.json")
_catalog_cache: list[dict] | None = None

_GATE = {
    "skill_gate_act": (
        "Must the assistant act on the user's FastBusiness project, files, "
        "database or services (not just explain)?", False),
    "skill_gate_proc": (
        "Would a careful FastBusiness expert follow a documented procedure "
        "or set of steps to do this?", False),
    "skill_gate_prose": (
        "Could a knowledgeable generalist answer this fully in prose "
        "without touching the project?", True),   # đảo chiều
}


def load_catalog() -> list[dict]:
    global _catalog_cache
    if _catalog_cache is None:
        try:
            _catalog_cache = json.loads(
                _CATALOG_PATH.read_text(encoding="utf-8")).get("skills") or []
        except Exception as e:
            logger.warning(f"skill_catalog.json lỗi: {e}")
            _catalog_cache = []
    return _catalog_cache


def stage1_questions(text: str) -> dict:
    """Gate + Choice skill — gộp vào request routing chính."""
    catalog = load_catalog()
    if not text or not catalog:
        return {}
    qs: dict = {
        k: {"type": "noul",
            "instructions": {"question": q, "request": text}}
        for k, (q, _) in _GATE.items()
    }
    qs["skill_pick"] = {
        "type": "choice",
        "instructions": {
            "question": "Which skill (playbook) best covers this request?",
            "request": text},
        "criteria": {s["name"]: s["description"][:_DESC_CAP]
                     for s in catalog},
    }
    return qs


def gate_score(answers: dict) -> float | None:
    vals = []
    for k, (_, inverted) in _GATE.items():
        a = answers.get(k)
        if not isinstance(a, dict) or a.get("noul") is None:
            return None
        v = float(a["noul"])
        vals.append(1 - v if inverted else v)
    return sum(vals) / len(vals)


def stage1_top(answers: dict, k: int = TOP_K) -> list[str]:
    probs = (answers.get("skill_pick") or {}).get("probabilities") or {}
    names = {s["name"] for s in load_catalog()}
    return [n for n, _ in sorted(probs.items(), key=lambda x: -x[1])
            if n in names][:k]


def rerank(cfg: dict, text: str, candidates: list[str]) -> list[dict]:
    """Call Jev thứ 2: description + body đầu cho top-k, Noul fit mỗi skill."""
    from jev import ask_jev

    by_name = {s["name"]: s for s in load_catalog()}
    cands = [by_name[c] for c in candidates if c in by_name]
    if not cands:
        return []
    detail = {s["name"]: {"description": s["description"],
                          "playbook_start": s.get("body", "")}
              for s in cands}
    qs: dict = {"rerank": {
        "type": "choice",
        "instructions": {"question": "Which playbook best fits the request?",
                         "request": text},
        "criteria": detail,
    }}
    for i, s in enumerate(cands):
        qs[f"fit{i}"] = {
            "type": "noul",
            "instructions": {
                "question": "Does this playbook cover the SPECIFIC thing "
                            "requested (not just the same topic)?",
                "request": text, "playbook": detail[s["name"]]},
        }
    res = ask_jev(cfg, {"request": text}, qs)
    if not res.get("ok"):
        return []
    answers = res.get("answers") or {}
    probs = (answers.get("rerank") or {}).get("probabilities") or {}
    out = []
    for i, s in enumerate(cands):
        fit = (answers.get(f"fit{i}") or {}).get("noul")
        if fit is None or float(fit) < FIT_MIN:
            continue
        out.append({"name": s["name"], "fit": round(float(fit), 2),
                    "rank_prob": round(float(probs.get(s["name"], 0)), 3)})
    out.sort(key=lambda x: (-x["rank_prob"], -x["fit"]))
    return out[:MAX_SKILLS]


def suggest(cfg: dict | None, text: str, answers: dict | None) -> dict:
    """→ {"skills": [...], "gate": float} hoặc {} nếu không gợi ý.

    ``answers`` = câu trả lời stage 1 trong call routing (None → bỏ qua).
    """
    if not cfg or not text or not answers:
        return {}
    try:
        gate = gate_score(answers)
        if gate is None or gate < GATE_MIN:
            return {"gate": gate} if gate is not None else {}
        top = stage1_top(answers)
        picked = rerank(cfg, text, top)
        return {"gate": round(gate, 2), "skills": picked}
    except Exception as e:  # gợi ý skill là phụ — không được làm hỏng routing
        logger.debug(f"skill_suggest error: {e}")
        return {}
