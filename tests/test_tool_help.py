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


@pytest.fixture(autouse=True)
def _clear_result_cache():
    """tool_help có in-process cache — clear giữa các test để khỏi leak."""
    from tool_help.service import _RESULT_CACHE
    _RESULT_CACHE.clear()
    yield
    _RESULT_CACHE.clear()


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
    assert "router" not in out   # router:"jev" không emit — chỉ báo fallback
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


def test_tier_counts_all_over_20pct(patch_jev):
    """Mọi option >20% đều đếm: 68/29 -> tier 2, alt rank=2."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_snippet",
                       "confidence": 0.66,
                       "probabilities": {"read_snippet": 0.68,
                                         "read_summary": 0.29,
                                         "read_flat": 0.03}}})
    out = _parse(tool_help("x", jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["confidence_to_use_top"] == 2
    alt = s["alternatives"][0]
    assert alt["task_type"] == "read_summary"
    assert alt["confidence_to_use_top"] == 2


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


def test_requirement_report_check_has_template(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "requirement_type": {"type": "choice", "choice": "report_check",
                             "confidence": 0.9,
                             "probabilities": {"report_check": 0.9}}})
    out = _parse(tool_help("x",
                           context={"task_requirement": "báo cáo tick chọn"},
                           jev_config=FAKE_CFG))
    req = out["requirement"]
    assert req["type"] == "report_check"
    assert req["template"]["dir"] == "template/report_check"
    assert req["template"]["clone_call"]["object"] == "report_check"


def test_requirement_retrieve_flow_has_template(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "requirement_type": {"type": "choice",
                             "choice": "retrieve_flow_parition_table",
                             "confidence": 0.9,
                             "probabilities": {
                                 "retrieve_flow_parition_table": 0.9}}})
    out = _parse(tool_help("x",
                           context={"task_requirement":
                                    "lấy dữ liệu từ phiếu nguồn"},
                           jev_config=FAKE_CFG))
    req = out["requirement"]
    assert req["type"] == "retrieve_flow_parition_table"
    assert req["template"]["dir"] == "template/retrieve_flow_parition_table"
    assert req["template"]["clone_call"]["object"] == \
        "retrieve_flow_parition_table"
    files = req["template"]["files"]
    assert any("Lookup" in f for f in files)
    assert any(f.endswith("_retrieve.sql") for f in files)


def test_requirement_voucher_variants_have_template(patch_jev):
    """4 variant voucher_* → requirement block trả template + clone_call."""
    cases = {
        "voucher_normal_no_currency": "Dir/{new}Tran.xml",
        "voucher_normal_currency": "Dir/{new}Tran.xml",
        "voucher_approval_no_currency": "Grid/{new}Approval.xml",
        "voucher_approval_currency": "Grid/{new}ApprovalFiles.xml",
    }
    for req_type, want in cases.items():
        patch_jev["fn"] = _fake_ask({
            "requirement_type": {"type": "choice", "choice": req_type,
                                 "confidence": 0.9,
                                 "probabilities": {req_type: 0.9}}})
        # cùng input qua cache — clear để fake mới có hiệu lực
        from tool_help.service import _RESULT_CACHE
        _RESULT_CACHE.clear()
        out = _parse(tool_help("x",
                               context={"task_requirement": "chứng từ mới"},
                               jev_config=FAKE_CFG))
        req = out["requirement"]
        assert req["type"] == req_type
        assert req["template"]["dir"] == f"template/{req_type}"
        assert req["template"]["clone_call"]["object"] == req_type
        assert req["template"]["clone_call"]["type"] == 4
        assert any(want in f for f in req["template"]["files"])


def test_no_api_key_in_output(patch_jev):
    patch_jev["fn"] = _fake_ask({})
    out = tool_help("x", jev_config={"api_key": "SECRET-KEY",
                                     "base_url": "http://x"})
    assert "SECRET-KEY" not in out


# ---------------- db_add_field (fsd_addFields) ----------------

def test_add_field_card(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_add_field",
                       "confidence": 0.9,
                       "probabilities": {"db_add_field": 0.9}}})
    out = _parse(tool_help("Thêm trường dvt_ebs vào bảng dmkh",
                           jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["task_type"] == "db_add_field"
    assert s["tool"] == "query_database"
    assert "fsd_addFields" in s["call"]["query"]
    assert s["call"]["query_type"] == 1
    assert any("d21$" in p for p in s["pitfalls"])   # ví dụ phân kỳ
    assert any("dmkh" in p for p in s["pitfalls"])   # ví dụ bảng thường


def test_add_field_keyword_fallback():
    for step in ("Thêm trường dvt_ebs vào bảng dmkh",
                 "Bổ sung cột nguoi_nhan cho chứng từ d21",
                 "add field so_ku to table dmkh"):
        out = _parse(tool_help(step, jev_config=None))
        assert out["steps"][0]["task_type"] == "db_add_field", step


# ---------------- new_sql_file (clone_things type=5) ----------------

def test_new_sql_file_card(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "new_sql_file",
                       "probabilities": {"new_sql_file": 0.9}}})
    out = _parse(tool_help("Tạo file sql mới để viết proc",
                           jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert s["task_type"] == "new_sql_file"
    assert s["tool"] == "clone_things"
    assert s["call"]["type"] == 5
    assert "project_source" in s["required_params"]


def test_new_sql_file_keyword_fallback():
    for step in ("Tạo file sql mới để viết proc",
                 "tạo file .sql trống",
                 "tạo file voucher.sql để đăng ký",
                 "new sql file cho script deploy"):
        out = _parse(tool_help(step, jev_config=None))
        assert out["steps"][0]["task_type"] == "new_sql_file", step


def test_open_existing_sql_not_new_file():
    """'Mở file x.sql xem' = đọc file có sẵn, KHÔNG route new_sql_file."""
    out = _parse(tool_help("mở file a.sql xem nội dung", jev_config=None))
    assert out["steps"][0]["task_type"] != "new_sql_file"


def test_warn_run_file_without_producer(patch_jev):
    """Plan check/run file .sql nhưng thiếu step tạo file → warning."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_run_file",
                       "probabilities": {"db_run_file": 0.9}}})
    out = _parse(tool_help("Chạy file script.sql", jev_config=FAKE_CFG))
    assert any("type=5" in w for w in out.get("warnings", []))


