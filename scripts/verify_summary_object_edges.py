#!/usr/bin/env python3
"""Edge-case verification for summary_object — run inline, not part of pytest."""
from __future__ import annotations

import inspect
import json
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from queryDatabase.bridges.summary_bridge import (
    summary_object,
    resolve_object_ref,
    _get_from_cache,
    _set_to_cache,
    _SUMMARY_CACHE,
)
from queryDatabase.object_catalog.fetcher import ObjectCatalogFetcher
from queryDatabase.object_catalog.models import DbObjectMeta
from sql_object_summary import build_call_graph, extract_snippet, analyze_definition
from sql_object_summary.options import AnalyzeOptions, DEFAULT_EXCLUDE_LIKE
from sql_object_summary.call_graph import build_call_graph as bcg
from tests.sql_object_summary.test_analyze_proc import FIXTURE_INTEREST_PROC

FINDINGS: list[dict] = []


def report(severity: str, location: str, expected: str, actual: str, fix: str, tested: str):
    FINDINGS.append(
        {
            "severity": severity,
            "location": location,
            "expected": expected,
            "actual": actual,
            "suggested_fix": fix,
            "covered_by_existing_tests": tested,
        }
    )


def mock_meta(**kw):
    defaults = dict(
        schema_name="dbo",
        name="test_proc",
        object_id=100,
        type_desc="SQL_STORED_PROCEDURE",
        sys_type="P",
        definition=FIXTURE_INTEREST_PROC,
        modify_date=datetime(2025, 1, 1),
        parameters=[],
    )
    defaults.update(kw)
    return DbObjectMeta(**defaults)


def test_execute_query_arg_order():
    """fetcher passes (sql, parsed) but executor signature is (parsed, query)."""
    sig = inspect.signature(__import__("queryDatabase.executor", fromlist=["execute_query"]).execute_query)
    params = list(sig.parameters.keys())
    fetcher_src = inspect.getsource(ObjectCatalogFetcher.fetch_one)
    calls_wrong = "execute_query(sql, self._parsed)" in fetcher_src
    calls_right = "execute_query(self._parsed, sql)" in fetcher_src
    if params[:2] == ["parsed", "query"] and calls_wrong and not calls_right:
        report(
            "blocker",
            "queryDatabase/object_catalog/fetcher.py — fetch_one/fetch_many/fetch_callers/fetch_parameters",
            "execute_query(parsed_conn, sql) matching queryDatabase/executor.py signature",
            "All fetcher calls use execute_query(sql, self._parsed) — reversed argument order",
            "Swap to execute_query(self._parsed, sql) in all 5 call sites",
            "No — mocks patch execute_query and return fake 'data' key, masking live failure",
        )


def test_result_sets_vs_data():
    """fetcher reads res['data'] but execute_query returns result_sets/columns/rows."""
    fetcher_src = inspect.getsource(ObjectCatalogFetcher)
    if 'res.get("data")' in fetcher_src:
        # Simulate real execute_query return shape
        fake_exec_return = {
            "success": True,
            "result_sets": [
                {
                    "columns": ["object_id", "schema_name", "name", "type", "type_desc", "definition", "modify_date"],
                    "rows": [[1, "dbo", "zc_bcthlv", "P", "SQL_STORED_PROCEDURE", "CREATE PROC...", None]],
                }
            ],
        }

        class FakeFetcher(ObjectCatalogFetcher):
            pass

        with patch("queryDatabase.object_catalog.fetcher.execute_query", return_value=fake_exec_return):
            f = FakeFetcher({"server": "s", "database": "d"})
            meta = f.fetch_one("zc_bcthlv", "dbo")
            if meta is None:
                report(
                    "blocker",
                    "queryDatabase/object_catalog/fetcher.py:46 — fetch_one rows = res.get('data')",
                    "Parse result_sets[0] columns+rows into dict rows (like parse_object_lookup_result)",
                    "fetch_one returns None — 'data' key absent in real execute_query response",
                    "Add helper _rows_from_result(res) mapping columns to dicts from result_sets",
                    "No — test_object_catalog mocks {'data': [...]} which real executor never returns",
                )


