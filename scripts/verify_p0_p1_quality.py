# -*- coding: utf-8 -*-
from __future__ import annotations

import time

from sql_object_summary import analyze_definition
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC


def main() -> None:
    small = analyze_definition(
        FIXTURE_INTEREST_PROC,
        object_name="dbo.rs_rptInterestDetailedByLoanContract",
    )
    print("SMALL", small.line_count, "ms", small.meta.parse_time_ms, "status", small.parse_status)
    print("  warnings", small.meta.warnings)
    print("  tables", small.summary.tables_read)
    print("  temps", small.summary.temp_tables)
    print("  rs", [rs.columns_hint for rs in small.summary.result_sets])
    print("  calls", [(c.name, c.kind) for c in small.summary.calls_direct])
    print("  effects", [(e.param, e.confidence) for e in small.summary.param_effects])
    print("  snippet_index", list(small.summary.snippet_index.keys()))
    print("  hints", small.summary.logic_hints.get("keywords_suggested"))

    pad = FIXTURE_INTEREST_PROC + ("\n-- pad\n" * 120)
    t0 = time.perf_counter()
    try:
        large = analyze_definition(pad, object_name="dbo.rs_rptInterestDetailedByLoanContract")
        elapsed = int((time.perf_counter() - t0) * 1000)
        print("LARGE", large.line_count, "ms", large.meta.parse_time_ms, "wall", elapsed, "status", large.parse_status)
        print("  warnings", large.meta.warnings)
        print("  tables", large.summary.tables_read)
        print("  temps", large.summary.temp_tables)
        print("  rs", [rs.columns_hint for rs in large.summary.result_sets])
        print("  calls", [(c.name, c.kind) for c in large.summary.calls_direct])
        print("  params", [p.name for p in large.summary.params][:9])
        print("  effects", [(e.param, e.confidence) for e in large.summary.param_effects])
        print("  snippet_index", large.summary.snippet_index)
    except Exception as exc:
        print("LARGE FAILED", type(exc).__name__, exc)

    assign_sql = """
CREATE PROC dbo.p
    @x INT
AS
BEGIN
    SELECT @round = val FROM options WHERE name = 'm_round_tien'
    SELECT a, b INTO #t FROM dmku
    DECLARE cur CURSOR FOR SELECT ma_ku FROM #t
    SELECT ma_ku, tl_th FROM #t
END
"""
    a2 = analyze_definition(assign_sql, object_name="dbo.p")
    print("ASSIGN rs", [(r.ordinal, r.columns_hint) for r in a2.summary.result_sets])
    print("ASSIGN tables", a2.summary.tables_read, "temps", a2.summary.temp_tables)

    p3 = analyze_definition(
        "CREATE PROC dbo.p AS BEGIN\n SELECT * FROM r00$000000 a JOIN d91$123456 b ON 1=1\nEND",
        object_name="dbo.p",
    )
    print("PART tables", p3.summary.tables_read)


if __name__ == "__main__":
    main()
