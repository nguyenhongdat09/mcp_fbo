"""Tests recovery lỗi Invalid object name (AC-OBJHINT-*).

Case lấy từ log thật E:\\fastbusiness_mcp\\logs + chạy thật CHUBB_SP2264.
"""

from datetime import date
from unittest.mock import patch

from query_database.formatter import format_query_result
from query_database.object_hint import build_object_hint, extract_invalid_objects
from query_database.service import query_database


def _err(*names):
    return "; ".join(f"[SQL Server]Invalid object name '{n}'. (208)"
                     for n in names)


def _fake_exec(tables: list[str], other_db_objects: set | None = None):
    """execute_query giả: sys.tables / sys.objects / OBJECT_ID."""
    other_db_objects = other_db_objects or set()

    def _exec(parsed, sql, max_rows=0, params=None):
        params = list(params or [])
        if "OBJECT_ID(?)" in sql and sql.strip().startswith("SELECT OBJECT_ID"):
            hit = params[0] in other_db_objects and parsed.get("db") == "sys"
            return {"success": True,
                    "result_sets": [{"rows": [[1 if hit else None]]}]}
        if "FROM sys.tables WHERE name LIKE" in sql:
            prefix = params[0].rstrip("%").rstrip("$")
            rows = [[t] for t in tables if t.startswith(prefix + "$")]
            return {"success": True, "result_sets": [{"rows": rows}]}
        if "FROM sys.objects" in sql:
            rows = [[t] for t in tables if "$" not in t]
            return {"success": True, "result_sets": [{"rows": rows}]}
        return {"success": False, "error": "unexpected"}
    return _exec


def _conn(fp, db_type):
    return {"success": True, "parsed": {"db": db_type}}


def test_ac_objhint_1_extract():
    assert extract_invalid_objects(_err("menu", "menu", "#q")) == ["menu", "#q"]
    assert extract_invalid_objects("Invalid column name 'x'") == []


def test_ac_objhint_2_wrong_db():
    with patch("query_database.executor.execute_query",
               side_effect=_fake_exec([], {"errorlog"})), \
         patch("query_database.connection.get_connection_config",
               side_effect=_conn):
        h = build_object_hint({"db": "app"}, _err("errorlog"),
                              file_path="x.xml", db_type="app")
    o = h["objects"]["errorlog"]
    assert o["kind"] == "wrong_db" and o["db_type"] == "sys"
    assert h["kind"] == "fix_args"


def test_ac_objhint_3_partition_periods_near_now():
    now = f"{date.today():%Y%m}"
    tables = ["d63$000000", "d63$log", "d63$203012", f"d63${now}",
              "d63$202001"]
    with patch("query_database.executor.execute_query",
               side_effect=_fake_exec(tables)):
        h = build_object_hint({}, _err("d63$$partition$current"))
    o = h["objects"]["d63$$partition$current"]
    assert o["kind"] == "partition"
    assert "placeholder" in o["note"]
    assert o["existing"] == ["d63$000000", f"d63${now}", "d63$202001"]
    assert o["skill"] == "fbo-partition-table-knowledge"


def test_ac_objhint_3_partition_bad_format():
    with patch("query_database.executor.execute_query",
               side_effect=_fake_exec(["c71$000000"])):
        h = build_object_hint({}, _err("c71$250901"))
    assert "sai định dạng kỳ YYYYMM" in h["objects"]["c71$250901"]["note"]


def test_ac_objhint_4_temp_and_builtin_no_db_call():
    with patch("query_database.executor.execute_query") as m:
        h = build_object_hint({}, _err("#q", "STRING_SPLIT"))
    m.assert_not_called()
    assert h["objects"]["#q"]["kind"] == "temp_table"
    assert h["objects"]["STRING_SPLIT"]["kind"] == "unsupported_builtin"


def test_ac_objhint_5_not_found_suggests_similar():
    with patch("query_database.executor.execute_query",
               side_effect=_fake_exec(["dmmagd", "dmtkgd", "dmvt"])), \
         patch("query_database.connection.get_connection_config",
               side_effect=_conn):
        h = build_object_hint({"db": "app"}, _err("dmgd"),
                              file_path="x.xml")
    o = h["objects"]["dmgd"]
    assert o["kind"] == "not_found"
    assert "dmmagd" in o["did_you_mean"]
    assert h["kind"] == "switch"


def test_ac_objhint_6_exception_swallowed():
    with patch("query_database.executor.execute_query",
               side_effect=RuntimeError("down")):
        assert build_object_hint({}, _err("c71$202609")) is None


def test_ac_objhint_7_service_and_formatter():
    with patch("query_database.service.get_connection_config",
               return_value={"success": True, "parsed": {"db": "app"}}), \
         patch("query_database.service.execute_query",
               return_value={"success": False, "error": _err("errorlog")}), \
         patch("query_database.executor.execute_query",
               side_effect=_fake_exec([], {"errorlog"})), \
         patch("query_database.connection.get_connection_config",
               side_effect=_conn):
        res = query_database(file_path="x.xml", query="SELECT * FROM errorlog")
    assert res["error"] == _err("errorlog")
    text = format_query_result(res)
    assert "[RECOVERY invalid_object]" in text
    assert "gọi lại với db_type='sys'" in text
