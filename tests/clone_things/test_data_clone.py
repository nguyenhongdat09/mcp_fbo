"""Tests for type=2 data clone (DELETE + INSERT script) — AC-DATA-*."""

from decimal import Decimal
from unittest.mock import patch

from clone_things.service import clone_things


def _conn_side_effect(file_path, db_type="app"):
    db_name = "test_sys_db" if db_type == "sys" else "test_app_db"
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type, "database": db_name},
    }


# sys.columns metadata cho bảng giả lập: identity int, nvarchar, decimal, datetime, bit, timestamp, computed
COLS_ROWS = [
    [1, "id", "int", 1, 0],
    [2, "ma_ct", "nvarchar", 0, 0],
    [3, "loai_ct", "nvarchar", 0, 0],
    [4, "sl", "decimal", 0, 0],
    [5, "ngay", "datetime", 0, 0],
    [6, "flag", "bit", 0, 0],
    [7, "note", "nvarchar", 0, 0],
    [8, "ts", "timestamp", 0, 0],
    [9, "comp_col", "int", 0, 1],
]

DATA_ROWS = [
    [7, "DDV", "1", Decimal("0.0000"), "2023-02-02 09:02:00.000", True, None],
]


def _exists_table_on_app(parsed, name, schema):
    if parsed.get("_db") == "app" and name == "dmmagd":
        return True, "U", "USER_TABLE"
    return False, "", ""


def _query_cols_and_data(parsed, sql, max_rows=20000, params=None):
    if "sys.columns" in sql:
        return {"success": True, "result_sets": [{"columns": ["c"], "rows": COLS_ROWS}]}
    return {
        "success": True,
        "result_sets": [{"columns": ["c"], "rows": DATA_ROWS}],
        "truncated": False,
    }


def test_ac_data_1_happy_path(tmp_path):
    sql_file = tmp_path / "out.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_table_on_app), \
         patch("clone_things.service.execute_query", side_effect=_query_cols_and_data), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):
        res = clone_things(
            table="dmmagd",
            where="ma_ct = 'DDV'",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is True
    assert res["type"] == 2
    assert res["mode"] == "data_clone"
    assert res["row_count"] == 1
    assert res["db"] == "app"
    assert res["identity_insert"] is True
    assert "ts(timestamp)" in res["skipped_columns"]
    assert any("comp_col" in c for c in res["skipped_columns"])

    content = sql_file.read_text(encoding="utf-8")
    assert "DELETE FROM [dbo].[dmmagd] WHERE ma_ct = 'DDV'" in content
    assert "SET IDENTITY_INSERT [dbo].[dmmagd] ON" in content
    assert "SET IDENTITY_INSERT [dbo].[dmmagd] OFF" in content
    assert "INSERT INTO [dbo].[dmmagd]([id], [ma_ct], [loai_ct], [sl], [ngay], [flag], [note])" in content
    assert "VALUES(7, N'DDV', N'1', 0.0000, '20230202 09:02:00', 1, NULL)" in content
    # timestamp/computed bị loại khỏi insert column list
    assert "[ts]" not in content
    assert "[comp_col]" not in content


def test_ac_data_2_table_param_triggers_data_mode(tmp_path):
    """Chỉ cần table+where (type mặc định 0, không object, không target) → data clone."""
    sql_file = tmp_path / "out.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_table_on_app), \
         patch("clone_things.service.execute_query", side_effect=_query_cols_and_data), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):
        res = clone_things(
            object="",
            table="dbo.dmmagd",
            where="WHERE ma_ct = 'DDV';",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is True
    assert res["type"] == 2
    content = sql_file.read_text(encoding="utf-8")
    # WHERE keyword + trailing ';' được strip — không lặp WHERE WHERE
    assert "WHERE WHERE" not in content
    assert "WHERE ma_ct = 'DDV'" in content


def test_ac_data_3_missing_where():
    res = clone_things(
        table="dmmagd",
        where="",
        project_source="E:\\FBO\\P1",
    )
    assert res["success"] is False
    assert res["error_code"] == "missing_where"


def test_ac_data_4_type2_missing_table():
    res = clone_things(
        type=2,
        object="zc_test",
        where="ma_ct = 'DDV'",
        project_source="E:\\FBO\\P1",
    )
    assert res["success"] is False
    assert res["error_code"] == "missing_table"


def test_ac_data_5_table_not_found(tmp_path):
    sql_file = tmp_path / "out.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", return_value=(False, "", "")):
        res = clone_things(
            table="dm_khong_co",
            where="x = 1",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is False
    assert res["error_code"] == "table_not_found"


def test_ac_data_6_not_a_table(tmp_path):
    sql_file = tmp_path / "out.sql"

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", return_value=(True, "P", "SQL_STORED_PROCEDURE")):
        res = clone_things(
            table="zc_proc",
            where="x = 1",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is False
    assert res["error_code"] == "not_a_table"


def test_ac_data_7_zero_rows_still_writes_delete(tmp_path):
    sql_file = tmp_path / "out.sql"

    def _q(parsed, sql, max_rows=20000, params=None):
        if "sys.columns" in sql:
            return {"success": True, "result_sets": [{"columns": ["c"], "rows": COLS_ROWS}]}
        return {"success": True, "result_sets": [{"columns": ["c"], "rows": []}], "truncated": False}

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_table_on_app), \
         patch("clone_things.service.execute_query", side_effect=_q), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):
        res = clone_things(
            table="dmmagd",
            where="ma_ct = 'XXX'",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is True
    assert res["row_count"] == 0
    content = sql_file.read_text(encoding="utf-8")
    assert "DELETE FROM [dbo].[dmmagd] WHERE ma_ct = 'XXX'" in content
    assert "INSERT INTO" not in content


def test_ac_data_8_invalid_table_name():
    res = clone_things(
        table="dmmagd; DROP TABLE x",
        where="y = 1",
        project_source="E:\\FBO\\P1",
    )
    assert res["success"] is False
    assert res["error_code"] == "invalid_table"


def test_ac_data_9_escaped_quote_in_value(tmp_path):
    """Value có dấu nháy → escape ''."""
    sql_file = tmp_path / "out.sql"
    rows = [[1, "O'Hara", "x", Decimal("1.5"), "2023-02-02 00:00:00.000", False, "n"]]

    def _q(parsed, sql, max_rows=20000, params=None):
        if "sys.columns" in sql:
            return {"success": True, "result_sets": [{"columns": ["c"], "rows": COLS_ROWS}]}
        return {"success": True, "result_sets": [{"columns": ["c"], "rows": rows}], "truncated": False}

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type", side_effect=_exists_table_on_app), \
         patch("clone_things.service.execute_query", side_effect=_q), \
         patch("clone_things.service.open_file_for_user", return_value=(True, None)):
        res = clone_things(
            table="dmmagd",
            where="id = 1",
            project_source="E:\\FBO\\P1",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

    assert res["success"] is True
    content = sql_file.read_text(encoding="utf-8")
    assert "N'O''Hara'" in content
