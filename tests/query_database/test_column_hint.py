"""Tests cho recovery lỗi Invalid column name (AC-COLHINT-*).

Case lấy từ log thật E:\\fastbusiness_mcp\\logs (16/9, 17/9).
"""

from unittest.mock import patch

from query_database import column_hint
from query_database.column_hint import (
    build_column_hint,
    extract_invalid_columns,
    extract_tables,
)
from query_database.formatter import format_query_result
from query_database.service import query_database

_ERR_NAME = (
    "('42S22', \"[42S22] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]"
    "Invalid column name 'name'. (207) (SQLExecDirectW); [42S22] [Microsoft]"
    "[ODBC Driver 18 for SQL Server][SQL Server]Invalid column name 'name'. (207)\")"
)
_ERR_DMCT = (
    "[SQL Server]Invalid column name 'm_ph'. (207); "
    "[SQL Server]Invalid column name 'm_ct'. (207)"
)

_SYSGENDATA_COLS = ["ma_ct", "ten_bang", "kieu", "stt"]
_DMCT_COLS = ["ma_ct", "ten_ct", "ma_ph", "ma_ct_me", "ngay_gh1", "ngay_gh2"]


def _cols_result(mapping: dict) -> dict:
    rows = [[t, c] for t, cs in mapping.items() for c in cs]
    return {"success": True, "result_sets": [{"columns": ["name_in", "name"],
                                              "rows": rows}]}


# ============================================================================
# AC-COLHINT-1: parse lỗi + bảng
# ============================================================================
def test_ac_colhint_1_extract_invalid_columns_dedup():
    assert extract_invalid_columns(_ERR_NAME) == ["name"]
    assert extract_invalid_columns(_ERR_DMCT) == ["m_ph", "m_ct"]
    assert extract_invalid_columns("Incorrect syntax near 'x'") == []


def test_ac_colhint_1_extract_tables():
    sql = """
    -- FROM comment_table
    SELECT a.ma_vt, b.ten_kh INTO #t
    FROM dbo.dmvt a
    LEFT JOIN [dmkh] b ON a.ma_kh = b.ma_kh
    JOIN m81$202601 c ON c.ma_vt = a.ma_vt
    WHERE a.ten_vt = 'FROM fake_table'
    UPDATE dmct SET ten_ct = '' ; INSERT INTO @tv SELECT 1
    """
    assert extract_tables(sql) == ["dmvt", "dmkh", "m81$202601", "dmct"]


# ============================================================================
# AC-COLHINT-2: difflib (chính tả) — case dmct 17/9
# ============================================================================
def test_ac_colhint_2_difflib_typo():
    sql = "SELECT ma_ct, m_ph, m_ct, ngay_gh1 FROM dmct WHERE ma_ct = 'DDV'"
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"dmct": _DMCT_COLS})) as m:
        hint = build_column_hint({"database": "d"}, sql, _ERR_DMCT,
                                 jev_config=None)
    # query sys.columns parameterized, đúng bảng
    assert m.call_args.kwargs["params"] == ["dmct"]
    assert hint["rule"] == "invalid_column"
    assert hint["table_columns"] == {"dmct": _DMCT_COLS}
    assert hint["did_you_mean"]["m_ph"][0] == {
        "column": "ma_ph", "table": "dmct", "by": "difflib", "score": 0.89}
    assert any(h["column"] == "ma_ct" for h in hint["did_you_mean"]["m_ct"])


def test_ac_colhint_2_strong_difflib_skips_jev():
    sql = "SELECT m_ct FROM dmct"
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"dmct": _DMCT_COLS})), \
         patch("jev.ask_jev") as ask:
        hint = build_column_hint({}, sql, "Invalid column name 'm_ct'",
                                 jev_config={"confidence_act": 0.7})
    ask.assert_not_called()                     # m_ct→ma_ct 0.89 đủ tin
    assert hint["did_you_mean"]["m_ct"][0]["column"] == "ma_ct"


_DMVT_COLS = ["ma_vt", "ten_vt", "dvt", "gia_ton", "ong_ba", "tk_vt"]


