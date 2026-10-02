"""A/B Jev payload — chạy bộ UR cố định, dump full answers + size ra
scratch/ab_<tag>.json để diff trước/sau khi nén catalog.

Chạy:  python -X utf8 scratch/jev_ab.py old
       python -X utf8 scratch/jev_ab.py new
       python -X utf8 scratch/jev_ab.py diff old new
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tool_help.service import (_AGENT_CONTEXT, _build_questions,
                               _normalize_steps)
from tool_help.cards import TASK_TYPE_CATALOG, REQUIREMENT_TYPE_CATALOG
from jev import load_jev_config, ask_jev
from jev_eval_cases import CASES, DEFAULT_STEPS

# Case riêng cho step-routing ngoài golden CASES (bond-maturity UR
# user test trên playground)
EXTRA_CASES = [
    {"id": "BOND",
     "ur": "Thêm mới chức năng đáo hạn Trái phiếu: liệt kê trái phiếu đến "
           "ngày đáo hạn, chọn dòng tạo bút toán hạch toán (có post sổ "
           "kho), chức năng xóa các bút toán vừa hạch toán.",
     "steps": [
         "Liệt kê trái phiếu đáo hạn theo điều kiện lọc (từ ngày, "
         "loại tài sản, đơn vị)",
         "Tính tiền lãi = mệnh giá x lãi suất năm/100/365 x số ngày "
         "kỳ lãi",
         "Tạo bút toán hạch toán đáo hạn: nợ TK ngân hàng, có TK tài "
         "sản, có TK doanh thu lãi",
         "Xóa các bút toán vừa hạch toán khi chọn dòng đã tạo",
         "Lấy số dư cuối kỳ theo kho cho báo cáo",
     ],
     "expected": "report_check"},
    {"id": "SAVEAS",
     "ur": "Thêm mới Báo cáo dòng tiền save as từ Báo cáo lưu chuyển "
           "tiền tệ theo phương pháp trực tiếp cho nhiều kỳ.",
     "steps": [
         "Tìm controller báo cáo nguồn theo title 'Báo cáo lưu chuyển "
         "tiền tệ theo phương pháp trực tiếp'",
         "Clone suite file + export proc nguồn ra file .sql mới",
         "Sửa bản clone theo yêu cầu cột và cách tính mới",
     ],
     "expected": "clone_existing"},
    {"id": "BAL",
     "ur": "Báo cáo số dư công nợ khách hàng và tồn kho theo kho/vị "
           "trí/lô/vật tư",
     "steps": [
         "Lấy số dư công nợ đầu kỳ và cuối kỳ theo khách hàng",
         "Tính tồn kho cuối kỳ theo kho vị trí lô vật tư",
         "Lấy số dư theo nhân viên bán hàng",
     ],
     "expected": "none"},
]


def run(tag: str) -> None:
    cfg = load_jev_config()
    if not cfg:
        print("KHÔNG có config_jev")
        sys.exit(2)
    out = {"tag": tag, "cases": {}}
    for case in CASES + EXTRA_CASES:
        steps = _normalize_steps(tuple(case.get("steps") or DEFAULT_STEPS))
        state = {"agent_context": _AGENT_CONTEXT,
                 "task_type_catalog": TASK_TYPE_CATALOG,
                 "steps": steps,
                 "task_requirement": case["ur"],
                 "requirement_type_catalog": REQUIREMENT_TYPE_CATALOG}
        questions = _build_questions(steps, case["ur"])
        payload = {"model": cfg.get("model"), "state": state,
                   "questions": questions}
        size = len(json.dumps(payload, ensure_ascii=False))
        res = ask_jev(cfg, state, questions)
        answers = {}
        for qk, av in (res.get("answers") or {}).items():
            answers[qk] = {"choice": av.get("choice"),
                           "confidence": av.get("confidence"),
                           "probs": av.get("probabilities")}
        out["cases"][case["id"]] = {
            "expected": case.get("expected"), "size": size,
            "usage": res.get("usage"), "answers": answers,
            "jev_ok": res.get("ok")}
        print(f'{case["id"]:>7} size={size:>6} '
              f'req={(answers.get("requirement_type") or {}).get("choice")} '
              f'usage={res.get("usage")}')
        time.sleep(0.3)
    fn = os.path.join(os.path.dirname(__file__), f"ab_{tag}.json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", fn)


def diff(a: str, b: str) -> int:
    base = os.path.dirname(__file__)
    old = json.load(open(os.path.join(base, f"ab_{a}.json"),
                         encoding="utf-8"))
    new = json.load(open(os.path.join(base, f"ab_{b}.json"),
                         encoding="utf-8"))
    n_mismatch = n_case = 0
    old_size = new_size = 0
    for cid, oc in old["cases"].items():
        nc = new["cases"].get(cid) or {}
        old_size += oc.get("size") or 0
        new_size += nc.get("size") or 0
        for qk, oa in (oc.get("answers") or {}).items():
            na = ((nc.get("answers") or {}).get(qk) or {})
            n_case += 1
            oc_, nc_ = oa.get("choice"), na.get("choice")
            if oc_ != nc_:
                n_mismatch += 1
                print(f"MISMATCH {cid}/{qk}: {a}={oc_} -> {b}={nc_}")
    print(f"questions: {n_case}, mismatch: {n_mismatch}")
    print(f"total payload: {a}={old_size} -> {b}={new_size} "
          f"({100 * (new_size - old_size) / max(old_size, 1):+.1f}%)")
    return 1 if n_mismatch else 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "diff":
        sys.exit(diff(sys.argv[2], sys.argv[3]))
    run(sys.argv[1] if len(sys.argv) > 1 else "new")
