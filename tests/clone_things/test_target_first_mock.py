"""Unit tests for Target-First and Dependency flow with mocks (TC-CORE-*, TC-DEP-*)."""

from unittest.mock import patch
from clone_things.service import clone_things


def _conn_side_effect(file_path, db_type="app"):
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type},
    }


def test_target_first_skipped_exists(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        # First lookup bucket (app) on target → exists
        mock_exists.return_value = (True, "U", "USER_TABLE")

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
        assert res["skipped_exists"][0]["db"] == "app"
        assert len(res["not_found_both"]) == 0


def test_clone_source_only(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_only_src AS SELECT 1"

        # target app F, target sys F, source app T
        mock_exists.side_effect = [
            (False, "", ""),
            (False, "", ""),
            (True, "P", "SQL_STORED_PROCEDURE"),
        ]

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
        assert res["cloned"][0]["db"] == "app"
        assert len(res["skipped_exists"]) == 0
        assert len(res["not_found_both"]) == 0

        content = sql_file.read_text(encoding="utf-8")
        assert "CREATE PROCEDURE dbo.zc_only_src AS SELECT 1" in content
        assert content.endswith("GO\n")
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args.kwargs.get("db_type") == "app" or mock_fetch.call_args[1].get("db_type") == "app"


def test_clone_from_source_sys_when_missing_on_app(tmp_path):
    """Object chỉ có trên sys DB nguồn → vẫn clone, db=sys."""
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE TABLE dbo.syscheckfields(id int)"

        # target app F, target sys F, source app F, source sys T
        mock_exists.side_effect = [
            (False, "", ""),
            (False, "", ""),
            (False, "", ""),
            (True, "U", "USER_TABLE"),
        ]

        res = clone_things(
            object="syscheckfields",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["cloned"]) == 1
        assert res["cloned"][0]["db"] == "sys"
        assert res["cloned"][0]["name"] == "dbo.syscheckfields"
        assert mock_fetch.call_args.kwargs.get("db_type") == "sys" or mock_fetch.call_args[1].get("db_type") == "sys"


def test_skipped_exists_on_target_sys(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        # target app F, target sys T
        mock_exists.side_effect = [
            (False, "", ""),
            (True, "U", "USER_TABLE"),
        ]

        res = clone_things(
            object="userinfo2",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        assert res["cloned"] == []
        assert res["skipped_exists"][0]["db"] == "sys"
        assert res["skipped_exists"][0]["name"] == "dbo.userinfo2"


def test_system_noise_not_in_not_found(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)

        res = clone_things(
            object="tempdb",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        assert "dbo.tempdb" in res["skipped_noise"]
        assert res["not_found_both"] == []
        mock_exists.assert_not_called()


def test_not_found_both(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
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
        # target app+sys + source app+sys
        assert mock_exists.call_count == 4

        content = sql_file.read_text(encoding="utf-8")
        assert "-- not found in 2 project: dbo.funcGhost\n" in content


def test_clone_with_execute_clone_true(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.deploy_script_to_target") as mock_deploy, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_calc AS SELECT 1"
        mock_deploy.return_value = (True, None)

        mock_exists.side_effect = [
            (False, "", ""),
            (False, "", ""),
            (True, "P", "SQL_STORED_PROCEDURE"),
        ]

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

        content = sql_file.read_text(encoding="utf-8")
        assert "CREATE PROCEDURE dbo.zc_calc AS SELECT 1" in content


def test_clone_with_execute_clone_fail(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.deploy_script_to_target") as mock_deploy, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_calc AS SELECT 1"
        mock_deploy.return_value = (False, "Syntax error near SELECT")

        mock_exists.side_effect = [
            (False, "", ""),
            (False, "", ""),
            (True, "P", "SQL_STORED_PROCEDURE"),
        ]

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
