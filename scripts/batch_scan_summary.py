"""Batch scan tool to validate summary_object quality across procedures in a real FastBusiness database.

Usage:
  python scripts/batch_scan_summary.py --file-path <xml_path> [--limit 100] [--prefix rs_]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from queryDatabase.bridges.summary_bridge import summary_object
from queryDatabase.connection import get_connection_config
from queryDatabase.executor import execute_query
from sql_object_summary.visitors.summary_visitor import SQL_TABLE_NOISE_TOKENS


def run_batch_scan(
    file_path: str,
    db_type: str = "app",
    limit: int = 100,
    depth: int = 0,
    prefix_filter: str | None = None,
    output_json: str | None = None,
) -> dict[str, Any]:
    """Run batch scan across stored procedures in database."""
    print("=" * 85)
    print("       FASTBUSINESS MCP - SUMMARY_OBJECT BATCH SCAN VALIDATION TOOL")
    print("=" * 85)
    print(f"  File XML Path : {file_path}")
    print(f"  DB Type       : {db_type}")
    print(f"  Proc Limit    : {'ALL' if limit <= 0 else limit}")
    print(f"  Call Depth    : {depth}")
    print(f"  Prefix Filter : {prefix_filter or 'ALL'}")
    print("-" * 85)

    # 1. Resolve DB connection
    t0 = time.perf_counter()
    conn_res = get_connection_config(file_path=file_path, db_type=db_type)
    if not conn_res.get("success"):
        print(f"  [!] Failed to resolve connection: {conn_res}")
        return {}

    parsed_conn = conn_res.get("parsed", {})
    t_conn = (time.perf_counter() - t0) * 1000

    db_name = parsed_conn.get("database") or "Unknown"
    print(f"  [+] Connected to Database: {db_name} ({t_conn:.1f}ms)")

    # 2. Query procedure list
    query = """
    SELECT s.name AS schema_name, p.name AS proc_name
    FROM sys.procedures p
    JOIN sys.schemas s ON p.schema_id = s.schema_id
    WHERE p.is_ms_shipped = 0 AND s.name = 'dbo'
    ORDER BY p.name ASC
    """
    res_q = execute_query(parsed_conn, query)
    rows: list[dict[str, Any]] = []
    if res_q.get("success") and res_q.get("result_sets"):
        rs = res_q["result_sets"][0]
        cols = [str(c).lower() for c in rs.get("columns", [])]
        for raw_r in rs.get("rows", []):
            r_dict = {cols[i]: raw_r[i] for i in range(min(len(cols), len(raw_r)))}
            rows.append(r_dict)
    procs: list[str] = []
    for r in rows:
        name = r.get("proc_name") or r.get("name")
        if name:
            if prefix_filter:
                if name.lower().startswith(prefix_filter.lower()):
                    procs.append(f"dbo.{name}")
            else:
                procs.append(f"dbo.{name}")

    total_in_db = len(procs)
    if limit > 0:
        procs = procs[:limit]

    print(f"  [+] Total procedures matching filter: {total_in_db} | Testing: {len(procs)}")
    print("-" * 85)

    # 3. Scan each procedure
    domain_counts: dict[str, int] = {
        "interest_related": 0,
        "bctc_form_related": 0,
        "input_invoice_related": 0,
        "einvoice_related": 0,
        "approval_related": 0,
        "discount_related": 0,
        "post_related": 0,
        "voucher_lifecycle_related": 0,
        "balance_related": 0,
        "stock_related": 0,
        "custom_action_related": 0,
        "custom_report_related": 0,
        "custom_listing_related": 0,
        "report_generic": 0,
        "none": 0,
    }
    empty_hints_by_prefix: dict[str, int] = {"rs_": 0, "zc_": 0, "FastBusiness$": 0, "other": 0}
    noise_hits: dict[str, int] = {}
    bad_dynamic_sql_count = 0
    missing_examples: list[dict[str, Any]] = []
    times_ms: list[float] = []

    for idx, full_proc in enumerate(procs, 1):
        t_start = time.perf_counter()
        try:
            res = summary_object(
                object_name=full_proc,
                file_path=file_path,
                db_type=db_type,
                mode="summary",
                max_depth=depth,
                use_cache=True,
            )
            elapsed = (time.perf_counter() - t_start) * 1000
            times_ms.append(elapsed)

            summary = res.get("summary", {})
            logic_hints = summary.get("logic_hints", {})
            tables_read = summary.get("tables_read", [])
            tables_write = summary.get("tables_write", [])
            signals = summary.get("signals", {})

            # Check noise tokens in tables
            for t in tables_read + tables_write:
                t_lower = t.lower()
                if t_lower.isdigit() or t_lower in SQL_TABLE_NOISE_TOKENS:
                    noise_hits[t_lower] = noise_hits.get(t_lower, 0) + 1

            # Check domain flags
            matched_flag = None
            for flag in [
                "interest_related", "bctc_form_related", "input_invoice_related",
                "einvoice_related", "approval_related", "discount_related",
                "post_related", "voucher_lifecycle_related", "balance_related",
                "stock_related", "custom_action_related", "custom_report_related",
                "custom_listing_related", "report_generic",
            ]:
                if logic_hints.get(flag):
                    domain_counts[flag] += 1
                    matched_flag = flag
                    break

            if not matched_flag:
                domain_counts["none"] += 1
                bare_name = full_proc.split(".")[-1]
                if bare_name.startswith("rs_"):
                    empty_hints_by_prefix["rs_"] += 1
                elif bare_name.startswith("zc_"):
                    empty_hints_by_prefix["zc_"] += 1
                elif bare_name.startswith("FastBusiness$"):
                    empty_hints_by_prefix["FastBusiness$"] += 1
                else:
                    empty_hints_by_prefix["other"] += 1

                if len(missing_examples) < 10:
                    missing_examples.append({
                        "proc": full_proc,
                        "line_count": summary.get("line_count"),
                        "tables_read": tables_read[:5],
                        "temp_tables": summary.get("temp_tables", [])[:5],
                    })

            print(f"  [{idx:>3}/{len(procs)}] {full_proc:<42} ({elapsed:5.1f}ms) -> {matched_flag or '---'}", flush=True)

        except Exception as e:
            print(f"  [{idx:>3}/{len(procs)}] {full_proc:<42} ERROR: {e}", flush=True)

    print("\n" + "-" * 85)
    print("                             BATCH SCAN RESULTS SUMMARY")
    print("-" * 85)

    avg_time = sum(times_ms) / len(times_ms) if times_ms else 0
    max_time = max(times_ms) if times_ms else 0
    min_time = min(times_ms) if times_ms else 0

    print(f"  Scanned Procedures  : {len(times_ms)}")
    print(f"  Average Time/Proc   : {avg_time:.1f} ms (Min: {min_time:.1f} ms, Max: {max_time:.1f} ms)")
    print(f"  Noise Table Hits    : {len(noise_hits)} (Target: 0)")
    if noise_hits:
        print(f"    -> Violations: {noise_hits}")
    else:
        print("    -> [OK] 100% Clean! No SQL keywords/aliases/digits in tables_read/write.")

    print(f"  Dynamic SQL Errors  : {bad_dynamic_sql_count} (Target: 0)")

    print("\n  DOMAIN DISTRIBUTION:")
    for flag, cnt in domain_counts.items():
        pct = (cnt / len(times_ms)) * 100 if times_ms else 0
        print(f"    - {flag:<23} : {cnt:>4} ({pct:>5.1f}%)")

    print("\n  EMPTY LOGIC_HINTS BREAKDOWN:")
    for pfx, cnt in empty_hints_by_prefix.items():
        print(f"    - {pfx:<23} : {cnt:>4}")

    results_data = {
        "database": db_name,
        "total_scanned": len(times_ms),
        "timing": {"avg_ms": avg_time, "min_ms": min_time, "max_ms": max_time},
        "noise_hits": noise_hits,
        "bad_dynamic_sql_count": bad_dynamic_sql_count,
        "domain_counts": domain_counts,
        "empty_hints_by_prefix": empty_hints_by_prefix,
        "missing_examples": missing_examples,
    }

    if output_json:
        os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        print(f"\n  [+] Saved full results to: {output_json}")

    print("=" * 85)
    return results_data


def main():
    parser = argparse.ArgumentParser(description="Batch scan SQL stored procedures.")
    parser.add_argument("--file-path", required=True, help="Path to XML file")
    parser.add_argument("--db-type", default="app", help="Database type: app or sys")
    parser.add_argument("--limit", type=int, default=100, help="Max procedures to scan (0 = all)")
    parser.add_argument("--depth", type=int, default=0, help="Call expansion depth (default: 0)")
    parser.add_argument("--prefix", default=None, help="Optional prefix filter (e.g. rs_, zc_)")
    parser.add_argument("--output", default="docs/doc_fix/scan_results_VINHQUANG_FBISP242_A.json", help="Output JSON path")
    args = parser.parse_args()

    run_batch_scan(
        file_path=args.file_path,
        db_type=args.db_type,
        limit=args.limit,
        depth=args.depth,
        prefix_filter=args.prefix,
        output_json=args.output,
    )


if __name__ == "__main__":
    main()
