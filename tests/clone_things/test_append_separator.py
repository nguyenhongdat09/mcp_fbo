"""Unit tests for script appending with GO separator and not_found summary."""

from pathlib import Path
from clone_things.file_manager import append_script_block, append_not_found_summary


def test_append_script_block_with_go_separator(tmp_path):
    sql_file = tmp_path / "output.sql"
    sql_file.write_text("", encoding="utf-8")

    # Block 1
    script1 = "CREATE PROCEDURE dbo.p1 AS SELECT 1"
    append_script_block(str(sql_file), script1, "dbo.p1", "PROCEDURE")

    content1 = sql_file.read_text(encoding="utf-8")
    assert "-- clone_things: dbo.p1 | PROCEDURE | from source" in content1
    assert "CREATE PROCEDURE dbo.p1 AS SELECT 1" in content1
    assert content1.endswith("GO\n")

    # Block 2
    script2 = "CREATE PROCEDURE dbo.p2 AS SELECT 2"
    append_script_block(str(sql_file), script2, "dbo.p2", "PROCEDURE")

    content2 = sql_file.read_text(encoding="utf-8")
    assert "GO\n\n-- clone_things: dbo.p2 | PROCEDURE | from source\nCREATE PROCEDURE dbo.p2 AS SELECT 2\nGO\n" in content2


def test_append_not_found_summary(tmp_path):
    sql_file = tmp_path / "output.sql"
    sql_file.write_text("CREATE TABLE t1(id int)\nGO\n", encoding="utf-8")

    append_not_found_summary(str(sql_file), ["dbo.funcGhost", "dbo.procMissing"])

    content = sql_file.read_text(encoding="utf-8")
    assert content.endswith("-- not found in 2 project: dbo.funcGhost, dbo.procMissing\n")
