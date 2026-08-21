"""Integration and smoke tests for summary_object covering Phase F requirements."""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.object_catalog.models import DbObjectMeta, ParameterMeta
from queryDatabase.service import query_database
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC, FIXTURE_PIVOT_PROC


FBISP242_XML = r"\\172.168.5.14\CustomerPro\FBI\SHOWA\FBISP242\App_Data\Controllers\Dir\LoanContract.xml"


def test_f1_interest_proc_summary():
    """F1: rs_rptInterestDetailedByLoanContract summary has @Status, ctdmku, cursor."""
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="rs_rptInterestDetailedByLoanContract",
        object_id=101,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta
    mock_fetcher.fetch_many.return_value = {}

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
        mode="summary",
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    assert res["spec_version"] == "1.0"
    assert res["object_type"] == "PROCEDURE"
    summary = res["summary"]
    param_names = [p["name"] for p in summary["params"]]
    assert "@Status" in param_names
    assert "ctdmku" in summary["tables_read"]
    assert summary["signals"]["has_cursor"] is True


def test_f2_pivot_proc_summary():
    """F2: zc_bcthlv summary detects pivot signals and #pivot."""
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="zc_bcthlv",
        object_id=102,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_PIVOT_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta
    mock_fetcher.fetch_many.return_value = {}

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.zc_bcthlv",
        mode="summary",
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    summary = res["summary"]
    assert summary["signals"]["uses_pivot_pattern"] is True
    assert "#pivot" in summary["temp_tables"]


def test_f3_snippet_keywords():
    """F3: snippet with tl_th, @Status returns snippet < 150 lines."""
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="rs_rptInterestDetailedByLoanContract",
        object_id=101,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
        mode="snippet",
        keywords=["tl_th", "@Status"],
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    assert res["mode"] == "snippet"
    assert len(res["snippets"]) > 0
    assert res["total_lines"] < 150


def test_f4_infra_proc_depth_zero():
    """F4: infra proc like ff_GetStartDateOfCycle defaults to depth 0 without expanding calls."""
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="ff_GetStartDateOfCycle",
        object_id=104,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition="CREATE PROCEDURE dbo.ff_GetStartDateOfCycle AS SELECT 1;",
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.ff_GetStartDateOfCycle",
        mode="summary",
        max_depth=1,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    mock_fetcher.fetch_many.assert_not_called()


def test_f5_view_no_call_graph():
    """F5: VIEW returns object_type=VIEW and does not expand call graph."""
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="v_test_view",
        object_id=105,
        type_desc="VIEW",
        sys_type="V",
        definition="CREATE VIEW dbo.v_test_view AS SELECT ma_kh FROM dmkh;",
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.v_test_view",
        mode="summary",
        max_depth=2,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    assert res["object_type"] == "VIEW"
    assert res.get("call_graph") is None
    assert "dmkh" in res["summary"]["tables_read"]


