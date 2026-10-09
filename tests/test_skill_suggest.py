"""Tests gợi ý skill bằng Jev (tool_help/skill_suggest.py)."""
from __future__ import annotations

import json

import pytest

from tool_help import skill_suggest as ss
from tool_help import tool_help

FAKE_CFG = {"api_key": "k", "base_url": "http://x",
            "confidence_act": 0.7, "confidence_review": 0.4}

_CATALOG = [
    {"name": "fbo-js-skill", "description": "JS onChange grid", "body": "b1"},
    {"name": "fbo_grid_filter", "description": "dòng lọc grid", "body": "b2"},
    {"name": "fbo-quy-doi-dvt", "description": "quy đổi dvt", "body": "b3"},
    {"name": "excel-mcp", "description": "excel", "body": "b4"},
]


@pytest.fixture(autouse=True)
def _catalog(monkeypatch):
    monkeypatch.setattr(ss, "_catalog_cache", list(_CATALOG))
    from tool_help.service import _RESULT_CACHE
    _RESULT_CACHE.clear()
    yield
    _RESULT_CACHE.clear()


def _jev(gate=(0.9, 0.9, 0.1), pick=None, fit=None, rerank=None):
    """ask_jev giả cho cả call routing (stage 1) và call rerank."""
    pick = pick or {"fbo-js-skill": 0.6, "fbo_grid_filter": 0.3,
                    "fbo-quy-doi-dvt": 0.05, "excel-mcp": 0.05}
    fit = fit or {}
    calls = []

    def _ask(cfg, state, questions):
        calls.append(questions)
        ans = {}
        for k, q in questions.items():
            if k == "skill_gate_act":
                ans[k] = {"noul": gate[0]}
            elif k == "skill_gate_proc":
                ans[k] = {"noul": gate[1]}
            elif k == "skill_gate_prose":
                ans[k] = {"noul": gate[2]}
            elif k == "skill_pick":
                ans[k] = {"choice": max(pick, key=pick.get),
                          "probabilities": pick}
            elif k == "rerank":
                probs = rerank or {n: 1 / len(q["criteria"])
                                   for n in q["criteria"]}
                ans[k] = {"choice": max(probs, key=probs.get),
                          "probabilities": probs}
            elif k.startswith("fit"):
                name = list(questions["rerank"]["criteria"])[int(k[3:])]
                ans[k] = {"noul": fit.get(name, 0.0)}
            elif k.endswith("_tool"):
                ans[k] = {"choice": "read_snippet", "confidence": 0.9,
                          "probabilities": {"read_snippet": 0.9}}
        return {"ok": True, "answers": ans, "usage": {}}
    return _ask, calls


def test_stage1_questions_shape():
    qs = ss.stage1_questions("thêm onChange ma_vt")
    assert set(qs) == {"skill_gate_act", "skill_gate_proc",
                       "skill_gate_prose", "skill_pick"}
    assert set(qs["skill_pick"]["criteria"]) == {s["name"] for s in _CATALOG}
    assert ss.stage1_questions("") == {}


def test_gate_score_inverts_prose():
    ans = {"skill_gate_act": {"noul": 0.9}, "skill_gate_proc": {"noul": 0.6},
           "skill_gate_prose": {"noul": 0.9}}
    assert round(ss.gate_score(ans), 2) == round((0.9 + 0.6 + 0.1) / 3, 2)
    assert ss.gate_score({}) is None


def test_suggest_end_to_end(monkeypatch):
    import jev
    ask, calls = _jev(fit={"fbo-js-skill": 0.9, "fbo_grid_filter": 0.2},
                      rerank={"fbo-js-skill": 0.8, "fbo_grid_filter": 0.15,
                              "fbo-quy-doi-dvt": 0.05})
    monkeypatch.setattr(jev, "ask_jev", ask)
    out = json.loads(tool_help("Thêm onChange ma_vt load giá trong "
                               "DDVDetail.xml", jev_config=FAKE_CFG))
    assert out["related_skills"][0] == "fbo-js-skill"
    assert out["related_skills_by"]["fbo-js-skill"] == "jev (fit 0.9)"
    assert "fbo_grid_filter" not in out["related_skills"]   # fit < 0.3
    assert len(calls) == 2                       # routing + rerank
    # rerank chỉ gửi top-3 kèm body
    assert set(calls[1]["rerank"]["criteria"]) == {
        "fbo-js-skill", "fbo_grid_filter", "fbo-quy-doi-dvt"}
    assert calls[1]["rerank"]["criteria"]["fbo-js-skill"][
        "playbook_start"] == "b1"


def test_gate_closed_no_rerank(monkeypatch):
    import jev
    ask, calls = _jev(gate=(0.1, 0.1, 0.9))
    monkeypatch.setattr(jev, "ask_jev", ask)
    out = json.loads(tool_help("Giải thích số dư đầu kỳ là gì",
                               jev_config=FAKE_CFG))
    assert len(calls) == 1                       # không gọi rerank
    assert "related_skills_by" not in out or all(
        v == "regex" for v in out["related_skills_by"].values())


def test_regex_merged_after_jev(monkeypatch):
    import jev
    ask, _ = _jev(fit={"fbo-js-skill": 0.9},
                  rerank={"fbo-js-skill": 0.9, "fbo_grid_filter": 0.05,
                          "fbo-quy-doi-dvt": 0.05})
    monkeypatch.setattr(jev, "ask_jev", ask)
    out = json.loads(tool_help(
        "Sửa onChange", context={"task_requirement":
                                 "thêm dòng lọc và onChange cho grid"},
        jev_config=FAKE_CFG))
    assert out["related_skills"][0] == "fbo-js-skill"
    assert "fbo_grid_filter" in out["related_skills"]      # từ regex
    assert out["related_skills_by"]["fbo_grid_filter"] == "regex"


def test_rerank_failure_keeps_routing(monkeypatch):
    import jev
    ask, _ = _jev()

    def _ask(cfg, state, questions):
        if "rerank" in questions:
            raise RuntimeError("down")
        return ask(cfg, state, questions)
    monkeypatch.setattr(jev, "ask_jev", _ask)
    out = json.loads(tool_help("Thêm onChange", jev_config=FAKE_CFG))
    assert out["steps"][0]["task_type"] == "read_snippet"


def test_catalog_file_valid():
    ss._catalog_cache = None
    cat = ss.load_catalog()
    assert len(cat) >= 10
    assert all(s["name"] and s["description"] for s in cat)
