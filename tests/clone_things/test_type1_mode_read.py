"""Unit tests for clone_things type=1 mode_read (TC-MR-01 to TC-MR-06) according to doc 14."""

from pathlib import Path
from unittest.mock import patch

from clone_things.service import clone_things, parse_mode_read


def _conn_side_effect(file_path, db_type="app"):
    db_name = "test_sys_db" if db_type == "sys" else "test_app_db"
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type, "database": db_name},
    }


def _exists_side(parsed, name, schema):
    valid_names = {
        "zc_sctnt": ("P", "SQL_STORED_PROCEDURE"),
        "FastBusiness$Balance$BContract": ("P", "SQL_STORED_PROCEDURE"),
        "cdku": ("U", "USER_TABLE"),
        "dmku": ("U", "USER_TABLE"),
        "fn_test": ("FN", "SQL_SCALAR_FUNCTION"),
        "v_test": ("V", "VIEW"),
        "p1": ("P", "SQL_STORED_PROCEDURE"),
        "p2": ("P", "SQL_STORED_PROCEDURE"),
        "p3": ("P", "SQL_STORED_PROCEDURE"),
        "p4": ("P", "SQL_STORED_PROCEDURE"),
        "p5": ("P", "SQL_STORED_PROCEDURE"),
    }
    if name in valid_names:
        t, d = valid_names[name]
        return True, t, d
    return False, "", ""


def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
    if clean_name == "zc_sctnt":
        return "CREATE PROCEDURE [dbo].[zc_sctnt] AS SELECT 1"
    if clean_name == "cdku":
        return "CREATE TABLE [dbo].[cdku] (id int)"
    if clean_name in ("p1", "p2", "p3", "p4", "p5"):
        return f"CREATE PROCEDURE [dbo].[{clean_name}] AS SELECT 1"
    return "CREATE PROCEDURE [dbo].[dummy] AS SELECT 1"


def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
    if clean_name == "zc_sctnt":
        return [
            "dbo.FastBusiness$Balance$BContract",
            "dbo.cdku",
            "dbo.dmku",
        ]
    return []


# ============================================================================
# Unit: parse_mode_read
# ============================================================================
def test_parse_mode_read():
    assert parse_mode_read(None) == (1, None)
    assert parse_mode_read(0) == (0, None)
    assert parse_mode_read(1) == (1, None)
    assert parse_mode_read(3) == (3, None)
    assert parse_mode_read("0") == (0, None)
    assert parse_mode_read("1") == (1, None)
    assert parse_mode_read("3") == (3, None)
    assert parse_mode_read(" 1 ") == (1, None)

    # Invalid values
    val, err = parse_mode_read(2)
    assert val is None and "invalid_mode_read" in err

    val, err = parse_mode_read("2")
    assert val is None and "invalid_mode_read" in err

    val, err = parse_mode_read("foo")
    assert val is None and "invalid_mode_read" in err

    val, err = parse_mode_read(True)
    assert val is None and "invalid_mode_read" in err


# ============================================================================
# TC-MR-01 (P0): Default mode_read=1 no file write
# ============================================================================
def test_tc_mr_01_default_mode_read_1_no_file_write(tmp_path):
    sql_file = tmp_path / "should_not_exist.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user") as mock_open:

        # Default: do not pass mode_read
        res = clone_things(
            type=1,
            object="dbo.zc_sctnt",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
        )

        assert res["success"] is True
        assert res["mode_read"] == 1
        assert res["meta"]["mode_read"] == 1
        assert res["path_to_pasted"] is None
        assert res["pasted"] == []
        assert len(res["analyzed"]) == 1
        item = res["analyzed"][0]
        assert item["name"] == "dbo.zc_sctnt"
        assert item["object_type"] == "SQL_STORED_PROCEDURE"
        assert item["db"] == "app"
        assert "definition" not in item
        assert "line_start" not in item
        assert "line_end" not in item
        assert item.get("child_proc") == "dbo.FastBusiness$Balance$BContract"
        assert item.get("child_table") == "dbo.cdku,dbo.dmku"

        # No file created, no open_file called
        assert not sql_file.exists()
        mock_open.assert_not_called()


# ============================================================================
# TC-MR-02 (P0): mode_read=0 still pastes + lines
# ============================================================================
def test_tc_mr_02_mode_read_0_pastes_and_lines(tmp_path):
    sql_file = tmp_path / "out_paste.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.zc_sctnt",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        assert res["mode_read"] == 0
        assert res["path_to_pasted"] == str(sql_file)
        assert len(res["pasted"]) == 1
        assert "analyzed" not in res
        p_item = res["pasted"][0]
        assert p_item["name"] == "dbo.zc_sctnt"
        assert p_item["line_start"] is not None
        assert p_item["line_end"] is not None
        assert p_item["script_style"] == "alter"
        assert sql_file.exists()
        content = sql_file.read_text(encoding="utf-8")
        assert "ALTER PROCEDURE [dbo].[zc_sctnt]" in content