def test_ac_colhint_2_weak_difflib_dropped_when_jev_none():
    # ca thật 9/10: gia_ban → gia_ton/ong_ba (nhiễu), dmvt không có cột giá
    sql = "SELECT ma_vt, ten_vt, gia_ban FROM dmvt"
    jev_res = {"ok": True, "answers": {"col0": {"choice": "none",
                                                "confidence": 0.9}}}
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"dmvt": _DMVT_COLS})), \
         patch("jev.ask_jev", return_value=jev_res) as ask:
        hint = build_column_hint({}, sql, "Invalid column name 'gia_ban'",
                                 jev_config={"confidence_act": 0.7})
    ask.assert_called_once()                    # difflib yếu → vẫn hỏi Jev
    assert "did_you_mean" not in hint
    assert hint["table_columns"]["dmvt"] == _DMVT_COLS


def test_ac_colhint_2_jev_hit_ranked_before_weak_difflib():
    sql = "SELECT gia_ban FROM dmvt"
    jev_res = {"ok": True, "answers": {"col0": {"choice": "gia_ton",
                                                "confidence": 0.8}}}
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"dmvt": _DMVT_COLS})), \
         patch("jev.ask_jev", return_value=jev_res):
        hint = build_column_hint({}, sql, "Invalid column name 'gia_ban'",
                                 jev_config={"confidence_act": 0.7})
    hits = hint["did_you_mean"]["gia_ban"]
    assert hits[0] == {"column": "gia_ton", "table": "dmvt", "by": "jev",
                       "confidence": 0.8}
    assert [h["column"] for h in hits[1:]] == ["ong_ba"]   # bỏ trùng gia_ton


# ============================================================================
# AC-COLHINT-3: Jev (sai nghĩa) — case sysgendata 16/9
# ============================================================================
def test_ac_colhint_3_jev_semantic_match():
    sql = "SELECT * FROM sysgendata WHERE name LIKE '%81%' ORDER BY name"
    jev_cfg = {"api_key": "k", "base_url": "u", "confidence_act": 0.7,
               "timeout_seconds": 15}
    jev_res = {"ok": True, "answers": {"col0": {
        "choice": "ten_bang", "confidence": 0.86,
        "probabilities": {"ten_bang": 0.88, "none": 0.05}}}}
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"sysgendata": _SYSGENDATA_COLS})), \
         patch("jev.ask_jev", return_value=jev_res) as ask:
        hint = build_column_hint({}, sql, _ERR_NAME, jev_config=jev_cfg)
    cfg_sent, state, questions = ask.call_args.args
    assert cfg_sent["timeout_seconds"] == 5            # cap timeout recovery
    assert set(questions["col0"]["criteria"]) == set(_SYSGENDATA_COLS) | {"none"}
    assert state["table_columns"] == {"sysgendata": _SYSGENDATA_COLS}
    assert hint["did_you_mean"]["name"] == [{
        "column": "ten_bang", "table": "sysgendata", "by": "jev",
        "confidence": 0.86}]


def test_ac_colhint_3_jev_uncertain_zone():
    # ca thật 9/10: unit → dvt conf 0.54 — đúng nhưng dưới act 0.7
    sql = "SELECT ma_vt, unit FROM dmvt"
    jev_res = {"ok": True, "answers": {"col0": {"choice": "dvt",
                                                "confidence": 0.54}}}
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"dmvt": _DMVT_COLS})), \
         patch("jev.ask_jev", return_value=jev_res):
        hint = build_column_hint({}, sql, "Invalid column name 'unit'",
                                 jev_config={"confidence_act": 0.7,
                                             "confidence_review": 0.4})
    assert hint["did_you_mean"]["unit"] == [{
        "column": "dvt", "table": "dmvt", "by": "jev", "confidence": 0.54,
        "uncertain": True}]
    text = format_query_result({"success": False, "error": "x",
                                "recovery": hint})
    assert "Gợi ý: unit → dmvt.dvt (jev 0.54, chưa chắc)" in text


def test_ac_colhint_3_jev_low_confidence_or_none_ignored():
    sql = "SELECT * FROM sysgendata WHERE name = 1"
    for ans in ({"choice": "ten_bang", "confidence": 0.3},
                {"choice": "none", "confidence": 0.95}):
        with patch("query_database.executor.execute_query",
                   return_value=_cols_result({"sysgendata": _SYSGENDATA_COLS})), \
             patch("jev.ask_jev",
                   return_value={"ok": True, "answers": {"col0": ans}}):
            hint = build_column_hint({}, sql, _ERR_NAME,
                                     jev_config={"confidence_act": 0.7})
        assert "did_you_mean" not in hint
        assert hint["table_columns"]["sysgendata"] == _SYSGENDATA_COLS


