"""Unit tests for kind=sql comparison in compare_things."""

from unittest.mock import MagicMock, patch
import pytest
from compare_things import compare_things


@pytest.fixture
def mock_dbs():
    with patch("compare_things.sql_compare.resolve_project_dbs") as mock_resolve:
        mock_resolve.return_value = {
            "app": {"server": "test", "database": "app_db"},
            "sys": {"server": "test", "database": "sys_db"},
        }
        yield mock_resolve


def test_tc_sql_01_identical(mock_dbs):
    with patch("compare_things.sql_compare.check_object_exists") as mock_exists, \
         patch("compare_things.sql_compare.check_is_encrypted") as mock_enc, \
         patch("compare_things.sql_compare.fetch_routine_definition") as mock_def:

        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_enc.return_value = False
        mock_def.return_value = "CREATE PROCEDURE dbo.ProcA AS SELECT 1"

        res = compare_things(
            kind="sql",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dbo.ProcA",
        )
        assert res["success"] is True
        assert "dbo.ProcA" in res["summary"]["identical"]
        assert res["summary"]["counts"]["identical"] == 1
        item = res["compared"][0]
        assert item["status"] == "identical"
        assert item["object_type"] == "proc"


def test_tc_sql_02_different(mock_dbs):
    with patch("compare_things.sql_compare.check_object_exists") as mock_exists, \
         patch("compare_things.sql_compare.check_is_encrypted") as mock_enc, \
         patch("compare_things.sql_compare.fetch_routine_definition") as mock_def:

        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_enc.return_value = False

        def get_def(proj, name, schema, db_type):
            if proj == "E:\\Source":
                return "CREATE PROC dbo.ProcDiff AS\nSELECT 1\nSELECT * FROM vdmduyetuq"
            return "CREATE PROC dbo.ProcDiff AS\nSELECT 1\nSELECT * FROM dmduyet"

        mock_def.side_effect = get_def

        res = compare_things(
            kind="sql",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dbo.ProcDiff",
        )
        assert res["success"] is True
        assert "dbo.ProcDiff" in res["summary"]["different"]
        item = res["compared"][0]
        assert item["status"] == "different"
        assert "source_refs_vdmduyetuq" in item["signals"]
        assert "target_refs_dmduyet" in item["signals"]

        hunks = item["content"]["hunks"]
        assert len(hunks) >= 1
        assert hunks[0]["source_line_start"] == 3
        assert hunks[0]["target_line_start"] == 3
        assert "review_hunks_before_alter" in res["next_actions"]


def test_tc_sql_03_missing_on_target(mock_dbs):
    with patch("compare_things.sql_compare._find_routine_on_dbs") as mock_find:
        # source exists, target does not
        def find_side(parsed_dbs, name, schema, dt, side, warnings):
            if side == "source":
                return True, "P", "SQL_STORED_PROCEDURE", "app", {}
            return False, "", "", None, None

        mock_find.side_effect = find_side

        res = compare_things(
            kind="sql",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dbo.ProcOnlySrc",
        )
        assert res["success"] is True
        assert "dbo.ProcOnlySrc" in res["summary"]["missing_on_target"]
        assert "clone_things_type0" in res["next_actions"]


def test_tc_sql_04_encrypted_skip(mock_dbs):
    with patch("compare_things.sql_compare.check_object_exists") as mock_exists, \
         patch("compare_things.sql_compare.check_is_encrypted") as mock_enc:

        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_enc.return_value = True

        res = compare_things(
            kind="sql",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dbo.ProcSecret",
        )
        assert res["success"] is True
        assert "dbo.ProcSecret" in res["summary"]["encrypted_skip"]
        assert "skip_encrypted" in res["next_actions"]


def test_tc_sql_06_seed_candidates(mock_dbs):
    with patch("compare_things.sql_compare.scan_seed_candidates") as mock_scan, \
         patch("compare_things.sql_compare.check_object_exists") as mock_exists, \
         patch("compare_things.sql_compare.check_is_encrypted") as mock_enc, \
         patch("compare_things.sql_compare.fetch_routine_definition") as mock_def:

        mock_scan.return_value = ["dbo.Proc1", "dbo.Proc2"]
        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_enc.return_value = False
        mock_def.return_value = "SELECT 1"

        res = compare_things(
            kind="sql",
            project_source="E:\\Source",
            project_target="E:\\Target",
            seed="dmuqduyet,vdmduyetuq",
        )
        assert res["success"] is True
        assert len(res["compared"]) == 2
        mock_scan.assert_called_once()


def test_tc_sql_missing_both(mock_dbs):
    with patch("compare_things.sql_compare._find_routine_on_dbs") as mock_find:
        mock_find.return_value = (False, "", "", None, None)

        res = compare_things(
            kind="sql",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dbo.ProcNonExistent",
        )
        assert res["success"] is True
        assert "dbo.ProcNonExistent" in res["summary"]["missing_both"]
        assert res["summary"]["counts"]["missing_both"] == 1
        item = res["compared"][0]
        assert item["status"] == "missing_both"
        assert "investigate_object_name" in item["next_actions"]


def test_tc_sql_strip_noise_header(mock_dbs):
    with patch("compare_things.sql_compare.check_object_exists") as mock_exists, \
         patch("compare_things.sql_compare.check_is_encrypted") as mock_enc, \
         patch("compare_things.sql_compare.fetch_routine_definition") as mock_def:

        mock_exists.return_value = (True, "P", "SQL_STORED_PROCEDURE")
        mock_enc.return_value = False

        def get_def(proj, name, schema, db_type):
            if proj == "E:\\Source":
                return "-- clone_things type=1: dbo.ProcA | paste-for-edit\n-- ================\nCREATE PROCEDURE dbo.ProcA AS SELECT 1"
            return "CREATE PROCEDURE dbo.ProcA AS SELECT 1"

        mock_def.side_effect = get_def

        res = compare_things(
            kind="sql",
            project_source="E:\\Source",
            project_target="E:\\Target",
            object="dbo.ProcA",
        )
        assert res["success"] is True
        assert "dbo.ProcA" in res["summary"]["identical"]
        assert res["compared"][0]["status"] == "identical"

