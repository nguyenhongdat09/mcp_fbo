"""Unit tests for clone_things type=1 (paste-for-edit) — TC-T1-01 to TC-T1-09."""

from pathlib import Path
from unittest.mock import patch

from clone_things.file_manager import (
    append_script_block,
    object_already_in_sql_file,
)
from clone_things.service import (
    clone_things,
    parse_object_list,
    transform_create_to_alter,
)


def _conn_side_effect(file_path, db_type="app"):
    db_name = "test_sys_db" if db_type == "sys" else "test_app_db"
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type, "database": db_name},
    }


# ============================================================================
# TC-T1-01: transform_create_to_alter
# ============================================================================
def test_tc_t1_01_transform_create_to_alter():
    # 1. CREATE PROCEDURE -> ALTER PROCEDURE
    sql_proc = "CREATE PROCEDURE [dbo].[zc_foo]\nAS\nSELECT 1\nGO"
    res_proc = transform_create_to_alter(sql_proc)
    assert res_proc.startswith("ALTER PROCEDURE [dbo].[zc_foo]")

    # 2. CREATE PROC -> ALTER PROC (preserves PROC)
    sql_p = "CREATE PROC zc_foo\nAS\nSELECT 1"
    res_p = transform_create_to_alter(sql_p)
    assert res_p.startswith("ALTER PROC zc_foo")

    # 3. CREATE FUNCTION -> ALTER FUNCTION
    sql_fn = "CREATE FUNCTION dbo.fn_bar(@x int)\nRETURNS int\nAS\nBEGIN\nRETURN @x\nEND"
    res_fn = transform_create_to_alter(sql_fn)
    assert res_fn.startswith("ALTER FUNCTION dbo.fn_bar")

    # 4. CREATE VIEW -> ALTER VIEW
    sql_view = "CREATE VIEW [dbo].[v_baz]\nAS\nSELECT 1 AS id"
    res_view = transform_create_to_alter(sql_view)
    assert res_view.startswith("ALTER VIEW [dbo].[v_baz]")

    # 5. CREATE OR ALTER -> preserved as is
    sql_or_alter = "CREATE OR ALTER PROCEDURE [dbo].[zc_foo]\nAS\nSELECT 1"
    res_or_alter = transform_create_to_alter(sql_or_alter)
    assert res_or_alter == sql_or_alter

    # 6. Already ALTER -> preserved as is
    sql_already_alter = "ALTER PROCEDURE [dbo].[zc_foo]\nAS\nSELECT 1"
    res_already_alter = transform_create_to_alter(sql_already_alter)
    assert res_already_alter == sql_already_alter

    # 7. CREATE TABLE -> preserved as is (not altered to ALTER TABLE)
    sql_tbl = "CREATE TABLE [dbo].[t1] (\n  id int\n)"
    res_tbl = transform_create_to_alter(sql_tbl)
    assert res_tbl == sql_tbl

    # 8. Leading comments before statement
    sql_with_comment = "-- Header\nCREATE PROCEDURE dbo.zc_with_comment AS SELECT 1"
    res_with_comment = transform_create_to_alter(sql_with_comment)
    assert "ALTER PROCEDURE dbo.zc_with_comment" in res_with_comment


# ============================================================================
# TC-T1-02: object_already_in_sql_file
# ============================================================================
def test_tc_t1_02_object_already_in_sql_file(tmp_path):
    sql_file = tmp_path / "test_dedup.sql"
    content = """USE [test_db]
GO

-- clone_things type=1: dbo.zc_exist | PROCEDURE | paste-for-edit | from source
ALTER PROCEDURE [dbo].[zc_exist]
AS
SELECT 1
GO

CREATE TABLE [dbo].[dm_exist] (
  id int
)
GO
"""
    sql_file.write_text(content, encoding="utf-8")

    # Match exact with schema and brackets
    exists, start, end = object_already_in_sql_file(str(sql_file), "dbo.zc_exist")
    assert exists is True
    assert start == 4  # line 4 is the comment header
    assert end == 8    # line 8 is the GO statement

    # Match without schema prefix (default dbo)
    exists, _, _ = object_already_in_sql_file(str(sql_file), "zc_exist")
    assert exists is True

    # Match table
    exists, _, _ = object_already_in_sql_file(str(sql_file), "dm_exist")
    assert exists is True

    # Case-insensitive
    exists, _, _ = object_already_in_sql_file(str(sql_file), "ZC_EXIST")
    assert exists is True

    # Non-existent object
    exists, start, end = object_already_in_sql_file(str(sql_file), "zc_not_in_file")
    assert exists is False
    assert start is None
    assert end is None


