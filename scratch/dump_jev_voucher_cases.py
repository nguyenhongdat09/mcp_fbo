"""Dump STATE+QUESTIONS payload cho NHIỀU case UR tạo chứng từ mới —
để paste vào Jev playground kiểm tra requirement_type classification
4 variants: voucher_normal_no_currency / voucher_normal_currency /
voucher_approval_no_currency / voucher_approval_currency.

Chạy:  python -X utf8 scratch/dump_jev_voucher_cases.py
Output: scratch/jev_voucher_cases.md — mỗi case 1 block STATE + QUESTIONS
        (question duy nhất cần test = requirement_type)
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool_help.service import _AGENT_CONTEXT, _build_questions, _normalize_steps
from tool_help.cards import TASK_TYPE_CATALOG, REQUIREMENT_TYPE_CATALOG

from jev_eval_cases import CASES as _RAW, DEFAULT_STEPS

# (id, UR nguyên văn, expected requirement_type) — dùng chung với jev_eval
CASES = [(c["id"], c["ur"], c["expected"]) for c in _RAW]

STEPS = DEFAULT_STEPS

lines = ["# Jev voucher-variant test payloads\n",
         "Mỗi case: paste STATE vào ô state, QUESTIONS vào ô questions.",
         "Chỉ cần trả lời `requirement_type`. Expected = cột mong đợi.\n",
         "| Case | Expected | UR |", "|---|---|---|"]
for cid, ur, exp in CASES:
    lines.append(f"| {cid} | `{exp}` | {ur[:60]}… |")
lines.append("")

for cid, ur, exp in CASES:
    steps = _normalize_steps(tuple(STEPS))
    state = {"agent_context": _AGENT_CONTEXT,
             "task_type_catalog": TASK_TYPE_CATALOG,
             "steps": steps,
             "task_requirement": ur,
             "requirement_type_catalog": REQUIREMENT_TYPE_CATALOG}
    questions = {"requirement_type": _build_questions(steps, ur)["requirement_type"]}
    lines += [f"\n## {cid} — expected `{exp}`\n",
              f"UR: {ur}\n", "### STATE\n```json",
              json.dumps(state, ensure_ascii=False, indent=1),
              "```", "### QUESTIONS\n```json",
              json.dumps(questions, ensure_ascii=False, indent=1),
              "```\n"]

out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "jev_voucher_cases.md")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print("wrote", out, f"({len(CASES)} cases)")
