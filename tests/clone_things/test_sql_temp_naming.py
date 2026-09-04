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

