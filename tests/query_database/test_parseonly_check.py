"""Tests for query_type=3 — check file .sql qua SET PARSEONLY (AC-PSC-*)."""

from unittest.mock import patch

from query_database.executor import (
    check_sql_batches,
    split_go_batches_with_lines,
)
from query_database.service import query_database


def _ok(parsed, q, max_rows=0, **kw):
    return {
        "success": True,
        "result_sets": [],
        "messages": [],
        "row_count": 0,
        "execution_time_ms": 1,
    }


# ---------------------------------------------------------------------------
# split_go_batches_with_lines
# ---------------------------------------------------------------------------


def test_split_with_lines_basic():
    script = "SELECT 1\nGO\nSELECT 2\ngo\nSELECT 3"
    batches = split_go_batches_with_lines(script)
    assert batches == [("SELECT 1", 1), ("SELECT 2", 3), ("SELECT 3", 5)]


def test_split_with_lines_blank_lines_and_empty_batch():
    # blank lines trước GO bị regex nuốt; batch rỗng (giữa 2 GO) vẫn cộng line đúng
    script = "-- header\nSELECT 1\n\n\nGO\nGO\nSELECT 3"
    batches = split_go_batches_with_lines(script)
    assert batches == [
        ("-- header\nSELECT 1", 1),
        ("SELECT 3", 7),
    ]


def test_split_with_lines_no_go():
    assert split_go_batches_with_lines("  SELECT 1\nSELECT 2") == [
        ("SELECT 1\nSELECT 2", 1)
    ]
    assert split_go_batches_with_lines("   \n\n") == []


# ---------------------------------------------------------------------------
# Fake pyodbc connection & cursor for session-level PARSEONLY tests
# ---------------------------------------------------------------------------


class FakeCursor:
    def __init__(self, side_fn=None):
        self.executed_queries = []
        self.messages = []
        self.closed = False
        self._side_fn = side_fn

    def execute(self, query, *args):
        self.executed_queries.append(query)
        if self._side_fn:
            res = self._side_fn(query, *args)
            if res is not None:
                return res

    def nextset(self):
        return False

    def close(self):
        self.closed = True


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


class MockPyodbc:
    def __init__(self, side_fn=None):
        self.side_fn = side_fn
        self.connect_calls = []
        self.cursors = []
        self.main_cursor = None
        self.main_conn = None

    def connect(self, conn_str, timeout=30, **kwargs):
        self.connect_calls.append((conn_str, timeout))
        cur = FakeCursor(self.side_fn)
        self.cursors.append(cur)
        conn = FakeConn(cur)
        if timeout == 30 or self.main_conn is None:
            self.main_conn = conn
            self.main_cursor = cur
        return conn


# ---------------------------------------------------------------------------
# check_sql_batches (mock pyodbc.connect)
# ---------------------------------------------------------------------------


def test_ac_psc_1_error_maps_to_file_line():
    """AC-PSC-1: INSERT sai syntax ở line 4 file → errors[0].line_start = 4."""
    script = (
        "-- header\n"          # line 1
        "SELECT 1\n"           # line 2
        "GO\n"                 # line 3
        "INSERT INTO t(a,b) VALUES(1,2,3)\n"  # line 4
        "GO\n"                 # line 5
        "SELECT 2"             # line 6
    )

    def side(q, *args):
        if "VALUES(1,2,3)" in q:
            raise Exception(
                "Msg 110, Level 15: There are fewer columns in the "
                "INSERT statement than values specified"
            )

    mock_db = MockPyodbc(side_fn=side)
    with patch("pyodbc.connect", side_effect=mock_db.connect):
        res = check_sql_batches({"database": "d", "server": "s"}, script)

    assert res["success"] is False
    assert res["check_mode"] == "parseonly"
    assert res["batch_count"] == 3
    assert res["batches_ok"] == 2
    assert len(res["errors"]) == 1
    err = res["errors"][0]
    assert err["batch_index"] == 2
    assert err["line_start"] == 4
    assert "Msg 110" in err["message"] or "fewer columns" in err["message"]
    assert "INSERT INTO t" in err["batch_preview"]
    assert res["scope_note"]


def test_ac_psc_2_clean_multi_batch():
    """AC-PSC-2: file sạch nhiều batch GO → success, batches_ok == batch_count."""
    script = "SELECT 1\nGO\nSELECT 2\nGO\nSELECT 3"
    mock_db = MockPyodbc()
    with patch("pyodbc.connect", side_effect=mock_db.connect):
        res = check_sql_batches({"database": "d", "server": "s"}, script)

    assert res["success"] is True
    assert res["batch_count"] == 3
    assert res["batches_ok"] == 3
    assert res["errors"] == []
    # Assert mới theo AC-POF: 1 conn cho cả file (timeout=30), SET PARSEONLY ON riêng trước mỗi batch, OFF trong finally
    t30_calls = [c for c in mock_db.connect_calls if c[1] == 30]
    assert len(t30_calls) == 1
    assert mock_db.main_conn.closed is True
    assert mock_db.main_cursor.closed is True
    queries = mock_db.main_cursor.executed_queries
    assert queries == [
        "SET PARSEONLY ON",
        "SELECT 1",
        "SET PARSEONLY ON",
        "SELECT 2",
        "SET PARSEONLY ON",
        "SELECT 3",
        "SET PARSEONLY OFF",
    ]