def test_no_warn_run_file_with_producer(patch_jev):
    """Có step new_sql_file/clone_* đi kèm → không warning."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "new_sql_file",
                       "probabilities": {"new_sql_file": 0.9}},
        "step2_tool": {"type": "choice", "choice": "db_check_syntax",
                       "probabilities": {"db_check_syntax": 0.9}}})
    out = _parse(tool_help("a", "b", jev_config=FAKE_CFG))
    assert not any("type=5" in w for w in out.get("warnings", []))


def test_new_sql_file_notice(patch_jev):
    """Step route new_sql_file → notice nhắc không tạo .sql trong workspace."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "new_sql_file",
                       "probabilities": {"new_sql_file": 0.9}}})
    out = _parse(tool_help("tạo file sql mới", jev_config=FAKE_CFG))
    texts = list((out.get("notice") or {}).values())
    assert any("sql_temp_folder" in t and "type=5" in t for t in texts)


# ---------------- notice ----------------

def test_notice_sql_style_on_db_steps(patch_jev):
    """Step route vào SQL task_type → notice sql_style đính kèm."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_run_sql",
                       "probabilities": {"db_run_sql": 0.9}}})
    out = _parse(tool_help("Kiểm tra dữ liệu bảng dmvt",
                           jev_config=FAKE_CFG))
    texts = list(out["notice"].values())
    assert "ưu tiên dùng IDE" in texts[0]   # always mcp_first
    assert any('skill "fbo-style-sql"' in t for t in texts)
    assert any("OBJECT_ID" in t for t in texts)           # schema_check


def test_notice_requirement_voucher_approval(patch_jev):
    """Classify voucher_approval_* → sql_style + append_config + gn_apv."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_template",
                       "probabilities": {"clone_template": 0.9}},
        "requirement_type": {"type": "choice",
                             "choice": "voucher_approval_currency",
                             "probabilities": {
                                 "voucher_approval_currency": 0.9}}})
    out = _parse(tool_help("Clone chứng từ mẫu",
                           context={"task_requirement": "Tạo chứng từ mới"},
                           jev_config=FAKE_CFG))
    texts = list((out.get("notice") or {}).values())
    assert any("fbo-style-sql" in t for t in texts)
    assert any("OBJECT_ID" in t for t in texts)
    assert any("PARSEONLY" in t for t in texts)
    assert any("%Partition" in t for t in texts)
    assert any("Structure/App" in t for t in texts)
    assert any("APPEND" in t for t in texts)
    assert any("gndmkieuduyet" in t for t in texts)


