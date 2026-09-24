"""Test Jev routing cho tool_help — KHÔNG in api_key.
Chạy: python scratch/test_jev_tool_help.py
"""
import json
import sys
import urllib.request

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFG = yaml.safe_load(open(r"E:\PythonProject\mcp_fbo\config_jev.yaml",
                        encoding="utf-8"))
API_KEY = CFG["api_key"]["jev"]
URL = "https://api.typesafe.ai/v1/systemone"

TOOL_CATALOG = {
    "query_database": "Literal SQL only: select rows, inspect table/proc/view/function schema, search DB objects by name/references, PARSEONLY check a .sql file. Not for finding or reading files.",
    "get_xml_entities": "DOCTYPE entities of an FBO XML controller: list declared entities, view entity content, find which .ent file declares an entity, lint undeclared &entity; or SYSTEM entity pointing to missing file.",
    "query_radar": "CodeGraph of XML controllers: which file calls X, master-detail/lookup/retrieve relations, neighbors/clusters around a file, count usages. Relationships BETWEEN XML files - not content, not DB.",
    "read_local_file": "Read ONE file whose path is already known (UNC): controller summary map, one JS function / SQL command / field / block, or old_string + diff_preview before editing.",
    "search_qlyc": "Past user requests/tickets (UR): by project code + request number, or semantic search for similar past work. 'Was this done before' - not code, not DB.",
    "compare_things": "Read-only compare of two projects/paths: diff XML/SQL/table/file/folder, missing/different items, or list files in one UNC folder (inventory). Does not copy.",
    "search_files": "Locate UNKNOWN files under a path: grep file content for a string, find definition/references of a symbol, match file names by glob. First step to FIND a similar object/template.",
    "clone_things": "Scaffold a NEW voucher/category/report by cloning a similar existing controller set (suite); also copy missing SQL objects, data rows, file sets between projects.",
    "no_match": "None of the tools fit this step.",
}

SHORT_CRITERIA = {
    "query_database": "Run SQL / inspect DB objects",
    "get_xml_entities": "XML DOCTYPE entity inspection/lint",
    "query_radar": "Relations between XML controller files (graph)",
    "read_local_file": "Read one known file on UNC",
    "search_qlyc": "Search past UR/ticket history",
    "compare_things": "Diff two projects / list folder inventory",
    "search_files": "Find unknown files: grep content/symbol/filename",
    "clone_things": "Clone suite/SQL/data/files between projects",
    "no_match": "None of the tools fit",
}

# (step_text, expected_tool_or_set, note)
STEPS = [
    ("Tìm xem trong dự án hiện tại đã có danh mục tương tự chưa",
     {"search_files"}, "find similar in project"),
    ("Viết script tạo bảng + view ra file .sql",
     {"no_match", "clone_things", "query_database"}, "ambiguous write-sql"),
    ("Đọc summary controller Dir/CNTTCDTran.xml",
     {"read_local_file"}, "read known file"),
    ("Xem proc zcCNTTCD có dùng bảng dmku không",
     {"query_database"}, "proc uses table"),
    ("List xem folder Grid có những file gì",
     {"compare_things"}, "inventory"),
    ("Dự án KHC từng làm UR nào về tất toán chưa",
     {"search_qlyc"}, "UR history"),
    ("Copy nguyên bộ controller HD2 sang mã mới",
     {"clone_things"}, "clone suite"),
    ("File nào đang gọi lookup dmku",
     {"query_radar", "search_files"}, "ambiguous caller"),
    ("Check file XML có entity nào chưa khai báo",
     {"get_xml_entities"}, "entity lint"),
    ("Deploy lên production cho khách",
     {"no_match"}, "negative"),
    ("coi thử chứng từ nào retrieve từ khế ước",
     {"query_radar", "search_files"}, "casual VN"),
    ("check syntax file .sql trước khi chạy",
     {"query_database"}, "parseonly"),
    ("đọc hàm js onChange trong file Grid",
     {"read_local_file"}, "read js func"),
    ("so sánh 2 project xem thiếu proc nào",
     {"compare_things"}, "diff projects"),
]


