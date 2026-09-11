"""Unit tests for encrypted object handling and UTF-8 BOM elimination (FIX-clone_things-encrypted-and-sql-bom.md)."""

from pathlib import Path
from unittest.mock import patch

from clone_things.file_manager import (
    _read_sql_file,
    _sql_file_body,
    append_script_block,
    ensure_use_db_sections,
)
from clone_things.service import clone_things, is_object_encrypted, is_system_noise_name


def _conn_side_effect(file_path, db_type="app"):
    db_name = "test_sys_db" if db_type == "sys" else "test_app_db"
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type, "database": db_name},
    }


# ============================================================================
# AC-ENC-01: Exists + IsEncrypted=1 + definition null -> encrypt_proc, not not_found
# ============================================================================
def test_encrypt_proc_when_is_encrypted(tmp_path):
    sql_file = tmp_path / "out_enc01.sql"

    def _exists_side(parsed, name, schema):
        if name == "FastBusiness$Partition$Execute":
            return True, "P", "SQL_STORED_PROCEDURE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        # Definition null/empty due to encryption
        return ""

    def _is_enc_side(parsed_conn, clean_name, schema="dbo"):
        if clean_name == "FastBusiness$Partition$Execute":
            return True
        return False

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.is_object_encrypted", side_effect=_is_enc_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.FastBusiness$Partition$Execute",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            open_file=False,
        )

        assert res["success"] is True
        assert len(res["pasted"]) == 0
        assert "dbo.FastBusiness$Partition$Execute" in res["encrypt_proc"]
        assert "dbo.FastBusiness$Partition$Execute" not in res["not_found_source"]
        assert not any("fetch_failed: dbo.FastBusiness$Partition$Execute" in w for w in res["warnings"])
        assert "mã hóa" in res["agent_message"] or "encrypted" in res["agent_message"]


# ============================================================================
# AC-ENC-02: Parent pasted; child encrypt in child_proc and encrypt_proc, sp_executesql excluded
# ============================================================================
def test_parent_pasted_child_encrypted_and_sp_executesql_excluded(tmp_path):
    sql_file = tmp_path / "out_enc02.sql"

    def _exists_side(parsed, name, schema):
        if name == "zc_sctnt":
            return True, "P", "SQL_STORED_PROCEDURE"
        elif name == "FastBusiness$Partition$Execute":
            return True, "P", "SQL_STORED_PROCEDURE"
        return False, "", ""

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        if clean_name == "zc_sctnt":
            return "CREATE PROCEDURE dbo.zc_sctnt AS SELECT 1"
        return ""

    def _extract_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
        if clean_name == "zc_sctnt":
            return ["dbo.FastBusiness$Partition$Execute", "dbo.sp_executesql"]
        return []

    def _is_enc_side(parsed_conn, clean_name, schema="dbo"):
        if clean_name == "FastBusiness$Partition$Execute":
            return True
        return False

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.extract_object_dependencies", side_effect=_extract_side), \
         patch("clone_things.service.is_object_encrypted", side_effect=_is_enc_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.zc_sctnt",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="1",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        # Parent zc_sctnt is pasted
        assert len(res["pasted"]) == 1
        parent_item = res["pasted"][0]
        assert parent_item["name"] == "dbo.zc_sctnt"
        assert "dbo.FastBusiness$Partition$Execute" in parent_item.get("child_proc", "")
        # sp_executesql should NOT be in child_proc (system noise)
        assert "sp_executesql" not in parent_item.get("child_proc", "")

        # Child is in encrypt_proc
        assert "dbo.FastBusiness$Partition$Execute" in res["encrypt_proc"]
        assert "dbo.FastBusiness$Partition$Execute" not in res["not_found_source"]

        # sp_executesql should NOT be in not_found_source or encrypt_proc
        assert "dbo.sp_executesql" not in res["not_found_source"]
        assert "dbo.sp_executesql" not in res["encrypt_proc"]

        # File should contain ALTER block for parent, but NOT for child
        content = sql_file.read_text(encoding="utf-8")
        assert "ALTER PROCEDURE dbo.zc_sctnt" in content
        assert "ALTER PROCEDURE dbo.FastBusiness$Partition$Execute" not in content