def test_notice_requirement_voucher_normal(patch_jev):
    """Classify voucher_normal_* → sql_style + append_config, KHÔNG gn_apv."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_template",
                       "probabilities": {"clone_template": 0.9}},
        "requirement_type": {"type": "choice",
                             "choice": "voucher_normal_no_currency",
                             "probabilities": {
                                 "voucher_normal_no_currency": 0.9}}})
    out = _parse(tool_help("Clone chứng từ mẫu",
                           context={"task_requirement": "Tạo chứng từ mới"},
                           jev_config=FAKE_CFG))
    texts = list((out.get("notice") or {}).values())
    assert any("fbo-style-sql" in t for t in texts)
    assert any("APPEND" in t for t in texts)
    assert any("%Partition" in t for t in texts)
    assert not any("gndmkieuduyet" in t for t in texts)


def test_notice_absent_when_irrelevant(patch_jev):
    """Step đọc file + không requirement → không có key notice."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_flat",
                       "probabilities": {"read_flat": 0.9}}})
    out = _parse(tool_help("Đọc file xml", jev_config=FAKE_CFG))
    # chỉ còn notice always (mcp_first), không rule task/requirement nào
    assert list((out.get("notice") or {}).values()) == [
        next(r["text"] for r in __import__(
            "tool_help.notices", fromlist=["NOTICE_RULES"]).NOTICE_RULES
         if r["id"] == "mcp_first")]


def test_clarify_block_on_generic_voucher(patch_jev):
    """Classify generic 'voucher' → response có clarify questions + map."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_template",
                       "probabilities": {"clone_template": 0.9}},
        "requirement_type": {"type": "choice", "choice": "voucher",
                             "probabilities": {"voucher": 0.9}}})
    out = _parse(tool_help("Clone chứng từ mẫu",
                           context={"task_requirement": "tạo chứng từ"},
                           jev_config=FAKE_CFG))
    cl = out["requirement"].get("clarify")
    assert cl and len(cl["questions"]) == 2
    assert cl["map"]["yes_yes"] == "voucher_approval_currency"
    assert cl["map"]["no_no"] == "voucher_normal_no_currency"


def test_secondary_requirements_multi_intent(patch_jev):
    """UR multi-intent → secondary_requirements chứa type phụ có template."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_template",
                       "probabilities": {"clone_template": 0.9}},
        "requirement_type": {
            "type": "choice", "choice": "voucher_approval_currency",
            "probabilities": {"voucher_approval_currency": 0.6,
                              "report_normal": 0.4,
                              "category_1_key": 0.1}}})
    out = _parse(tool_help("x",
                           context={"task_requirement": "tạo ct + báo cáo"},
                           jev_config=FAKE_CFG))
    sec = out["requirement"].get("secondary_requirements")
    assert sec == [{"type": "report_normal", "probability": 0.4}]


