"""tool_help — route step -> task_type bằng Jev, trả usage card tĩnh.

Nguyên tắc: Jev chỉ classify task_type (Choice, criteria=null + catalog
trong state). Param giá trị (path/pattern/symbol) agent tự điền theo card.
Mọi exception bắt chặt — tool này là cứu cánh, không được crash.
"""
from __future__ import annotations

import logging
import re

from .cards import (REQUIREMENT_TYPE_CATALOG, REQUIREMENT_TYPES,
                    TASK_TYPES, TOOL_PARAM_EXAMPLES,
                    card_for, task_type_for_call, template_block)
from .formatter import dumps
from .keywords import keyword_route
from .hierarchical import as_flat_answer, build_hierarchical_questions
from .plan_rules import lint_plan, linter_questions, step_flags
from .skill_suggest import stage1_questions as skill_stage1_questions
from .skill_suggest import suggest as skill_suggest
from .request import AGENT_CONTEXT, build_jev_request, build_questions_v1

logger = logging.getLogger(__name__)

ALT_PROB_MIN = 0.2          # sàn tuyệt đối cho candidate
NO_MATCH_PROB = 0.9         # no_match >=90% -> "agent tự xử lý step này"
SECONDARY_PROB_MIN = 0.3    # requirement phụ (multi-intent)
CONF_ACT_DEFAULT = 0.7      # confidence >= act → dùng luôn (config ghi đè)
CONF_REVIEW_DEFAULT = 0.4   # review <= confidence < act → đối chiếu

_AGENT_CONTEXT = AGENT_CONTEXT  # giữ tên cũ cho scratch scripts

# Cache kết quả trong process: cùng (steps, task_requirement) -> cùng
# response, khỏi gọi lại Jev (catalog immutable trong process).
_RESULT_CACHE: dict = {}
_RESULT_CACHE_MAX = 200


ARGS_FIXABLE_MIN = 0.5


def _failed_ctx(context: dict | None) -> dict | None:
    """Chuẩn hóa context.failed = {tool, args, error_code, message} +
    task_type suy từ (tool, args)."""
    f = (context or {}).get("failed")
    if not isinstance(f, dict) or not f.get("tool"):
        return None
    out = {"tool": str(f["tool"]),
           "args": f.get("args") if isinstance(f.get("args"), dict) else {},
           "error_code": str(f.get("error_code") or ""),
           "message": str(f.get("message") or "")[:300]}
    out["task_type"] = f.get("task_type") or task_type_for_call(
        out["tool"], out["args"])
    return out


def _drop_option(ans: dict, option: str) -> dict:
    """Bỏ 1 option khỏi answer (routing 2 tầng không lọc được criteria
    trước như flat) và chọn lại top."""
    probs = {k: v for k, v in (ans.get("probabilities") or {}).items()
             if k != option}
    if not probs or ans.get("choice") != option:
        return {**ans, "probabilities": probs} if probs else ans
    total = sum(probs.values()) or 1.0
    probs = {k: v / total for k, v in probs.items()}
    return {**ans, "choice": max(probs, key=probs.get),
            "probabilities": probs}


def _failure_result(failed: dict, step1: dict, fix_ans: dict | None) -> dict:
    """decision fix_args (giữ tool, sửa param) | switch (task_type khác)."""
    tt_failed = failed.get("task_type")
    p = None
    if isinstance(fix_ans, dict) and fix_ans.get("noul") is not None:
        p = float(fix_ans["noul"])
    if p is None:   # Jev tắt → luật đơn giản theo error_code
        p = 0.0 if failed["error_code"] in {"symbol_not_found"} else 0.7
    out: dict = {"failed": {"tool": failed["tool"], "task_type": tt_failed,
                            "error_code": failed["error_code"] or None},
                 "args_fixable": round(p, 3)}
    if p >= ARGS_FIXABLE_MIN and tt_failed and card_for(tt_failed):
        out["decision"] = "fix_args"
        out["why"] = ("Lỗi do giá trị param — giữ tool/mode, sửa param theo "
                      "message lỗi + khối recovery trong response lỗi")
        out["next"] = {"task_type": tt_failed, **card_for(tt_failed)}
    else:
        out["decision"] = "switch"
        out["why"] = ("Tool/mode vừa dùng không làm được việc này — dùng "
                      "task_type khác (đã loại option vừa fail)")
        nxt = step1.get("task_type")
        if nxt and nxt != tt_failed and card_for(nxt):
            out["next"] = {"task_type": nxt, **card_for(nxt)}
    return out


