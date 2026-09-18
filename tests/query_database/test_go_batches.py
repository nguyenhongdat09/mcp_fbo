"""Tests for GO batch splitting/execution (AC-GO-*) and cell truncation (AC-TRUNC-*)."""

from unittest.mock import patch

from query_database.executor import split_go_batches, execute_sql_batches
from query_database.formatter import format_query_result, _cell_text
from query_database.service import query_database


# ============================================================================
# AC-GO: split_go_batches / execute_sql_batches / type=2 wiring
# ============================================================================
def test_ac_go_1_three_batches():
    script = "SELECT 1\nGO\nSELECT 2\ngo\nSELECT 3"
    assert split_go_batches(script) == ["SELECT 1", "SELECT 2", "SELECT 3"]

    with patch("query_database.executor.execute_query") as m:
        m.return_value = {
            "success": True,
            "result_sets": [],
            "messages": [],
            "row_count": 0,
            "execution_time_ms": 1,
        }
        res = execute_sql_batches({"database": "d", "server": "s"}, script)

    assert res["success"] is True
    assert res["batch_count"] == 3
    assert res["batches_ok"] == 3
    assert m.call_count == 3


def test_ac_go_2_batch_failure_fails_fast():
    def side(parsed, q, max_rows=0):
        if "BAD" in q:
            return {"success": False, "error": "syntax error near BAD"}
        return {"success": True, "result_sets": [], "messages": [], "row_count": 0}

    with patch("query_database.executor.execute_query", side_effect=side) as m:
        res = execute_sql_batches({"database": "d"}, "SELECT 1\nGO\nBAD\nGO\nSELECT 3")

    assert res["success"] is False
    assert res["failed_batch_index"] == 2
    assert res["failed_batch_preview"] == "BAD"
    assert res["batches_ok"] == 1
    assert res["batch_count"] == 3
    assert m.call_count == 2  # dừng ngay, không chạy batch 3


def test_ac_go_3_no_go_single_batch():
    with patch("query_database.executor.execute_query") as m:
        m.return_value = {"success": True, "result_sets": [], "messages": [], "row_count": 1}
        res = execute_sql_batches({"database": "d"}, "SELECT 1\nSELECT 2")

    assert res["success"] is True
    assert res["batch_count"] == 1
    assert m.call_count == 1


def test_ac_go_4_go_inside_string_not_split():
    # 'GO' nằm giữa chuỗi (không đứng riêng 1 dòng) → không split
    script = "SELECT N'abcGOdef'\nSELECT 'x' + N'GO' + 'y'"
    assert len(split_go_batches(script)) == 1


def test_ac_go_5_deploy_uses_shared_helper():
    from clone_things.db_ops import deploy_script_to_target

    with patch("clone_things.service.execute_sql_batches") as m:
        m.return_value = {"success": True, "batch_count": 2, "batches_ok": 2}
        ok, err = deploy_script_to_target({"database": "d"}, "SELECT 1\nGO\nSELECT 2")

    assert ok is True
    assert err is None
    m.assert_called_once()
    assert m.call_args[0][1] == "SELECT 1\nGO\nSELECT 2"


def test_ac_go_5_deploy_error_reports_batch():
    from clone_things.db_ops import deploy_script_to_target

    with patch("clone_things.service.execute_sql_batches") as m:
        m.return_value = {
            "success": False,
            "error": "boom",
            "failed_batch_index": 2,
            "batch_count": 3,
        }
        ok, err = deploy_script_to_target({"database": "d"}, "x")

    assert ok is False
    assert "batch 2/3" in err
    assert "boom" in err


def test_ac_go_type2_uses_batches(tmp_path):
    sql_file = tmp_path / "script.sql"
    sql_file.write_text("SELECT 1\nGO\nSELECT 2", encoding="utf-8")

    with patch("query_database.service.get_connection_config") as mconn, \
         patch("query_database.service.execute_sql_batches") as mb:
        mconn.return_value = {"success": True, "parsed": {"database": "d"}}
        mb.return_value = {"success": True, "batch_count": 2, "batches_ok": 2,
                           "result_sets": [], "messages": [], "row_count": 0}
        res = query_database(
            file_path="E:\\FBO\\P1\\Web.config",
            query=str(sql_file),
            query_type=2,
        )

    assert res["success"] is True
    assert res["batch_count"] == 2
    assert res["sql_file_path"] == str(sql_file)
    mb.assert_called_once()


# ============================================================================
# AC-TRUNC: formatter không cắt JSON, preview an toàn
# ============================================================================
def test_ac_trunc_1_single_col_long_text_not_cut():
    long_def = "X" * 2700
    result = {
        "success": True,
        "query_type": 1,
        "result_sets": [{"columns": ["text"], "rows": [[long_def]]}],
        "row_count": 1,
        "messages": [],
    }
    out = format_query_result(result)
    assert long_def in out  # full 2700 chars trong preview
    assert "… [+" not in out


def test_ac_trunc_1b_definition_column_not_cut():
    long_def = "Y" * 500
    result = {
        "success": True,
        "query_type": 1,
        "result_sets": [{"columns": ["name", "definition"], "rows": [["p1", long_def]]}],
        "row_count": 1,
        "messages": [],
    }
    out = format_query_result(result)
    assert long_def in out


def test_ac_trunc_preview_flag_for_plain_columns():
    long_val = "Z" * 200
    result = {
        "success": True,
        "query_type": 1,
        "result_sets": [{"columns": ["id", "note"], "rows": [[1, long_val]]}],
        "row_count": 1,
        "messages": [],
    }
    out = format_query_result(result)
    assert "… [+123 chars]" in out  # 200 - 77 = 123


def test_ac_trunc_2_cell_text_json_untouched():
    # _cell_text chỉ ảnh hưởng preview text; rows JSON không qua _cell_text
    assert _cell_text("a" * 100, allow_full=True) == "a" * 100
    assert _cell_text(None) == "NULL"
    assert _cell_text("short") == "short"


def test_formatter_shows_batch_info():
    result = {
        "success": True,
        "query_type": 2,
        "result_sets": [],
        "row_count": 0,
        "messages": [],
        "batch_count": 3,
        "batches_ok": 3,
    }
    out = format_query_result(result)
    assert "Batches: 3/3 OK" in out


def test_formatter_failed_batch_info():
    result = {
        "success": False,
        "error": "boom",
        "failed_batch_index": 2,
        "batch_count": 3,
        "failed_batch_preview": "BAD SQL",
    }
    out = format_query_result(result)
    assert "Failed batch: 2/3" in out
    assert "BAD SQL" in out
