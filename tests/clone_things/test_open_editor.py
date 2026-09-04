"""Unit tests for open_editor helper (TC-FILE-*)."""

from pathlib import Path
from unittest.mock import patch
from clone_things.open_editor import open_file_for_user, _spawn_editor


def test_open_file_disabled(tmp_path):
    f = tmp_path / "x.sql"
    f.write_text("--", encoding="utf-8")
    ok, warn = open_file_for_user(str(f), open_file=False)
    assert ok is True
    assert warn is None

    ok, warn = open_file_for_user(str(f), open_editor_cmd="none")
    assert ok is True
    assert warn is None


def test_open_file_spawn_success(tmp_path):
    f = tmp_path / "vlotus_sp228 (4).sql"
    f.write_text("--", encoding="utf-8")
    with patch("clone_things.open_editor._resolve_editor_path", return_value="C:\\dummy\\cursor.cmd"), \
         patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = None
        ok, warn = open_file_for_user(str(f), open_editor_cmd="cursor")
        assert ok is True
        assert warn is None
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        # .cmd must go through cmd.exe /c; path with spaces preserved as own arg
        assert args[0].lower() == "cmd.exe"
        assert args[1].lower() == "/c"
        assert args[2].endswith("cursor.cmd")
        assert args[3] == str(f.resolve())


def test_spawn_editor_quotes_spaces_via_argv(tmp_path):
    f = tmp_path / "SQL Temp"
    f.mkdir()
    sql = f / "vlotus_sp228 (4).sql"
    sql.write_text("GO\n", encoding="utf-8")
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = None
        assert _spawn_editor(r"E:\cursor\resources\app\bin\cursor.CMD", str(sql)) is True
        args = mock_popen.call_args[0][0]
        assert " " in args[3] or "(" in args[3]


def test_open_file_fallback_soft_fail(tmp_path):
    f = tmp_path / "x.sql"
    f.write_text("--", encoding="utf-8")
    with patch("clone_things.open_editor._resolve_editor_path", return_value=None), \
         patch("os.startfile", side_effect=OSError("No association")):
        ok, warn = open_file_for_user(str(f), open_editor_cmd="cursor")
        assert ok is False
        assert warn is not None
        assert "open_file_failed" in warn