def test_warnings_template_without_clone_step(patch_jev):
    """req voucher_* nhưng plan chỉ đọc file → warning mismatch."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_flat",
                       "probabilities": {"read_flat": 0.9}},
        "requirement_type": {"type": "choice",
                             "choice": "voucher_normal_no_currency",
                             "probabilities": {
                                 "voucher_normal_no_currency": 0.9}}})
    out = _parse(tool_help("Đọc file xml",
                           context={"task_requirement": "tạo chứng từ"},
                           jev_config=FAKE_CFG))
    assert any("clone_template" in w for w in out.get("warnings", []))
    assert any("SQL" in w for w in out.get("warnings", []))


def test_no_warnings_when_consistent(patch_jev):
    """req voucher_* + plan có clone_template + SQL → không warnings."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_template",
                       "probabilities": {"clone_template": 0.9}},
        "step2_tool": {"type": "choice", "choice": "db_run_file",
                       "probabilities": {"db_run_file": 0.9}},
        "requirement_type": {"type": "choice",
                             "choice": "voucher_approval_no_currency",
                             "probabilities": {
                                 "voucher_approval_no_currency": 0.9}}})
    out = _parse(tool_help("Clone chứng từ", "Chạy voucher.sql",
                           context={"task_requirement": "tạo chứng từ"},
                           jev_config=FAKE_CFG))
    assert not out.get("warnings")


# ---------------- save-as / clone_existing ----------------

def test_save_as_keyword_routes():
    """Step save-as/copy-từ → save_as_existing (clone_things type=6)."""
    for step in ("Tạo báo cáo dòng tiền save as từ báo cáo lưu chuyển "
                 "tiền tệ",
                 "copy từ chức năng báo cáo X",
                 "clone từ báo cáo lưu chuyển tiền tệ",
                 "làm giống chức năng báo cáo cũ",
                 "tạo báo cáo dựa trên báo cáo có sẵn"):
        out = _parse(tool_help(step, jev_config=None))
        tt = out["steps"][0]["task_type"]
        assert tt == "save_as_existing", f"{step} -> {tt}"
        assert out["steps"][0]["call"]["type"] == 6


def test_save_as_not_steal_clone_sql():
    """'clone từ proc X' vẫn route clone_sql, không phải save_as."""
    out = _parse(tool_help("clone từ proc zc_abc sang project B",
                           jev_config=None))
    assert out["steps"][0]["task_type"] != "save_as_existing"


def test_find_by_title_keyword():
    out = _parse(tool_help("Tìm controller báo cáo theo tiêu đề",
                           jev_config=None))
    s = out["steps"][0]
    assert s["task_type"] == "find_by_title"
    assert s["tool"] == "query_radar"


def test_save_as_notice_on_task(patch_jev):
    """Step route save_as_existing → notice save_as_flow đính kèm."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "save_as_existing",
                       "probabilities": {"save_as_existing": 0.9}}})
    out = _parse(tool_help("save as báo cáo", jev_config=FAKE_CFG))
    texts = list((out.get("notice") or {}).values())
    assert any("saveas:" in t and "type=6" in t for t in texts)


def test_requirement_clone_existing_workflow(patch_jev):
    """requirement=clone_existing → block workflow (không phải note)."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "save_as_existing",
                       "probabilities": {"save_as_existing": 0.9}},
        "requirement_type": {"type": "choice", "choice": "clone_existing",
                             "probabilities": {"clone_existing": 0.9}}})
    out = _parse(tool_help("save as báo cáo",
                           context={"task_requirement":
                                    "Thêm báo cáo dòng tiền save as từ "
                                    "báo cáo lưu chuyển tiền tệ"},
                           jev_config=FAKE_CFG))
    req = out["requirement"]
    assert req["type"] == "clone_existing"
    assert req.get("workflow"), req
    assert any("type=6" in w for w in req["workflow"])
    assert "template" not in req
    # notice save_as_flow fire theo requirement
    texts = list((out.get("notice") or {}).values())
    assert any("saveas:" in t for t in texts)
    # plan đúng → không có warning clone_existing
    assert not any("clone_existing" in w for w in out.get("warnings", []))


