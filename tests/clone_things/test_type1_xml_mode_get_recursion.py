"""Unit tests for clone_things type=1 XML seed, mode_get, and mode_recursion according to doc 12."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from clone_things.file_manager import append_script_block
from clone_things.service import (
    clone_things,
    parse_mode_get,
    parse_mode_recursion,
)


def _conn_side_effect(file_path, db_type="app"):
    db_name = "test_sys_db" if db_type == "sys" else "test_app_db"
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type, "database": db_name},
    }


# ============================================================================
# TC-T1-GET-01: Parse mode_get aliases + full + invalid + recursion parsing
# ============================================================================
def test_tc_t1_get_01_parse_mode_get_and_recursion():
    # 1. Default & empty
    kinds, warns = parse_mode_get("")
    assert kinds == ["proc"]
    assert warns == []

    # 2. Single aliases
    assert parse_mode_get("procedure")[0] == ["proc"]
    assert parse_mode_get("p")[0] == ["proc"]
    assert parse_mode_get("func")[0] == ["func"]
    assert parse_mode_get("function")[0] == ["func"]
    assert parse_mode_get("fn")[0] == ["func"]
    assert parse_mode_get("view")[0] == ["view"]
    assert parse_mode_get("views")[0] == ["view"]
    assert parse_mode_get("v")[0] == ["view"]
    assert parse_mode_get("table")[0] == ["table"]
    assert parse_mode_get("tables")[0] == ["table"]
    assert parse_mode_get("tbl")[0] == ["table"]
    assert parse_mode_get("u")[0] == ["table"]

    # 3. Full / all / *
    for full_token in ("full", "all", "*", "FULL"):
        kinds, _ = parse_mode_get(full_token)
        assert set(kinds) == {"proc", "func", "view", "table"}

    # 4. Multi-token separated by comma / semicolon
    kinds, warns = parse_mode_get("proc,table;view")
    assert kinds == ["proc", "table", "view"]
    assert warns == []

    # 5. Unknown tokens yield warnings
    kinds, warns = parse_mode_get("proc,xyz_unknown")
    assert kinds == ["proc"]
    assert any("unknown_mode_get_token: xyz_unknown" in w for w in warns)

    # 6. Invalid mode_get (all unknown) -> empty kinds
    kinds, warns = parse_mode_get("invalid_token")
    assert kinds == []
    assert len(warns) == 1

    # 7. parse_mode_recursion
    assert parse_mode_recursion("0") == (0, None)
    assert parse_mode_recursion(0) == (0, None)
    assert parse_mode_recursion("") == (0, None)
    assert parse_mode_recursion(None) == (0, None)
    assert parse_mode_recursion("1") == (1, None)
    assert parse_mode_recursion(1) == (1, None)
    rec, err = parse_mode_recursion("2")
    assert rec is None
    assert "invalid_mode_recursion" in err


# ============================================================================
# TC-T1-XML-01: Mock summary_xml -> seed only procs when mode_get=proc
# ============================================================================
def test_tc_t1_xml_01_seed_only_procs(tmp_path):
    sql_file = tmp_path / "out_xml01.sql"
    fake_xml = tmp_path / "SVTran.xml"
    fake_xml.write_text("<controller></controller>", encoding="utf-8")

    mock_summary = {
        "success": True,
        "sql": {
            "procs": ["zc_upload_a", "dbo.zc_upload_b"],
            "tables": ["dmvt", "dmkh"],
            "views": ["v_order"],
        },
        "controller": {"db_table": "m91$"},
    }

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.summary_xml", return_value=mock_summary), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_test AS SELECT 1"

        res = clone_things(
            type=1,
            object=str(fake_xml),
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_get="proc",
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert res["mode_seed"] == "xml"
        assert res["meta"]["mode_get"] == "proc"
        assert res["meta"]["mode_get_kinds"] == ["proc"]
        assert res["meta"]["mode_recursion"] == 0

        pasted_names = [p["name"] for p in res["pasted"]]
        assert "dbo.zc_upload_a" in pasted_names
        assert "dbo.zc_upload_b" in pasted_names
        # Tables and views must NOT be pasted
        assert "dbo.dmvt" not in pasted_names
        assert "dbo.v_order" not in pasted_names


# ============================================================================
# TC-T1-XML-02: mode_get=proc,table extracts both kinds + db_table
# ============================================================================
def test_tc_t1_xml_02_proc_and_table(tmp_path):
    sql_file = tmp_path / "out_xml02.sql"
    fake_xml = tmp_path / "SVTran.xml"
    fake_xml.write_text("<controller></controller>", encoding="utf-8")

    mock_summary = {
        "success": True,
        "sql": {
            "procs": ["zc_upload_a"],
            "tables": ["dmvt"],
            "views": ["v_order"],
        },
        "controller": {"db_table": "m91$@@prime$partition$current"},
    }

    def _exists_side(parsed, name, schema):
        if name == "zc_upload_a":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name in ("dmvt", "m91$000000", "m91$"):
            return True, "U", "USER_TABLE"
        elif name == "v_order":
            return True, "V", "VIEW"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        if obj_type == "U":
            return f"CREATE TABLE dbo.{clean_name} (id int)"
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.summary_xml", return_value=mock_summary), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object=str(fake_xml),
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_get="proc,table",
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        pasted_names = [p["name"] for p in res["pasted"]]
        assert "dbo.zc_upload_a" in pasted_names
        assert "dbo.dmvt" in pasted_names
        assert "dbo.m91$000000" in pasted_names
        assert "dbo.v_order" not in pasted_names

        styles = {p["name"]: p["script_style"] for p in res["pasted"]}
        assert styles["dbo.zc_upload_a"] == "alter"
        assert styles["dbo.dmvt"] == "create"
        assert styles["dbo.m91$000000"] == "create"


# ============================================================================
# TC-T1-XML-03: XML missing -> xml_not_found
# ============================================================================
def test_tc_t1_xml_03_missing_xml(tmp_path):
    sql_file = tmp_path / "out_xml03.sql"
    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect):
        res = clone_things(
            type=1,
            object="C:\\NonExistentPath\\Missing.xml",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )
        assert res["success"] is False
        assert res["error_code"] == "xml_not_found"


# ============================================================================
# TC-T1-REC-01: recursion=0 does not enqueue child dependencies
# ============================================================================
def test_tc_t1_rec_01_no_recursion(tmp_path):
    sql_file = tmp_path / "out_rec01.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_extract, \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_parent AS SELECT 1"
        mock_extract.return_value = ["dbo.zc_child"]

        res = clone_things(
            type=1,
            object="dbo.zc_parent",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["pasted"]) == 1
        assert res["pasted"][0]["name"] == "dbo.zc_parent"
        # Under doc 13: recursion=0 extracts deps for child_*, but does not paste child into pasted[]
        assert res["pasted"][0].get("child_proc") == "dbo.zc_child"


# ============================================================================
# TC-T1-REC-02: recursion=1 enqueues deps; table is CREATE, proc is ALTER
# ============================================================================
def test_tc_t1_rec_02_with_recursion(tmp_path):
    sql_file = tmp_path / "out_rec02.sql"

    def _exists_side(parsed, name, schema):
        if name == "zc_parent":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "zc_child_proc":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "child_table":
            return True, "U", "USER_TABLE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        if obj_type == "U":
            return f"CREATE TABLE dbo.{clean_name} (id int)"
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "zc_parent":
            return ["dbo.zc_child_proc", "dbo.child_table"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.zc_parent",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="1",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        pasted_names = [p["name"] for p in res["pasted"]]
        assert "dbo.zc_parent" in pasted_names
        assert "dbo.zc_child_proc" in pasted_names
        assert "dbo.child_table" in pasted_names

        styles = {p["name"]: p["script_style"] for p in res["pasted"]}
        assert styles["dbo.zc_parent"] == "alter"
        assert styles["dbo.zc_child_proc"] == "alter"
        assert styles["dbo.child_table"] == "create"

        content = sql_file.read_text(encoding="utf-8")
        assert "ALTER PROCEDURE dbo.zc_parent" in content
        assert "ALTER PROCEDURE dbo.zc_child_proc" in content
        assert "CREATE TABLE dbo.child_table" in content


# ============================================================================
# TC-T1-REC-03: mode_get=proc but dependency is table -> table is still pasted
# ============================================================================
def test_tc_t1_rec_03_deps_not_filtered_by_mode_get(tmp_path):
    sql_file = tmp_path / "out_rec03.sql"
    fake_xml = tmp_path / "SVTran.xml"
    fake_xml.write_text("<controller></controller>", encoding="utf-8")

    mock_summary = {
        "success": True,
        "sql": {"procs": ["zc_upload"], "tables": ["ignored_table_seed"]},
    }

    def _exists_side(parsed, name, schema):
        if name == "zc_upload":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "dep_table":
            return True, "U", "USER_TABLE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        if obj_type == "U":
            return f"CREATE TABLE dbo.{clean_name} (id int)"
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "zc_upload":
            return ["dbo.dep_table"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.summary_xml", return_value=mock_summary), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object=str(fake_xml),
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_get="proc",
            mode_recursion="1",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        pasted_names = [p["name"] for p in res["pasted"]]
        assert "dbo.zc_upload" in pasted_names
        # dep_table must be pasted even though mode_get was only "proc"!
        assert "dbo.dep_table" in pasted_names
        assert "dbo.ignored_table_seed" not in pasted_names


# ============================================================================
# TC-T1-GET-02: Direct sql_name list ignores mode_get filtering
# ============================================================================
def test_tc_t1_get_02_sql_name_ignores_mode_get(tmp_path):
    sql_file = tmp_path / "out_get02.sql"

    def _exists_side(parsed, name, schema):
        if name == "dmkh":
            return True, "U", "USER_TABLE"
        elif name == "zc_proc":
            return True, "P", "SQL_STORED_PROCEDURE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        if obj_type == "U":
            return f"CREATE TABLE dbo.{clean_name} (id int)"
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        # mode_get="proc" but user explicitly requested table dmkh
        res = clone_things(
            type=1,
            object="dbo.dmkh, dbo.zc_proc",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_get="proc",
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert res["mode_seed"] == "sql_name"
        pasted_names = [p["name"] for p in res["pasted"]]
        assert "dbo.dmkh" in pasted_names
        assert "dbo.zc_proc" in pasted_names


# ============================================================================
# TC-T1-REG-01: type=0 regression passes with mode_get / mode_recursion ignored
# ============================================================================
def test_tc_t1_reg_01_type0_regression(tmp_path):
    sql_file = tmp_path / "out_type0.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies", return_value=[]), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        # Object missing on target, exists on source
        def _check_side(parsed, name, schema):
            db = parsed.get("_db")
            path = parsed.get("_path")
            if "Target" in path:
                return False, "", ""
            return True, "P", "SQL_STORED_PROCEDURE"

        mock_exists.side_effect = _check_side
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_type0 AS SELECT 1"

        res = clone_things(
            type=0,
            object="dbo.zc_type0",
            project_source="E:\\FBO\\Source",
            project_target="E:\\FBO\\Target",
            path_to_pasted=str(sql_file),
            mode_get="table",  # should be ignored in type 0
            mode_recursion="0",  # should be ignored in type 0
            open_file=False,
        )

        assert res["success"] is True
        assert res["type"] == 0
        assert len(res["cloned"]) == 1
        assert res["cloned"][0]["name"] == "dbo.zc_type0"


# ============================================================================
# TC-T1-REG-02: Append multiple blocks never produces 'GOUSE'
# ============================================================================
def test_tc_t1_reg_02_no_gouse_when_appending_multiple_blocks(tmp_path):
    sql_file = tmp_path / "out_gouse.sql"
    sql_file.write_text("USE [App_A]\nGO\n\nUSE [Sys_S]\nGO\n", encoding="utf-8")

    # Append block in App section
    append_script_block(
        str(sql_file),
        "CREATE PROCEDURE dbo.zc_app1 AS SELECT 1",
        "dbo.zc_app1",
        "PROCEDURE",
        db="app",
        app_db_name="App_A",
        sys_db_name="Sys_S",
    )

    # Append another block in App section
    append_script_block(
        str(sql_file),
        "CREATE PROCEDURE dbo.zc_app2 AS SELECT 2",
        "dbo.zc_app2",
        "PROCEDURE",
        db="app",
        app_db_name="App_A",
        sys_db_name="Sys_S",
    )

    # Append block in Sys section
    append_script_block(
        str(sql_file),
        "CREATE PROCEDURE dbo.zc_sys1 AS SELECT 3",
        "dbo.zc_sys1",
        "PROCEDURE",
        db="sys",
        app_db_name="App_A",
        sys_db_name="Sys_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert "GOUSE" not in content
    assert "GO\n\nUSE [Sys_S]" in content or "GO\nUSE [Sys_S]" in content