# ============================================================================
# AC-ENC-03: Truly missing object -> not_found_source only
# ============================================================================
def test_not_found_when_missing(tmp_path):
    sql_file = tmp_path / "out_enc03.sql"

    def _exists_side(parsed, name, schema):
        return False, "", ""

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.zc_non_existent",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            open_file=False,
        )

        assert res["success"] is True
        assert "dbo.zc_non_existent" in res["not_found_source"]
        assert "dbo.zc_non_existent" not in res["encrypt_proc"]


# ============================================================================
# AC-BOM-01: Pre-created file with UTF-8 BOM stripped on ensure and append
# ============================================================================
def test_strip_utf8_bom_on_ensure_and_append(tmp_path):
    sql_file = tmp_path / "bom_test.sql"

    # Case 1: File only has BOM
    sql_file.write_bytes(b"\xef\xbb\xbf")
    ensure_use_db_sections(str(sql_file), app_db_name="APP_DB", sys_db_name="SYS_DB")
    raw_bytes = sql_file.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf")
    assert b"\xef\xbb\xbf" not in raw_bytes
    text = sql_file.read_text(encoding="utf-8")
    assert "\ufeff" not in text

    # Case 2: Append script block
    line_start, line_end = append_script_block(
        file_path=str(sql_file),
        script="ALTER PROCEDURE dbo.zc_test AS SELECT 1",
        object_name="dbo.zc_test",
        object_type="SQL_STORED_PROCEDURE",
        db="app",
        app_db_name="APP_DB",
        sys_db_name="SYS_DB",
        header_tag="paste_edit",
    )
    raw_bytes_after = sql_file.read_bytes()
    assert b"\xef\xbb\xbf" not in raw_bytes_after
    text_after = sql_file.read_text(encoding="utf-8")
    assert "\ufeff" not in text_after
    # No BOM between GO and -- clone_things
    assert "GO\n\n-- clone_things type=1: dbo.zc_test" in text_after


# ============================================================================
# AC-BOM-02: Pre-created BOM + newline -> clone_things removes BOM, no GOUSE
# ============================================================================
def test_bom_precreated_in_clone_things(tmp_path):
    sql_file = tmp_path / "case_proc_r1.sql"
    # Pre-populate with UTF-8 BOM + whitespace
    sql_file.write_bytes(b"\xef\xbb\xbf\n\n")

    def _exists_side(parsed, name, schema):
        return True, "P", "SQL_STORED_PROCEDURE"

    def _fetch_side(file_path, clean_name, schema, obj_type, type_desc, db_type="app", wrap_exists=False):
        return f"CREATE PROCEDURE dbo.{clean_name} AS SELECT 1"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_side), \
         patch("clone_things.service.fetch_object_script", side_effect=_fetch_side), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):

        res = clone_things(
            type=1,
            object="dbo.zc_proc1",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            mode_recursion="0",
            mode_read=0,
            open_file=False,
        )

        assert res["success"] is True
        raw_bytes = sql_file.read_bytes()
        assert b"\xef\xbb\xbf" not in raw_bytes
        text = sql_file.read_text(encoding="utf-8")
        assert "\ufeff" not in text
        assert "GOUSE" not in text


# ============================================================================
# Unit tests for helpers _read_sql_file, _sql_file_body, is_system_noise_name
# ============================================================================
def test_helpers_bom_and_noise(tmp_path):
    f = tmp_path / "temp_bom.sql"
    f.write_bytes(b"\xef\xbb\xbfSELECT 1\n")
    assert _read_sql_file(f) == "SELECT 1\n"

    # _sql_file_body
    assert _sql_file_body("\ufeff   \n") == ""
    assert _sql_file_body("\ufeffSELECT 1") == "SELECT 1"

    # is_system_noise_name
    assert is_system_noise_name("sp_executesql") is True
    assert is_system_noise_name("sp_help") is True
    assert is_system_noise_name("xp_cmdshell") is True
    assert is_system_noise_name("sys.objects") is True
    assert is_system_noise_name("tempdb") is True
    assert is_system_noise_name("master") is True
    assert is_system_noise_name("FastBusiness$Partition$Execute") is False
    assert is_system_noise_name("zc_sctnt") is False
    assert is_system_noise_name("dmkh") is False
