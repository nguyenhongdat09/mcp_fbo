"""Unit tests for sql_object_summary.snippet."""

from sql_object_summary import extract_snippet, result_to_dict
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC


def test_snippet_by_keyword():
    res = extract_snippet(
        FIXTURE_INTEREST_PROC,
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
        keywords=["@Status", "tl_th"],
        max_lines=50,
    )
    assert res.success is True
    assert res.mode == "snippet"
    assert len(res.snippets) > 0
    assert res.total_lines > 0

    d = result_to_dict(res)
    assert d["spec_version"] == "1.0"
    assert "snippets" in d


def test_snippet_by_zone():
    res = extract_snippet(
        FIXTURE_INTEREST_PROC,
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
        zones=["header", "cursor"],
    )
    assert res.success is True
    assert len(res.snippets) > 0
