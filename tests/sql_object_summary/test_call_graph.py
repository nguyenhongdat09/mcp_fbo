"""Unit tests for sql_object_summary.call_graph."""

from sql_object_summary import build_call_graph
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC, FIXTURE_PIVOT_PROC


def test_build_call_graph_basic():
    definitions = {
        "dbo.rs_rptInterestDetailedByLoanContract": FIXTURE_INTEREST_PROC,
        "dbo.FastBusiness$Partition$Execute": "CREATE PROC dbo.FastBusiness$Partition$Execute AS SELECT 1;",
        "dbo.FastBusiness$Balance$BContract": "CREATE PROC dbo.FastBusiness$Balance$BContract AS SELECT * FROM cdku;",
    }

    cg = build_call_graph("dbo.rs_rptInterestDetailedByLoanContract", definitions, max_depth=1)
    assert cg.root == "dbo.rs_rptInterestDetailedByLoanContract"
    assert "dbo.rs_rptInterestDetailedByLoanContract" in cg.nodes
    assert "dbo.FastBusiness$Partition$Execute" in cg.nodes
    assert cg.nodes["dbo.FastBusiness$Partition$Execute"].kind == "infra"
    assert "dmku" in cg.impacted_tables
    assert "cdku" in cg.impacted_tables


def test_build_call_graph_truncation():
    definitions = {
        "dbo.root": FIXTURE_INTEREST_PROC,
    }
    cg = build_call_graph(
        "dbo.root",
        definitions,
        max_depth=1,
        truncated_objects=["dbo.child_1", "dbo.child_2"],
    )
    assert cg.truncated is True
    assert len(cg.truncated_objects) == 2
