"""Unit tests for clone_things type=1 parent_* and child_* relations (TC-T1-REL-01 to TC-T1-REL-06) according to doc 13."""

from pathlib import Path
from unittest.mock import patch

import pytest

from clone_things.service import clone_things


def _conn_side_effect(file_path, db_type="app"):
    db_name = "test_sys_db" if db_type == "sys" else "test_app_db"
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type, "database": db_name},
    }


# ============================================================================
# TC-T1-REL-01: recursion=0 -> child_* present on parent, len(pasted) == seed
# ============================================================================
def test_tc_t1_rel_01_recursion_0_child_present(tmp_path):
    sql_file = tmp_path / "out_rel01.sql"

    def _exists_side(parsed, name, schema):
        if name == "A":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name in ("B", "C"):
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "fn_x":
            return True, "FN", "SQL_SCALAR_FUNCTION"
        elif name == "dmkh":
            return True, "U", "USER_TABLE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "A":
            return ["dbo.B", "dbo.C", "dbo.fn_x", "dbo.dmkh"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.A",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        # Only seed A is pasted in file
        assert len(res["pasted"]) == 1
        item_a = res["pasted"][0]
        assert item_a["name"] == "dbo.A"
        assert item_a["child_proc"] == "dbo.B,dbo.C"
        assert item_a["child_func"] == "dbo.fn_x"
        assert item_a["child_table"] == "dbo.dmkh"
        assert "parent_proc" not in item_a
        assert "parent_func" not in item_a


# ============================================================================
# TC-T1-REL-02: recursion=1 -> parent_proc on deps + child_* on parent
# ============================================================================
def test_tc_t1_rel_02_recursion_1_parent_and_child(tmp_path):
    sql_file = tmp_path / "out_rel02.sql"

    def _exists_side(parsed, name, schema):
        if name in ("A", "B", "C"):
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "fn_x":
            return True, "FN", "SQL_SCALAR_FUNCTION"
        elif name == "dmkh":
            return True, "U", "USER_TABLE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        if obj_type == "U":
            return f"CREATE TABLE dbo.{clean_name} (id int)"
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "A":
            return ["dbo.B", "dbo.C", "dbo.fn_x", "dbo.dmkh"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.A",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="1",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        pasted = res["pasted"]
        assert len(pasted) == 5

        by_name = {p["name"]: p for p in pasted}
        # Parent A has child_* and no parent_*
        assert by_name["dbo.A"]["child_proc"] == "dbo.B,dbo.C"
        assert by_name["dbo.A"]["child_func"] == "dbo.fn_x"
        assert by_name["dbo.A"]["child_table"] == "dbo.dmkh"
        assert "parent_proc" not in by_name["dbo.A"]

        # All children have parent_proc = "dbo.A"
        assert by_name["dbo.B"]["parent_proc"] == "dbo.A"
        assert by_name["dbo.C"]["parent_proc"] == "dbo.A"
        assert by_name["dbo.fn_x"]["parent_proc"] == "dbo.A"
        assert by_name["dbo.dmkh"]["parent_proc"] == "dbo.A"


# ============================================================================
# TC-T1-REL-03: Dependency classification -> correct child fields & omit empty
# ============================================================================
def test_tc_t1_rel_03_classification_and_omit_empty(tmp_path):
    sql_file = tmp_path / "out_rel03.sql"

    def _exists_side(parsed, name, schema):
        if name == "p_proc_only":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "sub_proc":
            return True, "P", "SQL_STORED_PROCEDURE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "p_proc_only":
            return ["dbo.sub_proc"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.p_proc_only",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        item = res["pasted"][0]
        assert item["child_proc"] == "dbo.sub_proc"
        # Omit empty fields
        assert "child_func" not in item
        assert "child_table" not in item
        assert "child_view" not in item


# ============================================================================
# TC-T1-REL-04: parent_func when parent is a FUNCTION
# ============================================================================
def test_tc_t1_rel_04_parent_func_when_parent_is_function(tmp_path):
    sql_file = tmp_path / "out_rel04.sql"

    def _exists_side(parsed, name, schema):
        if name == "fn_calc":
            return True, "FN", "SQL_SCALAR_FUNCTION"
        elif name == "t_rates":
            return True, "U", "USER_TABLE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        if obj_type == "U":
            return f"CREATE TABLE dbo.{clean_name} (rate numeric)"
        return f"CREATE FUNCTION dbo.{clean_name}() RETURNS int AS BEGIN RETURN 1 END"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "fn_calc":
            return ["dbo.t_rates"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.fn_calc",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="1",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        by_name = {p["name"]: p for p in res["pasted"]}
        assert by_name["dbo.fn_calc"]["child_table"] == "dbo.t_rates"
        # Child table has parent_func set to fn_calc
        assert by_name["dbo.t_rates"]["parent_func"] == "dbo.fn_calc"
        assert "parent_proc" not in by_name["dbo.t_rates"]


# ============================================================================
# TC-T1-REL-05: Multi-level hierarchy A -> B -> D
# ============================================================================
def test_tc_t1_rel_05_multi_level_hierarchy(tmp_path):
    sql_file = tmp_path / "out_rel05.sql"

    def _exists_side(parsed, name, schema):
        if name in ("A", "B", "D"):
            return True, "P", "SQL_STORED_PROCEDURE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "A":
            return ["dbo.B"]
        elif clean_name == "B":
            return ["dbo.D"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.A",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="1",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        by_name = {p["name"]: p for p in res["pasted"]}
        # A calls B directly (not D)
        assert by_name["dbo.A"]["child_proc"] == "dbo.B"
        # B has parent A, and calls D directly
        assert by_name["dbo.B"]["parent_proc"] == "dbo.A"
        assert by_name["dbo.B"]["child_proc"] == "dbo.D"
        # D has parent B (not A directly)
        assert by_name["dbo.D"]["parent_proc"] == "dbo.B"


# ============================================================================
# TC-T1-REL-06: mode_get does not filter child_table on parent
# ============================================================================
def test_tc_t1_rel_06_mode_get_does_not_filter_child_table(tmp_path):
    sql_file = tmp_path / "out_rel06.sql"
    fake_xml = tmp_path / "SVTran.xml"
    fake_xml.write_text("<controller></controller>", encoding="utf-8")

    mock_summary = {
        "success": True,
        "sql": {"procs": ["zc_upload"]},
    }

    def _exists_side(parsed, name, schema):
        if name == "zc_upload":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "dmkh":
            return True, "U", "USER_TABLE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "zc_upload":
            return ["dbo.dmkh"]
        return []

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.summary_xml", return_value=mock_summary), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        # mode_get="proc" and recursion=0
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
        assert len(res["pasted"]) == 1
        item = res["pasted"][0]
        # child_table must still be present on zc_upload even though mode_get="proc"
        assert item["child_table"] == "dbo.dmkh"