def call_jev(state, questions):
    body = json.dumps({"state": state, "model": "jev-latest",
                       "questions": questions}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def run_variant(name, use_short_criteria):
    criteria = SHORT_CRITERIA if use_short_criteria else {
        k: None for k in TOOL_CATALOG}
    state = {
        "agent_context": "Agent on FastBusiness ERP. Code = XML controllers "
                         "on UNC paths; data = SQL Server. Tools from "
                         "fastbusiness-mcp.",
        "tool_catalog": TOOL_CATALOG,
        "steps": [s for s, _, _ in STEPS],
    }
    questions = {
        f"step{i}": {
            "type": "choice",
            "instructions": f"Which single MCP tool best serves this step: "
                            f"'{s}'? Option meanings are in "
                            f"state.tool_catalog.",
            "criteria": criteria,
        }
        for i, (s, _, _) in enumerate(STEPS, 1)
    }
    resp = call_jev(state, questions)
    ans = resp["answers"]
    print(f"\n===== {name} (usage={resp.get('usage')}) =====")
    ok = 0
    for i, (s, exp, note) in enumerate(STEPS, 1):
        a = ans[f"step{i}"]
        ch, cf = a["choice"], a["confidence"]
        mark = "OK " if ch in exp else "XX "
        ok += ch in exp
        probs = {k: round(v, 2) for k, v in
                 sorted(a["probabilities"].items(), key=lambda x: -x[1])
                 if v >= 0.01}
        print(f"{mark}[{i:>2}] {ch:<18} cf={cf:.2f} exp={sorted(exp)} "
              f"| {note}\n      {s[:60]}\n      {probs}")
    print(f"---- {name}: {ok}/{len(STEPS)} hit")


run_variant("A_criteria_null", use_short_criteria=False)
run_variant("B_short_criteria", use_short_criteria=True)

UR = ("Tạo mới danh mục 'Cập nhật tất toán TD,CD': Ngày bán; Mã TD,CD "
      "lookup danh mục khế ước; Số lượng; Giá bán; Giá trị bán; Tiền gốc "
      "thu về; Tiền lãi thu về; Tiền lãi dồn tích thu về; Tổng thu về. "
      "Tất cả tự nhập, có import. Khóa chính tự tăng theo cột ID, "
      "không check trùng.")


def run_with_ur():
    """C: steps + task_requirement (UR) trong state — hinh dang production."""
    criteria = {k: None for k in TOOL_CATALOG}
    state = {
        "agent_context": "Agent on FastBusiness ERP. Code = XML controllers "
                         "on UNC paths; data = SQL Server.",
        "tool_catalog": TOOL_CATALOG,
        "task_requirement": UR,
        "steps": [
            "1. Tìm xem trong dự án hiện tại đã có danh mục tương tự chưa",
            "2. Viết script tạo bảng + view ra file .sql",
        ],
    }
    questions = {
        f"step{i}": {
            "type": "choice",
            "instructions": f"Which single MCP tool best serves this step: "
                            f"'{s}'? Option meanings in state.tool_catalog.",
            "criteria": criteria,
        }
        for i, s in enumerate(state["steps"], 1)
    }
    resp = call_jev(state, questions)
    print(f"\n===== C_steps_with_UR (usage={resp.get('usage')}) =====")
    for k, a in resp["answers"].items():
        probs = {x: round(v, 2) for x, v in
                 sorted(a["probabilities"].items(), key=lambda x: -x[1])
                 if v >= 0.01}
        print(f"{k}: {a['choice']:<18} cf={a['confidence']:.2f} {probs}")


def run_raw_ur():
    """D: raw UR khong co steps — 1 question, do regression."""
    state = {
        "agent_context": "Agent on FastBusiness ERP. Code = XML controllers "
                         "on UNC paths; data = SQL Server.",
        "tool_catalog": TOOL_CATALOG,
        "task_requirement": UR,
    }
    questions = {
        "first_tool": {
            "type": "choice",
            "instructions": "Which single MCP tool should the agent call "
                            "FIRST for this task? Option meanings in "
                            "state.tool_catalog.",
            "criteria": {k: None for k in TOOL_CATALOG},
        }
    }
    resp = call_jev(state, questions)
    print(f"\n===== D_raw_ur_no_steps (usage={resp.get('usage')}) =====")
    for k, a in resp["answers"].items():
        probs = {x: round(v, 2) for x, v in
                 sorted(a["probabilities"].items(), key=lambda x: -x[1])
                 if v >= 0.01}
        print(f"{k}: {a['choice']:<18} cf={a['confidence']:.2f} {probs}")


run_with_ur()
run_raw_ur()


REAL_STEPS = [
    ("Tra lịch sử UR xem đã từng làm danh mục tất toán TD,CD hay tương tự chưa",
     {"search_qlyc"}),
    ("Tìm cặp file Dir/Grid của danh mục khế ước hoặc danh mục tương tự "
     "trong dự án để làm mẫu",
     {"search_files"}),
    ("Đọc summary 2 file Dir/Grid mẫu vừa tìm được để xem cấu trúc field, "
     "lookup, import",
     {"read_local_file"}),
    ("Clone cặp Dir/Grid mẫu sang tên controller danh mục mới",
     {"clone_things"}),
    ("Kiểm tra file XML vừa clone có entity nào thiếu/chưa khai báo",
     {"get_xml_entities"}),
    ("Check syntax file .sql tạo bảng danh mục + PK trước khi đưa user chạy",
     {"query_database"}),
    ("Đăng ký danh mục mới lên menu Quỹ đầu tư > Tiền gửi ngân hàng",
     {"no_match"}),
]


def run_real_ur():
    """E: plan thật của agent cho UR 'Cập nhật tất toán TD,CD'."""
    criteria = {k: None for k in TOOL_CATALOG}
    state = {
        "agent_context": "Agent on FastBusiness ERP. Code = XML controllers "
                         "on UNC paths; data = SQL Server.",
        "tool_catalog": TOOL_CATALOG,
        "task_requirement": UR,
        "steps": [s for s, _ in REAL_STEPS],
    }
    questions = {
        f"step{i}": {
            "type": "choice",
            "instructions": f"Which single MCP tool best serves this step: "
                            f"'{s}'? Option meanings in state.tool_catalog.",
            "criteria": criteria,
        }
        for i, (s, _) in enumerate(REAL_STEPS, 1)
    }
    resp = call_jev(state, questions)
    ans = resp["answers"]
    print(f"\n===== E_real_plan (usage={resp.get('usage')}) =====")
    ok = 0
    for i, (s, exp) in enumerate(REAL_STEPS, 1):
        a = ans[f"step{i}"]
        mark = "OK " if a["choice"] in exp else "XX "
        ok += a["choice"] in exp
        probs = {x: round(v, 2) for x, v in
                 sorted(a["probabilities"].items(), key=lambda x: -x[1])
                 if v >= 0.02}
        print(f"{mark}[{i}] {a['choice']:<18} cf={a['confidence']:.2f} "
              f"exp={sorted(exp)}\n      {s[:70]}\n      {probs}")
    print(f"---- E: {ok}/{len(REAL_STEPS)} hit")


run_real_ur()
