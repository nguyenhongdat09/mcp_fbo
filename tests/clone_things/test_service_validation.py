"""Unit tests for parameter validation (TC-VAL-*)."""

from clone_things.service import clone_things


def test_validation_missing_object():
    res = clone_things(object="", project_source="E:\\FBO\\P1", project_target="E:\\FBO\\P2")
    assert res["success"] is False
    assert res["error_code"] == "invalid_object"


def test_validation_missing_project_source():
    res = clone_things(object="zc_test", project_source="", project_target="E:\\FBO\\P2")
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_source"


def test_validation_missing_project_target():
    res = clone_things(object="zc_test", project_source="E:\\FBO\\P1", project_target="")
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_target"


def test_validation_relative_project_path():
    res = clone_things(object="zc_test", project_source="Relative\\Path", project_target="E:\\FBO\\P2")
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_source"


def test_validation_unsupported_type():
    res = clone_things(object="zc_test", project_source="E:\\FBO\\P1", project_target="E:\\FBO\\P2", type=2)
    assert res["success"] is False
    assert res["error_code"] == "unsupported_type"


def test_validation_invalid_path_to_pasted(tmp_path):
    invalid_txt = tmp_path / "out.txt"
    res = clone_things(
        object="zc_test",
        project_source="E:\\FBO\\P1",
        project_target="E:\\FBO\\P2",
        path_to_pasted=str(invalid_txt),
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_path_to_pasted"