def test_ac_colhint_3_jev_failure_keeps_columns():
    sql = "SELECT * FROM sysgendata WHERE name = 1"
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"sysgendata": _SYSGENDATA_COLS})), \
         patch("jev.ask_jev", side_effect=RuntimeError("down")):
        hint = build_column_hint({}, sql, _ERR_NAME, jev_config={"k": 1})
    assert hint["table_columns"]["sysgendata"] == _SYSGENDATA_COLS
    assert "did_you_mean" not in hint


# ============================================================================
# AC-COLHINT-4: an toàn — không áp dụng / lỗi recovery
# ============================================================================
def test_ac_colhint_4_not_invalid_column_returns_none():
    with patch("query_database.executor.execute_query") as m:
        assert build_column_hint({}, "SELECT 1", "Incorrect syntax") is None
    m.assert_not_called()


def test_ac_colhint_4_table_unknown_or_temp():
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({})):
        hint = build_column_hint({}, "SELECT x FROM nope", _ERR_NAME,
                                 jev_config=None)
    assert hint["unresolved_tables"] == ["nope"]
    assert "query_type=0" in hint["hint"]
    with patch("query_database.executor.execute_query") as m:
        hint = build_column_hint({}, "SELECT name FROM #t", _ERR_NAME,
                                 jev_config=None)
    m.assert_not_called()               # #temp không query catalog
    assert hint["table_columns"] == {}


def test_ac_colhint_4_exception_swallowed():
    with patch("query_database.executor.execute_query",
               side_effect=RuntimeError("conn lost")):
        assert build_column_hint({}, "SELECT a FROM t", _ERR_NAME,
                                 jev_config=None) is None


# ============================================================================
# AC-COLHINT-5: wiring service + formatter
# ============================================================================
def _run_service(sql, exec_side_effect, query_type=1):
    with patch("query_database.service.get_connection_config",
               return_value={"success": True, "parsed": {"database": "d"},
                             "project_root": "R"}), \
         patch("query_database.service.execute_query",
               side_effect=exec_side_effect), \
         patch.object(column_hint, "_jev_config_cache", None):
        return query_database(file_path="x.xml", query=sql,
                              query_type=query_type)


def test_ac_colhint_5_service_attaches_recovery_and_formats():
    sql = "SELECT ma_ct, m_ph FROM dmct"
    with patch("query_database.executor.execute_query",
               return_value=_cols_result({"dmct": _DMCT_COLS})):
        res = _run_service(
            sql, lambda *a, **k: {"success": False, "error": _ERR_DMCT})
    assert res["success"] is False
    assert res["error"] == _ERR_DMCT                     # lỗi gốc giữ nguyên
    assert res["recovery"]["rule"] == "invalid_column"
    text = format_query_result(res)
    assert text.startswith("[ERROR]")
    assert "[RECOVERY invalid_column]" in text
    assert "Gợi ý: m_ph → dmct.ma_ph" in text
    assert "Cột thật của dmct (6): ma_ct, ten_ct, ma_ph" in text


def test_ac_colhint_5_service_other_error_untouched():
    res = _run_service("SELECT 1 FROM t", lambda *a, **k: {
        "success": False, "error": "Incorrect syntax near 'x'"})
    assert "recovery" not in res
    assert "[RECOVERY" not in format_query_result(res)


def test_ac_colhint_5_call_log_records_rule(tmp_path):
    import json

    from fastbusiness_mcp.utils import call_log

    call_log.set_log_dir(tmp_path)
    try:
        call_log.log_tool_call(
            "query_database", {"query": "q"}, 1.0,
            response_text="[ERROR] Invalid column name 'x'\n\n"
                          "[RECOVERY invalid_column] Cột không tồn tại: x")
    finally:
        call_log.set_log_dir(None)
    rec = json.loads(next(tmp_path.glob("mcp-*.jsonl")).read_text(
        encoding="utf-8").splitlines()[-1])
    assert rec["ok"] is False
    assert rec["recovery_rule"] == "invalid_column"
