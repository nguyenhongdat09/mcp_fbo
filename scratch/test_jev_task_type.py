"""Test Jev routing tầng task-type (tool + mode/param template).
Chạy: python scratch/test_jev_task_type.py
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

# task_type -> (mô tả cho Jev, tool, call template mặc định)
TASK_TYPES = {
    # ---- read_local_file ----
    "read_summary": ("SAFE DEFAULT first read of ONE known file: summary "
                     "map for XML controllers in Dir/Grid/Filter (JS "
                     "funcs, SQL objects, fields); auto-falls back to raw "
                     "for other files (.sql/.js/Templates/Report)",
                     "read_local_file", {"read_option": 3}),
    "read_flat": ("Read FULL expanded content of one known XML file "
                  "(entities resolved) to see every line",
                  "read_local_file", {"read_option": 2}),
    "read_raw": ("Read raw content of one known file untouched - "
                 "non-controller files (.sql/.js/.ent/.aspx) or XML not "
                 "directly under Dir/Grid/Filter (Templates, Report)",
                 "read_local_file", {"read_option": 1}),
    "read_snippet": ("Extract ONE specific block from a known file: a JS "
                     "function, SQL command/action, field, or line range",
                     "read_local_file",
                     {"symbol|block|start_line+end_line": "..."}),
    "read_suggest_edit": ("Before editing a file: locate region and get "
                          "exact old_string + diff_preview for str_replace",
                          "read_local_file", {"read_option": 4}),
    # ---- search_files ----
    "grep_content": ("Find WHICH files contain a string/keyword inside "
                     "file content (grep). Target files unknown",
                     "search_files", {"mode": "content"}),
    "find_definition": ("Find WHERE a JS symbol/function is defined",
                        "search_files",
                        {"mode": "definition", "symbol": "..."}),
    "find_references": ("List ALL usage sites of a symbol for "
                        "rename/refactor",
                        "search_files",
                        {"mode": "references", "symbol": "..."}),
    "match_filename": ("List files matching a NAME/glob only - does not "
                       "read content",
                       "search_files", {"mode": "files_only"}),
    # ---- compare_things ----
    "diff_file": ("Compare TWO known files line-by-line",
                  "compare_things",
                  {"kind": "file", "file_a": "...", "file_b": "..."}),
    "diff_folder": ("Compare TWO folders/projects - what is missing or "
                    "different",
                    "compare_things",
                    {"kind": "folder", "folder_a": "...", "folder_b": "..."}),
    "list_folder": ("List files in ONE folder (like ls/dir), no compare",
                    "compare_things",
                    {"kind": "folder", "inventory": True,
                     "folder_a": "..."}),
    "diff_xml": ("Compare XML controllers between two projects by "
                 "relative path or keyword seed",
                 "compare_things", {"kind": "xml"}),
    "diff_sql_table": ("Compare SQL objects or table schemas between two "
                       "project databases",
                       "compare_things", {"kind": "sql|table"}),
    # ---- clone_things ----
    "clone_sql": ("Copy missing SQL objects (proc/func/view/table) from "
                  "source project to target project -> one .sql file",
                  "clone_things", {"type": 0}),
    "paste_sql": ("Export a SQL object body out to a .sql file (ALTER) or "
                  "analyze it, to edit manually",
                  "clone_things", {"type": 1}),
    "clone_data": ("Export table ROWS matching a where into DELETE+INSERT "
                   ".sql script",
                   "clone_things",
                   {"type": 2, "table": "...", "where": "..."}),
    "copy_files": ("Copy/rename files or a whole controller set (suite) "
                   "between or within projects",
                   "clone_things", {"type": 3, "execute": False}),
    # ---- query_database ----
    "db_object": ("Inspect ONE DB object: table schema (CREATE TABLE) or "
                  "proc/view/func summary - knows the object name",
                  "query_database",
                  {"query_type": 0, "mode": "summary"}),
    "db_snippet": ("Extract code blocks of a known proc by keywords/zones",
                   "query_database",
                   {"query_type": 0, "mode": "snippet"}),
    "db_run_sql": ("Run a short inline SELECT/SQL statement",
                   "query_database", {"query_type": 1}),
    "db_run_file": ("Execute a .sql FILE (long script)",
                    "query_database", {"query_type": 2}),
    "db_check_syntax": ("PARSEONLY syntax-check a .sql file before deploy "
                        "- does not execute",
                        "query_database", {"query_type": 3}),
    "db_search": ("Search DB objects by name LIKE or by references "
                  "('which proc uses table/field X')",
                  "query_database", {"mode": "search"}),
    # ---- get_xml_entities ----
    "entity_content": ("View the CONTENT of named DOCTYPE entities in an "
                       "XML file",
                       "get_xml_entities", {"mode": "content"}),
    "entity_path": ("Find WHERE (file:line) entities are declared",
                    "get_xml_entities", {"mode": "path"}),
    "entity_list": ("List all entities declared in an XML file",
                    "get_xml_entities", {"mode": "list"}),
    "entity_check": ("Lint XML: undeclared &entity; used or SYSTEM entity "
                     "pointing to missing files",
                     "get_xml_entities", {"mode": "checking"}),
    # ---- query_radar ----
    "graph_query": ("Query the XML controller graph (Kuzu): which "
                    "controller calls/retrieves/uses a lookup, table or "
                    "file; master-detail relations, neighbors, clusters - "
                    "via fixed Cypher templates",
                    "query_radar", {"mode": "query"}),
    # ---- search_qlyc ----
    "ur_semantic": ("Semantic search of past user requests/tickets by "
                    "description",
                    "search_qlyc", {"query": "..."}),
    "ur_exact": ("Fetch exact ticket(s) by fcode1 (YC number) or ma_da "
                 "(project code) - bypass semantic",
                 "search_qlyc", {"fcode1|ma_da": "..."}),
    "no_match": ("None of the above fits this step", None, None),
}

# (step, expected_task_types, note)
STEPS = [
    ("Đọc summary controller Dir/CNTTCDTran.xml", {"read_summary"}, ""),
    ("Xem full nội dung file XML sau khi expand entity để sửa từng dòng",
     {"read_flat"}, ""),
    ("Lấy old_string chính xác của hàm onChange để str_replace",
     {"read_suggest_edit"}, ""),
    ("Đọc riêng hàm js tinh_tong trong file Grid",
     {"read_snippet", "read_summary"}, ""),
    ("Tìm file nào chứa chuỗi 'dmku' trong project",
     {"grep_content"}, ""),
    ("Tìm file có tên chứa 'kheuoc'",
     {"match_filename"}, ""),
    ("Tìm nơi định nghĩa hàm open$CreateVoucher",
     {"find_definition"}, ""),
    ("Liệt kê mọi nơi dùng symbol Base64 để refactor",
     {"find_references"}, ""),
    ("List xem folder Grid có những file gì",
     {"list_folder"}, ""),
    ("So sánh 2 file .ent giữa 2 project",
     {"diff_file"}, ""),
    ("So sánh folder Controllers của 2 project xem thiếu file nào",
     {"diff_folder"}, ""),
    ("Xem schema bảng dmku có những cột gì",
     {"db_object"}, ""),
    ("Chạy select top 10 dmkh xem data",
     {"db_run_sql"}, ""),
    ("Check syntax file script.sql trước khi F5",
     {"db_check_syntax"}, ""),
    ("Tìm proc nào đang dùng bảng cttt20",
     {"db_search"}, "vs grep_content"),
    ("Clone các proc thiếu từ project A sang B",
     {"clone_sql"}, ""),
    ("Lấy proc zcABC ra file .sql để sửa tay",
     {"paste_sql"}, ""),
    ("Kéo data các dòng ma_ct='DDV' của dmmagd ra file .sql",
     {"clone_data"}, ""),
    ("Copy nguyên bộ controller HD2 sang mã mới",
     {"copy_files"}, ""),
    ("Tra ticket YC00123 của dự án KHC",
     {"ur_exact"}, ""),
    ("Tìm UR tương tự về tất toán khế ước đã làm",
     {"ur_semantic"}, ""),
    ("Xem file XML này khai báo những entity gì",
     {"entity_list"}, ""),
    ("Check file XML có entity nào dùng mà chưa khai báo",
     {"entity_check"}, ""),
    ("Hỏi graph file nào đang gọi lookup dmku",
     {"graph_query"}, ""),
    ("Deploy lên production cho khách",
     {"no_match"}, ""),
    ("Trích đoạn xử lý cursor trong proc rs_TheSo",
     {"db_snippet", "read_snippet"}, "ambiguous proc-block"),
]


def call_jev(state, questions):
    body = json.dumps({"state": state, "model": "jev-latest",
                       "questions": questions}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


catalog = {k: v[0] for k, v in TASK_TYPES.items()}
state = {
    "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on "
                     "UNC paths; data = SQL Server. MCP tools available.",
    "task_type_catalog": catalog,
    "steps": [s for s, _, _ in STEPS],
}
criteria = {k: None for k in TASK_TYPES}
questions = {
    f"step{i}": {
        "type": "choice",
        "instructions": f"Which task type best describes this step: '{s}'? "
                        f"Type meanings are in state.task_type_catalog.",
        "criteria": criteria,
    }
    for i, (s, _, _) in enumerate(STEPS, 1)
}
resp = call_jev(state, questions)
ans = resp["answers"]
print(f"usage={resp.get('usage')}")
ok = 0
for i, (s, exp, note) in enumerate(STEPS, 1):
    a = ans[f"step{i}"]
    good = a["choice"] in exp
    ok += good
    tool = TASK_TYPES[a["choice"]][1] if a["choice"] in TASK_TYPES else "?"
    probs = {x: round(v, 2) for x, v in
             sorted(a["probabilities"].items(), key=lambda x: -x[1])
             if v >= 0.03}
    print(f"{'OK ' if good else 'XX '}[{i:>2}] {a['choice']:<16}"
          f"-> {str(tool):<16} cf={a['confidence']:.2f} "
          f"exp={sorted(exp)} {note}\n      {s[:60]}\n      {probs}")
print(f"---- {ok}/{len(STEPS)} hit")

# ---- batch 2: case casual/khó hơn ----
STEPS2 = [
    ("coi thử proc zcCNTTCD viết gì bên trong", {"db_object"}, "view proc"),
    ("đọc file template import trên UNC",
     {"read_raw", "read_summary"}, "non-controller file"),
    ("tôi muốn sửa field ma_td trong Dir/CNTTCDTran.xml",
     {"read_suggest_edit"}, ""),
    ("so sánh bảng dmku giữa 2 project xem lệch cột gì",
     {"diff_sql_table"}, ""),
    ("chứng từ nào đang retrieve từ danh mục khế ước",
     {"graph_query"}, "graph vs grep"),
    ("kiểm tra entity &XMLFilter; khai báo ở file nào",
     {"entity_path"}, ""),
    ("xem nội dung entity ListField trong file Grid",
     {"entity_content"}, ""),
    ("kiểm tra project mới còn thiếu file XML nào so với project mẫu",
     {"diff_xml", "diff_folder"}, "missing xml"),
    ("chạy proc lấy số chứng từ mới nhất",
     {"db_run_sql"}, "exec proc"),
    ("xem cấu trúc graph DB đang có node/relation gì",
     {"graph_query", "no_match"}, "schema mode - only option"),
    ("tìm các UR về phân bổ chi phí của dự án này",
     {"ur_semantic"}, ""),
    ("deploy file .sql này lên server cho khách",
     {"db_run_file", "no_match"}, "run script vs no_match"),
]

criteria = {k: None for k in TASK_TYPES}
state2 = dict(state)
state2["steps"] = [s for s, _, _ in STEPS2]
questions2 = {
    f"step{i}": {
        "type": "choice",
        "instructions": f"Which task type best describes this step: '{s}'? "
                        f"Type meanings are in state.task_type_catalog.",
        "criteria": criteria,
    }
    for i, (s, _, _) in enumerate(STEPS2, 1)
}
resp2 = call_jev(state2, questions2)
ans2 = resp2["answers"]
print(f"\n===== batch2 usage={resp2.get('usage')} =====")
ok2 = 0
for i, (s, exp, note) in enumerate(STEPS2, 1):
    a = ans2[f"step{i}"]
    good = a["choice"] in exp
    ok2 += good
    probs = {x: round(v, 2) for x, v in
             sorted(a["probabilities"].items(), key=lambda x: -x[1])
             if v >= 0.03}
    print(f"{'OK ' if good else 'XX '}[{i:>2}] {a['choice']:<16}"
          f"cf={a['confidence']:.2f} exp={sorted(exp)} {note}\n"
          f"      {s[:60]}\n      {probs}")
print(f"---- batch2: {ok2}/{len(STEPS2)} hit")
