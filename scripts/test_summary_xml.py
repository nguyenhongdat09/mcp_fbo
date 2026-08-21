"""Test runner for summary_xml tool on specific XML controllers (local or UNC path).

Usage:
    python scripts/test_summary_xml.py
    python scripts/test_summary_xml.py "\\\\172.168.5.14\\CustomerPro\\HRM\\LIKSIN\\FBISP23\\App_Data\\Controllers\\Dir\\SVTran.xml"
"""

import os
import sys
import json
import time
from pathlib import Path

# Ensure UTF-8 output in Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from find_entity_by_xml.bridges import summary_xml, format_summary_xml_result

DEFAULT_UNC = r"\\172.168.5.14\CustomerPro\HRM\LIKSIN\FBISP23\App_Data\Controllers\Dir\SVTran.xml"


def main():
    target_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_UNC

    print("=" * 80)
    print(f"[TEST] SUMMARY_XML RUNNER")
    print(f"Target: {target_file}")
    print("=" * 80)

    # Check file accessibility
    if not Path(target_file).exists():
        print(f"\n[ERROR] Khong the truy cap file: {target_file}")
        print("Gợi ý:")
        print("  - Kiem tra ket noi mang / VPN toi server 172.168.5.14.")
        print("  - Dam bao thu muc share CustomerPro da duoc mo quyen truy cap.")
        sys.exit(1)

    print("\n[INFO] Dang phan tich file (flat expansion + JS/SQL AST parsing)...")
    t0 = time.perf_counter()
    result = summary_xml(target_file, use_cache=False)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"[OK] Hoan thanh trong: {elapsed_ms:.1f}ms\n")

    # Display Highlights
    meta = result.get("meta", {})
    ctrl = result.get("controller", {})
    js = result.get("js", {})
    sql = result.get("sql", {})
    fields = result.get("fields", [])

    print("-" * 80)
    print("THONG KE KET QUA:")
    print("-" * 80)
    print(f"  - File hien thi:          {result.get('file')}")
    print(f"  - Loai Controller:       {ctrl.get('folder_type')} | Bang DB: {ctrl.get('db_table')}")
    print(f"  - Tieu de:                {ctrl.get('title_v')}")
    print(f"  - So ky tu XML Flat:      {meta.get('flat_chars'):,} chars")
    print(f"  - Tokens tiet kiem (uoc): ~{meta.get('estimated_tokens_saved'):,} tokens")
    print(f"  - Parse Status JS:        {js.get('parse_status')} ({len(js.get('functions', []))} ham, {len(js.get('request_actions', []))} request actions)")
    print(f"  - Parse Status SQL:       {sql.get('parse_status')} ({len(sql.get('tables', []))} bang, {len(sql.get('procs', []))} procs, {len(sql.get('views', []))} views)")
    print(f"  - Signals SQL:            {', '.join(sql.get('signals', [])) or 'none'}")
    print(f"  - Tong so fields:         {len(fields)} fields")
    if meta.get("warnings"):
        print(f"  - Canh bao (warnings):    {', '.join(meta.get('warnings', []))}")

    # Top sample JS functions and SQL tables
    if js.get("functions"):
        print(f"\n  [JS Functions] ({min(8, len(js['functions']))}/{len(js['functions'])}):")
        for fn in js["functions"][:8]:
            print(f"      - {fn}")

    if sql.get("tables"):
        print(f"\n  [SQL Tables] ({min(8, len(sql['tables']))}/{len(sql['tables'])}):")
        for tb in sql["tables"][:8]:
            print(f"      - {tb}")

    print("\n" + "=" * 80)
    print("FORMATTED MCP RESPONSE (output tra ve Agent):")
    print("=" * 80)
    print(format_summary_xml_result(result))


if __name__ == "__main__":
    main()