def _context_key(context: dict | None) -> str:
    """Phần context ngoài task_requirement (path/ext/db/failed/done) vào
    cache key — cùng steps nhưng context khác phải hỏi lại Jev."""
    import json

    rest = {k: v for k, v in (context or {}).items()
            if k != "task_requirement"}
    return json.dumps(rest, sort_keys=True, ensure_ascii=False,
                      default=str) if rest else ""


def _normalize_steps(steps: tuple) -> list[str]:
    if len(steps) == 1 and isinstance(steps[0], (list, tuple)):
        steps = tuple(steps[0])
    return [str(s).strip() for s in steps if str(s).strip()]


# Tên cũ — scratch scripts (jev_ab*, dump_*) còn import.
_build_questions = build_questions_v1


def _requirement_result(answer: dict, cfg: dict | None = None) -> dict:
    choice = str(answer.get("choice") or "")
    probs = answer.get("probabilities") or {}
    cands = [{"task_type": k, "confidence_to_use_top": i}
             for i, (k, v) in enumerate(
                 sorted(probs.items(), key=lambda x: -x[1]), 1)
             if v > ALT_PROB_MIN and k in REQUIREMENT_TYPE_CATALOG]
    out = {"type": choice,
           "confidence_to_use_top": max(len(cands), 1)}
    conf = answer.get("confidence")
    decision = _decision(conf, cfg)
    if decision:
        out["confidence"] = round(float(conf), 3)
        out["decision"] = decision
        if decision != "act":
            out["decision_note"] = (
                "Jev chưa chắc loại yêu cầu — xem alternatives/"
                "secondary_requirements, hỏi lại user nếu UR mơ hồ")
    tpl = template_block(choice)
    if tpl:
        out["template"] = tpl
    elif choice and choice != "none":
        wf = REQUIREMENT_TYPES.get(choice, {}).get("workflow")
        if wf:
            out["workflow"] = wf
        else:
            out["note"] = (f"loại '{choice}' chưa có template mẫu — agent tự "
                           "tìm file tương tự trong project rồi dùng "
                           "clone_things type=3 (suite Old->New) để copy/đổi "
                           "tên, sửa nội dung tay")
    alts = [c for c in cands if c["task_type"] != choice]
    if alts:
        out["alternatives"] = alts
    clarify = REQUIREMENT_TYPES.get(choice, {}).get("clarify")
    if clarify:
        out["clarify"] = clarify
    # multi-intent: type có template HOẶC workflow (clone_existing), xác
    # suất >= ngưỡng, không phải choice → lộ ra cho UR nhiều ý
    secondary = [{"type": k, "probability": round(v, 3)}
                 for k, v in sorted(probs.items(), key=lambda x: -x[1])
                 if k != choice and v >= SECONDARY_PROB_MIN
                 and k in REQUIREMENT_TYPE_CATALOG
                 and (REQUIREMENT_TYPES.get(k, {}).get("template")
                      or REQUIREMENT_TYPES.get(k, {}).get("workflow"))]
    if secondary:
        out["secondary_requirements"] = secondary
    return out


