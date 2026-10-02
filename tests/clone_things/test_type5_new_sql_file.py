"""Tests cho clone_things type=5 — tạo file .sql temp rỗng (UTF-8 BOM)."""

from pathlib import Path

from clone_things.service import clone_things


def _cfg(tmp_path):
    return {"clone_things": {"sql_temp_folder": str(tmp_path),
                             "open_file": False}}


def test_type5_creates_empty_bom_file(tmp_path):
    res = clone_things(
        type=5,
        project_source=r"E:\FBO\SHOWA\FBISP242",
        open_file=False,
        config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert res["type"] == 5
    assert res["mode"] == "new_sql_file"
    p = Path(res["path_to_pasted"])
    assert p.parent == tmp_path
    assert p.name == "showa_fbisp242.sql"
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")


def test_type5_incremental_suffix(tmp_path):
    res1 = clone_things(type=5, project_source=r"E:\FBO\SHOWA\FBISP242",
                        open_file=False, config=_cfg(tmp_path))
    res2 = clone_things(type=5, project_source=r"E:\FBO\SHOWA\FBISP242",
                        open_file=False, config=_cfg(tmp_path))
    assert Path(res1["path_to_pasted"]).name == "showa_fbisp242.sql"
    assert Path(res2["path_to_pasted"]).name == "showa_fbisp242 (2).sql"


def test_type5_object_not_required(tmp_path):
    """type=5 không bắt buộc object — không phải invalid_object."""
    res = clone_things(
        type=5, object="",
        project_source=r"E:\FBO\VLOTUS\SP228",
        open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert Path(res["path_to_pasted"]).name == "vlotus_sp228.sql"


def test_type5_missing_project_source(tmp_path):
    res = clone_things(type=5, project_source="",
                       open_file=False, config=_cfg(tmp_path))
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_source"


def test_type5_relative_project_source(tmp_path):
    res = clone_things(type=5, project_source="relative\\path",
                       open_file=False, config=_cfg(tmp_path))
    assert res["success"] is False
    assert res["error_code"] == "invalid_project_source"


def test_type5_explicit_path_to_pasted(tmp_path):
    """path_to_pasted trỏ file chưa tồn tại → tạo file đó kèm BOM."""
    target = tmp_path / "my_script.sql"
    res = clone_things(
        type=5,
        project_source=r"E:\FBO\SHOWA\FBISP242",
        path_to_pasted=str(target),
        open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert Path(res["path_to_pasted"]) == target
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")


def test_type5_existing_file_untouched(tmp_path):
    """path_to_pasted trỏ file đã có nội dung → giữ nguyên, không BOM-ify."""
    target = tmp_path / "existing.sql"
    target.write_text("SELECT 1", encoding="utf-8")
    res = clone_things(
        type=5,
        project_source=r"E:\FBO\SHOWA\FBISP242",
        path_to_pasted=str(target),
        open_file=False, config=_cfg(tmp_path),
    )
    assert res["success"] is True
    assert target.read_text(encoding="utf-8") == "SELECT 1"


def test_type5_bad_sql_temp_folder(tmp_path):
    cfg = {"clone_things": {"sql_temp_folder": str(tmp_path / "not_exist"),
                            "open_file": False}}
    res = clone_things(type=5, project_source=r"E:\FBO\SHOWA\FBISP242",
                       open_file=False, config=cfg)
    assert res["success"] is False
    assert res["error_code"] == "sql_temp_folder_not_configured"
