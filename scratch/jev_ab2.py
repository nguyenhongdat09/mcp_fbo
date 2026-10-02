"""A/B cặp-đôi: build payload OLD (desc verbose + instructions cũ + sep
mặc định) vs NEW (jev_desc + instructions mới + compact sep) trên CÙNG
code version -> POST cả hai lên Jev -> so winner + Δprob từng question.

Chạy:  python -X utf8 scratch/jev_ab2.py            # chạy + in diff
       python -X utf8 scratch/jev_ab2.py BOND BAL   # chỉ vài case

Case set = golden CASES + EXTRA + STEPS_BATTERY (1 case ~38 step phủ
task families — cũng là worst-case criteria duplication).
"""
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tool_help.service import (_AGENT_CONTEXT, _build_questions,
                               _normalize_steps)
from tool_help.cards import (TASK_TYPES, REQUIREMENT_TYPES,
                             TASK_TYPE_CATALOG, REQUIREMENT_TYPE_CATALOG)
from jev import load_jev_config
from jev_eval_cases import CASES, DEFAULT_STEPS

# ---- payload OLD (mô phỏng nguyên trạng trước nén) ----
OLD_TASK_CATALOG = {k: v["desc"] for k, v in TASK_TYPES.items()}
OLD_REQ_CATALOG = {k: ({"desc": v["desc"], "examples": v["examples"]}
                       if v.get("examples") else v["desc"])
                   for k, v in REQUIREMENT_TYPES.items()}

OLD_STEP_INSTRUCTIONS = (
    "Which task type best describes this step: '{s}'? "
    "Type meanings are in state.task_type_catalog.")
OLD_REQ_INSTRUCTIONS = (
    "Classify the user requirement in state.task_requirement "
    "into ONE requirement type. IMPORTANT: template types "
    "(category_*, report_*, voucher) are ONLY for requests "
    "that CREATE a brand-new screen/report/category from "
    "scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when "
    "the request ADDS a data-retrieval (lay du lieu) feature "
    "onto an existing voucher - they still create new "
    "controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/"
    "{X}Lookup). For NEW voucher requests pick the voucher_* "
    "variant matching BOTH signals explicitly stated in the "
    "UR: duyet/phe duyet/trinh duyet -> approval variant; "
    "ngoai te/ma_nt/ty gia/nguyen te -> currency variant; "
    "both -> voucher_approval_currency; UR says khong/none of "
    "them -> the matching no_* variant; signals not mentioned "
    "at all -> generic 'voucher'. Otherwise, if the request "
    "edits/modifies/fixes/queries something that already "
    "exists, or intent is ambiguous, choose 'none' with high "
    "probability. Type meanings are in "
    "state.requirement_type_catalog.")


def _old_questions(steps, ur):
    q = {f"step{i}_tool": {
            "type": "choice",
            "instructions": OLD_STEP_INSTRUCTIONS.format(s=s),
            "criteria": {k: None for k in OLD_TASK_CATALOG}}
         for i, s in enumerate(steps, 1)}
    if ur:
        q["requirement_type"] = {
            "type": "choice",
            "instructions": OLD_REQ_INSTRUCTIONS,
            "criteria": {k: None for k in OLD_REQ_CATALOG}}
    return q


# ---- case sets ----
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
    # battery phủ task families — 38 step trong 1 call
    {"id": "BATTERY", "ur": "",
     "steps": [
         "Đọc summary file Dir/zclctt.xml xem các hàm JS và proc",
         "Đọc toàn bộ file Grid/zcgrid.xml xem từng dòng",
         "Đọc file script.sql trong folder SQL",
         "Đọc đoạn quanh hàm fsd_TinhLai trong file zclctt",
         "Lấy old_string chính xác vùng field ngay_ct để sửa",
         "Tìm file nào chứa chuỗi fsd_TinhLai trong Controllers",
         "Tìm nơi định nghĩa hàm fsd_StringToTable",
         "Tìm tất cả chỗ gọi fsd_StringToTable để refactor",
         "Tìm file Filter/*Import* trong project",
         "So sánh file a.xml và b.xml xem khác gì",
         "So sánh project A và B xem thiếu file gì",
         "Liệt kê các file trong folder Dir",
         "So XML Dir/zclctt.xml giữa 2 project",
         "So schema bảng dmvt giữa 2 database",
         "Kéo proc rs_abc từ project A sang project B",
         "Export proc zc_lctt ra file .sql để sửa",
         "Tạo file .sql mới để viết script test",
         "Clone dữ liệu mẫu bảng dmvt ra file .sql",
         "Sao chép file Dir/a.xml thành Dir/b.xml",
         "Save as báo cáo lưu chuyển tiền tệ thành báo cáo dòng tiền",
         "Xem schema bảng cdkh",
         "Lấy block INSERT trong proc zc_lctt",
         "Chạy SELECT count(*) FROM dmvt",
         "Chạy file script.sql vừa tạo trên database",
         "Check syntax file script.sql trước khi chạy",
         "Tìm proc nào đang dùng bảng cdvt",
         "Thêm cột test_col vào bảng dmvt",
         "Xem nội dung entity dmdt trong file xml",
         "Tìm entity khai báo ở file nào dòng nào",
         "Liệt kê tất cả entity trong file",
         "Check entity nào bị thiếu khai báo",
         "Tìm controller nào đang dùng lookup lk_ma_kh",
         "Tìm controller theo title Báo cáo lưu chuyển tiền tệ",
         "Tìm UR cũ về tất toán công nợ",
         "Lấy ticket YC.2024.00123",
         "Tạo báo cáo mới từ template report_normal",
         "Tính tiền lãi theo công thức mệnh giá x lãi suất",
         "Lấy số dư cuối kỳ theo kho",
     ]},
]


