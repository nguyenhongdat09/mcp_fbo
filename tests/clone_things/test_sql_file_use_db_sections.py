"""Unit tests for SQL file USE DB sections (TC-USE-01 to TC-USE-07)."""

from pathlib import Path
from clone_things.file_manager import ensure_use_db_sections, append_script_block
from clone_things.service import clone_things
from unittest.mock import patch


def test_tc_use_01_empty_file_ensure_and_append_app(tmp_path):
    """TC-USE-01: File rỗng -> ensure + append app -> Đầu file USE [AppDb] + GO; block app; có USE [SysDb] phía dưới."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text("", encoding="utf-8")

    append_script_block(
        str(sql_file),
        "CREATE PROCEDURE dbo.zc_app1 AS SELECT 1",
        "dbo.zc_app1",
        "SQL_STORED_PROCEDURE",
        db="app",
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert content.startswith("USE [Newpearl_R2SP223_A]\nGO")
    assert "-- clone_things: dbo.zc_app1 | SQL_STORED_PROCEDURE | from source" in content
    assert "CREATE PROCEDURE dbo.zc_app1 AS SELECT 1" in content
    assert "USE [Newpearl_R2SP223_S]\nGO" in content

    # Check order: USE App -> app block -> USE Sys
    idx_use_app = content.find("USE [Newpearl_R2SP223_A]")
    idx_app_block = content.find("dbo.zc_app1")
    idx_use_sys = content.find("USE [Newpearl_R2SP223_S]")
    assert idx_use_app < idx_app_block < idx_use_sys


def test_tc_use_02_empty_file_append_sys(tmp_path):
    """TC-USE-02: File rỗng -> append sys -> Block sys sau USE [SysDb]."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text("", encoding="utf-8")

    append_script_block(
        str(sql_file),
        "CREATE TABLE dbo.syscheckfields(id int)",
        "dbo.syscheckfields",
        "USER_TABLE",
        db="sys",
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    idx_use_app = content.find("USE [Newpearl_R2SP223_A]")
    idx_use_sys = content.find("USE [Newpearl_R2SP223_S]")
    idx_sys_block = content.find("dbo.syscheckfields")

    assert idx_use_app < idx_use_sys < idx_sys_block


def test_tc_use_03_existing_app_block_append_sys(tmp_path):
    """TC-USE-03: Đã có USE app+sys + 1 app block -> append sys -> Sys block sau USE sys; không đụng app section."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(
        "USE [Newpearl_R2SP223_A]\nGO\n\n"
        "-- clone_things: dbo.zc_app1 | SQL_STORED_PROCEDURE | from source\n"
        "CREATE PROCEDURE dbo.zc_app1 AS SELECT 1\nGO\n\n"
        "USE [Newpearl_R2SP223_S]\nGO\n",
        encoding="utf-8",
    )

    append_script_block(
        str(sql_file),
        "CREATE TABLE dbo.syscheckfields(id int)",
        "dbo.syscheckfields",
        "USER_TABLE",
        db="sys",
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    idx_use_app = content.find("USE [Newpearl_R2SP223_A]")
    idx_app_block = content.find("dbo.zc_app1")
    idx_use_sys = content.find("USE [Newpearl_R2SP223_S]")
    idx_sys_block = content.find("dbo.syscheckfields")

    assert idx_use_app < idx_app_block < idx_use_sys < idx_sys_block


def test_tc_use_04_existing_sys_block_append_app(tmp_path):
    """TC-USE-04: Đã có USE app+sys + 1 sys block -> append app -> App block trước USE sys."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(
        "USE [Newpearl_R2SP223_A]\nGO\n\n"
        "USE [Newpearl_R2SP223_S]\nGO\n\n"
        "-- clone_things: dbo.syscheckfields | USER_TABLE | from source\n"
        "CREATE TABLE dbo.syscheckfields(id int)\nGO\n",
        encoding="utf-8",
    )

    append_script_block(
        str(sql_file),
        "CREATE PROCEDURE dbo.zc_app1 AS SELECT 1",
        "dbo.zc_app1",
        "SQL_STORED_PROCEDURE",
        db="app",
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    idx_use_app = content.find("USE [Newpearl_R2SP223_A]")
    idx_app_block = content.find("dbo.zc_app1")
    idx_use_sys = content.find("USE [Newpearl_R2SP223_S]")
    idx_sys_block = content.find("dbo.syscheckfields")

    assert idx_use_app < idx_app_block < idx_use_sys < idx_sys_block


def test_tc_use_05_file_with_unmarked_script_ensure(tmp_path):
    """TC-USE-05: File có script không USE -> ensure -> Prepend USE app; content cũ nằm vùng app; thêm USE sys cuối."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(
        "-- existing user script\nCREATE PROCEDURE dbo.legacy AS SELECT 99\nGO\n",
        encoding="utf-8",
    )

    ensure_use_db_sections(
        str(sql_file),
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    idx_use_app = content.find("USE [Newpearl_R2SP223_A]")
    idx_legacy = content.find("dbo.legacy")
    idx_use_sys = content.find("USE [Newpearl_R2SP223_S]")

    assert idx_use_app < idx_legacy < idx_use_sys
    assert content.startswith("USE [Newpearl_R2SP223_A]\nGO\n\n-- existing user script")
    assert content.endswith("USE [Newpearl_R2SP223_S]\nGO\n")


def test_tc_use_06_detect_use_without_brackets_no_duplicate(tmp_path):
    """TC-USE-06: Detect USE Newpearl_R2SP223_A không bracket -> Không chèn trùng USE app."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text(
        "USE Newpearl_R2SP223_A\nGO\n\nCREATE PROCEDURE dbo.p1 AS SELECT 1\nGO\n",
        encoding="utf-8",
    )

    ensure_use_db_sections(
        str(sql_file),
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    # Must have only 1 occurrence of Newpearl_R2SP223_A
    assert content.count("Newpearl_R2SP223_A") == 1
    # Must append USE [Newpearl_R2SP223_S]
    assert "USE [Newpearl_R2SP223_S]\nGO" in content


def test_tc_use_07_sys_db_missing_connection_warning(tmp_path):
    """TC-USE-07: db=sys nhưng thiếu sys connection name -> warning; không crash; append cuối file."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text("", encoding="utf-8")

    # Call append_script_block with db='sys' but sys_db_name=''
    append_script_block(
        str(sql_file),
        "CREATE TABLE dbo.syscheckfields(id int)",
        "dbo.syscheckfields",
        "USER_TABLE",
        db="sys",
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert "USE [Newpearl_R2SP223_A]\nGO" in content
    assert "USE [" not in content.replace("USE [Newpearl_R2SP223_A]", "")
    assert "CREATE TABLE dbo.syscheckfields(id int)" in content

    # Test via service clone_things when target sys connection is missing
    def _conn_cfg(path, dt):
        if "TGT" in path:
            if dt == "app":
                return {"success": True, "parsed": {"server": "s", "database": "Target_A"}}
            return {"success": False, "error": "no sys db on target"}
        # SRC has both app and sys
        if dt == "app":
            return {"success": True, "parsed": {"server": "s", "database": "Source_A"}}
        return {"success": True, "parsed": {"server": "s", "database": "Source_S"}}

    with patch("clone_things.service.get_connection_config", side_effect=_conn_cfg), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        out_sql = tmp_path / "service_out.sql"
        out_sql.write_text("", encoding="utf-8")
        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE TABLE dbo.syscheckfields(id int)"

        # Target app F, Source app F, Source sys T
        mock_exists.side_effect = [
            (False, "", ""),
            (False, "", ""),
            (True, "U", "USER_TABLE"),
        ]

        res = clone_things(
            object="dbo.syscheckfields",
            project_source=r"E:\FBO\SRC",
            project_target=r"E:\FBO\TGT",
            path_to_pasted=str(out_sql),
            open_file=False,
        )

        assert res["success"] is True
        assert any("sys_db_name_missing_for_append" in w for w in res["warnings"])
        file_content = out_sql.read_text(encoding="utf-8")
        assert "CREATE TABLE dbo.syscheckfields(id int)" in file_content


def test_tc_use_08_repro_live_shape_syscheckfields_after_use_sys(tmp_path):
    """
    TC-USE-08 (repro live shape):
    Content giống file user: USE A, vài app block, syscheckfields sai chỗ (trước USE S),
    USE S ở EOF không có body -> append_script_block(..., db="sys", ...) ->
    block mới phải xuất hiện SAU USE [Newpearl_R2SP223_S] (không thêm vào trước marker).
    """
    sql_file = tmp_path / "live_shape.sql"
    sql_file.write_text(
        "USE [Newpearl_R2SP223_A]\nGO\n\n"
        "-- clone_things: dbo.zc_app1 | PROCEDURE | from source\n"
        "CREATE PROCEDURE dbo.zc_app1 AS SELECT 1\nGO\n\n"
        "-- clone_things: dbo.syscheckfields | USER_TABLE | from source\n"
        "CREATE TABLE dbo.syscheckfields(id int)\nGO\n\n"
        "USE [Newpearl_R2SP223_S]\nGO\n",
        encoding="utf-8",
    )

    append_script_block(
        str(sql_file),
        "CREATE TABLE dbo.syscheckfields(id int, col2 varchar(10))",
        "dbo.syscheckfields",
        "USER_TABLE",
        db="sys",
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    idx_use_sys = content.find("USE [Newpearl_R2SP223_S]")
    assert idx_use_sys != -1

    # Block mới phải nằm SAU USE [Newpearl_R2SP223_S]
    idx_new_sys_block = content.find("col2 varchar(10)")
    assert idx_new_sys_block > idx_use_sys


def test_tc_use_09_multiple_sys_blocks_all_after_use_sys(tmp_path):
    """
    TC-USE-09:
    USE A + app + USE S + đã có 1 sys block -> append sys thứ 2 ->
    cả hai sys sau USE S; không xen app.
    """
    sql_file = tmp_path / "multi_sys.sql"
    sql_file.write_text(
        "USE [Newpearl_R2SP223_A]\nGO\n\n"
        "-- clone_things: dbo.zc_app1 | PROCEDURE | from source\n"
        "CREATE PROCEDURE dbo.zc_app1 AS SELECT 1\nGO\n\n"
        "USE [Newpearl_R2SP223_S]\nGO\n\n"
        "-- clone_things: dbo.sys1 | USER_TABLE | from source\n"
        "CREATE TABLE dbo.sys1(id int)\nGO\n",
        encoding="utf-8",
    )

    append_script_block(
        str(sql_file),
        "CREATE TABLE dbo.sys2(id int)",
        "dbo.sys2",
        "USER_TABLE",
        db="sys",
        app_db_name="Newpearl_R2SP223_A",
        sys_db_name="Newpearl_R2SP223_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    idx_use_app = content.find("USE [Newpearl_R2SP223_A]")
    idx_app = content.find("dbo.zc_app1")
    idx_use_sys = content.find("USE [Newpearl_R2SP223_S]")
    idx_sys1 = content.find("dbo.sys1")
    idx_sys2 = content.find("dbo.sys2")

    assert idx_use_app < idx_app < idx_use_sys < idx_sys1 < idx_sys2


def test_tc_use_10_service_sys_object_flow(tmp_path):
    """
    TC-USE-10 (service):
    Mock find_object_on_side source trả db=sys cho syscheckfields ->
    assert file order USE A < USE S < syscheckfields, cloned[0]["db"] == "sys",
    và cloned[0]["target_db"] == "Target_S".
    """
    def _conn_cfg(path, dt):
        if "TGT" in path:
            if dt == "app":
                return {"success": True, "parsed": {"server": "s", "database": "Target_A"}}
            return {"success": True, "parsed": {"server": "s", "database": "Target_S"}}
        if dt == "app":
            return {"success": True, "parsed": {"server": "s", "database": "Source_A"}}
        return {"success": True, "parsed": {"server": "s", "database": "Source_S"}}

    with patch("clone_things.service.get_connection_config", side_effect=_conn_cfg), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        out_sql = tmp_path / "service_out_sys.sql"
        out_sql.write_text("", encoding="utf-8")
        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE TABLE dbo.syscheckfields(id int)"

        # Target app F, Target sys F, Source app F, Source sys T
        mock_exists.side_effect = [
            (False, "", ""),
            (False, "", ""),
            (False, "", ""),
            (True, "U", "USER_TABLE"),
        ]

        res = clone_things(
            object="dbo.syscheckfields",
            project_source=r"E:\FBO\SRC",
            project_target=r"E:\FBO\TGT",
            path_to_pasted=str(out_sql),
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["cloned"]) == 1
        assert res["cloned"][0]["db"] == "sys"
        assert res["cloned"][0]["target_db"] == "Target_S"

        content = out_sql.read_text(encoding="utf-8")
        idx_use_app = content.find("USE [Target_A]")
        idx_use_sys = content.find("USE [Target_S]")
        idx_sys_block = content.find("dbo.syscheckfields")

        assert idx_use_app < idx_use_sys < idx_sys_block


def test_no_gouse_bug_when_overwriting_app_block(tmp_path):
    """Ensure that overwriting an existing block in APP section does not eat newline and cause 'GOUSE'."""
    sql_file = tmp_path / "test_gouse.sql"
    sql_file.write_text(
        "USE [App_A]\nGO\n\n"
        "-- clone_things: dbo.zc_app | PROCEDURE | from source\n"
        "CREATE PROCEDURE dbo.zc_app AS SELECT 1\nGO\n\n"
        "USE [Sys_S]\nGO\n",
        encoding="utf-8",
    )

    # Overwrite dbo.zc_app
    append_script_block(
        str(sql_file),
        "CREATE PROCEDURE dbo.zc_app AS SELECT 2",
        "dbo.zc_app",
        "PROCEDURE",
        db="app",
        app_db_name="App_A",
        sys_db_name="Sys_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert "GOUSE" not in content
    assert "GO\n\nUSE [Sys_S]" in content or "GO\nUSE [Sys_S]" in content
    assert "SELECT 2" in content
    assert "SELECT 1" not in content

