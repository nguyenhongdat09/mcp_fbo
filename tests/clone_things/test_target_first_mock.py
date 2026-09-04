"""Unit tests for Target-First and Dependency flow with mocks (TC-CORE-*, TC-DEP-*)."""

from unittest.mock import patch
from pathlib import Path
from clone_things.service import clone_things


def test_target_first_skipped_exists(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_conn.return_value = {"success": True, "parsed": {}}
        mock_open.return_value = (True, None)

        # Object 'dmkh' exists on target
        def side_effect_exists(parsed_conn, clean_name, schema="dbo"):
            return True, "U", "USER_TABLE"

        mock_exists.side_effect = side_effect_exists

        res = clone_things(
            object="dmkh",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["cloned"]) == 0
        assert len(res["skipped_exists"]) == 1
        assert res["skipped_exists"][0]["name"] == "dbo.dmkh"
        assert res["skipped_exists"][0]["where"] == "target"
        assert len(res["not_found_both"]) == 0


def test_clone_source_only(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_conn.return_value = {"success": True, "parsed": {}}
        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_only_src AS SELECT 1"

        # Not on target, but exists on source
        call_count = [0]
        def side_effect_exists(parsed_conn, clean_name, schema="dbo"):
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                # Target check
                return False, "", ""
            else:
                # Source check
                return True, "P", "SQL_STORED_PROCEDURE"

        mock_exists.side_effect = side_effect_exists

        res = clone_things(
            object="zc_only_src",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["cloned"]) == 1
        assert res["cloned"][0]["name"] == "dbo.zc_only_src"
        assert res["cloned"][0]["from"] == "source"
        assert len(res["skipped_exists"]) == 0
        assert len(res["not_found_both"]) == 0

        # File content check
        content = sql_file.read_text(encoding="utf-8")
        assert "CREATE PROCEDURE dbo.zc_only_src AS SELECT 1" in content
        assert content.endswith("GO\n")


def test_not_found_both(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_conn.return_value = {"success": True, "parsed": {}}
        mock_open.return_value = (True, None)

        # Neither target nor source has this object
        mock_exists.return_value = (False, "", "")

        res = clone_things(
            object="funcGhost",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["cloned"]) == 0
        assert len(res["skipped_exists"]) == 0
        assert "dbo.funcGhost" in res["not_found_both"]

        # Summary line check at end of file
        content = sql_file.read_text(encoding="utf-8")
        assert "-- not found in 2 project: dbo.funcGhost\n" in content


def test_clone_with_execute_clone_true(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.deploy_script_to_target") as mock_deploy, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_conn.return_value = {"success": True, "parsed": {}}
        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_calc AS SELECT 1"
        mock_deploy.return_value = (True, None)

        call_count = [0]
        def side_effect_exists(parsed_conn, clean_name, schema="dbo"):
            call_count[0] += 1
            return (False, "", "") if call_count[0] % 2 == 1 else (True, "P", "SQL_STORED_PROCEDURE")

        mock_exists.side_effect = side_effect_exists

        res = clone_things(
            object="zc_calc",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            config={"clone_things": {"execute_clone": True}},
            open_file=False,
        )

        assert res["success"] is True
        assert res["deployed"] is True
        assert res["execute_clone"] is True
        assert len(res["cloned"]) == 1
        assert res["cloned"][0]["deployed"] is True
        mock_deploy.assert_called_once()

        # File is still appended
        content = sql_file.read_text(encoding="utf-8")
        assert "CREATE PROCEDURE dbo.zc_calc AS SELECT 1" in content


def test_clone_with_execute_clone_fail(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.deploy_script_to_target") as mock_deploy, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_conn.return_value = {"success": True, "parsed": {}}
        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_calc AS SELECT 1"
        mock_deploy.return_value = (False, "Syntax error near SELECT")

        call_count = [0]
        def side_effect_exists(parsed_conn, clean_name, schema="dbo"):
            call_count[0] += 1
            return (False, "", "") if call_count[0] % 2 == 1 else (True, "P", "SQL_STORED_PROCEDURE")

        mock_exists.side_effect = side_effect_exists

        res = clone_things(
            object="zc_calc",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            config={"clone_things": {"execute_clone": True}},
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["cloned"]) == 1
        assert res["cloned"][0]["deployed"] is False
        assert "Syntax error" in res["cloned"][0]["deploy_error"]
        assert any("deploy_failed" in w for w in res["warnings"])