def test_warn_clone_existing_missing_clone(patch_jev):
    """req=clone_existing nhưng plan không có step clone → warning."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_flat",
                       "probabilities": {"read_flat": 0.9}},
        "requirement_type": {"type": "choice", "choice": "clone_existing",
                             "probabilities": {"clone_existing": 0.9}}})
    out = _parse(tool_help("Đọc file",
                           context={"task_requirement": "save as báo cáo"},
                           jev_config=FAKE_CFG))
    assert any("clone_existing" in w for w in out.get("warnings", []))


def test_warn_clone_existing_with_template(patch_jev):
    """req=clone_existing + plan clone_template → warning classify nhầm."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_template",
                       "probabilities": {"clone_template": 0.9}},
        "requirement_type": {"type": "choice", "choice": "clone_existing",
                             "probabilities": {"clone_existing": 0.9}}})
    out = _parse(tool_help("Clone mẫu",
                           context={"task_requirement":
                                    "save as từ báo cáo X"},
                           jev_config=FAKE_CFG))
    assert any("clone_template" in w for w in out.get("warnings", []))


def test_save_as_satisfies_sql_consumer(patch_jev):
    """save_as_existing tự tạo .sql → không warning thiếu producer."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "save_as_existing",
                       "probabilities": {"save_as_existing": 0.9}},
        "step2_tool": {"type": "choice", "choice": "db_check_syntax",
                       "probabilities": {"db_check_syntax": 0.9}}})
    out = _parse(tool_help("a", "b", jev_config=FAKE_CFG))
    assert not any("type=5" in w for w in out.get("warnings", []))


# ---------------- db_balance (proc số-dư nội bộ) ----------------

def test_db_balance_keyword_routes():
    """Step tính/lấy số dư-tồn-công nợ-đáo hạn → db_balance."""
    for step in ("Tính số dư cuối kỳ theo mã kho",
                 "Lấy tồn kho đầu kỳ của vật tư",
                 "Lấy số dư cuối kỳ của tài khoản 1121",
                 "tính công nợ phải thu khách hàng",
                 "liệt kê trái phiếu đáo hạn và số dư",
                 "dư nợ hợp đồng cuối kỳ",
                 "lấy số dư theo khế ước",
                 "xem số dư theo hợp đồng",
                 "lấy tồn theo vị trí",
                 "tồn theo lô và vật tư cuối tháng",
                 "tồn theo mã kho",
                 "số dư theo nhân viên bán hàng",
                 "dư nợ theo NVBH",
                 "gọi FastBusiness$Balance$Item"):
        out = _parse(tool_help(step, jev_config=None))
        tt = out["steps"][0]["task_type"]
        assert tt == "db_balance", f"{step} -> {tt}"
        assert out["steps"][0]["tool"] == "query_database"
        assert out["steps"][0]["call"]["mode"] == "search"


def test_db_balance_no_false_positive():
    """Check data thường / kỳ báo cáo trần KHÔNG route db_balance."""
    out = _parse(tool_help("kiểm tra tồn trong bảng cdvt",
                           jev_config=None))
    assert out["steps"][0]["task_type"] == "db_run_sql"
    out = _parse(tool_help("Báo cáo đầu kỳ - trong kỳ theo hóa đơn",
                           jev_config=None))
    assert out["steps"][0]["task_type"] != "db_balance"
    out = _parse(tool_help("Chạy file a.sql", jev_config=None))
    assert out["steps"][0]["task_type"] == "db_run_file"


def test_db_balance_card_and_catalog():
    from tool_help.cards import TASK_TYPES, TASK_TYPE_CATALOG, card_for
    from tool_help import balance_catalog
    assert "db_balance" in TASK_TYPE_CATALOG
    card = card_for("db_balance")
    assert card["tool"] == "query_database"
    assert card["call"]["object_name"] == "FastBusiness$Balance$%"
    pit = "\n".join(card["pitfalls"])
    assert "Item" in pit and "Customer" in pit and "#t" in pit
    assert "Investment" in balance_catalog.BALANCE_PROCS
    assert "UpdateCurrentStock" in balance_catalog.OPENING_BALANCE_PROCS
    assert balance_catalog.render_map()


def test_db_balance_notice(patch_jev):
    """Step route db_balance → notice balance_procs + sql_temp_file."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_balance",
                       "probabilities": {"db_balance": 0.9}}})
    out = _parse(tool_help("tính số dư", jev_config=FAKE_CFG))
    texts = list((out.get("notice") or {}).values())
    assert any("Balance$" in t and "OpeningBalance$" in t for t in texts)
    assert any("type=5" in t for t in texts)   # sql_temp_file notice