def test_query_timeout_not_used():
    src = inspect.getsource(ObjectCatalogFetcher)
    uses_timeout = "_query_timeout" in src and "timeout" in src.split("_query_timeout")[1][:200]
    init_has = "query_timeout" in inspect.getsource(ObjectCatalogFetcher.__init__)
    if init_has and not uses_timeout:
        report(
            "major",
            "queryDatabase/object_catalog/fetcher.py:18-20 — __init__ stores query_timeout",
            "Per-query timeout enforced (docs: 10s catalog, 30s total request)",
            "query_timeout stored on instance but never passed to execute_query or pyodbc",
            "Pass timeout to execute_query(..., timeout=self._query_timeout) and honor in executor",
            "No",
        )


def test_expand_name_matching():
    """expand list uses bare names but calls_direct uses dbo. prefix."""
    child_def = "CREATE PROC dbo.zc_child AS SELECT 1;"
    root_def = "CREATE PROC dbo.root AS EXEC dbo.zc_child; SELECT * FROM dmku;"
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = mock_meta(name="root", definition=root_def)
    fetched = {}

    def fetch_many(keys):
        out = {}
        for s, n in keys:
            k = f"{s}.{n}"
            out[k] = mock_meta(name=n, schema_name=s, definition=child_def)
            fetched[k] = True
        return out

    mock_fetcher.fetch_many.side_effect = fetch_many

    # expand with bare name (doc example style)
    res = summary_object(
        file_path="x.xml",
        object_name="dbo.root",
        mode="summary",
        max_depth=1,
        expand=["zc_child"],
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    cg = res.get("call_graph")
    if cg and "dbo.zc_child" not in cg.get("nodes", {}) and not fetched:
        report(
            "major",
            "queryDatabase/bridges/summary_bridge.py:271 — call.name in expand_set",
            "expand=['zc_child'] should match call 'dbo.zc_child' (normalize bare vs schema-qualified)",
            f"fetch_many not called / child not in nodes. expand_set={{'zc_child'}}, call.name='dbo.zc_child'",
            "Normalize expand entries and call.name to comparable form (strip/add dbo. prefix)",
            "No",
        )

    # expand with dbo. prefix
    mock_fetcher2 = MagicMock()
    mock_fetcher2.fetch_one.return_value = mock_meta(name="root", definition=root_def)
    mock_fetcher2.fetch_many.side_effect = fetch_many
    fetched2 = {}
    res2 = summary_object(
        file_path="x.xml",
        object_name="dbo.root",
        mode="summary",
        max_depth=1,
        expand=["dbo.zc_child"],
        use_cache=False,
        fetcher_override=mock_fetcher2,
    )
    if res2.get("call_graph") and "dbo.zc_child" in res2.get("call_graph", {}).get("nodes", {}):
        pass  # dbo. form works — document asymmetry if bare failed


def test_exclude_like_none_bridge():
    """Bridge passes exclude_like=None to AnalyzeOptions when caller omits param."""
    import queryDatabase.bridges.summary_bridge as sb

    src = inspect.getsource(sb.summary_object)
    if "exclude_like=exclude_like" in src:
        opts = AnalyzeOptions(exclude_like=None)
        if opts.exclude_like is None:
            report(
                "major",
                "queryDatabase/bridges/summary_bridge.py:243 + sql_object_summary/options.py:33",
                "When exclude_like=None from bridge, use DEFAULT_EXCLUDE_LIKE (per docs §2.2)",
                "AnalyzeOptions(exclude_like=None) sets exclude_like to None, not default infra patterns",
                "In bridge: exclude_patterns = exclude_like if exclude_like is not None else list(DEFAULT_EXCLUDE_LIKE); pass to AnalyzeOptions and build_call_graph",
                "No — docs say bridge should merge default but implementation passes None through",
            )


def test_max_depth_2_no_recursion():
    """max_depth=2 should fetch grandchildren — bridge only fetches direct calls once."""
    grandchild = "CREATE PROC dbo.grand AS SELECT 1;"
    child = f"CREATE PROC dbo.child AS EXEC dbo.grand; SELECT * FROM ctdmku;"
    root = "CREATE PROC dbo.root AS EXEC dbo.child;"

    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = mock_meta(name="root", definition=root)

    def fetch_many(keys):
        out = {}
        for s, n in keys:
            if n == "child":
                out[f"{s}.{n}"] = mock_meta(name=n, schema_name=s, definition=child)
            elif n == "grand":
                out[f"{s}.{n}"] = mock_meta(name=n, schema_name=s, definition=grandchild)
        return out

    mock_fetcher.fetch_many.side_effect = fetch_many

    res = summary_object(
        file_path="x.xml",
        object_name="dbo.root",
        mode="summary",
        max_depth=2,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    cg = res.get("call_graph", {})
    nodes = cg.get("nodes", {})
    fetch_calls = mock_fetcher.fetch_many.call_count
    if "dbo.grand" not in nodes and fetch_calls <= 1:
        report(
            "major",
            "queryDatabase/bridges/summary_bridge.py:255-289 — call graph section",
            "max_depth=2 recursively fetches and parses child/grandchild business objects",
            f"Only 1-hop fetch (fetch_many called {fetch_calls}x); grandchild dbo.grand absent from nodes",
            "Implement recursive _collect_definitions loop until max_depth or max_objects (per docs §7)",
            "No — test_call_graph only tests build_call_graph with pre-built definitions dict",
        )


def test_encrypted_empty_definition():
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = mock_meta(definition="", sys_type="P", name="enc_proc")

    res = summary_object(
        file_path="x.xml",
        object_name="dbo.enc_proc",
        mode="summary",
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    if res.get("success") and res.get("parse_status") != "failed":
        report(
            "minor",
            "queryDatabase/bridges/summary_bridge.py + sql_object_summary/analyze.py",
            "Empty/encrypted definition (NULL→'') should surface clear warning or error (docs §6)",
            f"success=True, parse_status={res.get('parse_status')} with empty definition — silent empty summary",
            "Detect empty definition after fetch; return error encrypted_or_empty_definition or meta.warnings",
            "No",
        )


def test_called_by_format():
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = mock_meta(name="target")
    mock_fetcher.fetch_many.return_value = {}
    mock_fetcher.fetch_callers.return_value = ["dbo.caller_a", "dbo.caller_b"]

    res = summary_object(
        file_path="x.xml",
        object_name="dbo.target",
        mode="summary",
        include_called_by=True,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    cg = res.get("call_graph", {})
    cb = cg.get("called_by", [])
    if cb and isinstance(cb[0], dict) and "name" in cb[0]:
        # Check docs — 05_integration shows pure.called_by = list of strings
        report(
            "minor",
            "queryDatabase/bridges/summary_bridge.py:296 — called_by assignment",
            "Docs 05_integration: pure.called_by = fetcher.fetch_callers(...) → list[str]; schema shows called_by: []",
            f"called_by entries are dicts: {cb[0]}",
            "Use list[str] OR update JSON schema docs to [{name: str}] consistently",
            "No",
        )
    if not cg:
        report(
            "major",
            "queryDatabase/bridges/summary_bridge.py:291-298",
            "include_called_by=True populates call_graph.called_by",
            "call_graph is None when root has no calls_direct — called_by never attached",
            "Always create minimal CallGraph or put called_by at top level when include_called_by=True",
            "No",
        )


def test_view_no_call_graph():
    mock_fetcher = MagicMock()
    view_def = "CREATE VIEW dbo.v_test AS SELECT a.ma_ku FROM dmku a JOIN ctdmku b ON a.ma_ku=b.ma_ku;"
    mock_fetcher.fetch_one.return_value = mock_meta(
        name="v_test", sys_type="V", type_desc="VIEW", definition=view_def
    )

    res = summary_object(
        file_path="x.xml",
        object_name="dbo.v_test",
        mode="summary",
        max_depth=2,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    if res.get("object_type") != "VIEW":
        report("major", "summary_bridge map_object_type", "VIEW", res.get("object_type"), "fix mapping", "Partial")
    if res.get("call_graph") is not None:
        report(
            "minor",
            "queryDatabase/bridges/summary_bridge.py:259-260",
            "VIEW never expands call graph — call_graph omitted or null",
            f"call_graph present: {bool(res.get('call_graph'))}",
            "Ensure VIEW skips call_graph entirely (current code looks correct)",
            "No",
        )
    # VIEW tables should still parse
    tables = res.get("summary", {}).get("tables_read", [])
    if "dmku" not in tables:
        report(
            "minor",
            "sql_object_summary/visitors/summary_visitor.py — VIEW table extraction",
            "VIEW should extract tables_read from FROM/JOIN",
            f"tables_read={tables}",
            "Verify visitor handles CREATE VIEW path",
            "No",
        )


def test_resolve_object_ref_edge_cases():
    cases = [
        ("[dbo].[zc_test]", "dbo", ("dbo", "zc_test")),
        ('dbo."weird"', "dbo", None),  # quotes inside — sanitize may fail
        ("dbo.zc_test.extra", "dbo", None),  # multi-dot
        ("", "dbo", None),
    ]
    for name, schema, expected in cases:
        try:
            got = resolve_object_ref(name, schema)
            if expected and got != expected:
                report(
                    "minor",
                    f"queryDatabase/bridges/summary_bridge.py:91 — resolve_object_ref('{name}')",
                    str(expected),
                    str(got),
                    "Handle bracketed names; reject/warn multi-segment names",
                    "Partial — test_resolve_object_ref covers basic cases only",
                )
            if name == "dbo.zc_test.extra" and got == ("dbo", "zc_test"):
                report(
                    "minor",
                    "summary_bridge.py:95 — partition('.')",
                    "Reject or resolve 3-part names (schema.proc.suffix)",
                    f"Returns {got} — takes first dot only, silently wrong name 'zc_test'",
                    "Validate at most one dot in object_name or use rsplit",
                    "No",
                )
        except Exception as e:
            if expected is not None:
                report("minor", "resolve_object_ref", str(expected), f"raised {e}", "document behavior", "No")


def test_snippet_zones_only_keywords_only():
    # zones only — bridge validation
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_one.return_value = mock_meta(name="p")
    res_z = summary_object(
        file_path="x.xml",
        object_name="dbo.p",
        mode="snippet",
        zones=["header"],
        keywords=None,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    if not res_z.get("success"):
        report("major", "snippet zones only", "success", res_z, "fix validation", "No")

    res_k = summary_object(
        file_path="x.xml",
        object_name="dbo.p",
        mode="snippet",
        keywords=["@Status"],
        zones=None,
        use_cache=False,
        fetcher_override=mock_fetcher,
    )
    if not res_k.get("success") or not res_k.get("snippets"):
        report("major", "snippet keywords only", "snippets returned", res_k, "fix", "Partial — test_snippet uses both")

    # zone with no matches
    res_empty = extract_snippet("SELECT 1", zones=["cursor"], object_name="dbo.x")
    if res_empty.snippets == [] and res_empty.success and not res_empty.meta.warnings:
        report(
            "minor",
            "sql_object_summary/snippet.py — empty zone match",
            "Indicate no matches (warning or truncated flag)",
            "success=True, snippets=[], no warning in meta",
            "Add meta.warnings when zones/keywords match nothing",
            "No",
        )


def test_cache_key_modes():
    _SUMMARY_CACHE.clear()
    base = dict(server="srv", database="db", object_id=42, modify_date=datetime(2025, 1, 1))

    d1 = {"success": True, "mode": "summary", "meta": {"cache_hit": False}}
    d2 = {"success": True, "mode": "snippet", "meta": {"cache_hit": False}}

    _set_to_cache(**base, mode="summary", max_depth=1, result=d1)
    hit_summary = _get_from_cache(**base, mode="summary", max_depth=1)
    hit_snippet = _get_from_cache(**base, mode="snippet", max_depth=1)

    if hit_summary and hit_snippet:
        report("major", "cache key", "different modes = different cache entries", "collision?", "include mode in key", "No")
    if not hit_summary:
        report("major", "cache", "summary cached", "miss", "fix cache", "No")

    # keywords not in cache key — snippet with different keywords returns same cache
    _set_to_cache(**base, mode="snippet", max_depth=1, result=d2)
    hit_snip = _get_from_cache(**base, mode="snippet", max_depth=1)
    if hit_snip and "keywords" not in str(_get_from_cache.__code__.co_varnames):
        report(
            "major",
            "queryDatabase/bridges/summary_bridge.py:48 — cache key",
            "Cache key includes snippet params (keywords/zones) or snippet mode not cached",
            "Key is (server, db, object_id, modify_date, mode, max_depth) — ignores keywords/zones",
            "Extend cache key with hash(keywords, zones) for snippet mode",
            "No",
        )

    # expand/max_objects not in key
    if "expand" not in str(_get_from_cache.__code__.co_varnames):
        report(
            "minor",
            "summary_bridge.py:48 — cache key tuple",
            "Different max_depth/expand/max_objects produce different cache entries",
            "Key includes max_depth but NOT expand, max_objects, include_called_by, exclude_like",
            "Add relevant params to cache key or document intentional omission",
            "No",
        )

    _SUMMARY_CACHE.clear()


def test_build_call_graph_exclude_like_unused():
    src = inspect.getsource(bcg)
    if "exclude_patterns" in src and "exclude_patterns =" in src:
        body = src.split("exclude_patterns =")[1]
        # Remove the rest of the assignment line
        body_rest = body.split("\n", 1)[1] if "\n" in body else ""
        if "exclude_patterns" not in body_rest and "_matches_exclude" not in src:
            report(
                "major",
                "sql_object_summary/call_graph.py — exclude_patterns",
                "exclude_like filters infra objects from expansion/recursion",
                "exclude_patterns computed but never referenced in build_call_graph",
                "Apply exclude_patterns when deciding which calls to expand/fetch",
                "No",
            )



def test_call_graph_max_depth_semantics():
    """build_call_graph: max_depth>1 only sets expanded=True on child nodes, no deeper fetch."""
    child = "CREATE PROC dbo.child AS EXEC dbo.grand;"
    definitions = {
        "dbo.root": "CREATE PROC dbo.root AS EXEC dbo.child;",
        "dbo.child": child,
    }
    cg = build_call_graph("dbo.root", definitions, max_depth=2)
    child_node = cg.nodes.get("dbo.child")
    if child_node and child_node.expanded and child_node.depth == 1:
        # expanded flag true but grand never in definitions — calls may list dbo.grand but not fetched
        if "dbo.grand" in child_node.calls and "dbo.grand" not in cg.nodes:
            report(
                "minor",
                "sql_object_summary/call_graph.py:78 — max_depth>1",
                "depth=2 includes grandchild nodes when definitions provided",
                "child.calls lists dbo.grand but grand not added to nodes (only 1-hop in definitions loop)",
                "Document as shallow-only graph or recurse build_call_graph",
                "No",
            )


def main():
    test_execute_query_arg_order()
    test_result_sets_vs_data()
    test_query_timeout_not_used()
    test_expand_name_matching()
    test_exclude_like_none_bridge()
    test_max_depth_2_no_recursion()
    test_encrypted_empty_definition()
    test_called_by_format()
    test_view_no_call_graph()
    test_resolve_object_ref_edge_cases()
    test_snippet_zones_only_keywords_only()
    test_cache_key_modes()
    test_build_call_graph_exclude_like_unused()
    test_call_graph_max_depth_semantics()

    print(json.dumps(FINDINGS, indent=2, ensure_ascii=False))
    print(f"\nTotal findings: {len(FINDINGS)}")


if __name__ == "__main__":
    main()