_BALANCE_STEP = re.compile(
    r"(tính|lấy|xem|đọc|xác định|hạch toán).{0,30}(số dư|dư đầu|dư cuối|"
    r"tồn đầu|tồn cuối|công nợ|dư nợ|dư có)|"
    r"(số dư|dư|tồn)\s*(đầu|cuối)\s*kỳ|tồn kho|dư nợ|dư có|công nợ|"
    r"tồn\s*(theo\s+)?(kho|mã kho|vị trí|lô|vật tư|site|location|lot|"
    r"item)|đáo hạn|maturity|balance\$|openingbalance|"
    r"số dư (theo )?(tk|tài khoản|khách hàng|kho|khế ước|hợp đồng|"
    r"vụ việc|công trình|nhân viên|nvbh|sale)|"
    r"dư (khế ước|hợp đồng|vụ việc|nhân viên|nvbh)",
    re.IGNORECASE | re.UNICODE)

# Step text tự nói clone/copy — hậu kiểm "thiếu bước clone" phải tính cả
# text vì 1 step chỉ nhận 1 task_type (step ghép "clone suite + export proc"
# có thể route sang clone_sql mà vẫn LÀ bước clone).
_CLONE_STEP = re.compile(
    r"save[\s_-]*as|saveas\s*:|clone|copy\s+(?:theo|từ|giống|tương\s+tự|"
    r"dựa\s+trên|sang)|suite\s*:",
    re.IGNORECASE)

# Step đã nêu path .sql cụ thể (có dấu / hoặc \) → file tồn tại sẵn (vd
# clone_things type=5/6 vừa sinh ở call trước) — bỏ qua warning thiếu step
# tạo file. Chỉ "script.sql" trần (không path) vẫn warning.
_SQL_PATH_STEP = re.compile(r"[\w.\\/:~-]*[\\/][\w.\\/:~-]*\.sql\b",
                            re.IGNORECASE)


def _consistency_warnings(out_steps: list[dict],
                          req_type: str | None) -> list[str]:
    """Hậu kiểm Jev↔plan: requirement có template nhưng plan thiếu bước
    tương ứng → cảnh báo (không chặn).

    ``used`` = task_type top-1; ``used_weak`` thêm task_type trong
    alternatives — warning chỉ fire khi coverage yếu cũng không có, tránh
    false-positive khi Jev xếp step clone làm hạng 2 hoặc step ghép nhiều
    ý chỉ giữ 1 label.
    """
    warns: list[str] = []
    used = {s.get("task_type") for s in out_steps}
    used_weak = set(used) | {
        a.get("task_type")
        for s in out_steps
        for a in (s.get("alternatives") or [])
    }
    has_template = bool(req_type
                        and REQUIREMENT_TYPES.get(req_type, {}).get(
                            "template"))
    sql_tt = {"db_run_sql", "db_run_file", "db_add_field"}
    voucher_like = {k for k, v in REQUIREMENT_TYPES.items()
                    if str(v.get("template", "")).startswith("voucher")
                    or k == "voucher"} | {"retrieve_flow_parition_table",
                                         "retrieve_flow_single_table"}
    if has_template and "clone_template" not in used_weak:
        warns.append(f"requirement '{req_type}' có template nhưng plan "
                     "không có step nào route clone_template — kiểm tra "
                     "plan thiếu bước clone hay classify sai")
    if req_type in voucher_like and not (used_weak & sql_tt):
        warns.append(f"requirement '{req_type}' cần bước SQL đăng ký/"
                     "tạo bảng (voucher.sql SYS/APP) nhưng plan không có "
                     "step nào route query_database")
    if req_type == "none" and "clone_template" in used:
        warns.append("plan có step clone_template nhưng requirement=none "
                     "— kiểm tra UR có thật là tạo mới hay chỉ chỉnh sửa")
    sql_consumers = {"db_run_file", "db_check_syntax"}
    sql_producers = {"new_sql_file", "paste_sql", "clone_sql",
                     "clone_data", "clone_template", "save_as_existing"}
    step_texts = [s.get("step") or "" for s in out_steps]
    if ((used_weak & sql_consumers) and not (used_weak & sql_producers)
            and not any(_SQL_PATH_STEP.search(t) for t in step_texts)):
        warns.append("plan có step chạy/check file .sql nhưng không có "
                     "step tạo file (new_sql_file/paste_sql/clone_*/"
                     "clone_template) — nếu file chưa tồn tại, thêm step "
                     "clone_things type=5 (bỏ qua nếu file .sql đã tạo "
                     "bởi clone_things type=5/6 ở lần gọi trước)")
    if req_type == "clone_existing":
        clone_hit = bool(used_weak & {"save_as_existing", "copy_files"})
        if not clone_hit:
            clone_hit = any(
                _CLONE_STEP.search(t) for t in step_texts)
        if not clone_hit:
            warns.append("requirement 'clone_existing' (save-as từ chức "
                         "năng có sẵn) nhưng plan không có step nào route "
                         "save_as_existing/copy_files — kiểm tra plan "
                         "thiếu bước clone suite nguồn")
        if "clone_template" in used:
            warns.append("requirement 'clone_existing' (save-as) nhưng "
                         "plan có step clone_template — template chỉ cho "
                         "tạo mới từ mẫu, kiểm tra classify")
    # step nhắc số dư/tồn nhưng route sang SQL chạy tay → agent sắp tự
    # viết logic thay vì dùng proc nội bộ FastBusiness$Balance$*
    if "db_balance" not in used_weak:
        hit = [s["step"] for s in out_steps
               if _BALANCE_STEP.search(s.get("step") or "")
               and s.get("task_type") in {"db_run_sql", "db_run_file",
                                          "no_match"}]
        if hit:
            warns.append("step nhắc tính/lấy số dư-tồn-công nợ nhưng "
                         "route generic (" + "; ".join(hit) + ") — FBO "
                         "có proc nội bộ FastBusiness$Balance$*/"
                         "$OpeningBalance$*, kiểm tra route db_balance")
    return warns