def _post(cfg, payload, compact):
    data = json.dumps(payload, ensure_ascii=False,
                      separators=((",", ":") if compact else None)
                      ).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg['base_url'].rstrip('/')}/v1/systemone", data=data,
        headers={"Authorization": f"Bearer {cfg['api_key']}",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=cfg.get("timeout_seconds", 15)
                                ) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body.get("answers") or {}, body.get("usage") or {}, len(data)


def _build_payload(variant, steps, ur):
    """variant='old' -> desc verbose + instr cũ; 'new' -> jev_desc + instr
    mới."""
    if variant == "old":
        tc, rc, compact = OLD_TASK_CATALOG, OLD_REQ_CATALOG, False
        questions = _old_questions(steps, ur)
    else:
        tc, rc, compact = TASK_TYPE_CATALOG, REQUIREMENT_TYPE_CATALOG, True
        questions = _build_questions(steps, ur)
    state = {"agent_context": _AGENT_CONTEXT, "task_type_catalog": tc,
             "steps": steps}
    if ur:
        state["task_requirement"] = ur
        state["requirement_type_catalog"] = rc
    return {"model": "jev-latest", "state": state,
            "questions": questions}, compact


def _top(probs, n=3):
    return sorted((probs or {}).items(), key=lambda x: -x[1])[:n]


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    cfg = load_jev_config()
    if not cfg:
        print("KHÔNG có config_jev")
        return 2
    out = {}
    tot_old_tok = tot_new_tok = tot_q = tot_mismatch = 0
    for case in CASES + EXTRA_CASES:
        if only and case["id"] not in only:
            continue
        steps = _normalize_steps(tuple(case.get("steps") or DEFAULT_STEPS))
        ur = case["ur"]
        rec = {"expected": case.get("expected"), "q": {}}
        for variant in ("old", "new"):
            payload, compact = _build_payload(variant, steps, ur)
            try:
                ans, usage, size = _post(cfg, payload, compact)
            except Exception as e:
                rec[variant] = {"error": str(e)[:120]}
                continue
            rec[variant] = {"size": size, "usage": usage, "answers": ans}
            time.sleep(0.25)
        # so sánh
        for qk, oa in (rec.get("old", {}).get("answers") or {}).items():
            na = (rec.get("new", {}).get("answers") or {}).get(qk) or {}
            oc, nc = oa.get("choice"), na.get("choice")
            op, np_ = (oa.get("probabilities") or {}), (na.get("probabilities") or {})
            tot_q += 1
            if oc != nc:
                tot_mismatch += 1
                print(f"DIFF {case['id']}/{qk}: old={oc} {_top(op)} "
                      f"-> new={nc} {_top(np_)}")
            else:
                d = abs((op.get(oc) or 0) - (np_.get(nc) or 0))
                if d > 0.25:
                    print(f"drift>0.25 {case['id']}/{qk}: {oc} "
                          f"{op.get(oc):.2f}->{np_.get(nc):.2f}")
            rec["q"][qk] = {"old": oc, "new": nc,
                            "old_top": _top(op), "new_top": _top(np_)}
        ou = rec.get("old", {}).get("usage") or {}
        nu = rec.get("new", {}).get("usage") or {}
        tot_old_tok += ou.get("input_tokens") or 0
        tot_new_tok += nu.get("input_tokens") or 0
        print(f'{case["id"]:>8} old={ou.get("input_tokens")} '
              f'new={nu.get("input_tokens")} '
              f'({100 * ((nu.get("input_tokens") or 0) - (ou.get("input_tokens") or 1)) / max(ou.get("input_tokens") or 1, 1):+.0f}%)')
        out[case["id"]] = rec
    print("=" * 60)
    print(f"questions so sánh: {tot_q} | winner khác: {tot_mismatch}")
    print(f"input_tokens: old={tot_old_tok} new={tot_new_tok} "
          f"({100 * (tot_new_tok - tot_old_tok) / max(tot_old_tok, 1):+.1f}%)")
    fn = os.path.join(os.path.dirname(__file__), "ab2_out.json")
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved", fn)
    return 0 if tot_mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
