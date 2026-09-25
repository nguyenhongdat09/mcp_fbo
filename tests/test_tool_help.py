"""Unit tests cho tool_help/ — routing Jev + keyword fallback + rules."""
from __future__ import annotations

import json
import sys
import types

import pytest

import tool_help as th_pkg
from tool_help import tool_help


FAKE_CFG = {"api_key": "k", "base_url": "http://x",
            "confidence_act": 0.7, "confidence_review": 0.4}


def _parse(out: str) -> dict:
    return json.loads(out)


def _fake_ask(answers: dict):
    """Trả hàm ask_jev giả trả `answers` cho mọi state/questions."""
    def _ask(cfg, state, questions):
        return {"ok": True, "answers": answers,
                "usage": {"input_tokens": 1, "output_tokens": 1}}
    return _ask


@pytest.fixture
def patch_jev(monkeypatch):
    """Cho phép test set jev.ask_jev giả."""
    import jev
    holder = {}
    monkeypatch.setattr(jev, "ask_jev",
                        lambda *a, **k: holder["fn"](*a, **k))
    return holder


# ---------------- normalize ----------------

def test_empty_steps():
    out = _parse(tool_help(jev_config=FAKE_CFG))
    assert out["router"] == "none"
    assert "steps" in out


def test_accepts_list_or_varargs(patch_jev):
    patch_jev["fn"] = _fake_ask({})
    a = _parse(tool_help("s1", "s2", jev_config=FAKE_CFG))
    b = _parse(tool_help(["s1", "s2"], jev_config=FAKE_CFG))
    assert len(a["steps"]) == len(b["steps"]) == 2


# ---------------- jev routing ----------------

