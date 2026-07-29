"""Test graph cho case thue CPTran/CDTran loai 6,9."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xml_fbograph.query.engine import xml_graph_query

REF = r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Dir\CPTran.xml"


def run(label: str, query_type: str, target: str, **kwargs) -> tuple[float, dict]:
    t0 = time.time()
    result = xml_graph_query(query_type, target, REF, **kwargs)
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"[{elapsed:.2f}s] {label}: {query_type} -> {target}")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:4000])
    if len(json.dumps(result, ensure_ascii=False)) > 4000:
        print("... (truncated)")
    return elapsed, result


def main():
    times = []

    steps = [
        ("1. Map Giay bao no", "search", "giấy báo nợ", {}),
        ("2. Map Phieu chi", "search", "phiếu chi", {}),
        ("3. Context CPTran", "context", "CPTran", {}),
        ("4. Context CDTran", "context", "CDTran", {}),
        ("5. Navigate CPTran", "navigate", "CPTran", {}),
        ("6. Field ten_vt tab thue", "search", "tên hàng hóa", {"folder_filter": "Grid", "limit": 5}),
        ("7. Search thue", "search", "thuế", {"limit": 8}),
        ("8. Search dien_giai+ten_vt", "search", "dien_giai ten_vt", {"limit": 5}),
        ("9. Blocks GLTax", "blocks", "GLTax", {}),
        ("10. Context GLTax", "context", "GLTax", {}),
        ("11. Search loai_hd", "search", "loai_hd", {"type_filter": "grid", "limit": 5}),
        ("12. Dependencies CPTran", "dependencies", "CPTran", {}),
    ]

    for label, qtype, target, kwargs in steps:
        elapsed, _ = run(label, qtype, target, **kwargs)
        times.append((label, elapsed))

    print(f"\n{'='*60}")
    print("TONG KET THOI GIAN:")
    for label, elapsed in times:
        print(f"  {elapsed:6.2f}s  {label}")
    print(f"  TOTAL: {sum(t for _, t in times):.2f}s")


if __name__ == "__main__":
    main()
