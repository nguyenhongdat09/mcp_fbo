"""Unit tests cho sql_temp_source manifest (.fbo_sql_temp_source.json).

Manifest là kênh chung giữa fastbusiness-mcp (writer) và extension
fbo-autocomplete (reader) — extension không đọc được globalState từ ngoài.
"""
import json
from pathlib import Path

from clone_things.sql_temp_source import (
    MANIFEST_NAME,
    group_label_from_project,
    remember_sql_temp_source,
)


def test_group_label_from_project_parity_extension():
    """Parity AppDataPathHelper.getGroupName + .toUpperCase()."""
    assert (
        group_label_from_project(
            r"\\172.168.5.14\CustomerPro\FBI\ANNHIEN\FBISP24"
        )
        == "ANNHIEN - FBISP24"
    )
    assert group_label_from_project(r"E:\FBO\VLOTUS\SP228") == "VLOTUS - SP228"
    # Path tới file trong project -> cắt App_Data trước khi lấy 2 segment cuối
    assert (
        group_label_from_project(
            r"\\172.168.5.14\CustomerPro\FBO\VLOTUS\SP228\App_Data\Controllers\Dir\x.xml"
        )
        == "VLOTUS - SP228"
    )
    assert group_label_from_project("") == ""


def test_remember_sql_temp_source_writes_manifest(tmp_path):
    f = tmp_path / "annhien_-_fbisp24.sql"
    f.write_text("\ufeffSELECT 1", encoding="utf-8")

    ok = remember_sql_temp_source(
        str(f),
        object_name="zc_test",
        project_path=r"E:\FBO\ANNHIEN\FBISP24",
    )
    assert ok is True

    manifest = tmp_path / MANIFEST_NAME
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))

    key = str(f.resolve()).lower()
    assert key in data
    entry = data[key]
    assert entry["group_label"] == "ANNHIEN - FBISP24"
    assert entry["db_type"] == "app"
    assert entry["object_name"] == "zc_test"
    assert "created_at" in entry


def test_remember_sql_temp_source_upsert_and_second_file(tmp_path):
    f1 = tmp_path / "a.sql"
    f1.write_text("\ufeff", encoding="utf-8")
    f2 = tmp_path / "b.sql"
    f2.write_text("\ufeff", encoding="utf-8")

    assert remember_sql_temp_source(str(f1), "o1", r"E:\FBO\VLOTUS\SP228")
    assert remember_sql_temp_source(str(f2), "o2", r"E:\FBO\VLOTUS\SP228")

    data = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[str(f1.resolve()).lower()]["object_name"] == "o1"
    assert data[str(f2.resolve()).lower()]["object_name"] == "o2"


def test_remember_sql_temp_source_no_project_no_write(tmp_path):
    f = tmp_path / "x.sql"
    f.write_text("\ufeff", encoding="utf-8")
    assert remember_sql_temp_source(str(f), "o", "") is False
    assert not (tmp_path / MANIFEST_NAME).exists()


def test_resolve_output_file_writes_manifest(tmp_path):
    """resolve_output_file auto-record nguồn cho file temp."""
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

    manifest = tmp_path / MANIFEST_NAME
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entry = data[str(Path(out_file).resolve()).lower()]
    # target thắng (giống naming_base)
    assert entry["group_label"] == "SHOWA - FBISP242"


def test_resolve_output_file_path_to_pasted_writes_manifest(tmp_path):
    """Nhánh path_to_pasted cũng ghi manifest (file sẵn có)."""
    from clone_things.file_manager import resolve_output_file

    existing = tmp_path / "existing.sql"
    existing.write_text("\ufeffSELECT 1", encoding="utf-8")
    config = {"clone_things": {"sql_temp_folder": str(tmp_path)}}
    out_file, err = resolve_output_file(
        str(existing),
        "zc_test",
        config,
        project_source=r"E:\FBO\VLOTUS\SP228",
    )
    assert err is None

    data = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    entry = data[str(existing.resolve()).lower()]
    assert entry["group_label"] == "VLOTUS - SP228"