def test_high_conf_returns_card(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "grep_content",
                       "confidence": 0.98,
                       "probabilities": {"grep_content": 0.98}}})
    out = _parse(tool_help("Tìm file chứa chuỗi dmku",
                           jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert out["router"] == "jev"
    assert s["task_type"] == "grep_content"
    assert s["confidence_to_use_top"] == 1
    assert s["tool"] == "search_files"
    assert s["call"]["mode"] == "content"
    assert "root" in s["required_params"]
    assert s["pitfalls"]


def test_mid_conf_has_alternatives(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "match_filename",
                       "confidence": 0.46,
                       "probabilities": {"match_filename": 0.46,
                                         "grep_content": 0.29,
                                         "list_folder": 0.15,
                                         "no_match": 0.05}}})
    out = _parse(tool_help("Tìm cặp file Dir/Grid", jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["task_type"] == "match_filename"
    assert s["confidence_to_use_top"] == 2
    # alternatives = các option >20% trừ top-1, kèm tool đích
    alts = {a["task_type"]: a for a in s["alternatives"]}
    assert alts["grep_content"]["tool"] == "search_files"
    assert "list_folder" not in alts   # 15% < 20% bị loại


def test_low_conf_tier3_and_alts(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "list_folder",
                       "confidence": 0.26,
                       "probabilities": {"list_folder": 0.28,
                                         "graph_query": 0.24,
                                         "grep_content": 0.22,
                                         "no_match": 0.14}}})
    out = _parse(tool_help("Tìm danh mục mẫu có import",
                           jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["confidence_to_use_top"] == 3
    alts = {a["task_type"] for a in s["alternatives"]}
    assert alts == {"graph_query", "grep_content"}   # >20% đều liệt kê


def test_dominant_top1_is_tier1_no_alts(patch_jev):
    """Top-1 áp đảo (68% vs 29% < 68%/2) -> tier 1, không alternative."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_snippet",
                       "confidence": 0.66,
                       "probabilities": {"read_snippet": 0.68,
                                         "read_summary": 0.29,
                                         "read_flat": 0.03}}})
    out = _parse(tool_help("x", jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["confidence_to_use_top"] == 1
    assert "alternatives" not in s


def test_alts_carry_full_card(patch_jev):
    """Alternative phải đầy đủ như top-1: tool/call/required_params/pitfalls."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "match_filename",
                       "confidence": 0.46,
                       "probabilities": {"match_filename": 0.46,
                                         "grep_content": 0.29}}})
    out = _parse(tool_help("x", jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["confidence_to_use_top"] == 2
    alt = s["alternatives"][0]
    assert alt["task_type"] == "grep_content"
    assert alt["confidence_to_use_top"] == 2    # thứ hạng, không phải prob
    assert "probability" not in alt
    assert alt["tool"] == "search_files"
    assert alt["call"]                          # full call template
    assert "required_params" in alt
    assert "pitfalls" in alt


def test_no_match_near_100_self_handle(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "no_match",
                       "confidence": 0.98,
                       "probabilities": {"no_match": 0.98}}})
    out = _parse(tool_help("Đăng ký menu lên web", jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["task_type"] == "no_match"
    assert "tự xử lý" in s["note"]
    assert "tool" not in s


def test_unknown_choice_falls_back_keyword(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "khong_co_gi",
                       "confidence": 0.9,
                       "probabilities": {"khong_co_gi": 0.9}}})
    out = _parse(tool_help("check syntax file a.sql",
                           jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["task_type"] == "db_check_syntax"   # keyword bắt được
    assert s["router"] == "keyword"


def test_multi_step_single_jev_call(patch_jev):
    calls = []

    def _ask(cfg, state, questions):
        calls.append((state, questions))
        return {"ok": True, "answers": {
            k: {"type": "choice", "choice": "read_summary",
                "confidence": 0.9,
                "probabilities": {"read_summary": 0.9}}
            for k in questions}, "usage": {}}

    patch_jev["fn"] = _ask
    out = _parse(tool_help("step A", "step B", "step C",
                           jev_config=FAKE_CFG))
    assert len(calls) == 1                      # 1 HTTP call duy nhất
    assert len(calls[0][1]) == 3                # 3 questions song song
    assert len(out["steps"]) == 3


# ---------------- fallback ----------------

def test_jev_fail_keyword_fallback(patch_jev):
    def _fail(cfg, state, questions):
        return {"ok": False, "error": "api_loi", "detail": "HTTP 500"}
    patch_jev["fn"] = _fail
    out = _parse(tool_help("tìm file nào chứa chuỗi dmku",
                           jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert out["router"] == "keyword"
    assert s["task_type"] == "grep_content"
    assert s["tool"] == "search_files"


def test_jev_fail_no_keyword_no_match(patch_jev):
    def _fail(cfg, state, questions):
        return {"ok": False, "error": "timeout", "detail": "x"}
    patch_jev["fn"] = _fail
    out = _parse(tool_help("xyzzy plugh nothing matches",
                           jev_config=FAKE_CFG))
    assert out["steps"][0]["task_type"] == "no_match"


def test_no_config_keyword_only():
    # jev_config=None -> thẳng keyword fallback
    out = _parse(tool_help("check syntax file a.sql", jev_config=None))
    assert out["router"] == "keyword"
    assert out["steps"][0]["task_type"] == "db_check_syntax"


def test_never_crashes_on_exception(patch_jev):
    def _boom(cfg, state, questions):
        raise RuntimeError("boom")
    patch_jev["fn"] = _boom
    out = _parse(tool_help("abc", jev_config=FAKE_CFG))
    assert out["router"] == "keyword"          # exception -> fallback


def test_param_examples_only_for_used_tools(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "grep_content",
                       "confidence": 0.95,
                       "probabilities": {"grep_content": 0.95}},
        "step2_tool": {"type": "choice", "choice": "db_check_syntax",
                       "confidence": 0.9,
                       "probabilities": {"db_check_syntax": 0.9}},
        "step3_tool": {"type": "choice", "choice": "no_match",
                       "confidence": 0.95,
                       "probabilities": {"no_match": 0.95}}})
    out = _parse(tool_help("a", "b", "c", jev_config=FAKE_CFG))
    pe = out["param_examples"]
    assert set(pe) - {"_note"} == {"search_files", "query_database"}
    assert "VÍ DỤ" in pe["_note"]
    assert pe["search_files"]["root"].startswith("\\\\")
    assert "file_path" in pe["query_database"]


def test_requirement_block_with_context(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_summary",
                       "confidence": 0.9,
                       "probabilities": {"read_summary": 0.9}},
        "requirement_type": {"type": "choice", "choice": "category_1_key",
                             "confidence": 0.9,
                             "probabilities": {"category_1_key": 0.9}}})
    out = _parse(tool_help("đọc file mẫu",
                           context={"task_requirement": "Thêm mới danh mục"},
                           jev_config=FAKE_CFG))
    req = out["requirement"]
    assert req["type"] == "category_1_key"
    assert req["template"]["dir"] == "template/category_1_key"
    assert req["template"]["clone_call"]["type"] == 4
    assert req["template"]["files"]


def test_no_requirement_without_context(patch_jev):
    patch_jev["fn"] = _fake_ask({})
    out = _parse(tool_help("x", jev_config=FAKE_CFG))
    assert "requirement" not in out


def test_requirement_no_template_has_note(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "requirement_type": {"type": "choice", "choice": "voucher",
                             "confidence": 0.9,
                             "probabilities": {"voucher": 0.9}}})
    out = _parse(tool_help("x",
                           context={"task_requirement": "chứng từ mới"},
                           jev_config=FAKE_CFG))
    req = out["requirement"]
    assert req["type"] == "voucher"
    assert "template" not in req
    assert "chưa có template" in req["note"]


def test_no_api_key_in_output(patch_jev):
    patch_jev["fn"] = _fake_ask({})
    out = tool_help("x", jev_config={"api_key": "SECRET-KEY",
                                     "base_url": "http://x"})
    assert "SECRET-KEY" not in out