# ============================================================================
# TC-MR-03 (P0): mode_read=3 returns definition
# ============================================================================
def test_tc_mr_03_mode_read_3_returns_definition(tmp_path):
    sql_file = tmp_path / "should_not_be_written.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.open_file_for_user") as mock_open:

        res = clone_things(
            type=1,
            object="dbo.zc_sctnt",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            mode_read=3,
        )

        assert res["success"] is True
        assert res["mode_read"] == 3
        assert res["path_to_pasted"] is None
        assert res["pasted"] == []
        assert len(res["analyzed"]) == 1
        item = res["analyzed"][0]
        assert item["name"] == "dbo.zc_sctnt"
        assert item["script_style"] == "alter"
        assert item["definition"].startswith("ALTER PROCEDURE [dbo].[zc_sctnt]")
        assert item["chars"] == len(item["definition"])
        assert item.get("child_proc") == "dbo.FastBusiness$Balance$BContract"
        assert "line_start" not in item
        assert not sql_file.exists()
        mock_open.assert_not_called()


# ============================================================================
# TC-MR-04 (P0): mode_read=3 + recursion=1 -> error
# ============================================================================
def test_tc_mr_04_mode_read_3_recursion_1_error():
    res = clone_things(
        type=1,
        object="dbo.zc_sctnt",
        project_source="E:\\FBO\\P1",
        mode_recursion="1",
        mode_read=3,
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_mode_read_combo"


# ============================================================================
# TC-MR-05 (P1): mode_read=3 seed > 3 -> error
# ============================================================================
def test_tc_mr_05_mode_read_3_seed_gt_3_error():
    # 4 objects > 3 default max
    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect):
        res = clone_things(
            type=1,
            object="dbo.p1, dbo.p2, dbo.p3, dbo.p4",
            project_source="E:\\FBO\\P1",
            mode_recursion="0",
            mode_read=3,
        )
        assert res["success"] is False
        assert res["error_code"] == "invalid_mode_read"
        assert "at most 3" in res["message"] or "mode_read=1" in res["message"]


# ============================================================================
# TC-MR-06 (P1): encrypt_proc with mode_read=1 and 3
# ============================================================================
def test_tc_mr_06_encrypt_proc_mode_read_1_and_3():
    def _exists_enc(parsed, name, schema):
        if name == "FastBusiness$Partition$Execute":
            return True, "P", "SQL_STORED_PROCEDURE"
        return False, "", ""

    def _is_enc(parsed_conn, clean_name, schema="dbo"):
        return clean_name == "FastBusiness$Partition$Execute"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_enc), \
         patch("clone_things.service.is_object_encrypted", side_effect=_is_enc):

        # 1. mode_read=1
        res1 = clone_things(
            type=1,
            object="dbo.FastBusiness$Partition$Execute",
            project_source="E:\\FBO\\P1",
            mode_read=1,
        )
        assert res1["success"] is True
        assert len(res1["analyzed"]) == 0
        assert "dbo.FastBusiness$Partition$Execute" in res1["encrypt_proc"]
        assert "mã hóa" in res1["agent_message"] or "encrypted" in res1["agent_message"]

        # 2. mode_read=3
        res3 = clone_things(
            type=1,
            object="dbo.FastBusiness$Partition$Execute",
            project_source="E:\\FBO\\P1",
            mode_read=3,
        )
        assert res3["success"] is True
        assert len(res3["analyzed"]) == 0
        assert "dbo.FastBusiness$Partition$Execute" in res3["encrypt_proc"]
        assert "mã hóa" in res3["agent_message"] or "encrypted" in res3["agent_message"]


# ============================================================================
# AC-MR-03: mode_read=1 + XML + recursion=0
# ============================================================================
def test_ac_mr_03_mode_read_1_xml_seed(tmp_path):
    xml_file = tmp_path / "Voucher.xml"
    xml_file.write_text("<root />", encoding="utf-8")
    sql_file = tmp_path / "temp.sql"

    xml_summary = {
        "success": True,
        "controller": {"db_table": "dmkh"},
        "sql": {
            "procs": ["dbo.zc_sctnt"],
            "tables": ["dbo.cdku"],
            "views": [],
            "functions": [],
        },
    }

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.summary_xml", return_value=xml_summary), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side):

        res = clone_things(
            type=1,
            object=str(xml_file),
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_get="proc",
            mode_recursion="0",
            mode_read=1,
        )

        assert res["success"] is True
        assert res["path_to_pasted"] is None
        assert not sql_file.exists()
        assert len(res["analyzed"]) == 1
        assert res["analyzed"][0]["name"] == "dbo.zc_sctnt"
        assert res["analyzed"][0].get("child_proc") == "dbo.FastBusiness$Balance$BContract"


# ============================================================================
# AC-MR-08: type=0 + mode_read=1 ignored
# ============================================================================
def test_ac_mr_08_type0_ignores_mode_read():
    # Calling type=0 without project_target fails with invalid_project_target (type=0 validation),
    # proving type=0 flow is executed and mode_read does not change type=0 behavior.
    res = clone_things(
        type=0,
        object="dbo.zc_sctnt",
        project_source="E:\\FBO\\P1",
        project_target="",
        mode_read=1,
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_target"