def test_warn_balance_step_misrouted(patch_jev):
    """Step nhắc số dư nhưng Jev route db_run_sql → warning db_balance."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_run_sql",
                       "probabilities": {"db_run_sql": 0.9}}})
    out = _parse(tool_help("Tính số dư cuối kỳ theo mã kho",
                           jev_config=FAKE_CFG))
    assert any("db_balance" in w for w in out.get("warnings", []))


def test_no_warn_balance_step_routed(patch_jev):
    """Step nhắc số dư route db_balance hoặc db_object → không warn."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_object",
                       "probabilities": {"db_object": 0.9}}})
    out = _parse(tool_help("Xem summary FastBusiness$Balance$Item",
                           jev_config=FAKE_CFG))
    assert not any("db_balance" in w for w in out.get("warnings", []))


# ---------------- jev_desc compression ----------------

def test_jev_desc_coverage_all_types():
    """Mọi task_type + requirement_type phải có bản nén jev_desc —
    thêm type mới mà quên jev_desc thì test này fail."""
    from tool_help.cards import (TASK_TYPES, REQUIREMENT_TYPES,
                                 _JEV_TASK_DESCS, _JEV_REQ_DESCS)
    assert set(_JEV_TASK_DESCS) == set(TASK_TYPES)
    assert set(_JEV_REQ_DESCS) == set(REQUIREMENT_TYPES)


def test_catalog_prefers_jev_desc():
    from tool_help.cards import (TASK_TYPE_CATALOG, TASK_TYPES,
                                 REQUIREMENT_TYPE_CATALOG, REQUIREMENT_TYPES,
                                 _JEV_TASK_DESCS, _JEV_REQ_DESCS)
    for k in TASK_TYPES:
        assert TASK_TYPE_CATALOG[k] == _JEV_TASK_DESCS[k]
    for k in REQUIREMENT_TYPES:
        entry = REQUIREMENT_TYPE_CATALOG[k]
        got = entry["desc"] if isinstance(entry, dict) else entry
        assert got == _JEV_REQ_DESCS[k]


def test_req_catalog_keeps_examples():
    """Nén nhưng examples (signal VN quan trọng) phải giữ nguyên."""
    from tool_help.cards import (REQUIREMENT_TYPE_CATALOG,
                                 REQUIREMENT_TYPES)
    for k, v in REQUIREMENT_TYPES.items():
        if v.get("examples"):
            assert REQUIREMENT_TYPE_CATALOG[k]["examples"] == v["examples"]


def test_payload_size_compressed():
    """Payload 5 step + UR phải nhỏ hơn ngưỡng nén (trước ~21.8k chars)."""
    from tool_help.service import (_AGENT_CONTEXT, _build_questions)
    from tool_help.cards import (TASK_TYPE_CATALOG,
                                 REQUIREMENT_TYPE_CATALOG)
    steps = ["a", "b", "c", "d", "e"]
    state = {"agent_context": _AGENT_CONTEXT,
             "task_type_catalog": TASK_TYPE_CATALOG,
             "steps": steps, "task_requirement": "ur mau",
             "requirement_type_catalog": REQUIREMENT_TYPE_CATALOG}
    payload = {"model": "jev-latest", "state": state,
               "questions": _build_questions(steps, "ur mau")}
    size = len(json.dumps(payload, ensure_ascii=False,
                          separators=(",", ":")))
    assert size < 17000, f"payload phình lại: {size}"


def test_result_cache_same_input(patch_jev):
    """Cùng input 2 lần -> lần 2 không gọi Jev (trả cache)."""
    calls = []

    def _ask(cfg, state, questions):
        calls.append(1)
        return {"ok": True, "answers": {
            "step1_tool": {"choice": "read_flat", "confidence": 0.9,
                           "probabilities": {"read_flat": 0.9}}},
                "usage": {}}
    patch_jev["fn"] = _ask
    a = tool_help("doc file abc", jev_config=FAKE_CFG)
    b = tool_help("doc file abc", jev_config=FAKE_CFG)
    assert a == b
    assert len(calls) == 1


