"""Tests for type=0 object list split (AC-LIST-*) and trigger support (AC-TRG-*)."""

from unittest.mock import patch

from clone_things.service import clone_things
from clone_things.script_transform import wrap_check_exists, _wrap_trigger_ddl
from clone_things.db_ops import fetch_object_script


def _conn_side_effect(file_path, db_type="app"):
    db_name = "test_sys_db" if db_type == "sys" else "test_app_db"
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type, "database": db_name},
    }


# ============================================================================
# AC-LIST: type=0 sql_name seed → parse_object_list
# ============================================================================
def test_ac_list_1_comma_separated_objects(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    def _exists(parsed, name, schema):
        return False, "", ""  # không tồn tại đâu cả

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists):
        res = clone_things(
            object="t1,t2,t3",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is True
    assert res["parsed_objects"] == ["dbo.t1", "dbo.t2", "dbo.t3"]
    assert sorted(res["not_found_both"]) == ["dbo.t1", "dbo.t2", "dbo.t3"]
    assert all("," not in n for n in res["not_found_both"])


def test_ac_list_2_semicolon_newline_separated(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", return_value=(False, "", "")):
        res = clone_things(
            object="tA; tB\ntC",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["parsed_objects"] == ["dbo.tA", "dbo.tB", "dbo.tC"]
    assert len(res["not_found_both"]) == 3


def test_ac_list_3_only_missing_name_in_not_found(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    def _exists(parsed, name, schema):
        is_source = "P1" in parsed.get("_path", "")
        if not is_source:
            return False, "", ""  # target: chưa có gì
        if name == "missing_tbl":
            return False, "", ""
        return True, "U", "USER_TABLE"

    def _fetch(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=True):
        return f"CREATE TABLE [dbo].[{clean_name}] (id int)"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch), \
         patch("clone_things.service.extract_object_dependencies", return_value=[]), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):
        res = clone_things(
            object="tbl_ok1,missing_tbl,tbl_ok2",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is True
    assert res["not_found_both"] == ["dbo.missing_tbl"]
    assert len(res["cloned"]) == 2


def test_ac_list_4_xml_path_not_split(tmp_path):
    # XML seed path không bị split theo dấu phẩy
    xml_file = tmp_path / "Foo,Bar.xml"  # tên file có dấu phẩy vẫn là 1 seed
    xml_file.write_text("<root />", encoding="utf-8")
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    xml_summary = {
        "success": True,
        "controller": {"db_table": ""},
        "sql": {"procs": ["dbo.p1"], "tables": [], "views": [], "functions": []},
    }

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.summary_xml", return_value=xml_summary), \
         patch("clone_things.service.check_object_exists_and_type", return_value=(False, "", "")), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):
        res = clone_things(
            object=str(xml_file),
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is True
    assert res["mode_seed"] == "xml"
    assert res["not_found_both"] == ["dbo.p1"]


# ============================================================================
# AC-TRG: trigger support
# ============================================================================
def test_ac_trg_1_mode_read_3_trigger_with_dollar(tmp_path):
    trg_ddl = (
        "CREATE TRIGGER [dbo].[C15$000000_trg] ON [dbo].[C15$000000]\n"
        "AFTER INSERT AS BEGIN\n\tSELECT 1\nEND"
    )

    def _exists(parsed, name, schema):
        if name == "C15$000000_trg":
            return True, "TR", "SQL_TRIGGER"
        return False, "", ""

    def _fetch(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        assert obj_type == "TR"
        return trg_ddl

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch), \
         patch("clone_things.service.is_object_encrypted", return_value=False):
        res = clone_things(
            type=1,
            object="dbo.C15$000000_trg",
            project_source="E:\\FBO\\P1",
            mode_recursion="0",
            mode_read=3,
        )

    assert res["success"] is True
    assert len(res["analyzed"]) == 1
    item = res["analyzed"][0]
    assert item["name"] == "dbo.C15$000000_trg"
    assert item["object_type"] == "SQL_TRIGGER"
    assert item["script_style"] == "create"
    assert "CREATE TRIGGER" in item["definition"]
    assert "ALTER TRIGGER" not in item["definition"]
    assert not any("fetch_failed" in w for w in res["warnings"])


def test_ac_trg_3_mode_read_0_trigger_keeps_create(tmp_path):
    sql_file = tmp_path / "out.sql"
    trg_ddl = "CREATE TRIGGER [dbo].[t_trg] ON [dbo].[t] AFTER INSERT AS BEGIN SELECT 1 END"

    def _exists(parsed, name, schema):
        if name == "t_trg":
            return True, "TR", "SQL_TRIGGER"
        return False, "", ""

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists), \
         patch("clone_things.service.fetch_object_script", return_value=trg_ddl), \
         patch("clone_things.service.extract_object_dependencies", return_value=[]), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):
        res = clone_things(
            type=1,
            object="dbo.t_trg",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

    assert res["success"] is True
    assert len(res["pasted"]) == 1
    assert res["pasted"][0]["script_style"] == "create"
    content = sql_file.read_text(encoding="utf-8")
    assert "CREATE TRIGGER" in content
    assert "ALTER TRIGGER" not in content


def test_ac_trg_fetch_object_script_trigger_branch():
    """fetch_object_script nhánh TR → OBJECT_DEFINITION qua execute_query."""
    trg_def = "CREATE TRIGGER [dbo].[x_trg] ON [dbo].[x] AFTER INSERT AS SELECT 1"

    with patch("clone_things.service.get_connection_config") as mconn, \
         patch("clone_things.service.execute_query") as mq:
        mconn.return_value = {"success": True, "parsed": {"database": "d"}}
        mq.return_value = {
            "success": True,
            "result_sets": [{"columns": ["c"], "rows": [[trg_def]]}],
        }
        out, meta = fetch_object_script(
            file_path="E:\\FBO\\P1",
            clean_name="x_trg",
            schema="dbo",
            obj_type="TR",
            type_desc="SQL_TRIGGER",
            wrap_exists=False,
        )

    assert out == trg_def
    assert meta.get("truncated_upstream") is False
    # QUOTENAME trong SQL → tên có $ escape đúng
    sql_arg = mq.call_args[0][1]
    assert "OBJECT_DEFINITION" in sql_arg
    assert "QUOTENAME" in sql_arg


def test_ac_trg_fetch_object_script_encrypted_returns_empty():
    """Trigger encrypted → OBJECT_DEFINITION NULL → '' → caller đẩy encrypt_proc."""
    with patch("clone_things.service.get_connection_config") as mconn, \
         patch("clone_things.service.execute_query") as mq:
        mconn.return_value = {"success": True, "parsed": {"database": "d"}}
        mq.return_value = {
            "success": True,
            "result_sets": [{"columns": ["c"], "rows": [[None]]}],
        }
        out, meta = fetch_object_script(
            file_path="E:\\FBO\\P1",
            clean_name="enc_trg",
            schema="dbo",
            obj_type="TR",
            type_desc="SQL_TRIGGER",
            wrap_exists=False,
        )

    assert out == ""
    assert meta.get("truncated_upstream") is False


def test_trigger_wrap_idempotent_table_with_trigger():
    """wrap_check_exists chạy 2 lần trên script table+trigger → output giống nhau."""
    raw = (
        "CREATE TABLE [dbo].[t1] (id int)\n"
        "GO\n"
        "CREATE TRIGGER [dbo].[t1_trg] ON [dbo].[t1] AFTER INSERT AS BEGIN SELECT 1 END"
    )
    once = wrap_check_exists(raw, "t1", "dbo", "U", "USER_TABLE")
    twice = wrap_check_exists(once, "t1", "dbo", "U", "USER_TABLE")
    assert once == twice
    # Trigger ra batch riêng với guard EXEC
    assert "GO\n" in once
    assert "IF OBJECT_ID(N'[dbo].[t1_trg]', N'TR') IS NULL" in once
    assert "EXEC(N'CREATE TRIGGER" in once
    # Không nested EXEC / duplicate guard
    assert once.count("OBJECT_ID(N'[dbo].[t1_trg]'") == 1


def test_wrap_trigger_ddl_direct_idempotent():
    trg = "CREATE TRIGGER [dbo].[x] ON [dbo].[t] AFTER INSERT AS BEGIN SELECT 1 END"
    once = _wrap_trigger_ddl(trg, "dbo")
    twice = _wrap_trigger_ddl(once, "dbo")
    assert once == twice
    assert twice.count("OBJECT_ID") == 1
