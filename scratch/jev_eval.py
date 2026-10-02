"""Golden eval harness — replay eval_cases qua Jev THẬT (config_jev.yaml)
và chấm accuracy requirement_type (+ optional step task_type).

Chạy:  python -X utf8 scratch/jev_eval.py
       python -X utf8 scratch/jev_eval.py A1 B2      # chỉ vài case
       python -X utf8 scratch/jev_eval.py --steps    # chấm cả step type

Cần config_jev.yaml hợp lệ + Jev endpoint chạy. Dùng khi sửa
requirement_type_catalog / instruction để phát hiện hồi quy.
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


def run_case(case: dict, cfg: dict, score_steps: bool) -> dict:
    steps = _normalize_steps(tuple(case.get("steps") or DEFAULT_STEPS))
    state = {"agent_context": _AGENT_CONTEXT,
             "task_type_catalog": TASK_TYPE_CATALOG,
             "steps": steps,
             "task_requirement": case["ur"],
             "requirement_type_catalog": REQUIREMENT_TYPE_CATALOG}
    res = ask_jev(cfg, state, _build_questions(steps, case["ur"]))
    ans = (res.get("answers") or {}).get("requirement_type") or {}
    got = str(ans.get("choice") or "?")
    probs = ans.get("probabilities") or {}
    top2 = sorted(probs.items(), key=lambda x: -x[1])[:3]
    row = {"id": case["id"], "expected": case["expected"], "got": got,
           "ok": got == case["expected"], "top3": top2,
           "jev_ok": res.get("ok")}
    if score_steps and case.get("expected_steps"):
        sg = []
        for i in range(1, len(steps) + 1):
            a = (res.get("answers") or {}).get(f"step{i}_tool") or {}
            sg.append(str(a.get("choice") or "?"))
        exp = case["expected_steps"]
        row["steps_got"] = sg
        row["steps_ok"] = all(e is None or g == e
                              for e, g in zip(exp, sg))
    return row


def main() -> int:
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    score_steps = "--steps" in sys.argv
    cfg = load_jev_config()
    if not cfg:
        print("KHÔNG có config_jev.yaml — không chạy được eval")
        return 2

    cases = [c for c in CASES if not only or c["id"] in only]
    rows, n_ok, n_step_ok, n_step_total = [], 0, 0, 0
    for c in cases:
        try:
            r = run_case(c, cfg, score_steps)
        except Exception as e:
            r = {"id": c["id"], "expected": c["expected"], "got": "ERR",
                 "ok": False, "top3": [], "jev_ok": False,
                 "error": str(e)}
        rows.append(r)
        n_ok += r["ok"]
        if r.get("steps_got") is not None:
            n_step_total += 1
            n_step_ok += r.get("steps_ok", False)
        mark = "OK " if r["ok"] else "MISS"
        print(f'{mark} {r["id"]:>3} exp={r["expected"]:<28} '
              f'got={r["got"]:<28} top3={r.get("top3")}'
              + (f'  steps={r.get("steps_got")}' if r.get("steps_got")
                 else ""))
        time.sleep(0.3)

    print("=" * 60)
    print(f"requirement_type: {n_ok}/{len(rows)} đúng "
          f"({100 * n_ok / max(len(rows), 1):.0f}%)")
    if n_step_total:
        print(f"steps (all-match): {n_step_ok}/{n_step_total}")
    misses = [r for r in rows if not r["ok"]]
    if misses:
        print("MISS:", ", ".join(r["id"] for r in misses))
    return 0 if not misses else 1


if __name__ == "__main__":
    sys.exit(main())
