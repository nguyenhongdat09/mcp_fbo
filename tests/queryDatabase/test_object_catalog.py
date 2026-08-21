"""Unit tests for queryDatabase.object_catalog with mock executor matching real return structure."""

from unittest.mock import patch
from queryDatabase.object_catalog.fetcher import ObjectCatalogFetcher, _rows_from_result
from queryDatabase.object_catalog.models import DbObjectMeta


def test_object_catalog_fetch_one_mock():
    mock_result_set = {
        "success": True,
        "result_sets": [
            {
                "columns": ["object_id", "schema_name", "name", "type", "type_desc", "definition", "modify_date"],
                "rows": [
                    [12345, "dbo", "zc_bcthlv", "P", "SQL_STORED_PROCEDURE", "CREATE PROCEDURE dbo.zc_bcthlv AS SELECT 1;", None]
                ],
                "row_count": 1,
            }
        ],
    }

    with patch("queryDatabase.object_catalog.fetcher.execute_query") as mock_exec:
        mock_exec.return_value = mock_result_set
        conn_dict = {"server": "localhost", "database": "test"}
        fetcher = ObjectCatalogFetcher(conn_dict)
        meta = fetcher.fetch_one("zc_bcthlv", "dbo")

        assert meta is not None
        assert meta.name == "zc_bcthlv"
        assert meta.schema_name == "dbo"
        assert meta.object_id == 12345
        assert meta.sys_type == "P"
        assert meta.definition == "CREATE PROCEDURE dbo.zc_bcthlv AS SELECT 1;"

        # Assert correct argument order (parsed_conn, sql) for both queries
        assert len(mock_exec.call_args_list) == 2
        first_call = mock_exec.call_args_list[0][0]
        assert first_call[0] == conn_dict
        assert isinstance(first_call[1], str)
        assert "WHERE o.name = N'zc_bcthlv'" in first_call[1]

        second_call = mock_exec.call_args_list[1][0]
        assert second_call[0] == conn_dict
        assert "FROM sys.parameters p" in second_call[1]


def test_object_catalog_fetch_callers_mock():
    mock_result_set = {
        "success": True,
        "result_sets": [
            {
                "columns": ["caller"],
                "rows": [["dbo.caller_proc_1"], ["dbo.caller_proc_2"]],
                "row_count": 2,
            }
        ],
    }

    with patch("queryDatabase.object_catalog.fetcher.execute_query") as mock_exec:
        mock_exec.return_value = mock_result_set
        conn_dict = {"server": "localhost", "database": "test"}
        fetcher = ObjectCatalogFetcher(conn_dict)
        callers = fetcher.fetch_callers(12345, "dbo", "zc_bcthlv")

        assert len(callers) == 2
        assert "dbo.caller_proc_1" in callers
        assert mock_exec.call_args[0][0] == conn_dict