def _candidates(probs: dict) -> list[dict]:
    """Mọi option >20%, sort desc — thứ tự = rank 1,2,3...
    confidence_to_use_top = số candidate = "đáp án nằm trong top-N"."""
    out = []
    for k, v in sorted(probs.items(), key=lambda x: -x[1]):
        if v > ALT_PROB_MIN and k in TASK_TYPES:
            out.append({"task_type": k, "tool": TASK_TYPES[k]["tool"],
                        "probability": round(v, 3)})
    return out


def _decision(confidence, cfg: dict | None) -> str | None:
    """3 vùng theo docs TypeSafe: act / review / fallback (None nếu Jev
    không trả confidence)."""
    if confidence is None:
        return None
    cfg = cfg or {}
    act = float(cfg.get("confidence_act") or CONF_ACT_DEFAULT)
    review = float(cfg.get("confidence_review") or CONF_REVIEW_DEFAULT)
    c = float(confidence)
    if c >= act:
        return "act"
    if c >= review:
        return "review"
    return "fallback"


def _tool_level(probs: dict) -> dict | None:
    """Gộp xác suất task_type theo tool — mức thô khi task_type không chắc
    (nhiều task_type cùng tool chia nhau xác suất)."""
    agg: dict[str, float] = {}
    for k, v in probs.items():
        tool = (TASK_TYPES.get(k) or {}).get("tool")
        if tool:
            agg[tool] = agg.get(tool, 0.0) + float(v)
    if not agg:
        return None
    tool, p = max(agg.items(), key=lambda x: x[1])
    return {"tool": tool, "probability": round(p, 3)}


_DECISION_NOTES = {
    "review": ("Jev chưa chắc task_type — đối chiếu pitfalls/required_params "
               "của top-1 và alternatives trước khi gọi"),
    "fallback": ("Jev không chắc task_type — chỉ tin mức tool (tool_level); "
                 "tự chọn mode theo step, hoặc tách step rõ hơn rồi hỏi lại"),
}


