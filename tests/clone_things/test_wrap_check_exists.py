"""Unit tests for wrap_check_exists and duplicate block cleanup."""

from clone_things.service import wrap_check_exists
from clone_things.file_manager import append_script_block


def test_wrap_check_exists_table():
    raw_ddl = "CREATE TABLE syscheckfields(\n\tid int\n)\nALTER TABLE syscheckfields ADD CONSTRAINT PK PRIMARY KEY(id)"
    wrapped = wrap_check_exists(raw_ddl, "syscheckfields", "dbo", "U", "USER_TABLE")
    assert wrapped.startswith("IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[syscheckfields]') AND type = N'U')")
    assert "BEGIN\nCREATE TABLE syscheckfields" in wrapped
    assert wrapped.endswith("\nEND")


def test_wrap_check_exists_procedure():
    raw_proc = "CREATE PROCEDURE dbo.p1 AS SELECT 1"
    wrapped = wrap_check_exists(raw_proc, "p1", "dbo", "P", "SQL_STORED_PROCEDURE")
    assert wrapped.startswith("IF OBJECT_ID(N'[dbo].[p1]', N'P') IS NOT NULL\n    DROP PROCEDURE [dbo].[p1]\nGO\n")
    assert "CREATE PROCEDURE dbo.p1 AS SELECT 1" in wrapped


def test_wrap_check_exists_function():
    raw_func = "CREATE FUNCTION dbo.fn1() RETURNS INT AS BEGIN RETURN 1 END"
    wrapped = wrap_check_exists(raw_func, "fn1", "dbo", "FN", "SQL_SCALAR_FUNCTION")
    assert wrapped.startswith("IF OBJECT_ID(N'[dbo].[fn1]') IS NOT NULL\n    DROP FUNCTION [dbo].[fn1]\nGO\n")
    assert "CREATE FUNCTION dbo.fn1()" in wrapped


def test_wrap_check_exists_view():
    raw_view = "CREATE VIEW dbo.v1 AS SELECT 1 AS id"
    wrapped = wrap_check_exists(raw_view, "v1", "dbo", "V", "VIEW")
    assert wrapped.startswith("IF OBJECT_ID(N'[dbo].[v1]', N'V') IS NOT NULL\n    DROP VIEW [dbo].[v1]\nGO\n")
    assert "CREATE VIEW dbo.v1 AS SELECT 1" in wrapped


def test_wrap_check_exists_idempotent():
    raw_ddl = "IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[t]') AND type = N'U')\nBEGIN\nCREATE TABLE t(id int)\nEND"
    wrapped = wrap_check_exists(raw_ddl, "t", "dbo", "U", "USER_TABLE")
    assert wrapped == raw_ddl


def test_append_script_block_deduplicates_same_object(tmp_path):
    sql_file = tmp_path / "out_dedup.sql"
    sql_file.write_text("", encoding="utf-8")

    # Append first time
    append_script_block(
        str(sql_file),
        "CREATE TABLE syscheckfields(v1 int)",
        "dbo.syscheckfields",
        "USER_TABLE",
        db="sys",
        app_db_name="App_A",
        sys_db_name="Sys_S",
    )

    # Append second time with updated script
    append_script_block(
        str(sql_file),
        "CREATE TABLE syscheckfields(v2 int)",
        "dbo.syscheckfields",
        "USER_TABLE",
        db="sys",
        app_db_name="App_A",
        sys_db_name="Sys_S",
    )

    content = sql_file.read_text(encoding="utf-8")
    assert content.count("-- clone_things: dbo.syscheckfields") == 1
    assert "v2 int" in content
    assert "v1 int" not in content