# ---------------- proc-reading routing (đọc proc) ----------------

def test_keyword_doc_proc_whole_vs_fragment():
    """'đọc/xem proc X' → paste_sql (toàn bộ); có cue đoạn → db_snippet."""
    for step in ("Đọc proc rs_rptDirectCashFlowMultiPeriod",
                 "xem proc zc_abc",
                 "đọc nội dung proc zc_bcdt"):
        out = _parse(tool_help(step, jev_config=None))
        assert out["steps"][0]["task_type"] == "paste_sql", step
    for step in ("Đọc proc rs_x xem cách tính",
                 "trích đoạn proc zc_abc",
                 "đọc đoạn tính tồn cuối kỳ trong proc rs_x"):
        out = _parse(tool_help(step, jev_config=None))
        assert out["steps"][0]["task_type"] == "db_snippet", step


def test_paste_sql_desc_covers_read_whole():
    """paste_sql phải tự nhận 'đọc toàn bộ' — không chỉ 'export'."""
    from tool_help.cards import TASK_TYPE_CATALOG
    assert "read" in TASK_TYPE_CATALOG["paste_sql"].lower()
    assert "WHOLE" in TASK_TYPE_CATALOG["paste_sql"]


# ---------------- related_skills ----------------

def test_related_skills_per_step(patch_jev):
    """Step nhắc ẩn field → related_skills trỏ fbo-design-view-field."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_flat",
                       "probabilities": {"read_flat": 0.9}}})
    out = _parse(tool_help("Ẩn field kieu_bc trên Filter",
                           jev_config=FAKE_CFG))
    s = out["steps"][0]
    assert "fbo-design-view-field" in s["related_skills"]


def test_related_skills_from_ur(patch_jev):
    """UR nhắc đồ thị → top-level related_skills."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_flat",
                       "probabilities": {"read_flat": 0.9}}})
    out = _parse(tool_help(
        "Đọc file",
        context={"task_requirement": "thêm nút đồ thị cho báo cáo"},
        jev_config=FAKE_CFG))
    assert "fbo-procedure-create-report" in (out.get("related_skills") or [])


def test_related_skills_excel_pivot(patch_jev):
    """Step nhắc mẫu Excel/pivot → fbo-excel-pivot-template."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "copy_files",
                       "probabilities": {"copy_files": 0.9}}})
    out = _parse(tool_help("copy mẫu excel rpt_01.xlsx",
                           jev_config=FAKE_CFG))
    assert "fbo-excel-pivot-template" in out["steps"][0]["related_skills"]


def test_no_related_skills_when_irrelevant(patch_jev):
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_run_file",
                       "probabilities": {"db_run_file": 0.9}}})
    out = _parse(tool_help("Chạy file a.sql", jev_config=FAKE_CFG))
    assert "related_skills" not in out["steps"][0]
    assert "related_skills" not in out


# ---------------- proc_name_suggestions ----------------

def test_proc_name_suggestions(patch_jev):
    """UR chứa zcxxxx/rsxxxx → map tên chuẩn chèn '_'."""
    patch_jev["fn"] = _fake_ask({})
    out = _parse(tool_help("x",
                           context={"task_requirement":
                                    "đặt tên zcbcdt theo rsxxxx"},
                           jev_config=FAKE_CFG))
    assert out["proc_name_suggestions"] == {"zcbcdt": "zc_bcdt",
                                            "rsxxxx": "rs_xxxx"}
    texts = list((out.get("notice") or {}).values())
    assert any("proc_name_suggestions" in t for t in texts)


def test_no_proc_name_suggestion_when_underscored(patch_jev):
    """zc_bcdt (đã có '_') KHÔNG sinh suggestion."""
    patch_jev["fn"] = _fake_ask({})
    out = _parse(tool_help("x",
                           context={"task_requirement": "sửa proc zc_bcdt"},
                           jev_config=FAKE_CFG))
    assert "proc_name_suggestions" not in out


# ---------------- consistency warnings: weak coverage ----------------

def test_no_warn_clone_existing_when_step_text_clone(patch_jev):
    """Step ghép route clone_sql nhưng text đã nói clone → không warn."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_sql",
                       "probabilities": {"clone_sql": 0.9}},
        "requirement_type": {"type": "choice", "choice": "clone_existing",
                             "probabilities": {"clone_existing": 0.9}}})
    out = _parse(tool_help("Clone từ chức năng nguồn sang ctrl mới",
                           context={"task_requirement": "save as báo cáo"},
                           jev_config=FAKE_CFG))
    assert not any("clone_existing" in w for w in out.get("warnings", []))


