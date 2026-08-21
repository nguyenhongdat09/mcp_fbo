"""Tests for integrated query_database with summary_object functionality."""

from unittest.mock import MagicMock, patch
from queryDatabase import query_database
from queryDatabase.formatter import format_query_result
from queryDatabase.object_catalog.models import DbObjectMeta
from fastbusiness_mcp.mcp_app import query_database_tool
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC


def test_query_database_type0_proc_summary():
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="rs_rptInterestDetailedByLoanContract",
        object_id=999,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta
    mock_fetcher.fetch_many.return_value = {}

    with patch("queryDatabase.service.get_connection_config") as mock_conn, \
         patch("queryDatabase.service.execute_query") as mock_exec:
        mock_conn.return_value = {
            "success": True,
            "parsed": {"server": "SRV", "database": "DB"},
            "project_root": "E:\\FBO",
            "web_config_path": "E:\\FBO\\Web.config",
        }
        mock_exec.return_value = {
            "success": True,
            "result_sets": [
                {"columns": ["type", "type_desc"], "rows": [["P", "SQL_STORED_PROCEDURE"]]}
            ],
        }

        res = query_database(
            file_path="mock_path.xml",
            query="dbo.rs_rptInterestDetailedByLoanContract",
            query_type=0,
            mode="summary",
            max_depth=1,
            use_cache=False,
            fetcher_override=mock_fetcher,
        )

        assert res["success"] is True
        assert res["object"] == "dbo.rs_rptInterestDetailedByLoanContract"
        assert res["object_type"] == "PROCEDURE"
        assert res["resolved_as"] == "object_summary"
        assert "summary" in res

        formatted = format_query_result(res)
        assert "[OK] summary_object" in formatted
        assert "dbo.rs_rptInterestDetailedByLoanContract" in formatted
        assert "```json" in formatted


def test_query_database_type0_proc_snippet():
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="rs_rptInterestDetailedByLoanContract",
        object_id=999,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta
    mock_fetcher.fetch_many.return_value = {}

    with patch("queryDatabase.service.get_connection_config") as mock_conn, \
         patch("queryDatabase.service.execute_query") as mock_exec:
        mock_conn.return_value = {
            "success": True,
            "parsed": {"server": "SRV", "database": "DB"},
            "project_root": "E:\\FBO",
            "web_config_path": "E:\\FBO\\Web.config",
        }
        mock_exec.return_value = {
            "success": True,
            "result_sets": [
                {"columns": ["type", "type_desc"], "rows": [["P", "SQL_STORED_PROCEDURE"]]}
            ],
        }

        res = query_database(
            file_path="mock_path.xml",
            query="rs_rptInterestDetailedByLoanContract",
            query_type=0,
            mode="snippet",
            keywords=["tl_th"],
            use_cache=False,
            fetcher_override=mock_fetcher,
        )

        assert res["success"] is True
        assert res["mode"] == "snippet"
        assert res["resolved_as"] == "object_summary"
        assert "snippets" in res
        assert len(res["snippets"]) > 0

        formatted = format_query_result(res)
        assert "[OK] summary_object" in formatted
        assert "Mode: snippet" in formatted


def test_query_database_type0_proc_full():
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="rs_rptInterestDetailedByLoanContract",
        object_id=999,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta
    mock_fetcher.fetch_many.return_value = {}

    with patch("queryDatabase.service.get_connection_config") as mock_conn, \
         patch("queryDatabase.service.execute_query") as mock_exec:
        mock_conn.return_value = {
            "success": True,
            "parsed": {"server": "SRV", "database": "DB"},
            "project_root": "E:\\FBO",
            "web_config_path": "E:\\FBO\\Web.config",
        }
        mock_exec.return_value = {
            "success": True,
            "result_sets": [
                {"columns": ["type", "type_desc"], "rows": [["P", "SQL_STORED_PROCEDURE"]]}
            ],
        }

        res = query_database(
            file_path="mock_path.xml",
            query="rs_rptInterestDetailedByLoanContract",
            query_type=0,
            mode="full",
            use_cache=False,
            fetcher_override=mock_fetcher,
        )

        assert res["success"] is True
        assert res["mode"] == "full"
        assert res["definition"] == FIXTURE_INTEREST_PROC

        formatted = format_query_result(res)
        assert "[OK] summary_object" in formatted
        assert "Mode: full" in formatted


def test_query_database_type0_table_schema():
    with patch("queryDatabase.service.get_connection_config") as mock_conn, \
         patch("queryDatabase.service.execute_query") as mock_exec:
        mock_conn.return_value = {
            "success": True,
            "parsed": {"server": "SRV", "database": "DB"},
            "project_root": "E:\\FBO",
            "web_config_path": "E:\\FBO\\Web.config",
        }
        # First call: lookup sys.objects -> returns 'U' USER_TABLE
        # Second call: execute table_schema.sql -> returns schema lines
        mock_exec.side_effect = [
            {
                "success": True,
                "result_sets": [
                    {"columns": ["type", "type_desc"], "rows": [["U", "USER_TABLE"]]}
                ],
            },
            {
                "success": True,
                "server": "SRV",
                "database": "DB",
                "execution_time_ms": 15,
                "row_count": 1,
                "result_sets": [
                    {"columns": ["val"], "rows": [["CREATE TABLE [dbo].[dmkh] (ma_kh varchar(33));"]]}
                ],
            },
        ]

        res = query_database(
            file_path="mock_path.xml",
            query="dmkh",
            query_type=0,
        )

        assert res["success"] is True
        assert res["resolved_as"] == "table_schema"
        assert res["object_name"] == "dmkh"

        formatted = format_query_result(res)
        assert "[OK] Query executed" in formatted
        assert "Resolved as: table_schema" in formatted
        assert "CREATE TABLE [dbo].[dmkh]" in formatted


def test_mcp_query_database_tool_integration():
    with patch("fastbusiness_mcp.mcp_app.query_database") as mock_qd:
        mock_qd.return_value = {
            "success": True,
            "spec_version": "1.0",
            "object": "dbo.zc_bcthlv",
            "object_type": "PROCEDURE",
            "mode": "summary",
            "resolved_as": "object_summary",
            "summary": {"parameters": []},
        }

        # Test direct query_database_tool call with query_type=0
        out1 = query_database_tool(
            file_path="E:\\FBO\\Filter\\test.xml",
            query="zc_bcthlv",
            query_type=0,
            mode="summary",
        )
        assert "[OK] summary_object" in out1
        assert "dbo.zc_bcthlv" in out1