def test_ac_psc_3_multiple_errors_no_stop_at_first():
    """AC-PSC-3: 2 batch đều lỗi → errors gom CẢ 2 (không stop-at-first)."""
    script = "BAD1\nGO\nSELECT ok\nGO\nBAD2"

    def side(q, *args):
        if "BAD" in q:
            raise Exception(f"syntax error in {q.strip()[:30]}")

    mock_db = MockPyodbc(side_fn=side)
    with patch("pyodbc.connect", side_effect=mock_db.connect):
        res = check_sql_batches({"database": "d", "server": "s"}, script)

    assert res["success"] is False
    assert len(res["errors"]) == 2
    assert res["errors"][0]["batch_index"] == 1
    assert res["errors"][0]["line_start"] == 1
    assert res["errors"][1]["batch_index"] == 3
    assert res["errors"][1]["line_start"] == 5
    assert res["batches_ok"] == 1
    # Cả 3 batch đều được gửi
    assert "BAD1" in mock_db.main_cursor.executed_queries
    assert "SELECT ok" in mock_db.main_cursor.executed_queries
    assert "BAD2" in mock_db.main_cursor.executed_queries


def test_ac_psc_4_create_then_insert_no_binding_error():
    """AC-PSC-4: CREATE TABLE t + INSERT INTO t → parse-only KHÔNG báo
    invalid object (mock mô phỏng server: PARSEONLY skip binding)."""
    script = "CREATE TABLE t(a int)\nGO\nINSERT INTO t(a) VALUES(1)"
    mock_db = MockPyodbc()
    with patch("pyodbc.connect", side_effect=mock_db.connect):
        res = check_sql_batches({"database": "d", "server": "s"}, script)
    assert res["success"] is True
    assert res["errors"] == []


def test_ac_pof_1_proc_definition_no_1059():
    """AC-POF-1 & AC-POF-2: Module DDL (CREATE/ALTER PROC/FUNC) không bị nuốt SET PARSEONLY OFF."""
    script = (
        "CREATE PROCEDURE dbo.zc_TestProc\n"
        "AS\n"
        "BEGIN\n"
        "    SET NOCOUNT ON;\n"
        "    SELECT 1;\n"
        "END"
    )
    mock_db = MockPyodbc()
    with patch("pyodbc.connect", side_effect=mock_db.connect):
        res = check_sql_batches({"database": "d", "server": "s"}, script)
    assert res["success"] is True
    assert res["errors"] == []
    # Batch được gửi nguyên văn không bị append SET PARSEONLY OFF vào cuối batch
    assert mock_db.main_cursor.executed_queries == [
        "SET PARSEONLY ON",
        script,
        "SET PARSEONLY OFF",
    ]


def test_ac_pof_8_reissue_parseonly_per_batch():
    """AC-POF-8: File tự chứa SET PARSEONLY OFF ở batch 1 → batch 2 vẫn được bật lại ON."""
    script = "SET PARSEONLY OFF\nGO\nSELECT 1"
    mock_db = MockPyodbc()
    with patch("pyodbc.connect", side_effect=mock_db.connect):
        res = check_sql_batches({"database": "d", "server": "s"}, script)
    assert res["success"] is True
    assert mock_db.main_cursor.executed_queries == [
        "SET PARSEONLY ON",
        "SET PARSEONLY OFF",
        "SET PARSEONLY ON",
        "SELECT 1",
        "SET PARSEONLY OFF",
    ]


def test_check_empty_script():
    res = check_sql_batches({"database": "d", "server": "s"}, "  \nGO\n  ")
    assert res["success"] is False
    assert res["batch_count"] == 0


# ---------------------------------------------------------------------------
# service wiring query_type=3
# ---------------------------------------------------------------------------


def _patch_conn():
    return patch("query_database.service.get_connection_config")


def test_ac_psc_5_stateless_next_query_normal(tmp_path):
    """AC-PSC-5: sau check type=3, query type=1 'SELECT 1' chạy bình thường —
    không leak PARSEONLY (mỗi execute_query tự wrap, mock thấy query sạch)."""
    sql_file = tmp_path / "ok.sql"
    sql_file.write_text("SELECT 1", encoding="utf-8")

    calls = []

    def capture_exec(parsed, q, max_rows=0, **kw):
        calls.append(q)
        return {
            "success": True,
            "result_sets": [{"columns": ["x"], "rows": [[1]], "row_count": 1}],
            "messages": [],
            "row_count": 1,
        }

    mock_db = MockPyodbc()
    with _patch_conn() as mconn, \
         patch("pyodbc.connect", side_effect=mock_db.connect), \
         patch("query_database.service.execute_query", side_effect=capture_exec):
        mconn.return_value = {"success": True, "parsed": {"database": "d", "server": "s"}}

        res3 = query_database(
            file_path="E:\\FBO\\P1\\Web.config",
            query=str(sql_file),
            query_type=3,
        )
        res1 = query_database(
            file_path="E:\\FBO\\P1\\Web.config",
            query="SELECT 1",
            query_type=1,
        )

    assert res3["success"] is True
    assert res3["check_mode"] == "parseonly"
    assert res1["success"] is True
    assert res1["result_sets"][0]["rows"] == [[1]]
    # call type=1 không bị wrap PARSEONLY
    assert calls[0].strip() == "SELECT 1"


