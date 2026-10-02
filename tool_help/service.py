"""tool_help — route step -> task_type bằng Jev, trả usage card tĩnh.

Nguyên tắc: Jev chỉ classify task_type (Choice, criteria=null + catalog
trong state). Param giá trị (path/pattern/symbol) agent tự điền theo card.
Mọi exception bắt chặt — tool này là cứu cánh, không được crash.
"""
from __future__ import annotations

import logging
import re

from .cards import (REQUIREMENT_TYPE_CATALOG, REQUIREMENT_TYPES,
                    TASK_TYPE_CATALOG, TASK_TYPES, TOOL_PARAM_EXAMPLES,
                    card_for, template_block)
from .formatter import dumps
from .keywords import keyword_route

logger = logging.getLogger(__name__)

ALT_PROB_MIN = 0.2          # sàn tuyệt đối cho candidate
NO_MATCH_PROB = 0.9         # no_match >=90% -> "agent tự xử lý step này"
SECONDARY_PROB_MIN = 0.3    # requirement phụ (multi-intent)

_AGENT_CONTEXT = (
    "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; "
    "data = SQL Server. MCP tools available."
)

# Cache kết quả trong process: cùng (steps, task_requirement) -> cùng
# response, khỏi gọi lại Jev (catalog immutable trong process).
_RESULT_CACHE: dict = {}
_RESULT_CACHE_MAX = 200


def _normalize_steps(steps: tuple) -> list[str]:
    if len(steps) == 1 and isinstance(steps[0], (list, tuple)):
        steps = tuple(steps[0])
    return [str(s).strip() for s in steps if str(s).strip()]


def _build_questions(steps: list[str],
                     task_requirement: str = "") -> dict:
    criteria = {k: None for k in TASK_TYPE_CATALOG}
    questions = {
        f"step{i}_tool": {
            "type": "choice",
            "instructions": (
                f"task_type for step '{s}'? "
                "meanings: state.task_type_catalog"
            ),
            "criteria": criteria,
        }
        for i, s in enumerate(steps, 1)
    }
    if task_requirement:
        questions["requirement_type"] = {
            "type": "choice",
            "instructions": (
                "Classify state.task_requirement into ONE "
                "requirement_type. template types (category_*/report_*/"
                "voucher) ONLY for create-from-scratch. EXCEPTION: "
                "retrieve_flow_* also fits ADDING lay du lieu onto an "
                "existing voucher (creates new {X}Filter/{X}MultiForm/"
                "{X}MultiGrid/{X}Lookup). voucher_* by UR signals: "
                "duyet/phe duyet/trinh duyet->approval; ngoai te/ma_nt/"
                "ty gia/nguyen te->currency; both->voucher_approval_"
                "currency; UR says khong/none->no_* variant; signals "
                "unstated->'voucher'. edits/fixes/queries on existing "
                "targets or ambiguous->'none' high probability. "
                "meanings: state.requirement_type_catalog"
            ),
            "criteria": {k: None for k in REQUIREMENT_TYPE_CATALOG},
        }
    return questions


def _requirement_result(answer: dict) -> dict:
    choice = str(answer.get("choice") or "")
    probs = answer.get("probabilities") or {}
    cands = [{"task_type": k, "confidence_to_use_top": i}
             for i, (k, v) in enumerate(
                 sorted(probs.items(), key=lambda x: -x[1]), 1)
             if v > ALT_PROB_MIN and k in REQUIREMENT_TYPE_CATALOG]
    out = {"type": choice,
           "confidence_to_use_top": max(len(cands), 1)}
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


def _step_result_jev(step: str, answer: dict, cfg: dict) -> dict:
    choice = str(answer.get("choice") or "")
    probs = answer.get("probabilities") or {}
    cands = _candidates(probs)
    # confidence_to_use_top = số candidate >20% = "đáp án nằm trong
    # top-N": 1 = dùng top-1 luôn; 2/3/... = xem thêm alternatives.
    base = {"step": step, "task_type": choice,
            "confidence_to_use_top": max(len(cands), 1)}

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
    return base


def _step_result_keyword(step: str) -> dict:
    tt = keyword_route(step)
    if tt is None or card_for(tt) is None:
        return {"step": step, "task_type": "no_match",
                "note": "không có tool phù hợp — agent tự xử lý step này"}
    out = {"step": step, "task_type": tt, "router": "keyword"}
    out.update(card_for(tt))
    return out


def tool_help(*steps, context: dict | None = None,
              jev_config: dict | None = None) -> str:
    """Route các bước plan -> tool + call template + pitfalls."""
    steps = _normalize_steps(steps)
    try:
        if not steps:
            return dumps({"router": "none", "steps": [],
                          "error": "steps rỗng — truyền các bước plan, "
                                   "không truyền raw UR"})

        task_requirement = ""
        if context and context.get("task_requirement"):
            task_requirement = context["task_requirement"]

        cache_key = (tuple(steps), task_requirement, bool(jev_config))
        cached = _RESULT_CACHE.get(cache_key)
        if cached is not None:
            return cached

        state = {
            "agent_context": _AGENT_CONTEXT,
            "task_type_catalog": TASK_TYPE_CATALOG,
            "steps": steps,
        }
        if task_requirement:
            state["task_requirement"] = task_requirement
            state["requirement_type_catalog"] = REQUIREMENT_TYPE_CATALOG

        res = {"ok": False}
        if jev_config:
            try:
                from jev import ask_jev
                res = ask_jev(jev_config, state,
                              _build_questions(steps, task_requirement))
            except Exception as e:
                res = {"ok": False, "error": "jev_exception",
                       "detail": str(e)}

        out_steps: list[dict] = []
        usage = res.get("usage") or {}
        answers = res.get("answers") or {}

        if res.get("ok"):
            for i, s in enumerate(steps, 1):
                ans = answers.get(f"step{i}_tool") or {}
                out_steps.append(_step_result_jev(s, ans, jev_config))
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
                            "recommended one fails or cannot fulfill the task."),
            "steps": out_steps,
            "param_examples": param_examples,
            "jev_usage": usage}
        if router != "jev":
            payload["router"] = router   # chỉ báo khi fallback/error
        req_ans = answers.get("requirement_type")
        req_type = None
        if task_requirement and res.get("ok") and req_ans:
            payload["requirement"] = _requirement_result(req_ans)
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
        if task_requirement:
            ur_hints = skill_hints(task_requirement)
            if ur_hints:
                payload["related_skills"] = ur_hints
        # ID dạng zcxxxx/rsxxxx trong UR → gợi ý tên proc chuẩn (chèn '_').
        id_hits = list(dict.fromkeys(re.findall(
            r"\b((?:zc|rs)(?!_)[a-z0-9]{3,})\b", ur_text)))
        if id_hits:
            payload["proc_name_suggestions"] = {
                i: f"{i[:2]}_{i[2:]}" for i in id_hits}
        warns = _consistency_warnings(out_steps, req_type)
        if warns:
            payload["warnings"] = warns
        result = dumps(payload)
        if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
            _RESULT_CACHE.pop(next(iter(_RESULT_CACHE)))
        _RESULT_CACHE[cache_key] = result
        return result
    except Exception as e:  # tuyệt đối không crash
        logger.exception("tool_help error")
        return dumps({"router": "error", "steps": [
            {"step": s, "task_type": "no_match",
             "note": f"tool_help lỗi: {e} — agent tự xử lý"}
            for s in steps]})