def test_no_warn_clone_existing_weak_alt(patch_jev):
    """save_as_existing nằm trong alternatives → vẫn tính coverage."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "clone_sql",
                       "probabilities": {"clone_sql": 0.5,
                                         "save_as_existing": 0.35}},
        "requirement_type": {"type": "choice", "choice": "clone_existing",
                             "probabilities": {"clone_existing": 0.9}}})
    out = _parse(tool_help("x",
                           context={"task_requirement": "save as"},
                           jev_config=FAKE_CFG))
    assert not any("clone_existing" in w for w in out.get("warnings", []))


def test_no_warn_sql_consumer_with_path(patch_jev):
    """Step check file .sql kèm path cụ thể → file đã tồn tại, không warn."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "db_check_syntax",
                       "probabilities": {"db_check_syntax": 0.9}}})
    out = _parse(tool_help(r"Check syntax C:\temp\proc.sql",
                           jev_config=FAKE_CFG))
    assert not any("type=5" in w for w in out.get("warnings", []))


def test_warn_template_missing_clone_weak_alt_only(patch_jev):
    """clone_template trong alternatives (không top-1) → không warn."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "read_flat",
                       "probabilities": {"read_flat": 0.55,
                                         "clone_template": 0.35}},
        "step2_tool": {"type": "choice", "choice": "db_run_file",
                       "probabilities": {"db_run_file": 0.9}},
        "requirement_type": {"type": "choice",
                             "choice": "category_1_key",
                             "probabilities": {"category_1_key": 0.9}}})
    out = _parse(tool_help("Đọc file mẫu", r"chạy C:\t\voucher.sql",
                           context={"task_requirement": "thêm danh mục"},
                           jev_config=FAKE_CFG))
    assert not any("clone_template" in w for w in out.get("warnings", []))


def test_secondary_requirements_includes_workflow_type(patch_jev):
    """clone_existing (workflow, không template) lộ trong secondary."""
    patch_jev["fn"] = _fake_ask({
        "requirement_type": {"type": "choice", "choice": "report_normal",
                             "probabilities": {"report_normal": 0.6,
                                               "clone_existing": 0.35}}})
    out = _parse(tool_help("x",
                           context={"task_requirement": "tạo bc + save as"},
                           jev_config=FAKE_CFG))
    sec = out["requirement"].get("secondary_requirements")
    assert sec == [{"type": "clone_existing", "probability": 0.35}]


def test_notice_report_graph_button(patch_jev):
    """UR/step nhắc đồ thị → notice liệt kê đủ bộ Chart.ascx/Graph.xml."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "save_as_existing",
                       "probabilities": {"save_as_existing": 0.9}}})
    out = _parse(tool_help("save as báo cáo có nút đồ thị",
                           jev_config=FAKE_CFG))
    texts = list((out.get("notice") or {}).values())
    assert any("Chart.ascx" in t and "Identification" in t for t in texts)


def test_notice_excel_pivot_template(patch_jev):
    """Step nhắc mẫu excel → notice trỏ skill + MissingItemsLimit."""
    patch_jev["fn"] = _fake_ask({
        "step1_tool": {"type": "choice", "choice": "copy_files",
                       "probabilities": {"copy_files": 0.9}}})
    out = _parse(tool_help("copy file mẫu excel rpt_01.xlsx",
                           jev_config=FAKE_CFG))
    texts = list((out.get("notice") or {}).values())
    assert any("MissingItemsLimit" in t for t in texts)
