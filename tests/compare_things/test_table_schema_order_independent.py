"""Unit tests for kind=table order-independent schema comparison in compare_things."""

from unittest.mock import MagicMock, patch
import pytest
from compare_things import compare_things
from compare_things.table_schema import compute_table_fingerprint


def test_tc_table_01_column_order_independent():
    # Source has K, L; Target has L, K
    sch_src = {
        "columns": {
            "k": {"name": "K", "type": "int null"},
            "l": {"name": "L", "type": "int null"},
        },
        "pk": ["k"],
        "indexes": {},
        "triggers": {},
    }
    sch_tgt = {
        "columns": {
            "l": {"name": "L", "type": "int null"},
            "k": {"name": "K", "type": "int null"},
        },
        "pk": ["k"],
        "indexes": {},
        "triggers": {},
    }

    fp_src = compute_table_fingerprint(sch_src)
    fp_tgt = compute_table_fingerprint(sch_tgt)
    assert fp_src == fp_tgt


@pytest.fixture
def mock_table_dbs():
    with patch("compare_things.table_compare.resolve_project_dbs") as mock_resolve:
        mock_resolve.return_value = {
            "app": {"server": "test", "database": "app_db"},
            "sys": {"server": "test", "database": "sys_db"},
        }
        yield mock_resolve


def test_tc_table_01_compare_order_independent(mock_table_dbs):
    with patch("compare_things.table_compare.fetch_table_schema") as mock_fetch:
        def fetch_side(conn, name, schema):
            return {
                "columns": {
                    "k": {"name": "K", "type": "int null"},
                    "l": {"name": "L", "type": "int null"},
                },
                "pk": ["k"],
                "indexes": {},
                "triggers": {},
            }

        mock_fetch.side_effect = fetch_side

        res = compare_things(
            kind="table",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dmuqduyet",
        )
        assert res["success"] is True
        assert "dbo.dmuqduyet" in res["summary"]["identical"]
        assert res["compared"][0]["status"] == "identical"


def test_tc_table_02_type_mismatch(mock_table_dbs):
    with patch("compare_things.table_compare.fetch_table_schema") as mock_fetch:
        mock_fetch.side_effect = [
            {
                "columns": {"so_luong": {"name": "so_luong", "type": "int null"}},
                "pk": [],
                "indexes": {},
                "triggers": {},
            },
            {
                "columns": {"so_luong": {"name": "so_luong", "type": "bigint null"}},
                "pk": [],
                "indexes": {},
                "triggers": {},
            },
        ]

        res = compare_things(
            kind="table",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dmuqduyet",
        )
        assert res["success"] is True
        assert "dbo.dmuqduyet" in res["summary"]["different"]
        item = res["compared"][0]
        assert item["status"] == "different"
        diff = item["schema_diff"]
        assert len(diff["columns_type_mismatch"]) == 1
        assert diff["columns_type_mismatch"][0]["column"] == "so_luong"
        assert "review_column_type" in res["next_actions"]


def test_tc_table_03_missing_column(mock_table_dbs):
    with patch("compare_things.table_compare.fetch_table_schema") as mock_fetch:
        mock_fetch.side_effect = [
            {
                "columns": {
                    "k": {"name": "K", "type": "int null"},
                    "col_src_only": {"name": "col_src_only", "type": "varchar(20) null"},
                },
                "pk": [],
                "indexes": {},
                "triggers": {},
            },
            {
                "columns": {"k": {"name": "K", "type": "int null"}},
                "pk": [],
                "indexes": {},
                "triggers": {},
            },
        ]

        res = compare_things(
            kind="table",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dmuqduyet",
        )
        assert res["success"] is True
        item = res["compared"][0]
        assert "col_src_only" in item["schema_diff"]["columns_only_source"]
        assert "alter_add_column" in res["next_actions"]


def test_tc_table_04_pk_diff(mock_table_dbs):
    with patch("compare_things.table_compare.fetch_table_schema") as mock_fetch:
        mock_fetch.side_effect = [
            {"columns": {}, "pk": ["id", "code"], "indexes": {}, "triggers": {}},
            {"columns": {}, "pk": ["id"], "indexes": {}, "triggers": {}},
        ]

        res = compare_things(
            kind="table",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dmuqduyet",
        )
        assert res["success"] is True
        item = res["compared"][0]
        assert item["schema_diff"]["pk_diff"] is True
        assert "review_pk" in res["next_actions"]


def test_tc_table_07_missing_on_target(mock_table_dbs):
    with patch("compare_things.table_compare.fetch_table_schema") as mock_fetch:
        # source exists, target returns None
        mock_fetch.side_effect = [
            {"columns": {"id": {"name": "id", "type": "int not null"}}, "pk": ["id"], "indexes": {}, "triggers": {}},
            None,
        ]

        res = compare_things(
            kind="table",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dmuqduyet",
        )
        assert res["success"] is True
        assert "dbo.dmuqduyet" in res["summary"]["missing_on_target"]
        assert "clone_things_type0" in res["next_actions"]


def test_tc_table_missing_both(mock_table_dbs):
    with patch("compare_things.table_compare.fetch_table_schema") as mock_fetch:
        # source returns None, target returns None
        mock_fetch.side_effect = [None, None]

        res = compare_things(
            kind="table",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="tbl_not_exist",
        )
        assert res["success"] is True
        assert "dbo.tbl_not_exist" in res["summary"]["missing_both"]
        assert res["compared"][0]["status"] == "missing_both"

