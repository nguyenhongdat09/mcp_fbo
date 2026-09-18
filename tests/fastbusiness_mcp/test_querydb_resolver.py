"""AC-QDB-* — query_database.file_path qua resolve_any_path (sticky context).

Spec: docs/doc/gemini/GEMINI-mcp-querydb-resolver.md
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from fastbusiness_mcp.mcp_app import query_database_tool
from xml_fbograph.utils.any_path import (
    known_projects,
    reset_sticky_context,
    resolve_any_path,
)

WEB_CONFIG = """<configuration>
  <appSettings>
    <add key="sysDatabaseName" value="PROJ_S" />
  </appSettings>
  <connectionStrings>
    <add name="appConnectionString" connectionString="Data Source=SRV;Initial Catalog=PROJ_A;Uid=sa;Pwd=x" />
  </connectionStrings>
</configuration>
"""


@pytest.fixture(autouse=True)
def _reset():
    reset_sticky_context()
    yield
    reset_sticky_context()


@pytest.fixture
def fbo_project(tmp_path):
    proj = tmp_path / "PROJ"
    ctrl = proj / "App_Data" / "Controllers" / "Grid"
    ctrl.mkdir(parents=True)
    (ctrl / "SOTran.xml").write_text("<grid/>", encoding="utf-8")
    (proj / "Web.config").write_text(WEB_CONFIG, encoding="utf-8")
    return proj


def _captured_file_path(mock_qd) -> str:
    assert mock_qd.called, "query_database phải được gọi sau khi resolve OK"
    return mock_qd.call_args.kwargs["file_path"]


@pytest.fixture
def mock_query_database():
    with patch("fastbusiness_mcp.mcp_app.query_database") as mock_qd:
        mock_qd.return_value = {"success": True, "mode": "search", "objects": []}
        yield mock_qd


def test_ac_qdb_1_relative_after_abs_call(fbo_project, mock_query_database):
    """AC-QDB-1: sau 1 call abs bất kỳ → file_path relative resolve được."""
    xml = fbo_project / "App_Data" / "Controllers" / "Grid" / "SOTran.xml"
    # Seed sticky bằng 1 call abs (đại diện cho read_local_file/search_files trước đó)
    assert resolve_any_path(str(xml)).ok is True

    out = query_database_tool(
        file_path="Grid/SOTran.xml", mode="search", references="fsdSttRecRef"
    )
    assert "[LỖI ĐƯỜNG DẪN]" not in out
    assert Path(_captured_file_path(mock_query_database)).resolve() == xml.resolve()
    assert mock_query_database.call_args.kwargs["mode"] == "search"


def test_ac_qdb_2_relative_web_config(fbo_project, mock_query_database):
    """AC-QDB-2: file_path='Web.config' relative → project_root/Web.config."""
    resolve_any_path(str(fbo_project))  # seed sticky bằng project root abs

    query_database_tool(file_path="Web.config", mode="search", references="x")
    assert (
        Path(_captured_file_path(mock_query_database)).resolve()
        == (fbo_project / "Web.config").resolve()
    )


def test_ac_qdb_3_fresh_no_context():
    """AC-QDB-3: fresh server + relative → JSON no_project_context, không crash."""
    with patch("fastbusiness_mcp.mcp_app.query_database") as mock_qd:
        out = query_database_tool(file_path="Grid/SOTran.xml", mode="search", references="x")
        assert not mock_qd.called

    err = json.loads(out)
    assert err["success"] is False
    assert err["error_code"] == "no_project_context"
    assert "known_projects" in err
    assert "[LỖI ĐƯỜNG DẪN]" not in out


def test_ac_qdb_4_abs_path_no_regress(fbo_project, mock_query_database):
    """AC-QDB-4: abs path như cũ; mọi param/mode truyền y nguyên."""
    xml = fbo_project / "App_Data" / "Controllers" / "Grid" / "SOTran.xml"
    out = query_database_tool(
        file_path=str(xml),
        query="dmkh",
        query_type=0,
        mode="summary",
        db_type="sys",
    )
    assert "[LỖI ĐƯỜNG DẪN]" not in out
    kw = mock_query_database.call_args.kwargs
    assert Path(kw["file_path"]).resolve() == xml.resolve()
    assert kw["query"] == "dmkh"
    assert kw["query_type"] == 0
    assert kw["mode"] == "summary"
    assert kw["db_type"] == "sys"


def test_ac_qdb_5_dir_input(fbo_project, mock_query_database):
    """AC-QDB-5: file_path là dir (project root abs) → resolve + tìm được Web.config."""
    query_database_tool(file_path=str(fbo_project), mode="search", references="x")
    assert Path(_captured_file_path(mock_query_database)).resolve() == fbo_project.resolve()

    # End-to-end: find_connection_by_path nhận dir vẫn mò được Web.config
    from find_connect_by_path import find_connection_by_path

    conn = find_connection_by_path(str(fbo_project), "app")
    assert conn["success"] is True
    assert conn["parsed"]["database"] == "PROJ_A"


def test_ac_qdb_6_sticky_fed(fbo_project, mock_query_database):
    """AC-QDB-6: resolve thành công → sticky _PROJECT_ROOTS được nuôi."""
    xml = fbo_project / "App_Data" / "Controllers" / "Grid" / "SOTran.xml"
    query_database_tool(file_path=str(xml), mode="search", references="x")

    roots = [r.lower() for r in known_projects()]
    assert str(fbo_project).lower() in roots

    # Tool khác (read_local_file…) dùng chung resolver → relative ăn context
    res = resolve_any_path("Grid/SOTran.xml")
    assert res.ok is True
    assert Path(res.abs_path).resolve() == xml.resolve()


def test_ac_qdb_extra_path_not_found(fbo_project):
    """Path không tồn tại → JSON path_not_found + tried[]."""
    resolve_any_path(str(fbo_project))  # có context nhưng rel path không tồn tại
    out = query_database_tool(file_path="Grid/KhongCo.xml", mode="search", references="x")
    err = json.loads(out)
    assert err["success"] is False
    assert err["error_code"] == "path_not_found"
    assert err["tried"]
