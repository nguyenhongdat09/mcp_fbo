"""Unit tests for parameter validation in compare_things service."""

import pytest
from compare_things import compare_things


def test_tc_api_01_invalid_kind():
    res = compare_things(kind="invalid_kind_xyz")
    assert res["success"] is False
    assert res["error_code"] == "invalid_kind"
    assert "Chỉ chấp nhận" in res["message"]


def test_invalid_mode():
    res = compare_things(kind="file", mode="super_detailed")
    assert res["success"] is False
    assert res["error_code"] == "invalid_mode"


def test_invalid_limit():
    res = compare_things(kind="file", file_a="a", file_b="b", max_diff_lines=0)
    assert res["success"] is False
    assert res["error_code"] == "invalid_limit"


def test_tc_api_02_sql_missing_project():
    res = compare_things(kind="sql", project_source="", project_target="E:\\Target")
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_source"

    res2 = compare_things(kind="sql", project_source="E:\\Source", project_target="")
    assert res2["success"] is False
    assert res2["error_code"] == "invalid_project_target"


def test_sql_missing_object_and_seed():
    res = compare_things(kind="sql", project_source="E:\\Source", project_target="E:\\Target", object="", seed="")
    assert res["success"] is False
    assert res["error_code"] == "invalid_object_or_seed"


def test_sql_invalid_db_type():
    res = compare_things(
        kind="sql",
        project_source="E:\\Source",
        project_target="E:\\Target",
        object="ProcA",
        db_type="invalid_db",
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_db_type"


def test_tc_api_04_import_architecture():
    import compare_things
    from compare_things import compare_things as svc_fn
    from compare_things.formatter import format_compare_result
    from compare_things.models import Hunk, FileMeta, ContentDiff
    from compare_things.text_normalize import normalize_text_lines
    from compare_things.meta_stat import get_file_meta_and_bytes
    from compare_things.line_diff import build_line_diff
    from compare_things.file_compare import compare_files

    assert callable(svc_fn)
    assert callable(format_compare_result)
