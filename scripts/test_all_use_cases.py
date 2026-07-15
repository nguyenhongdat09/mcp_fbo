"""Chay xml_graph_cli.py query cho nhieu use case — phan tich chat luong + token."""
import json
import subprocess
import sys
import time
from pathlib import Path

REF_DIR = r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Dir\CPTran.xml"
REF_GRID = r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Grid\Customer.xml"
CLI = Path(__file__).resolve().parents[1] / "xml_graph_cli.py"
PY = sys.executable

# (category, label, query_type, target, ref, extra_args)
CASES = [
    # --- SEARCH: field / code / synonym / tieng Viet ---
    ("search", "field ma_kh", "search", "ma_kh", REF_DIR, []),
    ("search", "field so_luong", "search", "so_luong", REF_DIR, []),
    ("search", "code onChange Voucher", "search", "onChange$Voucher", REF_DIR, []),
    ("search", "code f.request", "search", "f.request", REF_DIR, []),
    ("search", "code TenVtFromDienGiai", "search", "TenVtFromDienGiai", REF_DIR, []),
    ("search", "synonym gia ban", "search", "gia ban", REF_DIR, []),
    ("search", "synonym khach hang", "search", "khach hang", REF_DIR, []),
    ("search", "synonym excel", "search", "excel", REF_DIR, []),
    ("search", "synonym giay bao no", "search", "giay bao no", REF_DIR, []),
    ("search", "synonym phieu chi", "search", "phieu chi", REF_DIR, []),
    ("search", "noisy thue", "search", "thue", REF_DIR, []),
    ("search", "sql fsd_addfields", "search", "fsd_addfields", REF_DIR, []),
    ("search", "multi-word", "search", "dien_giai ten_vt", REF_DIR, []),
    ("search", "filter Grid ma_vt", "search", "ma_vt", REF_GRID, ["--folder", "Grid", "--limit", "5"]),
    ("search", "filter dir loai_ct", "search", "loai_ct", REF_DIR, ["--type-filter", "dir", "--limit", "5"]),
    ("search", "file name Customer", "search", "Customer", REF_DIR, []),
    # --- CONTEXT: Dir / Grid / Lookup ---
    ("context", "Dir CPTran", "context", "CPTran", REF_DIR, []),
    ("context", "Dir CDTran", "context", "CDTran", REF_DIR, []),
    ("context", "Grid Customer", "context", "Customer", REF_GRID, []),
    ("context", "Grid CPDetail", "context", "CPDetail", REF_DIR, []),
    ("context", "Lookup TransactionType", "context", "TransactionType", REF_DIR, []),
    ("context", "Filter CPTran companion", "context", "Filter/CPTran", REF_DIR, []),
    # --- NAVIGATE ---
    ("navigate", "CPTran grids", "navigate", "CPTran", REF_DIR, []),
    ("navigate", "CDTran grids", "navigate", "CDTran", REF_DIR, []),
    ("navigate", "Customer lookups", "navigate", "Customer", REF_GRID, []),
    # --- BLOCKS ---
    ("blocks", "CPTran blocks", "blocks", "CPTran", REF_DIR, []),
    ("blocks", "CPDetail blocks", "blocks", "CPDetail", REF_DIR, []),
    ("blocks", "Customer blocks", "blocks", "Customer", REF_GRID, []),
    # --- DEPENDENCIES / DEPENDENTS ---
    ("deps", "deps CPTran", "dependencies", "CPTran", REF_DIR, []),
    ("deps", "deps Customer", "dependencies", "Customer", REF_GRID, []),
    ("deps", "dependents Customer", "dependents", "Customer", REF_GRID, []),
    ("deps", "dependents TransactionType", "dependents", "TransactionType", REF_DIR, []),
    # --- ENTITY ---
    ("entity", "entity ListQuery", "entity", "ListQuery", REF_DIR, []),
    ("entity", "entity Invoice", "entity", "Invoice", REF_DIR, []),
    # --- IMPACT ---
    ("impact", "impact shared include", "impact", "Include/XML/WhenVoucherInit.xml", REF_DIR, []),
    # --- USE_CASE ---
    ("use_case", "use_case CPTran", "use_case", "CPTran", REF_DIR, []),
    ("use_case", "use_case CDTran", "use_case", "CDTran", REF_DIR, []),
    ("use_case", "use_case Customer", "use_case", "Customer", REF_GRID, []),
    # --- EDGE: not found ---
    ("edge", "missing XYZFoo", "context", "XYZFooNotExist", REF_DIR, []),
]


