"""Golden eval harness — replay case qua Jev THẬT (config_jev.yaml).

Dựng request bằng ``tool_help.request.build_jev_request`` (cùng code
production) nên đo đúng thứ đang chạy.

Chạy:
  python -X utf8 scratch/jev_eval.py                 # 21 case requirement_type
  python -X utf8 scratch/jev_eval.py A1 B2           # chỉ vài case
  python -X utf8 scratch/jev_eval.py --steps         # chấm cả expected_steps
  python -X utf8 scratch/jev_eval.py --steps-set     # golden set cấp step
  python -X utf8 scratch/jev_eval.py --steps-set --style v2
  python -X utf8 scratch/jev_eval.py --steps-set --routing hierarchical
  python -X utf8 scratch/jev_eval.py --steps-set --shuffle 3
      # xáo thứ tự criteria 3 lần — báo step đổi winner (thiên vị option đầu)

Option ``--style`` (v1|v2) và ``--routing`` (flat|hierarchical) ghi đè
config. Dùng khi sửa catalog / instruction / cách hỏi để phát hiện hồi quy.
"""
import os
import random
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jev import ask_jev, load_jev_config
from jev_eval_cases import CASES, DEFAULT_STEPS
from jev_eval_steps import STEP_CASES
from tool_help.request import build_jev_request
from tool_help.service import _normalize_steps

_BATCH = 5  # số step / request ở --steps-set (giống plan thật 3-6 step)


def _arg(name: str, default: str) -> str:
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _shuffle_criteria(questions: dict, rnd: random.Random) -> dict:
    out = {}
    for k, q in questions.items():
        crit = q.get("criteria")
        if isinstance(crit, dict):
            items = list(crit.items())
            rnd.shuffle(items)
            q = {**q, "criteria": dict(items)}
        out[k] = q
    return out


def run_case(case: dict, cfg: dict, score_steps: bool, style: str) -> dict:
    steps = _normalize_steps(tuple(case.get("steps") or DEFAULT_STEPS))
    state, questions = build_jev_request(steps, case["ur"], style=style)
    res = ask_jev(cfg, state, questions)
    ans = (res.get("answers") or {}).get("requirement_type") or {}
    got = str(ans.get("choice") or "?")
    probs = ans.get("probabilities") or {}
    top3 = sorted(probs.items(), key=lambda x: -x[1])[:3]
    row = {"id": case["id"], "expected": case["expected"], "got": got,
           "ok": got == case["expected"], "top3": top3,
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


def _route_batch(steps: list[str], cfg: dict, style: str, routing: str,
                 rnd: random.Random | None) -> list[dict]:
    """→ per step {choice, top3, confidence} theo routing flat|hierarchical."""
    if routing == "hierarchical":
        from tool_help.hierarchical import (build_hierarchical_questions,
                                            resolve_hierarchical)
        state, _ = build_jev_request(steps, "", style=style)
        questions = build_hierarchical_questions(steps)
    else:
        state, questions = build_jev_request(steps, "", style=style)
    if rnd is not None:
        questions = _shuffle_criteria(questions, rnd)
    res = ask_jev(cfg, state, questions)
    answers = res.get("answers") or {}
    out = []
    for i in range(1, len(steps) + 1):
        if routing == "hierarchical":
            r = resolve_hierarchical(answers, i)
            out.append({"choice": r["task_type"], "top3": r["top3"],
                        "confidence": r["confidence"]})
        else:
            a = answers.get(f"step{i}_tool") or {}
            probs = a.get("probabilities") or {}
            out.append({"choice": str(a.get("choice") or "?"),
                        "top3": [k for k, _ in sorted(
                            probs.items(), key=lambda x: -x[1])[:3]],
                        "confidence": a.get("confidence")})
    return out


def run_steps_set(cfg: dict, style: str, routing: str, shuffle: int) -> int:
    from scripts.jev_feedback.reports import load_approved

    # + case tự sinh từ log (scripts.jev_feedback harvest) đã duyệt
    cases = STEP_CASES + load_approved()
    runs = max(shuffle, 0) + 1
    winners: dict[str, list[str]] = {c["id"]: [] for c in cases}
    top1 = top3 = 0
    for run in range(runs):
        rnd = random.Random(run) if run else None
        for b in range(0, len(cases), _BATCH):
            batch = cases[b:b + _BATCH]
            res = _route_batch([c["step"] for c in batch], cfg, style,
                               routing, rnd)
            for c, r in zip(batch, res):
                winners[c["id"]].append(r["choice"])
                if run:
                    continue
                hit1 = r["choice"] in c["ok"]
                hit3 = bool(set(r["top3"]) & set(c["ok"]))
                top1 += hit1
                top3 += hit3
                mark = "OK  " if hit1 else ("TOP3" if hit3 else "MISS")
                conf = r.get("confidence")
                print(f'{mark} {c["id"]} got={r["choice"]:<18} '
                      f'conf={conf if conf is None else round(conf, 2)} '
                      f'ok={c["ok"]}  | {c["step"][:70]}')
            time.sleep(0.2)
    n = len(cases)
    print("=" * 60)
    print(f"style={style} routing={routing}  top1 {top1}/{n} "
          f"({100 * top1 / n:.0f}%)  top3 {top3}/{n} ({100 * top3 / n:.0f}%)")
    if shuffle:
        flips = {k: v for k, v in winners.items() if len(set(v)) > 1}
        print(f"shuffle x{shuffle}: {len(flips)}/{n} step đổi winner theo "
              "thứ tự option")
        for k, v in flips.items():
            print(f"  {k}: {v}")
    return 0


def main() -> int:
    only = [a for a in sys.argv[1:] if not a.startswith("--")
            and a not in {_arg("--style", ""), _arg("--routing", ""),
                          _arg("--shuffle", "")}]
    cfg = load_jev_config()
    if not cfg:
        print("KHÔNG có config_jev.yaml — không chạy được eval")
        return 2
    style = _arg("--style", cfg.get("prompt_style") or "v1")
    routing = _arg("--routing", cfg.get("routing") or "flat")
    print(f"model={cfg.get('model')} style={style} routing={routing}")

    if "--steps-set" in sys.argv:
        return run_steps_set(cfg, style, routing,
                             int(_arg("--shuffle", "0")))

    score_steps = "--steps" in sys.argv
    cases = [c for c in CASES if not only or c["id"] in only]
    rows, n_ok, n_step_ok, n_step_total = [], 0, 0, 0
    for c in cases:
        try:
            r = run_case(c, cfg, score_steps, style)
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
