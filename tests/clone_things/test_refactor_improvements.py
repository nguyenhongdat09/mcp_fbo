"""Unit tests for clone_things refactored improvements.

Tests:
- SQL escaping in check_object_exists_and_type & is_object_encrypted
- collect_and_classify_child_deps deduplicated helper
- FBO_*_PATH environment variable overrides in open_editor
- Error response type uniformity across type=0 and type=1
"""

from unittest.mock import patch, MagicMock
from pathlib import Path
import os

from clone_things.db_ops import check_object_exists_and_type, is_object_encrypted
from clone_things.child_deps import collect_and_classify_child_deps
from clone_things.open_editor import _resolve_editor_path
from clone_things.service import clone_things


def test_sql_escaping_in_check_object_exists_and_type():
    """Ensure single quotes in object or schema names are escaped to avoid SQL syntax errors."""
    mock_conn = {"server": "localhost", "database": "test"}
    executed_sqls = []

    def fake_execute(conn, sql, max_rows=5):
        executed_sqls.append(sql)
        return {"success": True, "result_sets": [{"rows": []}]}

    with patch("clone_things.service.execute_query", side_effect=fake_execute):
        exists, otype, odesc = check_object_exists_and_type(
            mock_conn, clean_name="test'obj", schema="db'o"
        )
        assert exists is False
        # Verify SQL has escaped quotes: ''
        assert any("N'test''obj'" in s for s in executed_sqls)
        assert any("N'db''o'" in s for s in executed_sqls)


def test_sql_escaping_in_is_object_encrypted():
    """Ensure single quotes in object names are escaped in encryption queries."""
    mock_conn = {"server": "localhost", "database": "test"}
    executed_sqls = []

    def fake_execute(conn, sql, max_rows=5):
        executed_sqls.append(sql)
        return {"success": True, "result_sets": [{"rows": []}]}

    with patch("clone_things.service.execute_query", side_effect=fake_execute):
        enc = is_object_encrypted(mock_conn, clean_name="my'proc")
        assert enc is False
        assert any("my''proc" in s for s in executed_sqls)


def test_collect_and_classify_child_deps():
    """Ensure collect_and_classify_child_deps correctly partitions deps and updates parent_map."""
    fake_deps = ["dbo.p_child", "dbo.fn_child", "dbo.dmkh", "dbo.v_child", "#temp", "@table"]
    parent_map = {}
    visited = set()
    queue = []

    def fake_extract(**kwargs):
        return fake_deps

    def fake_classify(source_dbs, clean_name, schema, order):
        if "fn_" in clean_name:
            return "func"
        if "v_" in clean_name:
            return "view"
        if "dm" in clean_name:
            return "table"
        return "proc"

    res = collect_and_classify_child_deps(
        project_source="E:\\FBO\\P1",
        item_clean_name="p_parent",
        item_schema="dbo",
        s_type="P",
        s_desc="SQL_STORED_PROCEDURE",
        fetch_db="app",
        source_dbs={"app": {}},
        lookup_order=("app", "sys"),
        full_item_name="dbo.p_parent",
        parent_map=parent_map,
        visited=visited,
        queue=queue,
        recursion=1,
        extract_deps_fn=fake_extract,
        classify_dep_fn=fake_classify,
    )

    assert res.get("child_proc") == "dbo.p_child"
    assert res.get("child_func") == "dbo.fn_child"
    assert res.get("child_table") == "dbo.dmkh"
    assert res.get("child_view") == "dbo.v_child"
    # Temp tables filtered out
    assert "#temp" not in queue
    assert "@table" not in queue
    # recursion=1 enqueued dependencies
    assert "dbo.p_child" in queue
    assert "dbo.fn_child" in queue


def test_resolve_editor_path_env_var(tmp_path):
    """Ensure FBO_*_PATH environment variables override editor paths."""
    fake_cursor = tmp_path / "custom_cursor.cmd"
    fake_cursor.write_text("@echo off")

    with patch.dict(os.environ, {"FBO_CURSOR_PATH": str(fake_cursor)}):
        resolved = _resolve_editor_path("cursor")
        assert resolved == str(fake_cursor)


def test_error_response_type_uniformity():
    """Ensure type key is present in all error responses for both type=0 and type=1."""
    # Type 0 missing source
    r0 = clone_things(object="test", project_source="", project_target="E:\\FBO\\P2", type=0)
    assert r0["success"] is False
    assert r0["type"] == 0

    # Type 0 missing target
    r0_tgt = clone_things(object="test", project_source="E:\\FBO\\P1", project_target="", type=0)
    assert r0_tgt["success"] is False
    assert r0_tgt["type"] == 0

    # Type 1 missing source
    r1 = clone_things(object="test", project_source="", type=1)
    assert r1["success"] is False
    assert r1["type"] == 1

    # Unsupported type
    r_unsup = clone_things(object="test", project_source="E:\\FBO\\P1", type=99)
    assert r_unsup["success"] is False
    assert r_unsup["type"] == 99
