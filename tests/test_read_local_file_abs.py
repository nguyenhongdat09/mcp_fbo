"""Unit tests for read_local_file tool absolute path auto-resolution.

Covers AC-RLF-1 to AC-RLF-3 from docs/doc/gemini/GEMINI-mcp-agent-gaps.md.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from xml_fbograph.mcp_tools import mcp_read_local_file


@pytest.fixture
def fbo_project(tmp_path):
    proj = tmp_path / "FBO_PROJ"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "Web.config").write_text("<configuration/>", encoding="utf-8")

    # Main folder
    main_dir = proj / "Main"
    main_dir.mkdir(parents=True, exist_ok=True)
    aspx_file = main_dir / "zccnslkdhtpnc.aspx"
    aspx_file.write_text("<%@ Page Language=\"C#\" %><div>Hello FBO</div>", encoding="utf-8")

    # App_Data/Controllers/Dir
    ctrl_dir = proj / "App_Data" / "Controllers" / "Dir"
    ctrl_dir.mkdir(parents=True, exist_ok=True)
    xml_file = ctrl_dir / "TestDir.xml"
    xml_file.write_text("<dir id=\"TestDir\"><fields><field name=\"ma_kh\"/></fields></dir>", encoding="utf-8")

    return proj, aspx_file, xml_file


def test_ac_rlf_1_abs_path_without_reference_file(fbo_project):
    """AC-RLF-1: Abs path khong can reference_file -> doc OK."""
    _, aspx_file, _ = fbo_project
    content = mcp_read_local_file(
        file_path=str(aspx_file),
        reference_file="",
        read_option=1,
    )
    assert "Hello FBO" in content
    assert "Loi:" not in content


def test_ac_rlf_2_relative_path_missing_reference_file(fbo_project):
    """AC-RLF-2: Relative path thieu reference_file -> bao loi reference_file_required."""
    content = mcp_read_local_file(
        file_path="Filter/x.xml",
        reference_file="",
        read_option=1,
    )
    assert "reference_file_required" in content
    assert "Loi:" in content


def test_ac_rlf_3_no_regress_read_options(fbo_project):
    """AC-RLF-3: Khong regress cac options 1, 2, 3."""
    _, _, xml_file = fbo_project
    # Option 1: raw
    raw = mcp_read_local_file(file_path=str(xml_file), reference_file="", read_option=1)
    assert "<dir id=\"TestDir\">" in raw

    # Option 2: flat
    flat = mcp_read_local_file(file_path=str(xml_file), reference_file="", read_option=2)
    assert "TestDir" in flat

    # Option 3: summary_xml (controller .xml)
    summary = mcp_read_local_file(file_path=str(xml_file), reference_file="", read_option=3)
    assert "TestDir" in summary or "{" in summary