def test_ac_psc_type3_wires_check_and_metadata(tmp_path):
    """type=3 → check_sql_batches (không execute_sql_batches), sql_file_path +
    label sql_check_file: giống type=2."""
    sql_file = tmp_path / "s.sql"
    sql_file.write_text("SELECT 1\nGO\nSELECT 2", encoding="utf-8")

    with _patch_conn() as mconn, \
         patch("query_database.service.execute_sql_batches") as mexec, \
         patch("query_database.service.check_sql_batches") as mchk:
        mconn.return_value = {"success": True, "parsed": {"database": "d"}}
        mchk.return_value = {
            "success": True,
            "check_mode": "parseonly",
            "batch_count": 2,
            "batches_ok": 2,
            "errors": [],
        }
        res = query_database(
            file_path="E:\\FBO\\P1\\Web.config",
            query=str(sql_file),
            query_type=3,
        )

    mchk.assert_called_once()
    mexec.assert_not_called()
    assert res["success"] is True
    assert res["check_mode"] == "parseonly"
    assert res["sql_file_path"] == str(sql_file)
    assert res["query_label"].startswith("sql_check_file:")
    assert res["query_type"] == 3


def test_ac_psc_6_utf16_sql_file(tmp_path):
    """AC-PSC-6: file .sql UTF-16LE → check đúng (read_sql_file đã decode)."""
    sql_file = tmp_path / "u16.sql"
    sql_file.write_bytes("SELECT 1\nGO\nSELECT 2".encode("utf-16"))

    mock_db = MockPyodbc()
    with _patch_conn() as mconn, \
         patch("pyodbc.connect", side_effect=mock_db.connect):
        mconn.return_value = {"success": True, "parsed": {"database": "d", "server": "s"}}
        res = query_database(
            file_path="E:\\FBO\\P1\\Web.config",
            query=str(sql_file),
            query_type=3,
        )

    assert res["success"] is True
    assert res["batch_count"] == 2
    for q in mock_db.main_cursor.executed_queries:
        assert "\x00" not in q


def test_ac_psc_7_non_sql_path_error(tmp_path):
    """AC-PSC-7: query_type=3 với query không phải .sql → error rõ ràng."""
    not_sql = tmp_path / "a.txt"
    not_sql.write_text("SELECT 1", encoding="utf-8")

    with _patch_conn() as mconn:
        mconn.return_value = {"success": True, "parsed": {"database": "d"}}
        res = query_database(
            file_path="E:\\FBO\\P1\\Web.config",
            query=str(not_sql),
            query_type=3,
        )
    assert res["success"] is False
    assert ".sql" in res["error"]


def test_ac_psc_normalize_type3():
    from query_database.query_resolver import normalize_query_type

    assert normalize_query_type(3) == 3
    import pytest

    with pytest.raises(ValueError):
        normalize_query_type(4)


# ---------------------------------------------------------------------------
# formatter — check_mode=parseonly phải render errors[], không 'Unknown error'
# ---------------------------------------------------------------------------


def test_formatter_parseonly_fail_renders_errors():
    """Bug: errors[] không có key 'error' top-level → generic branch in
    'Unknown error', mất line_start/message. Fix = nhánh parseonly riêng."""
    from query_database.formatter import format_query_result

    res = {
        "success": False,
        "check_mode": "parseonly",
        "batch_count": 3,
        "batches_ok": 2,
        "errors": [
            {
                "batch_index": 2,
                "line_start": 4,
                "message": "Msg 110: fewer columns than values",
                "batch_preview": "INSERT INTO dmct(...",
            }
        ],
        "scope_note": "PARSEONLY chỉ check syntax/structure",
        "database": "DB",
        "server": "S",
        "sql_file_path": "E:/T/x.sql",
    }
    out = format_query_result(res)
    assert "[FAIL]" in out
    assert "Msg 110" in out
    assert "dòng file" in out and "4" in out
    assert "Unknown error" not in out


def test_formatter_parseonly_pass():
    from query_database.formatter import format_query_result

    res = {
        "success": True,
        "check_mode": "parseonly",
        "batch_count": 2,
        "batches_ok": 2,
        "errors": [],
        "scope_note": "x",
        "database": "DB",
        "server": "S",
    }
    out = format_query_result(res)
    assert "[OK] Parse-only check PASSED" in out
    assert "Batches: 2/2" in out