def _step_result_jev(step: str, answer: dict, cfg: dict) -> dict:
    choice = str(answer.get("choice") or "")
    probs = answer.get("probabilities") or {}
    cands = _candidates(probs)
    # confidence_to_use_top = số candidate >20% = "đáp án nằm trong
    # top-N": 1 = dùng top-1 luôn; 2/3/... = xem thêm alternatives.
    base = {"step": step, "task_type": choice,
            "confidence_to_use_top": max(len(cands), 1)}
    conf = answer.get("confidence")
    decision = _decision(conf, cfg)
    if decision:
        base["confidence"] = round(float(conf), 3)
        base["decision"] = decision

    if choice == "no_match" and probs.get("no_match", 0) >= NO_MATCH_PROB:
        base["note"] = ("không có tool phù hợp — agent tự xử lý step này "
                        "(viết file tay / thao tác web / hỏi user)")
        return base

    card = card_for(choice)
    if card is None:
        # choice lạ hoặc no_match yếu -> keyword fallback riêng step này
        return _step_result_keyword(step)

    base.update(card)
    # Alternatives = các option >20% còn lại, full card như top-1;
    # confidence_to_use_top = thứ hạng của option đó trong top-N
    alts = []
    for rank, c in enumerate(cands, 1):
        if c["task_type"] == choice:
            continue
        alt = {"task_type": c["task_type"],
               "confidence_to_use_top": rank}
        alt_card = card_for(c["task_type"])
        if alt_card:
            alt.update(alt_card)   # tool, call, required_params, pitfalls
        else:
            alt["tool"] = c["tool"]
        alts.append(alt)
    if alts:
        base["alternatives"] = alts
    if decision in _DECISION_NOTES:
        base["decision_note"] = _DECISION_NOTES[decision]
        tl = _tool_level(probs)
        if tl:
            base["tool_level"] = tl
    return base


def _step_result_keyword(step: str) -> dict:
    tt = keyword_route(step)
    if tt is None or card_for(tt) is None:
        return {"step": step, "task_type": "no_match",
                "note": "không có tool phù hợp — agent tự xử lý step này"}
    out = {"step": step, "task_type": tt, "router": "keyword"}
    out.update(card_for(tt))
    return out