def test_f6_max_objects_truncation():
    """F6: max_objects=2 on proc calling multiple children triggers truncation."""
    root_sql = "CREATE PROC dbo.root_multi AS EXEC dbo.zc_child1; EXEC dbo.zc_child2; EXEC dbo.zc_child3;"
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = DbObjectMeta(
        schema_name="dbo",
        name="root_multi",
        object_id=106,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=root_sql,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_many.return_value = {
        "dbo.zc_child1": DbObjectMeta(
            schema_name="dbo",
            name="zc_child1",
            object_id=107,
            type_desc="SQL_STORED_PROCEDURE",
            sys_type="P",
            definition="CREATE PROC dbo.zc_child1 AS SELECT 1;",
            modify_date=None,
            parameters=[],
        )
    }

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.root_multi",
        mode="summary",
        max_depth=1,
        max_objects=2,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    cg = res.get("call_graph")
    assert cg is not None
    assert cg["truncated"] is True
    assert len(cg["truncated_objects"]) > 0


def test_f7_include_called_by():
    """F7: include_called_by returns called_by list."""
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = DbObjectMeta(
        schema_name="dbo",
        name="zc_target",
        object_id=108,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition="CREATE PROC dbo.zc_target AS SELECT 1;",
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_callers.return_value = ["dbo.caller_a", "dbo.caller_b"]

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.zc_target",
        mode="summary",
        include_called_by=True,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    cg = res.get("call_graph")
    assert cg is not None
    assert "dbo.caller_a" in cg["called_by"]
    assert "dbo.caller_b" in cg["called_by"]


def test_f8_query_database_regression():
    """F8: query_database regression test for query_type=0, 1, 2."""
    mock_conn = {
        "success": True,
        "parsed": {"server": "srv", "database": "db", "user": "u", "password": "p"},
        "project_root": "E:/mock_fbo",
    }

    def fake_execute(parsed, sql, max_rows=20000):
        if "sys.objects" in sql:
            return {
                "success": True,
                "result_sets": [
                    {
                        "columns": ["type", "type_desc"],
                        "rows": [["P", "SQL_STORED_PROCEDURE"]],
                        "row_count": 1,
                    }
                ],
                "row_count": 1,
                "messages": [],
            }
        return {
            "success": True,
            "result_sets": [
                {
                    "columns": ["Text"],
                    "rows": [["CREATE PROC dbo.zc_bcthlv AS SELECT 1;"]],
                    "row_count": 1,
                }
            ],
            "row_count": 1,
            "messages": [],
        }

    with patch("queryDatabase.service.get_connection_config", return_value=mock_conn), \
         patch("queryDatabase.connection.get_connection_config", return_value=mock_conn), \
         patch("queryDatabase.bridges.summary_bridge.get_connection_config", return_value=mock_conn), \
         patch("queryDatabase.service.execute_query", side_effect=fake_execute):

        # Type 1: inline SQL
        res1 = query_database(file_path="mock.xml", query="SELECT 1", query_type=1)
        assert res1["success"] is True
        assert "result_sets" in res1

        # Type 0: object lookup (table schema)
        def fake_table_execute(parsed, sql, max_rows=20000):
            if "sys.objects" in sql:
                return {
                    "success": True,
                    "result_sets": [
                        {"columns": ["type", "type_desc"], "rows": [["U", "USER_TABLE"]]}
                    ],
                }
            return {
                "success": True,
                "result_sets": [
                    {"columns": ["val"], "rows": [["CREATE TABLE [dbo].[dmkh] (ma_kh varchar(33));"]]}
                ],
            }

        with patch("queryDatabase.service.execute_query", side_effect=fake_table_execute):
            res0_table = query_database(file_path="mock.xml", query="dmkh", query_type=0)
            assert res0_table["success"] is True
            assert res0_table["resolved_as"] == "table_schema"

        # Type 0: object lookup (proc summary)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_one.return_value = DbObjectMeta(
            schema_name="dbo",
            name="zc_bcthlv",
            object_id=1,
            type_desc="SQL_STORED_PROCEDURE",
            sys_type="P",
            definition="CREATE PROC dbo.zc_bcthlv AS SELECT 1;",
            modify_date=None,
            parameters=[],
        )
        mock_fetcher.fetch_many.return_value = {}

        res0_proc = query_database(
            file_path="mock.xml",
            query="zc_bcthlv",
            query_type=0,
            use_cache=False,
            fetcher_override=mock_fetcher,
        )
        assert res0_proc["success"] is True
        assert res0_proc["resolved_as"] == "object_summary"


def test_f9_schema_resolution_consistency():
    """F9: dbo.zc_x vs zc_x with schema=dbo produces consistent results."""
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="zc_x",
        object_id=109,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition="CREATE PROC dbo.zc_x AS SELECT 1;",
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta

    res1 = summary_object(
        file_path="mock.xml",
        object_name="dbo.zc_x",
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    res2 = summary_object(
        file_path="mock.xml",
        object_name="zc_x",
        schema="dbo",
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res1["object"] == res2["object"] == "dbo.zc_x"


def test_f10_snippet_validation():
    """F10: snippet without keywords or zones returns snippet_params_required."""
    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.zc_x",
        mode="snippet",
    )
    assert res["success"] is False
    assert res["error"] == "snippet_params_required"


def test_f11_cache_key_different_max_objects():
    """F11 / R3: cache key distinguishes different max_objects values."""
    root_sql = "CREATE PROC dbo.root_cache AS EXEC dbo.zc_child1; EXEC dbo.zc_child2; EXEC dbo.zc_child3;"
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = DbObjectMeta(
        schema_name="dbo",
        name="root_cache",
        object_id=99999,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=root_sql,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_many.return_value = {
        "dbo.zc_child1": DbObjectMeta(
            schema_name="dbo",
            name="zc_child1",
            object_id=10001,
            type_desc="SQL_STORED_PROCEDURE",
            sys_type="P",
            definition="CREATE PROC dbo.zc_child1 AS SELECT 1;",
            modify_date=None,
            parameters=[],
        ),
        "dbo.zc_child2": DbObjectMeta(
            schema_name="dbo",
            name="zc_child2",
            object_id=10002,
            type_desc="SQL_STORED_PROCEDURE",
            sys_type="P",
            definition="CREATE PROC dbo.zc_child2 AS SELECT 1;",
            modify_date=None,
            parameters=[],
        ),
    }

    # Call with max_objects=2 (truncated)
    res_trunc = summary_object(
        file_path="mock.xml",
        object_name="dbo.root_cache",
        mode="summary",
        max_depth=1,
        max_objects=2,
        use_cache=True,
        fetcher_override=mock_fetcher,
    )
    assert res_trunc["call_graph"]["truncated"] is True

    # Call with max_objects=30 (not truncated) -> must NOT hit the max_objects=2 cache
    res_full = summary_object(
        file_path="mock.xml",
        object_name="dbo.root_cache",
        mode="summary",
        max_depth=1,
        max_objects=30,
        use_cache=True,
        fetcher_override=mock_fetcher,
    )
    assert res_full["call_graph"]["truncated"] is False


def test_f12_p0_p1_improvements():
    """F12: Verify clean tables_read, filtered result_sets, snippet_index, and logic_hints."""
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="rs_rptInterestDetailedByLoanContract",
        object_id=101,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta
    mock_fetcher.fetch_many.return_value = {}

    res = summary_object(
        file_path="mock.xml",
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
        mode="summary",
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    assert res["success"] is True
    summary = res["summary"]

    # Tables: clean, no aliases (a, b, c, cur), no temp tables
    assert "dmku" in summary["tables_read"]
    assert "ctdmku" in summary["tables_read"]
    assert "a" not in summary["tables_read"]
    assert "cur" not in summary["tables_read"]
    assert "#report" not in summary["tables_read"]
    assert "#report" in summary["temp_tables"]

    # Result sets: exactly 1 RS (the final select, no variable assignments)
    assert len(summary["result_sets"]) == 1
    rs1 = summary["result_sets"][0]
    assert rs1["ordinal"] == 1
    assert "ma_ku" in rs1["columns_hint"]
    assert "tl_th" in rs1["columns_hint"]
    assert "@days" not in rs1["columns_hint"]

    # Snippet Index
    assert "header" in summary["snippet_index"]
    assert "cursor" in summary["snippet_index"]
    assert "result_set" in summary["snippet_index"]

    # Logic Hints
    assert summary["logic_hints"]["interest_related"] is True
    assert "tl_th" in summary["logic_hints"]["keywords_suggested"]


@pytest.mark.skipif(not os.getenv("FBISP242_XML"), reason="Set FBISP242_XML env var to run live test against SQL Server")
def test_live_rs_rpt_interest_summary():
    """Live E2E test against FBISP242 share and SQL Server if network is accessible."""
    fbisp_xml = os.getenv("FBISP242_XML", FBISP242_XML)
    t_start = time.perf_counter()
    res = summary_object(
        file_path=fbisp_xml,
        object_name="rs_rptInterestDetailedByLoanContract",
        mode="summary",
        use_cache=False,
    )
    total_elapsed = time.perf_counter() - t_start

    meta = res.get("meta", {})
    timing = meta.get("timing", {})
    total_ms = timing.get("total_time_ms") or int(total_elapsed * 1000)

    print("\n" + "=" * 80)
    print("  LIVE FBISP242 SUMMARY_OBJECT BENCHMARK & RESULT")
    print("=" * 80)
    print(f"  Object       : {res.get('object')} ({res.get('object_type')})")
    print(f"  Database     : {res.get('database')}")
    print(f"  Parse Status : {res.get('parse_status')}")
    print(f"  Line Count   : {res.get('line_count')} lines")
    print(f"  Total Time   : {total_elapsed:.2f}s ({total_ms} ms)")
    print("-" * 80)
    print("  CHI TIẾT THỜI GIAN TỪNG CÔNG ĐOẠN (TIMING BREAKDOWN)")
    print("-" * 80)
    if timing:
        for k, v in timing.items():
            if k == "total_time_ms":
                continue
            pct = (v / (total_ms or 1)) * 100
            bar = "#" * int(min(20, pct // 5))
            print(f"  - {k:<25} : {v:>7} ms ({pct:>5.1f}%) | {bar}")
        print(f"  * {'total_time_ms':<25} : {total_ms:>7} ms (100.0%)")
    else:
        print(f"  - ANTLR Parse Time         : {meta.get('parse_time_ms', 0):>7} ms")
        print(f"  * Total Execution Time     : {total_ms:>7} ms")
    print("-" * 80)
    print("  JSON RESULT TRẢ VỀ CHO AGENT:")
    print("-" * 80)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("=" * 80 + "\n")

    assert res["success"] is True
    assert res["object_type"] == "PROCEDURE"

