"""Unit tests for SQL temp file naming and creation (TC-FILE-*)."""

from pathlib import Path
from clone_things.file_manager import (
    sanitize_filename_base,
    create_sql_temp_file,
    sql_temp_base_name_from_project,
)


def test_sanitize_filename_base():
    assert sanitize_filename_base("zc_example_report") == "zc_example_report"
    assert sanitize_filename_base("dbo.zc_example_report") == "zc_example_report"
    assert sanitize_filename_base("dbo.[zc_My Proc]") == "zc_my_proc"
    assert sanitize_filename_base("SVTran.xml") == "svtran"
    assert sanitize_filename_base("some_script.sql") == "some_script"
    assert sanitize_filename_base("") == "temp"


def test_sql_temp_base_name_from_project_unc_xml():
    """Parity NewSqlTemp group.label: VLOTUS/SP228 → vlotus_sp228 (không lấy stem XML)."""
    src = r"\\172.168.5.14\CustomerPro\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\zcbkctnb.xml"
    assert sql_temp_base_name_from_project(src) == "vlotus_sp228"


def test_sql_temp_base_name_from_project_root():
    assert sql_temp_base_name_from_project(r"E:\FBO\SHOWA\FBISP242") == "showa_fbisp242"


def test_create_sql_temp_file(tmp_path):
    f1 = create_sql_temp_file("vlotus_sp228", str(tmp_path))
    assert Path(f1).name == "vlotus_sp228.sql"
    assert Path(f1).exists()

    f2 = create_sql_temp_file("vlotus_sp228", str(tmp_path))
    assert Path(f2).name == "vlotus_sp228 (2).sql"
    assert Path(f2).exists()

    f3 = create_sql_temp_file("vlotus_sp228", str(tmp_path))
    assert Path(f3).name == "vlotus_sp228 (3).sql"
    assert Path(f3).exists()


def test_resolve_output_file_prefers_target(tmp_path):
    from clone_things.file_manager import resolve_output_file

    config = {"clone_things": {"sql_temp_folder": str(tmp_path)}}
    out_file, err = resolve_output_file(
        "",
        "zc_test",
        config,
        project_target=r"E:\FBO\SHOWA\FBISP242",
        project_source=r"E:\FBO\VLOTUS\SP228",
    )
    assert err is None
    assert Path(out_file).name == "showa_fbisp242.sql"


def test_resolve_output_file_empty_config():
    from clone_things.file_manager import resolve_output_file

    config = {"clone_things": {"sql_temp_folder": ""}}
    out_file, err = resolve_output_file(
        "",
        "zc_test_empty",
        config,
        project_target=r"E:\FBO\SHOWA\FBISP242",
        project_source=r"E:\FBO\VLOTUS\SP228",
    )
    assert err is None
    out_path = Path(out_file)
    assert out_path.exists()
    assert out_path.parent.name.lower() == "scripts"
    # Dọn dẹp file test
    try:
        out_path.unlink()
    except Exception:
        pass


def test_is_antigravity_ide(monkeypatch):
    from clone_things.file_manager import is_antigravity_ide

    # Override MCP_CLIENT = antigravity
    monkeypatch.setenv("MCP_CLIENT", "antigravity")
    assert is_antigravity_ide() is True

    # Override MCP_CLIENT = cursor
    monkeypatch.setenv("MCP_CLIENT", "cursor")
    assert is_antigravity_ide() is False

    monkeypatch.delenv("MCP_CLIENT", raising=False)
    monkeypatch.setenv("TEST_ANTIGRAVITY", "1")
    monkeypatch.setenv("ANTIGRAVITY_AGENT", "1")
    assert is_antigravity_ide() is True


def test_resolve_sql_temp_folder_cursor():
    from clone_things.file_manager import resolve_sql_temp_folder

    # Khi không phải Antigravity -> trả về nguyên folder_path
    res = resolve_sql_temp_folder(r"E:\SQL Temp", is_antigravity=False)
    assert res == r"E:\SQL Temp"


def test_resolve_sql_temp_folder_antigravity(tmp_path):
    from clone_things.file_manager import resolve_sql_temp_folder

    skills_root = tmp_path / "skills"
    # Giả lập setting là 'E:\SQL Temp'
    res = resolve_sql_temp_folder(
        r"E:\SQL Temp",
        is_antigravity=True,
        custom_skills_root=str(skills_root),
    )
    expected_dir = skills_root / "SQL Temp"
    assert Path(res) == expected_dir
    assert expected_dir.exists()
    assert expected_dir.is_dir()

    # Gọi lại lần 2 khi folder đã tồn tại -> vẫn trỏ đúng và không lỗi
    res2 = resolve_sql_temp_folder(
        r"E:/SQL Temp",
        is_antigravity=True,
        custom_skills_root=str(skills_root),
    )
    assert Path(res2) == expected_dir


def test_resolve_output_file_antigravity_skills(tmp_path):
    from clone_things.file_manager import resolve_output_file

    skills_root = tmp_path / "skills"
    config = {
        "clone_things": {
            "sql_temp_folder": r"E:\SQL Temp",
        }
    }

    # Tạo file đầu tiên
    f1, err1 = resolve_output_file(
        "",
        "zc_test",
        config,
        project_target=r"E:\FBO\SHOWA\FBISP242",
        is_antigravity=True,
        custom_skills_root=str(skills_root),
    )
    assert err1 is None
    p1 = Path(f1)
    assert p1.parent == skills_root / "SQL Temp"
    assert p1.name == "showa_fbisp242.sql"
    assert p1.exists()

    # Tạo file thứ 2 -> tự động sinh (2).sql trong cùng folder SQL Temp
    f2, err2 = resolve_output_file(
        "",
        "zc_test",
        config,
        project_target=r"E:\FBO\SHOWA\FBISP242",
        is_antigravity=True,
        custom_skills_root=str(skills_root),
    )
    assert err2 is None
    p2 = Path(f2)
    assert p2.parent == skills_root / "SQL Temp"
    assert p2.name == "showa_fbisp242 (2).sql"
    assert p2.exists()


