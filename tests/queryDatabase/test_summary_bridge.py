"""Unit tests for queryDatabase.bridges.summary_bridge with mock fetcher."""

from unittest.mock import MagicMock
from queryDatabase.bridges.summary_bridge import summary_object, resolve_object_ref, map_object_type
from queryDatabase.bridges.summary_format import format_summary_result
from queryDatabase.object_catalog.models import DbObjectMeta
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC


def test_resolve_object_ref():
    assert resolve_object_ref("zc_bcthlv", "dbo") == ("dbo", "zc_bcthlv")
    assert resolve_object_ref("dbo.zc_bcthlv", "custom") == ("dbo", "zc_bcthlv")
    assert resolve_object_ref("FastBusiness$Balance$BContract") == ("dbo", "FastBusiness$Balance$BContract")


def test_map_object_type():
    assert map_object_type("P") == "PROCEDURE"
    assert map_object_type("FN") == "FUNCTION"
    assert map_object_type("V") == "VIEW"
    assert map_object_type("TR") == "UNSUPPORTED"


def test_summary_bridge_with_mock_fetcher():
    mock_fetcher = MagicMock()
    mock_meta = DbObjectMeta(
        schema_name="dbo",
        name="rs_rptInterestDetailedByLoanContract",
        object_id=999,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=None,
        parameters=[],
    )
    mock_fetcher.fetch_one.return_value = mock_meta
    mock_fetcher.fetch_many.return_value = {}

    res = summary_object(
        file_path="mock_path.xml",
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
        mode="summary",
        max_depth=1,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )

    assert res["success"] is True
    assert res["spec_version"] == "1.0"
    assert res["object"] == "dbo.rs_rptInterestDetailedByLoanContract"
    assert res["object_type"] == "PROCEDURE"
    assert "summary" in res

    # Check Markdown formatter
    formatted = format_summary_result(res)
    assert "[OK] summary_object" in formatted
    assert "dbo.rs_rptInterestDetailedByLoanContract" in formatted
    assert "```json" in formatted


def test_summary_bridge_snippet_validation():
    res = summary_object(
        file_path="mock_path.xml",
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
        mode="snippet",
        keywords=[],
        zones=[],
    )
    assert res["success"] is False
    assert res["error"] == "snippet_params_required"