def tool_help_with_meta(*steps, context: dict | None = None,
                        jev_config: dict | None = None) -> tuple[str, dict]:
    """Như ``tool_help`` nhưng trả thêm meta routing cho call log."""
    steps = _normalize_steps(steps)
    try:
        if not steps:
            return dumps({"router": "none", "steps": [],
                          "error": "steps rỗng — truyền các bước plan, "
                                   "không truyền raw UR"}), {"router": "none"}

        task_requirement = ""
        if context and context.get("task_requirement"):
            task_requirement = context["task_requirement"]

        cache_key = (tuple(steps), task_requirement, bool(jev_config),
                     _context_key(context))
        cached = _RESULT_CACHE.get(cache_key)
        if cached is not None:
            return cached

        style = str((jev_config or {}).get("prompt_style") or "v1")
        state, questions = build_jev_request(
            steps, task_requirement, context, style=style)
        hierarchical = (jev_config or {}).get("routing") == "hierarchical"
        if hierarchical:
            for i in range(1, len(steps) + 1):
                questions.pop(f"step{i}_tool", None)
            questions.update(build_hierarchical_questions(steps))
        # Định tuyến lại sau lỗi: loại option vừa fail + hỏi "sửa param là
        # đủ hay phải đổi tool" (step lỗi = steps[0])
        failed = _failed_ctx(context)
        if failed:
            state["failure"] = {k: failed[k] for k in
                                ("tool", "error_code", "message", "args")
                                if failed.get(k)}
            q1 = questions.get("step1_tool")
            if q1 and failed.get("task_type"):
                q1["criteria"] = {k: v for k, v in q1["criteria"].items()
                                  if k != failed["task_type"]}
            questions["failure_args_fixable"] = {
                "type": "noul",
                "instructions": {
                    "question": "The previous tool call for this step "
                                "failed. Would fixing parameter values "
                                "(path, name, column, block...) while "
                                "keeping the SAME tool and mode solve it?",
                    "step": steps[0], "failure": state["failure"]},
                "criteria": {
                    "true": "lỗi do giá trị param sai: sai tên/đường "
                            "dẫn/cột/bảng/block, thiếu param",
                    "false": "tool/mode không làm được việc này: cần tool "
                             "khác (vd symbol nằm ở file khác, cần tìm "
                             "trước, cần query DB thay vì đọc file)"},
            }
        # Plan linter: Noul cờ per-step hỏi chung call (song song, ~0 latency)
        questions.update(linter_questions(steps))
        # Gợi ý skill stage 1 (gate + Choice skill) cũng chung call
        skill_text = task_requirement or " ; ".join(steps)
        if jev_config:
            questions.update(skill_stage1_questions(skill_text))

        res = {"ok": False}
        if jev_config:
            try:
                from jev import ask_jev
                res = ask_jev(jev_config, state, questions)
            except Exception as e:
                res = {"ok": False, "error": "jev_exception",
                       "detail": str(e)}

        out_steps: list[dict] = []
        usage = res.get("usage") or {}
        answers = res.get("answers") or {}

        if res.get("ok"):
            for i, s in enumerate(steps, 1):
                if hierarchical:
                    ans = as_flat_answer(answers, i)
                    if i == 1 and failed and failed.get("task_type"):
                        ans = _drop_option(ans, failed["task_type"])
                else:
                    ans = answers.get(f"step{i}_tool") or {}
                res_step = _step_result_jev(s, ans, jev_config)
                out_steps.append(res_step)
            router = "jev"
        else:
            logger.warning(f"tool_help: Jev fail "
                           f"({res.get('error')}: {res.get('detail')}) "
                           f"-> keyword fallback")
            out_steps = [_step_result_keyword(s) for s in steps]
            router = "keyword"

        used = {s.get("tool") for s in out_steps} - {None}
        param_examples = {t: TOOL_PARAM_EXAMPLES[t]
                          for t in used if t in TOOL_PARAM_EXAMPLES}
        if param_examples:
            param_examples = {
                "_note": ("CHỈ LÀ VÍ DỤ format giá trị — thay mọi path "
                          "\\\\172.168.5.14\\...\\SP2264 bằng path project "
                          "HIỆN TẠI của user; đừng copy nguyên địa chỉ/tên "
                          "file trong ví dụ"),
                **param_examples}
        payload = {
            "description": ("Each step is recommended the most suitable tool "
                            "to execute. Always try the recommended tool "
                            "first (step.tool + step.call). Only fall back to "
                            "step.alternatives or another tool if the "
                            "recommended one fails or cannot fulfill the task. "
                            "confidence_to_use_top = số candidate Jev chấm "
                            ">20% (đáp án nằm trong top-N) — KHÔNG phải xác "
                            "suất đúng; luôn đối chiếu pitfalls và required_"
                            "params trước khi call."),
            "steps": out_steps,
            "param_examples": param_examples,
            "jev_usage": usage}
        if router != "jev":
            payload["router"] = router   # chỉ báo khi fallback/error
        req_ans = answers.get("requirement_type")
        req_type = None
        if task_requirement and res.get("ok") and req_ans:
            payload["requirement"] = _requirement_result(req_ans, jev_config)
            req_type = payload["requirement"].get("type")
        from tool_help.notices import collect_notices
        used_tt = {s.get("task_type") for s in out_steps} - {None}
        ur_text = " ".join([task_requirement] + steps)
        notice = collect_notices(
            used_tt, req_type, ur_text=ur_text)
        if notice:
            payload["notice"] = notice
        # related_skills: step thiết kế/sửa layout, JS, mẫu in... thường
        # route read_local_file/no_match — trỏ thẳng skill liên quan để
        # agent khỏi tự nhớ.
        from tool_help.skill_hints import skill_hints
        for s in out_steps:
            hints = skill_hints(s.get("step") or "")
            if hints:
                s["related_skills"] = hints
        ur_hints = skill_hints(task_requirement) if task_requirement else []
        sug = (skill_suggest(jev_config, skill_text, answers)
               if res.get("ok") else {})
        jev_skills = [s["name"] for s in sug.get("skills") or []]
        merged = jev_skills + [h for h in ur_hints if h not in jev_skills]
        if merged:
            payload["related_skills"] = merged
            payload["related_skills_by"] = {
                **{h: "regex" for h in ur_hints},
                **{s["name"]: f"jev (fit {s['fit']})"
                   for s in sug.get("skills") or []}}
        # ID dạng zcxxxx/rsxxxx trong UR → gợi ý tên proc chuẩn (chèn '_').
        id_hits = list(dict.fromkeys(re.findall(
            r"\b((?:zc|rs)(?!_)[a-z0-9]{3,})\b", ur_text)))
        if id_hits:
            payload["proc_name_suggestions"] = {
                i: f"{i[:2]}_{i[2:]}" for i in id_hits}
        warns = _consistency_warnings(out_steps, req_type)
        if warns:
            payload["warnings"] = warns
        flags = step_flags(steps, out_steps,
                           answers if res.get("ok") else None)
        payload.update(lint_plan(steps, out_steps, flags, context))
        if failed:
            payload["recovery"] = _failure_result(
                failed, out_steps[0] if out_steps else {},
                answers.get("failure_args_fixable") if res.get("ok")
                else None)
        if res.get("model"):
            payload["jev_model"] = res["model"]
        result = dumps(payload)
        meta = _build_meta(payload, router)
        # Chỉ cache kết quả Jev — fallback keyword do Jev lỗi tạm thời
        # không được dính cache tới lúc restart.
        if router == "jev":
            if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
                _RESULT_CACHE.pop(next(iter(_RESULT_CACHE)))
            _RESULT_CACHE[cache_key] = (result, meta)
        return result, meta
    except Exception as e:  # tuyệt đối không crash
        logger.exception("tool_help error")
        return dumps({"router": "error", "steps": [
            {"step": s, "task_type": "no_match",
             "note": f"tool_help lỗi: {e} — agent tự xử lý"}
            for s in steps]}), {"router": "error"}


