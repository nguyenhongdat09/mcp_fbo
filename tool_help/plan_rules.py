"""Plan linter — luật an toàn CLAUDE.md áp lên CHUỖI step của plan.

Định tuyến chỉ trả lời "step này dùng tool gì"; linter trả lời "plan có thiếu
bước bắt buộc không" và trả ``plan_patch`` (step cần chèn + tool + call).

Hai lớp (đúng triết lý TypeSafe: Jev phán đoán hẹp, code giữ luật):
1. **Cờ per-step** — Noul hỏi Jev trong CÙNG call routing ("step có sửa
   proc không?"...). Jev tắt/lỗi → regex fallback. Thêm cờ từ task_type.
2. **Luật** — code: cờ X ở step i → cần bước Y trước/sau i; bước Y coi là
   đã có nếu task_type (top-1 ∪ alternatives) hoặc text step khớp, hoặc
   agent báo ``context.done``.

Thêm luật = thêm 1 entry vào ``RULES``; thêm cờ = thêm vào ``FLAGS``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FLAG_MIN = 0.6  # noul >= ngưỡng → cờ bật

_I = re.IGNORECASE | re.UNICODE

# name → Noul question + regex fallback + task_type tự bật cờ
FLAGS: dict[str, dict] = {
    "edits_db_object": {
        "question": "Does this step modify (ALTER/edit/fix/add logic to) an "
                    "existing stored procedure, function or view in the "
                    "database?",
        "criteria": {
            "true": "sửa/chỉnh/thêm logic vào proc/func/view có sẵn (rs_*, "
                    "zc_*, fs_*, FastBusiness$*), ALTER PROCEDURE",
            "false": "chỉ đọc/xem/tìm proc, chạy SELECT, sửa file XML, tạo "
                     "proc hoàn toàn mới",
        },
        "regex": re.compile(
            r"(sửa|chỉnh|alter|fix|thêm|bổ sung|cập nhật|update).{0,40}"
            r"(\bproc\b|procedure|function|\bfunc\b|\bview\b|\brs_|\bzc_|"
            r"\bfs_|\bfsd_|fastbusiness\$)", _I),
        "task_types": set(),
    },
    "writes_db_columns": {
        "question": "Does this step write data into specific table columns "
                    "or add columns (INSERT/UPDATE named columns, ALTER "
                    "TABLE ADD, add field to table)?",
        "criteria": {
            "true": "insert/update vào cột cụ thể, thêm cột/trường vào bảng, "
                    "SELECT INTO bảng đích với danh sách cột",
            "false": "chỉ đọc/xem dữ liệu, sửa XML, tìm file",
        },
        "regex": re.compile(
            r"\binsert\b|\bupdate\b.{0,30}(bảng|table|cột|set)|"
            r"thêm\s*(cột|trường|field).{0,20}(bảng|table|vào)|"
            r"alter\s+table|add\s+column|fsd_addfields|ghi\s*(vào\s*)?cột",
            _I),
        "task_types": {"db_add_field"},
    },
    "edits_xml_controller": {
        "question": "Does this step edit an XML controller file on disk "
                    "(Dir/Grid/Filter/Report/Lookup .xml: fields, views, "
                    "JS, SQL commands inside XML)?",
        "criteria": {
            "true": "sửa/thêm/xóa/ẩn field, view, category, JS, command SQL "
                    "trong file XML controller",
            "false": "chỉ đọc/xem/tìm trong XML, sửa proc DB, chạy SQL",
        },
        "regex": re.compile(
            r"(sửa|chỉnh|thêm|xóa|ẩn|hiện|đổi|edit|bổ sung|replace).{0,50}"
            r"(\.xml\b|controller|\bDir/|\bGrid/|\bFilter/|\bfield\b|"
            r"category|\bview\b.{0,10}xml)", _I),
        "task_types": set(),
    },
    "produces_sql_file": {
        "question": "Does this step create or modify a .sql script file "
                    "that will later be run on the database (export proc to "
                    ".sql, write/edit script, generate data script)?",
        "criteria": {
            "true": "tạo/viết/sửa/xuất file .sql (script tạo bảng, ALTER "
                    "proc, insert dữ liệu) để user F5 sau",
            "false": "chỉ đọc file .sql, chạy SELECT trực tiếp, sửa XML",
        },
        "regex": re.compile(
            r"(tạo|viết|sinh|xuất|export|clone|sửa|ghi).{0,40}"
            r"(\.sql\b|file\s*sql|script\s*sql)", _I),
        "task_types": {"new_sql_file", "paste_sql", "clone_sql",
                       "clone_data"},
    },
    "runs_sql_on_db": {
        "question": "Does this step execute a .sql script or DDL/DML that "
                    "changes the database (deploy proc, run script file, "
                    "CREATE/ALTER/INSERT/UPDATE/DELETE)?",
        "criteria": {
            "true": "chạy/deploy file .sql, ALTER/CREATE proc, "
                    "INSERT/UPDATE/DELETE lên DB",
            "false": "chỉ SELECT đọc dữ liệu, check syntax PARSEONLY, đọc "
                     "file",
        },
        "regex": re.compile(
            r"(chạy|run|execute|exec|deploy|f5|apply).{0,30}"
            r"(\.sql\b|script|file\s*sql)|deploy", _I),
        "task_types": {"db_run_file"},
    },
}

# Regex nhận ra bước "đã làm" trong step text (bổ sung cho task_type)
_DONE_RE = {
    "export_proc": re.compile(
        r"clone_things|type\s*=\s*1|paste_sql|(xuất|export|lấy|clone|dump)"
        r".{0,40}(ra\s*)?(file\s*)?\.sql|dạng\s*alter|[\w.\\/:~-]*[\\/]"
        r"[\w .\\/:~()-]*\.sql\b", _I),
    "schema_check": re.compile(
        r"cấu\s*trúc|schema|query_type\s*=\s*0|có\s*cột|check\s*cột|"
        r"kiểm\s*tra\s*cột|sys\.columns|information_schema", _I),
    "suggest_edit": re.compile(
        r"read_option\s*=\s*4|suggest_edit|old_string", _I),
    "parse_check": re.compile(
        r"read_option\s*=\s*3|parse_status|kiểm\s*tra\s*lại|đọc\s*lại", _I),
    "parseonly": re.compile(
        r"parseonly|query_type\s*=\s*3|check\s*syntax|kiểm\s*tra\s*cú\s*"
        r"pháp|cú\s*pháp", _I),
}


@dataclass
class Rule:
    id: str
    trigger: str                    # cờ kích hoạt
    position: str                   # before | after | ask_user
    satisfied_types: set = field(default_factory=set)
    satisfied_text: str = ""        # key trong _DONE_RE
    step: str = ""
    tool: str | None = None
    call: dict | None = None
    why: str = ""
    include_self: bool = True       # step trigger tự thỏa luật?


RULES: list[Rule] = [
    Rule("clone_before_alter", "edits_db_object", "before",
         {"paste_sql"}, "export_proc",
         "Xuất proc/func/view cần sửa ra file .sql dạng ALTER",
         "clone_things", {"type": 1, "mode_read": 0},
         "CLAUDE.md: lấy proc/func/view ra sửa BẮT BUỘC qua clone_things "
         "type=1, không sp_helptext/mode=full"),
    Rule("schema_check_before_write", "writes_db_columns", "before",
         {"db_object", "db_list_tables"}, "schema_check",
         "Kiểm tra bảng nguồn/đích có đủ cột sẽ ghi",
         "query_database", {"query_type": 0, "query": "<tên bảng>"},
         "CLAUDE.md: insert/update cột phải check schema bằng query_type=0, "
         "không đoán", include_self=False),
    Rule("suggest_edit_before_xml", "edits_xml_controller", "before",
         {"read_suggest_edit"}, "suggest_edit",
         "Lấy old_string chính xác của vùng cần sửa",
         "read_local_file", {"read_option": 4},
         "CLAUDE.md: XML controller lấy old_string bằng read_option=4 trước "
         "khi Edit"),
    Rule("parse_check_after_xml", "edits_xml_controller", "after",
         {"read_summary"}, "parse_check",
         "Đọc lại file vừa sửa kiểm tra js/sql parse_status",
         "read_local_file", {"read_option": 3},
         "CLAUDE.md: sau khi sửa gọi read_option=3 check parse_status",
         include_self=False),
    Rule("parseonly_before_f5", "produces_sql_file", "after",
         {"db_check_syntax"}, "parseonly",
         "Check syntax file .sql (PARSEONLY) trước khi báo user F5",
         "query_database", {"query_type": 3, "query": "<path file .sql>"},
         "CLAUDE.md: file .sql phải PARSEONLY trước khi báo user F5",
         include_self=False),
    Rule("ask_before_deploy", "runs_sql_on_db", "ask_user",
         step="Hỏi user trước khi deploy/chạy script lên DB",
         why="CLAUDE.md: không deploy proc/func hay update bảng khi chưa "
             "hỏi user"),
]


# ------------------------------------------------------------ questions/flags
def linter_questions(steps: list[str]) -> dict:
    """Noul per step × cờ — gộp vào cùng request routing."""
    out = {}
    for i, s in enumerate(steps, 1):
        for name, f in FLAGS.items():
            out[f"step{i}_flag_{name}"] = {
                "type": "noul",
                "instructions": {"question": f["question"], "step": s},
                "criteria": f["criteria"],
            }
    return out


def step_flags(steps: list[str], out_steps: list[dict],
               answers: dict | None) -> list[set[str]]:
    """Cờ bật cho từng step: Noul Jev (nếu có) ∪ task_type; regex khi
    thiếu câu trả lời Jev."""
    answers = answers or {}
    result = []
    for i, s in enumerate(steps, 1):
        tt = (out_steps[i - 1] if i - 1 < len(out_steps) else {}).get(
            "task_type")
        flags = set()
        for name, f in FLAGS.items():
            ans = answers.get(f"step{i}_flag_{name}")
            if isinstance(ans, dict) and ans.get("noul") is not None:
                on = float(ans["noul"]) >= FLAG_MIN
            else:
                on = bool(f["regex"].search(s))
            if on or tt in f["task_types"]:
                flags.add(name)
        result.append(flags)
    return result


# ---------------------------------------------------------------------- lint
def _coverage(step: dict) -> set:
    cov = {step.get("task_type")}
    cov |= {a.get("task_type") for a in step.get("alternatives") or []}
    return cov - {None}


def _satisfied(rule: Rule, idxs: range, steps: list[str],
               out_steps: list[dict], done: set) -> bool:
    if rule.satisfied_types & done or rule.id in done:
        return True
    rx = _DONE_RE.get(rule.satisfied_text)
    for j in idxs:
        if rule.satisfied_types & _coverage(out_steps[j]):
            return True
        if rx is not None and rx.search(steps[j]):
            return True
    return False


def lint_plan(steps: list[str], out_steps: list[dict],
              flags: list[set[str]], context: dict | None = None) -> dict:
    """→ {"plan_patch": [...], "patched_plan": [...]} (rỗng nếu đủ bước)."""
    done = set((context or {}).get("done") or [])
    n = len(steps)
    patches: list[dict] = []
    seen: set[tuple] = set()
    for rule in RULES:
        trig = [i for i in range(n) if rule.trigger in flags[i]]
        if not trig:
            continue
        if rule.position == "ask_user":
            i = trig[0]
            patches.append({"insert_before": i + 1, "rule": rule.id,
                            "step": rule.step, "tool": None,
                            "why": rule.why})
            continue
        # luật "after" chỉ xét step trigger CUỐI (vd PARSEONLY 1 lần sau
        # bước sửa .sql cuối cùng); "before" xét step trigger ĐẦU.
        i = trig[-1] if rule.position == "after" else trig[0]
        if rule.position == "before":
            rng = range(0, i + 1 if rule.include_self else i)
        else:
            rng = range(i if rule.include_self else i + 1, n)
        if _satisfied(rule, rng, steps, out_steps, done):
            continue
        key = (rule.id, i)
        if key in seen:
            continue
        seen.add(key)
        patch = {("insert_before" if rule.position == "before"
                  else "insert_after"): i + 1,
                 "rule": rule.id, "step": rule.step, "tool": rule.tool,
                 "call": rule.call, "why": rule.why}
        patches.append(patch)
    if not patches:
        return {}
    return {"plan_patch": patches,
            "patched_plan": _apply(steps, patches)}


def _apply(steps: list[str], patches: list[dict]) -> list[str]:
    before: dict[int, list[str]] = {}
    after: dict[int, list[str]] = {}
    for p in patches:
        label = f"[+{p['rule']}] {p['step']}"
        if "insert_before" in p:
            before.setdefault(p["insert_before"], []).append(label)
        else:
            after.setdefault(p["insert_after"], []).append(label)
    out: list[str] = []
    for i, s in enumerate(steps, 1):
        out += before.get(i, [])
        out.append(s)
        out += after.get(i, [])
    return out
