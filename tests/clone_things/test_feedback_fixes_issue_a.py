"""Unit tests for Issue A: Fallback to OBJECT_DEFINITION on truncation & mode_read=3 spill.
Tests TC-A1 and TC-A2.
"""

from pathlib import Path
from unittest.mock import patch

from clone_things.db_ops import fetch_object_script
from clone_things.service import clone_things


def test_tc_a1_fetch_object_script_fallback_object_definition():
    """TC-A1: Mock summary_object trả truncated=True → fetch_object_script fallback OBJECT_DEFINITION."""
    full_body = "ALTER PROCEDURE [dbo].[large_proc] AS\nBEGIN\n" + ("-- comment\n" * 500) + "SELECT 1;\nEND"

    with patch("clone_things.service.summary_object") as mock_sum, \
         patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.execute_query") as mock_exec:

        mock_sum.return_value = {
            "success": True,
            "truncated": True,
            "definition": "ALTER PROCEDURE [dbo].[large_proc] AS\nBEGIN\n-- truncated...",
        }
        mock_conn.return_value = {
            "success": True,
            "parsed": {"server": "test_server", "database": "test_db"},
        }
        mock_exec.return_value = {
            "success": True,
            "result_sets": [{"columns": ["def"], "rows": [[full_body]]}],
        }

        script, meta = fetch_object_script(
            file_path=r"E:\FBO\P1",
            clean_name="large_proc",
            schema="dbo",
            obj_type="P",
            type_desc="SQL_STORED_PROCEDURE",
            wrap_exists=False,
        )

        assert script == full_body
        assert meta["truncated_upstream"] is False
        mock_exec.assert_called_once()
        called_sql = mock_exec.call_args[0][1]
        assert "OBJECT_DEFINITION" in called_sql
        assert "QUOTENAME(N'dbo')" in called_sql
        assert "QUOTENAME(N'large_proc')" in called_sql


def test_tc_a1_fallback_fails_keeps_truncated_with_flag():
    """TC-A1 fallback: Khi fallback OBJECT_DEFINITION cũng fail → giữ truncated script và gán truncated_upstream=True."""
    truncated_body = "ALTER PROCEDURE [dbo].[large_proc] AS\nBEGIN\n-- truncated..."

    with patch("clone_things.service.summary_object") as mock_sum, \
         patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.execute_query") as mock_exec:

        mock_sum.return_value = {
            "success": True,
            "truncated": True,
            "definition": truncated_body,
        }
        mock_conn.return_value = {
            "success": True,
            "parsed": {"server": "test_server", "database": "test_db"},
        }
        # Fallback query returns empty
        mock_exec.return_value = {
            "success": True,
            "result_sets": [{"columns": ["def"], "rows": [[]]}],
        }

        script, meta = fetch_object_script(
            file_path=r"E:\FBO\P1",
            clean_name="large_proc",
            schema="dbo",
            obj_type="P",
            type_desc="SQL_STORED_PROCEDURE",
            wrap_exists=False,
        )

        assert script == truncated_body
        assert meta["truncated_upstream"] is True


def test_tc_a2_mode_read_3_spills_large_definition(tmp_path):
    """TC-A2: mode_read=3 + mode_read_full_max_chars nhỏ → definition_path tồn tại, file chứa full body, definition_truncated=True."""
    large_sql = "ALTER PROCEDURE [dbo].[zc_test_spill] AS\n" + ("-- filler text\n" * 100) + "SELECT 1;\nGO"
    sql_file = tmp_path / "dummy.sql"

    def _conn_side(path, dt="app"):
        return {"success": True, "parsed": {"server": "s", "database": "db_app"}}

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side), \
         patch("clone_things.service.check_object_exists_and_type", return_value=(True, "P", "SQL_STORED_PROCEDURE")), \
         patch("clone_things.service.fetch_object_script", return_value=(large_sql, {"truncated_upstream": False})), \
         patch("clone_things.service.extract_object_dependencies", return_value=[]), \
         patch("clone_things.type1_flow._get_default_scripts_folder", return_value=tmp_path), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.zc_test_spill",
            project_source=str(tmp_path),
            path_to_pasted=str(sql_file),
            mode_read=3,
            mode_recursion="0",
            open_file=False,
            config={"clone_things": {"mode_read_full_max_chars": 50}},
        )

        assert res["success"] is True
        assert len(res["analyzed"]) == 1
        item = res["analyzed"][0]
        assert item["definition_truncated"] is True
        assert item["chars"] == 50
        assert "definition_path" in item
        assert Path(item["definition_path"]).exists()

        spilled_content = Path(item["definition_path"]).read_text(encoding="utf-8")
        assert spilled_content == large_sql
        assert any("definition_truncated" in w for w in res["warnings"])
        assert "definition_path" in res["agent_message"]