def run_cli(query_type: str, target: str, ref: str, extra: list) -> tuple[float, dict | str]:
    cmd = [PY, str(CLI), "query", "-t", query_type, target, "--ref", ref] + extra
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.time() - t0
    out = proc.stdout.strip()
    if proc.returncode != 0:
        return elapsed, {"error": proc.stderr or out or f"exit {proc.returncode}"}
    try:
        return elapsed, json.loads(out)
    except json.JSONDecodeError:
        return elapsed, {"raw": out[:500]}


def summarize_result(cat: str, qtype: str, data: dict) -> str:
  if "error" in data and len(data) == 1:
    return f"ERROR: {data['error'][:80]}"
  if "raw" in data:
    return f"NON-JSON: {data['raw'][:60]}"
  if qtype == "search":
    fc = len(data.get("file_matches", []))
    fld = len(data.get("field_matches", []))
    code = len(data.get("code_matches", []))
    exp = data.get("expanded_query", "")[:60]
    return f"file={fc} field={fld} code={code} | exp={exp}"
  if qtype == "context":
    grids = len(data.get("grid_details", []))
    lookups = len(data.get("lookup_references", []))
    fields = len(data.get("fields", []))
    deps = len(data.get("dependencies", []))
    enc = "[enc]" if any("Encrypted" in str(x) for x in [data]) else ""
    return f"fields={fields} grids={grids} lookups={lookups} deps={deps} {enc}"
  if qtype == "navigate":
    return (
      f"grids={len(data.get('grid_details',[]))} "
      f"retrieve={len(data.get('retrieve_sources',[]))} "
      f"lookups={len(data.get('lookup_references',[]))} "
      f"companions={len(data.get('companion_files',[]))}"
    )
  if qtype == "blocks":
    return f"sql={len(data.get('sql_blocks',[]))} js={len(data.get('js_blocks',[]))}"
  if qtype == "dependencies":
    return f"deps={len(data.get('dependencies',[]))}"
  if qtype == "dependents":
    return f"dependents={len(data.get('dependents',[]))}"
  if qtype == "entity":
    return f"decl={len(data.get('declarations',[]))} use={len(data.get('usages',[]))}"
  if qtype == "impact":
    return f"impacted={data.get('impacted_count', 0)}"
  if qtype == "use_case":
    return (
      f"table={data.get('main_db_table')} "
      f"tables={len(data.get('related_db_tables',[]))} "
      f"procs={len(data.get('stored_procedures_executed',[]))}"
    )
  return str(list(data.keys())[:5])


def main():
    rows = []
    print(f"CLI: {CLI}")
    print(f"Cases: {len(CASES)}\n")

    for cat, label, qtype, target, ref, extra in CASES:
        elapsed, data = run_cli(qtype, target, ref, extra)
        js = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
        size = len(js)
        summary = summarize_result(cat, qtype, data if isinstance(data, dict) else {"raw": js})
        rows.append((cat, label, qtype, elapsed, size, summary))
        flag = "!!" if ("ERROR" in summary or (qtype == "search" and "file=0 field=0 code=0" in summary)) else "ok"
        print(f"[{flag}] {elapsed:5.2f}s {size:6d}B | {cat:8} | {label:28} | {summary}")

    print("\n" + "=" * 90)
    print("TONG HOP THEO CATEGORY:")
    by_cat: dict[str, list] = {}
    for r in rows:
        by_cat.setdefault(r[0], []).append(r)
    for cat, items in sorted(by_cat.items()):
        avg_t = sum(x[3] for x in items) / len(items)
        avg_sz = sum(x[4] for x in items) / len(items)
        fails = sum(1 for x in items if "ERROR" in x[5] or "file=0 field=0 code=0" in x[5])
        print(f"  {cat:10} n={len(items):2} avg_time={avg_t:5.2f}s avg_size={avg_sz:7.0f}B issues={fails}")

    print(f"\nTOTAL time: {sum(r[3] for r in rows):.1f}s  TOTAL cases: {len(rows)}")
    cold = rows[0][3] if rows else 0
    warm = sum(r[3] for r in rows[1:]) / max(len(rows) - 1, 1)
    print(f"Cold(first): {cold:.2f}s  Warm(avg rest): {warm:.2f}s")


if __name__ == "__main__":
    main()