# ============================================================================
# TC-T1-03: append_script_block line range
# ============================================================================
def test_tc_t1_03_append_script_block_line_range(tmp_path):
    sql_file = tmp_path / "test_lines.sql"
    sql_file.write_text("USE [app_db]\nGO\n", encoding="utf-8")

    script = "ALTER PROCEDURE dbo.zc_range\nAS\nSELECT 100\nGO"
    l_start, l_end = append_script_block(
        str(sql_file),
        script,
        "dbo.zc_range",
        "PROCEDURE",
        db="app",
        header_tag="paste_edit",
    )

    content = sql_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Verify 1-based indexing
    assert l_start > 0
    assert l_end >= l_start
    block_lines = lines[l_start - 1 : l_end]
    assert block_lines[0].startswith("-- clone_things type=1: dbo.zc_range")
    assert block_lines[-1].strip() == "GO"


# ============================================================================
# TC-T1-04: Service mock paste 1 proc -> JSON schema + agent_message
# ============================================================================
def test_tc_t1_04_service_paste_one_proc(tmp_path):
    sql_file = tmp_path / "test_pasted.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_test_p1 AS SELECT 1"

        res = clone_things(
            type=1,
            object="zc_test_p1",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert res["type"] == 1
        assert res["mode"] == "paste_for_edit"
        assert len(res["pasted"]) == 1
        assert res["pasted"][0]["name"] == "dbo.zc_test_p1"
        assert res["pasted"][0]["script_style"] == "alter"
        assert res["pasted"][0]["line_start"] > 0
        assert res["pasted"][0]["line_end"] >= res["pasted"][0]["line_start"]
        assert len(res["skipped_already_in_file"]) == 0
        assert len(res["not_found_source"]) == 0
        assert "Đã paste 1 object" in res["agent_message"]
        assert res["meta"]["execute_clone"] is False

        # Verify file content
        content = sql_file.read_text(encoding="utf-8")
        assert "ALTER PROCEDURE dbo.zc_test_p1" in content
        assert "CREATE PROCEDURE dbo.zc_test_p1" not in content


# ============================================================================
# TC-T1-05: Dedup on second run -> skipped_already_in_file
# ============================================================================
def test_tc_t1_05_dedup_second_call(tmp_path):
    sql_file = tmp_path / "test_dedup_service.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_dedup AS SELECT 1"

        # 1st call: pasted
        res1 = clone_things(
            type=1,
            object="zc_dedup",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )
        assert len(res1["pasted"]) == 1
        assert len(res1["skipped_already_in_file"]) == 0

        # 2nd call: skipped_already_in_file
        res2 = clone_things(
            type=1,
            object="zc_dedup",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )
        assert len(res2["pasted"]) == 0
        assert len(res2["skipped_already_in_file"]) == 1
        assert res2["skipped_already_in_file"][0]["name"] == "dbo.zc_dedup"
        assert "line_start" in res2["skipped_already_in_file"][0]
        assert "Không paste object mới" in res2["agent_message"]


# ============================================================================
# TC-T1-06: project_target rỗng OK in type=1, but fails in type=0
# ============================================================================
def test_tc_t1_06_project_target_empty(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    # type=0 without project_target fails
    res_t0 = clone_things(
        type=0,
        object="zc_test",
        project_source="E:\\FBO\\P1",
        project_target="",
        path_to_pasted=str(sql_file),
    )
    assert res_t0["success"] is False
    assert res_t0["error_code"] == "invalid_project_target"

    # type=1 without project_target succeeds
    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROC dbo.zc_t1_notarget AS SELECT 1"

        res_t1 = clone_things(
            type=1,
            object="zc_t1_notarget",
            project_source="E:\\FBO\\P1",
            project_target="",
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )
        assert res_t1["success"] is True
        assert len(res_t1["pasted"]) == 1


# ============================================================================
# TC-T1-07: List parse + max_objects
# ============================================================================
def test_tc_t1_07_parse_object_list_and_max_objects(tmp_path):
    # Parse list helper
    raw = "dbo.a, b; c\nd, a"
    parsed = parse_object_list(raw)
    assert parsed == ["dbo.a", "dbo.b", "dbo.c", "dbo.d"]

    # max_objects in service
    sql_file = tmp_path / "out_max.sql"
    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROCEDURE dbo.x AS SELECT 1"

        res = clone_things(
            type=1,
            object="p1, p2, p3, p4",
            project_source="E:\\FBO\\P1",
            max_objects=2,
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )
        assert res["success"] is True
        assert len(res["pasted"]) == 2
        assert any("truncated_max_objects" in w for w in res["warnings"])


# ============================================================================
# TC-T1-08: execute_clone config true does NOT deploy when type=1
# ============================================================================
def test_tc_t1_08_execute_clone_forced_false(tmp_path):
    sql_file = tmp_path / "out_nodeploy.sql"
    cfg = {"clone_things": {"execute_clone": True}}

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.deploy_script_to_target") as mock_deploy, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_nodeploy AS SELECT 1"

        res = clone_things(
            type=1,
            object="zc_nodeploy",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            config=cfg,
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert res["meta"]["execute_clone"] is False
        mock_deploy.assert_not_called()


# ============================================================================
# TC-T1-09: sys object -> USE sys section (source names)
# ============================================================================
def test_tc_t1_09_sys_object_use_sys_section(tmp_path):
    sql_file = tmp_path / "out_sys.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        # First check (app) -> False, second check (sys) -> True
        mock_exists.side_effect = [
            (False, "", ""),
            (True, "P", "SQL_STORED_PROCEDURE"),
        ]
        mock_fetch.return_value = "CREATE PROCEDURE dbo.sys_proc AS SELECT 1"

        res = clone_things(
            type=1,
            object="sys_proc",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["pasted"]) == 1
        assert res["pasted"][0]["db"] == "sys"

        content = sql_file.read_text(encoding="utf-8")
        # Ensure USE sections use source names
        assert "USE [test_app_db]" in content
        assert "USE [test_sys_db]" in content
        # Ensure sys_proc is placed AFTER USE [test_sys_db]
        sys_use_pos = content.find("USE [test_sys_db]")
        proc_pos = content.find("ALTER PROCEDURE dbo.sys_proc")
        assert sys_use_pos != -1
        assert proc_pos != -1
        assert proc_pos > sys_use_pos


# ============================================================================
# XML Seed & Table Handling in type=1 (superseded by doc 12)
# ============================================================================
def test_tc_t1_xml_seed_missing(tmp_path):
    sql_file = tmp_path / "out_xml.sql"
    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect):
        res = clone_things(
            type=1,
            object="Dir/NonExistent.xml",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )
        assert res["success"] is False
        assert res["error_code"] == "xml_not_found"


def test_tc_t1_table_kept_create(tmp_path):
    sql_file = tmp_path / "out_tbl.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_exists.return_value = (True, "U", "USER_TABLE")
        mock_fetch.return_value = "CREATE TABLE dbo.dmkh (id int)"

        res = clone_things(
            type=1,
            object="dmkh",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["pasted"]) == 1
        assert res["pasted"][0]["script_style"] == "create"
        assert any("table_kept_create" in w for w in res["warnings"])
        # Ensure file DOES contain CREATE TABLE
        content = sql_file.read_text(encoding="utf-8")
        assert "CREATE TABLE dbo.dmkh" in content


def test_tc_t1_no_drop_procedure_in_type1(tmp_path):
    """Ensure type=1 output never contains IF OBJECT_ID ... DROP PROCEDURE statements."""
    # 1. Test transform_create_to_alter strips leading DROP statement
    raw_wrapped = (
        "IF OBJECT_ID(N'[dbo].[zc_PostPXNTran]', N'P') IS NOT NULL\n"
        "    DROP PROCEDURE [dbo].[zc_PostPXNTran]\n"
        "GO\n"
        "CREATE PROCEDURE [dbo].[zc_PostPXNTran]\n"
        "AS\n"
        "SELECT 1\n"
        "GO"
    )
    altered = transform_create_to_alter(raw_wrapped)
    assert "DROP PROCEDURE" not in altered
    assert "IF OBJECT_ID" not in altered
    assert altered.startswith("ALTER PROCEDURE [dbo].[zc_PostPXNTran]")

    # 2. Test service type=1 never outputs DROP
    sql_file = tmp_path / "out_nodrop.sql"
    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_PostPXNTran AS SELECT 1"

        res = clone_things(
            type=1,
            object="zc_PostPXNTran",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        content = sql_file.read_text(encoding="utf-8")
        assert "DROP PROCEDURE" not in content
        assert "IF OBJECT_ID" not in content
        assert "ALTER PROCEDURE dbo.zc_PostPXNTran" in content


# ============================================================================
# TC-C: Marker strip and lazy USE [sys_db] (GEMINI-mcp-agent-feedback-fixes.md)
# ============================================================================
def test_tc_c1_strip_old_clone_things_markers(tmp_path):
    """TC-C1: Script input chứa sẵn các dòng marker cũ (do baked vào definition) → append xong chỉ có 1 marker duy nhất."""
    sql_file = tmp_path / "c1_test.sql"
    sql_file.write_text("", encoding="utf-8")

    baked_script = (
        "-- clone_things type=1: dbo.zc_TestProc | PROCEDURE | paste-for-edit | from source\n"
        "-- clone_things type=1: dbo.zc_TestProc | PROCEDURE | paste-for-edit | from source\n"
        "ALTER PROCEDURE dbo.zc_TestProc AS\n"
        "SELECT 1;\n"
        "GO\n"
    )

    append_script_block(
        str(sql_file),
        baked_script,
        "dbo.zc_TestProc",
        "SQL_STORED_PROCEDURE",
        db="app",
        app_db_name="AppDb",
        sys_db_name="SysDb",
        header_tag="paste_edit",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert content.count("-- clone_things type=1: dbo.zc_TestProc") == 1
    assert content.count("-- clone_things") == 1

    # Idempotent: paste lại cùng script đã chứa marker cũ → vẫn chỉ 1 marker
    append_script_block(
        str(sql_file),
        baked_script,
        "dbo.zc_TestProc",
        "SQL_STORED_PROCEDURE",
        db="app",
        app_db_name="AppDb",
        sys_db_name="SysDb",
        header_tag="paste_edit",
    )
    content2 = sql_file.read_text(encoding="utf-8")
    assert content2.count("-- clone_things type=1: dbo.zc_TestProc") == 1
    assert content2.count("-- clone_things") == 1


def test_tc_c2_lazy_sys_section_paste(tmp_path):
    """TC-C2: App-only paste không có USE [sys_db]; paste app + sys tạo USE [sys_db] đúng vị trí trước block sys."""
    sql_file = tmp_path / "c2_test.sql"
    sql_file.write_text("", encoding="utf-8")

    # 1. Paste app object -> File sạch, không có USE [SysDb]
    append_script_block(
        str(sql_file),
        "ALTER PROCEDURE dbo.zc_app1 AS SELECT 1;\nGO",
        "dbo.zc_app1",
        "SQL_STORED_PROCEDURE",
        db="app",
        app_db_name="AppDb",
        sys_db_name="SysDb",
        header_tag="paste_edit",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert content.startswith("USE [AppDb]\nGO")
    assert "USE [SysDb]" not in content

    # 2. Paste sys object -> xuất hiện USE [SysDb] trước block sys
    append_script_block(
        str(sql_file),
        "CREATE TABLE dbo.syscheckfields(id int);\nGO",
        "dbo.syscheckfields",
        "USER_TABLE",
        db="sys",
        app_db_name="AppDb",
        sys_db_name="SysDb",
        header_tag="paste_edit",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert content.count("USE [AppDb]") == 1
    assert content.count("USE [SysDb]") == 1
    idx_app = content.find("USE [AppDb]")
    idx_p1 = content.find("dbo.zc_app1")
    idx_sys = content.find("USE [SysDb]")
    idx_s1 = content.find("dbo.syscheckfields")
    assert idx_app < idx_p1 < idx_sys < idx_s1

    # 3. Paste thêm 1 app object vào file đã có section sys -> app object chèn trước USE [SysDb]
    append_script_block(
        str(sql_file),
        "ALTER PROCEDURE dbo.zc_app2 AS SELECT 2;\nGO",
        "dbo.zc_app2",
        "SQL_STORED_PROCEDURE",
        db="app",
        app_db_name="AppDb",
        sys_db_name="SysDb",
        header_tag="paste_edit",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert content.count("USE [SysDb]") == 1
    idx_p2 = content.find("dbo.zc_app2")
    idx_sys = content.find("USE [SysDb]")
    idx_s1 = content.find("dbo.syscheckfields")
    assert idx_p2 < idx_sys < idx_s1

