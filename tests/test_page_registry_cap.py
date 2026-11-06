"""read_local_file không dump cả Page*.xml (program SP30+) — cap nhỏ + hint search_files."""

from pathlib import Path

from xml_fbograph.mcp_tools import (
    _PAGE_REGISTRY_CAP_CHARS,
    _is_page_registry,
    mcp_read_local_file,
)

LINE = '<page id="p{n}" v="Trang" e="Page" controller="Ctrl{n}" template="Page.001"/>\n'


def _mk(tmp_path: Path) -> Path:
    proj = tmp_path / "FBISP30"
    meta = proj / "App_Data" / "Metadata"
    meta.mkdir(parents=True)
    (meta / "Page.001.xml").write_text(
        "".join(LINE.format(n=i) for i in range(2000)), encoding="utf-8"
    )
    other = proj / "App_Data" / "Controllers" / "Report"
    other.mkdir(parents=True)
    (other / "Big.xml").write_text("<r>" + "x" * 20_000 + "</r>", encoding="utf-8")
    return proj


def test_is_page_registry(tmp_path):
    proj = _mk(tmp_path)
    assert _is_page_registry(proj / "App_Data" / "Metadata" / "Page.001.xml")
    assert not _is_page_registry(proj / "App_Data" / "Controllers" / "Report" / "Big.xml")


def test_full_read_of_page_registry_is_capped_with_hint(tmp_path):
    proj = _mk(tmp_path)
    out = mcp_read_local_file(
        str(proj / "App_Data" / "Metadata" / "Page.001.xml"), read_option=1
    )
    assert "[TRUNCATED]" in out
    assert "search_files" in out
    assert len(out) < _PAGE_REGISTRY_CAP_CHARS + 2000


def test_line_range_of_page_registry_still_works(tmp_path):
    proj = _mk(tmp_path)
    out = mcp_read_local_file(
        str(proj / "App_Data" / "Metadata" / "Page.001.xml"),
        read_option=1, start_line=5, end_line=6,
    )
    assert "Ctrl4" in out and "TRUNCATED" not in out


def test_other_files_keep_normal_cap(tmp_path):
    proj = _mk(tmp_path)
    out = mcp_read_local_file(
        str(proj / "App_Data" / "Controllers" / "Report" / "Big.xml"), read_option=1
    )
    assert "TRUNCATED" not in out
