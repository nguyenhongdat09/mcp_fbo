"""CLI script de test truc tiep summary_object voi bat ky file XML va Stored Procedure nao tren SQL Server.

Cach dung:
  python scripts/test_summary.py "<path_to_xml>" "<proc_name>"

Vi du:
  # 1. Test summary che do mac dinh (cold run, khong cache)
  python scripts/test_summary.py "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242\\App_Data\\Controllers\\Dir\\LoanContract.xml" "rs_rptInterestDetailedByLoanContract"

  # 2. Test voi mot procedure khac bat ky trong DB (vd: zc_bcthlv, ap_..., so_...)
  python scripts/test_summary.py "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242\\App_Data\\Controllers\\Dir\\LoanContract.xml" "zc_bcthlv"

  # 3. Test mode snippet voi tu khoa
  python scripts/test_summary.py "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242\\App_Data\\Controllers\\Dir\\LoanContract.xml" "rs_rptInterestDetailedByLoanContract" --mode snippet --keywords tl_th @Status ctdmku

  # 4. Test bat LRU cache de xem toc do warm-run
  python scripts/test_summary.py "\\\\172.168.5.14\\CustomerPro\\FBI\\SHOWA\\FBISP242\\App_Data\\Controllers\\Dir\\LoanContract.xml" "rs_rptInterestDetailedByLoanContract" --use-cache
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Them thu muc goc vao sys.path de import duoc cac module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from queryDatabase.bridges.summary_bridge import summary_object


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI Test Tool cho summary_object FastBusiness SQL Server",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        default=os.getenv("FBISP242_XML", r"\\172.168.5.14\CustomerPro\FBI\SHOWA\FBISP242\App_Data\Controllers\Dir\LoanContract.xml"),
        help="Duong dan toi file XML trong project FBO (de resolve Web.config)",
    )
    parser.add_argument(
        "object_name",
        nargs="?",
        default="rs_rptInterestDetailedByLoanContract",
        help="Ten Stored Procedure, Function hoac View can phan tich (vd: rs_rptInterestDetailedByLoanContract)",
    )
    parser.add_argument(
        "--mode",
        choices=["summary", "snippet", "full"],
        default="summary",
        help="Che do phan tich: summary (mac dinh), snippet, hoac full",
    )
    parser.add_argument(
        "--db-type",
        choices=["app", "sys"],
        default="app",
        help="Loai database: app (mac dinh) hoac sys",
    )
    parser.add_argument(
        "--schema",
        default="dbo",
        help="Schema mac dinh (mac dinh: dbo)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=1,
        help="Do sau de quy call graph (0-3, mac dinh: 1)",
    )
    parser.add_argument(
        "--max-objects",
        type=int,
        default=30,
        help="So luong object toi da fetch trong call graph (mac dinh: 30)",
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=None,
        help="Danh sach tu khoa cho mode snippet (vd: --keywords tl_th @Status ctdmku)",
    )
    parser.add_argument(
        "--zones",
        nargs="*",
        default=None,
        help="Danh sach zone cho mode snippet (vd: --zones header cursor processing result_set)",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        default=False,
        help="Bat LRU Cache in-memory (mac dinh: False de luon do cold-run thuc te)",
    )
    parser.add_argument(
        "--include-called-by",
        action="store_true",
        default=False,
        help="Truy van inbound dependencies (cac object khac goi toi object nay)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 85)
    print("           FASTBUSINESS MCP - SUMMARY_OBJECT LIVE TEST TOOL")
    print("=" * 85)
    print(f"  File XML Path : {args.file_path}")
    print(f"  Target Object : {args.object_name}")
    print(f"  Mode          : {args.mode}")
    print(f"  DB Type       : {args.db_type} | Schema: {args.schema}")
    print(f"  Call Depth    : {args.max_depth} | Max Objects: {args.max_objects}")
    print(f"  Use RAM Cache : {args.use_cache}")
    if args.keywords:
        print(f"  Keywords      : {args.keywords}")
    if args.zones:
        print(f"  Zones         : {args.zones}")
    print("-" * 85)
    print("  [>] Dang ket noi SQL Server va phan tich...")

    t_start = time.perf_counter()
    try:
        res = summary_object(
            file_path=args.file_path,
            object_name=args.object_name,
            mode=args.mode,
            db_type=args.db_type,
            schema=args.schema,
            max_depth=args.max_depth,
            max_objects=args.max_objects,
            keywords=args.keywords,
            zones=args.zones,
            include_called_by=args.include_called_by,
            use_cache=args.use_cache,
        )
    except Exception as e:
        print(f"\n[ERROR] Exception xay ra khi chay summary_object: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    t_total = time.perf_counter() - t_start
    total_ms = int(t_total * 1000)

    if not res.get("success"):
        print(f"\n[THAT BAI] Error: {res.get('error')}")
        print(f"  Message: {res.get('message')}")
        print("=" * 85 + "\n")
        sys.exit(1)

    meta = res.get("meta", {})
    timing = meta.get("timing", {})

    print(f"  [+] Hoan tat trong {t_total:.3f}s ({total_ms} ms)!")
    print("-" * 85)
    print(f"  Object       : {res.get('object')} ({res.get('object_type')})")
    print(f"  Database     : {res.get('database')}")
    print(f"  Parse Status : {res.get('parse_status')}")
    print(f"  Line Count   : {res.get('line_count', 0)} dong")
    print(f"  Modify Date  : {res.get('modify_date')}")
    print("-" * 85)
    print("  CHI TIET THOI GIAN TUNG CONG DOAN (TIMING BREAKDOWN)")
    print("-" * 85)

    if timing:
        for k, v in timing.items():
            if k == "total_time_ms":
                continue
            pct = (v / (total_ms or 1)) * 100
            bar = "#" * int(min(25, pct // 4))
            print(f"  - {k:<25} : {v:>7} ms ({pct:>5.1f}%) | {bar}")
        print(f"  * {'total_time_ms':<25} : {total_ms:>7} ms (100.0%)")
    else:
        print(f"  - ANTLR Parse Time         : {meta.get('parse_time_ms', 0):>7} ms")
        print(f"  * Total Execution Time     : {total_ms:>7} ms")

    print("-" * 85)
    print("  JSON RESULT TRA VE CHO AGENT:")
    print("-" * 85)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    print("=" * 85 + "\n")


if __name__ == "__main__":
    main()