def _build_meta(payload: dict, router: str) -> dict:
    """Meta gọn cho call log (không gửi agent) — đủ để ghép step↔call sau."""
    import hashlib

    routing = []
    for i, s in enumerate(payload.get("steps") or [], 1):
        routing.append({
            "i": i, "step": s.get("step"), "task_type": s.get("task_type"),
            "tool": s.get("tool"), "confidence": s.get("confidence"),
            "decision": s.get("decision"),
            "alts": [a.get("task_type") for a in s.get("alternatives") or []],
        })
    key = "|".join(r["step"] or "" for r in routing)
    meta = {
        "help_id": hashlib.sha1(key.encode("utf-8")).hexdigest()[:12],
        "router": router,
        "routing": routing,
    }
    if payload.get("jev_model"):
        meta["jev_model"] = payload["jev_model"]
    req = payload.get("requirement") or {}
    if req.get("type"):
        meta["requirement_type"] = req["type"]
    if payload.get("plan_patch"):
        meta["plan_patch_rules"] = [p.get("rule") for p in payload["plan_patch"]]
    if payload.get("related_skills"):
        meta["skills"] = payload["related_skills"]
    return meta


def tool_help(*steps, context: dict | None = None,
              jev_config: dict | None = None) -> str:
    """Route các bước plan -> tool + call template + pitfalls (JSON text)."""
    return tool_help_with_meta(*steps, context=context,
                               jev_config=jev_config)[0]
