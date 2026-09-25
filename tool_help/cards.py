"""Task-type catalog + usage cards tĩnh.

- `desc`  : 1 câu EN đưa vào state.task_type_catalog gửi Jev (criteria=null).
- `call`  : template call mặc định — placeholder "<...>" agent tự điền.
- `required`: param bắt buộc agent phải cung cấp.
- `pitfalls`: cạm bẫy hay gặp của tool/mode đó.

Task_type map 1-1 -> (tool + mode/param mặc định). Jev chỉ chọn label;
KHÔNG generate giá trị param.
"""

TASK_TYPES = {
    # ---------------- read_local_file ----------------
    "read_summary": {
        "desc": "SAFE DEFAULT first read of ONE known file: summary map for "
                "XML controllers in Dir/Grid/Filter (JS funcs, SQL objects, "
                "fields); auto-falls back to raw for other files "
                "(.sql/.js/Templates/Report)",
        "tool": "read_local_file",
        "call": {"file_path": "<path file>", "read_option": 3},
        "required": ["file_path"],
        "pitfalls": [
            "read_option=3 chỉ summary cho .xml trực thuộc Dir/Grid/Filter; "
            "file khác tự fallback raw",
        ],
    },
    "read_flat": {
        "desc": "Read FULL expanded content of one known XML file (entities "
                "resolved) to see every line",
        "tool": "read_local_file",
        "call": {"file_path": "<path file>", "read_option": 2},
        "required": ["file_path"],
        "pitfalls": [
            "Dùng khi snippet không đủ — output dài, tốn token",
        ],
    },
    "read_raw": {
        "desc": "Read raw content of one known file untouched - "
                "non-controller files (.sql/.js/.ent/.aspx) or XML not "
                "directly under Dir/Grid/Filter (Templates, Report)",
        "tool": "read_local_file",
        "call": {"file_path": "<path file>", "read_option": 1},
        "required": ["file_path"],
        "pitfalls": [],
    },
    "read_snippet": {
        "desc": "Extract ONE specific block from a known file: a JS "
                "function, SQL command/action, field, or line range",
        "tool": "read_local_file",
        "call": {"file_path": "<path file>",
                 "symbol|block|start_line+end_line": "<selector>"},
        "required": ["file_path"],
        "pitfalls": [
            "symbol='<tên hàm JS>' hoặc block='action:<id>'/"
            "'command:<event>'/'field:<name>'/'query:<n>'",
            "Truyền 1 trong: symbol / block / start_line+end_line",
        ],
    },
    "read_suggest_edit": {
        "desc": "Before editing a file: locate region and get exact "
                "old_string + diff_preview for str_replace",
        "tool": "read_local_file",
        "call": {"file_path": "<path file>", "read_option": 4,
                 "old_string|symbol|block": "<selector>",
                 "new_string": "<code thay thế>"},
        "required": ["file_path"],
        "pitfalls": [
            "Nhiều edit 1 file → truyền edits[] (batch) thay vì selector "
            "top-level",
        ],
    },
    # ---------------- search_files ----------------
    "grep_content": {
        "desc": "Find WHICH files contain a string/keyword inside file "
                "content (grep), or which files match a criterion (e.g. "
                "controllers having an import filter). Target files "
                "unknown",
        "tool": "search_files",
        "call": {"root": "<abs path>", "pattern": "<chuỗi>",
                 "mode": "content"},
        "required": ["root", "pattern"],
        "pitfalls": [
            "mode=files_only KHÔNG đọc nội dung — chỉ match tên file; tìm "
            "chuỗi trong file phải dùng mode=content",
            "regex=True chỉ khi pattern có ký tự regex; mặc định literal",
        ],
    },
    "find_definition": {
        "desc": "Find WHERE a JS symbol/function is defined",
        "tool": "search_files",
        "call": {"root": "<abs path>", "symbol": "<tên symbol>",
                 "mode": "definition"},
        "required": ["root", "symbol"],
        "pitfalls": [],
    },
    "find_references": {
        "desc": "List ALL usage sites of a symbol for rename/refactor",
        "tool": "search_files",
        "call": {"root": "<abs path>", "symbol": "<tên symbol>",
                 "mode": "references"},
        "required": ["root", "symbol"],
        "pitfalls": [],
    },
    "match_filename": {
        "desc": "Find files by NAME/glob pattern across the project "
                "(e.g. Filter/*Import*, *.xml in Templates/Upload) - does "
                "not read content",
        "tool": "search_files",
        "call": {"root": "<abs path>", "include_glob": "<*pattern*>",
                 "mode": "files_only"},
        "required": ["root"],
        "pitfalls": [
            "KHÔNG đọc nội dung — chỉ lọc theo tên/path file",
        ],
    },
    # ---------------- compare_things ----------------
    "diff_file": {
        "desc": "Compare TWO known files line-by-line",
        "tool": "compare_things",
        "call": {"kind": "file", "file_a": "<abs path>",
                 "file_b": "<abs path>"},
        "required": ["kind", "file_a", "file_b"],
        "pitfalls": ["Không hỗ trợ .f mã hóa và .xsd"],
    },
    "diff_folder": {
        "desc": "Compare TWO folders/projects - what is missing or "
                "different",
        "tool": "compare_things",
        "call": {"kind": "folder", "folder_a": "<abs path>",
                 "folder_b": "<abs path>"},
        "required": ["kind", "folder_a", "folder_b"],
        "pitfalls": [
            "detail=True mới trả compared[] per-file; mặc định chỉ summary "
            "theo bucket",
        ],
    },
    "list_folder": {
        "desc": "ONLY list children of ONE ALREADY-KNOWN folder (like "
                "ls/dir). NOT a search tool - cannot find files by name "
                "pattern or content criteria",
        "tool": "compare_things",
        "call": {"kind": "folder", "inventory": True,
                 "folder_a": "<abs path>"},
        "required": ["kind", "folder_a", "inventory"],
        "pitfalls": ["Chỉ cần folder_a — inventory=True không so sánh"],
    },
    "diff_xml": {
        "desc": "Compare XML controllers between two projects by relative "
                "path or keyword seed",
        "tool": "compare_things",
        "call": {"kind": "xml", "project_source": "<abs path>",
                 "project_target": "<abs path>",
                 "object|seed": "<relative path hoặc từ khóa>"},
        "required": ["kind", "project_source", "project_target"],
        "pitfalls": [
            "xml_view='flat' để so sau expand entity; mặc định 'original'",
        ],
    },
    "diff_sql_table": {
        "desc": "Compare SQL objects or table schemas between two project "
                "databases",
        "tool": "compare_things",
        "call": {"kind": "sql|table", "project_source": "<abs path>",
                 "project_target": "<abs path>", "object": "<tên object>"},
        "required": ["kind", "project_source", "project_target"],
        "pitfalls": [],
    },
    # ---------------- clone_things ----------------
    "clone_sql": {
        "desc": "Copy missing SQL objects (proc/func/view/table) from "
                "source project to target project -> one .sql file",
        "tool": "clone_things",
        "call": {"type": 0, "object": "<tên object hoặc list>",
                 "project_source": "<abs path>",
                 "project_target": "<abs path>"},
        "required": ["type", "object", "project_source", "project_target"],
        "pitfalls": [
            "Target-first: chỉ xuất object THIẾU ra .sql — không deploy",
        ],
    },
    "paste_sql": {
        "desc": "Export a SQL object body out to a .sql file (ALTER) or "
                "analyze it, to edit manually",
        "tool": "clone_things",
        "call": {"type": 1, "object": "<tên proc/func/view>",
                 "project_source": "<abs path>", "mode_read": 0},
        "required": ["type", "object", "project_source"],
        "pitfalls": [
            "mode_read: 1=summary+deps không ghi file, 0=ghi .sql ALTER để "
            "sửa, 3=full body JSON (<=3 object)",
        ],
    },
    "clone_data": {
        "desc": "Export table ROWS matching a where into DELETE+INSERT "
                ".sql script",
        "tool": "clone_things",
        "call": {"type": 2, "table": "<tên bảng>", "where": "<điều kiện>",
                 "project_source": "<abs path>"},
        "required": ["type", "table", "where", "project_source"],
        "pitfalls": [
            "where không cần chữ WHERE; script có DELETE FROM + INSERT từng "
            "dòng",
        ],
    },
    "copy_files": {
        "desc": "Copy/rename files or a whole controller set (suite) "
                "between or within projects",
        "tool": "clone_things",
        "call": {"type": 3, "object": "<path|glob|suite:Old->New>",
                 "project_source": "<abs path>",
                 "project_target": "<abs path hoặc rỗng=cùng project>",
                 "execute": False},
        "required": ["type", "object", "project_source"],
        "pitfalls": [
            "execute=False (mặc định) = dry-run; execute=True mới copy",
            "overwrite cần overwrite=True + confirm_overwrite=True sau khi "
            "hỏi user",
        ],
    },
    # ---------------- query_database ----------------
    "db_object": {
        "desc": "Inspect ONE DB object: table schema (CREATE TABLE) or "
                "proc/view/func summary - knows the object name",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<tên object>", "query_type": 0,
                 "mode": "summary"},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": [
            "KHÔNG dùng mode=full chỉ để đọc proc — đó là việc của "
            "clone_things type=1",
        ],
    },
    "db_snippet": {
        "desc": "Extract code blocks of a known proc by keywords/zones",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<tên proc>", "query_type": 0,
                 "mode": "snippet", "keywords|zones": "<list>"},
        "required": ["file_path", "query", "query_type", "mode"],
        "pitfalls": [],
    },
    "db_run_sql": {
        "desc": "Run a short inline SELECT/SQL statement",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<SQL inline>", "query_type": 1},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": [],
    },
    "db_run_file": {
        "desc": "Execute a .sql FILE (long script)",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<path file .sql>", "query_type": 2},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": ["Script dài dùng type=2 thay vì paste inline"],
    },
    "db_check_syntax": {
        "desc": "PARSEONLY syntax-check a .sql file before deploy - does "
                "not execute",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<path file .sql>", "query_type": 3},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": [
            "Parse-only không check tên bảng/cột tồn tại; bỏ qua false "
            "positive 1059",
        ],
    },
    "db_search": {
        "desc": "Search DB objects by name LIKE or by references ('which "
                "proc uses table/field X')",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>", "mode": "search",
                 "object_name|references": "<pattern>"},
        "required": ["file_path", "mode"],
        "pitfalls": [
            "references = literal trong definition; object_name = LIKE "
            "pattern; cần ít nhất 1 trong 2",
        ],
    },
    # ---------------- get_xml_entities ----------------
    "entity_content": {
        "desc": "View the CONTENT of named DOCTYPE entities in an XML file",
        "tool": "get_xml_entities",
        "call": {"file_path": "<path file>", "mode": "content",
                 "entities": ["<tên entity>"]},
        "required": ["file_path", "entities"],
        "pitfalls": [],
    },
    "entity_path": {
        "desc": "Find WHERE (file:line) entities are declared",
        "tool": "get_xml_entities",
        "call": {"file_path": "<path file>", "mode": "path",
                 "entities": ["<tên entity>"]},
        "required": ["file_path", "entities"],
        "pitfalls": [],
    },
    "entity_list": {
        "desc": "List all entities declared in an XML file",
        "tool": "get_xml_entities",
        "call": {"file_path": "<path file>", "mode": "list"},
        "required": ["file_path"],
        "pitfalls": ["Không cần truyền entities khi mode=list"],
    },
    "entity_check": {
        "desc": "Lint XML: undeclared &entity; used or SYSTEM entity "
                "pointing to missing files",
        "tool": "get_xml_entities",
        "call": {"file_path": "<path file>", "mode": "checking"},
        "required": ["file_path"],
        "pitfalls": [
            "source_roots=[<abs path project mẫu>] để gợi ý entity có sẵn "
            "ở nguồn",
        ],
    },
    # ---------------- query_radar ----------------
    "graph_query": {
        "desc": "Query the XML controller graph (Kuzu): which controller "
                "calls/retrieves/uses a lookup, table or file; "
                "master-detail relations, neighbors, clusters - via fixed "
                "Cypher templates",
        "tool": "query_radar",
        "call": {"reference_file": "<abs path file XML trong Controllers>",
                 "mode": "query", "cypher_query": "<1 trong template>"},
        "required": ["reference_file", "cypher_query"],
        "pitfalls": [
            "reference_file BẮT BUỘC absolute — relative bị reject",
            "CẤM tự ghép Cypher — chỉ dùng template có sẵn",
        ],
    },
    # ---------------- search_qlyc ----------------
    "ur_semantic": {
        "desc": "Semantic search of past user requests/tickets by "
                "description",
        "tool": "search_qlyc",
        "call": {"query": "<mô tả nghiệp vụ ngắn>"},
        "required": ["query"],
        "pitfalls": [
            "Chưa thấy kết quả → lật hết page trước khi đổi query; tối đa "
            "3 cách diễn đạt/lượt",
        ],
    },
    "ur_exact": {
        "desc": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da "
                "(project code) - bypass semantic",
        "tool": "search_qlyc",
        "call": {"query": "", "fcode1|ma_da": "<mã>"},
        "required": [],
        "pitfalls": [
            "query='' + fcode1/ma_da = bypass AI, siêu nhanh",
        ],
    },
    "clone_template": {
        "desc": "Paste a BUNDLED template suite (template/<name>/ shipped "
                "with the server) into target project - copies files + "
                "renames + rewrites controller/table tokens inside",
        "tool": "clone_things",
        "call": {"type": 4, "object": "<tên template>",
                 "new_name": "<tên controller mới>",
                 "project_target": "<abs path project>",
                 "execute": False},
        "required": ["type", "object", "new_name", "project_target"],
        "pitfalls": [
            "execute=False (mặc định) = dry-run; execute=True mới ghi file",
            "object='?' để list template có sẵn",
            "File paste ra còn placeholder name_* (và {{...}} chưa fill — "
            "xem unresolved_placeholders + edit_guide trong response): "
            "agent đổi field theo UR, khớp Dir/Grid/Upload/Filter + bảng SQL",
        ],
    },
    "no_match": {
        "desc": "None of the above fits this step",
        "tool": None,
        "call": None,
        "required": [],
        "pitfalls": [],
    },
}

# Loại yêu cầu -> template dir tương ứng (None = chưa có mẫu).
# Dùng cho question 'requirement_type' khi context.task_requirement có UR.
REQUIREMENT_TYPES = {
    "category_1_key": {
        "desc": "CREATE a brand-new master/category screen with SINGLE "
                "identity PK (id column), no detail tab, optional Excel "
                "import - ONLY when the request ADDS a new category, "
                "NEVER for editing an existing one",
        "template": "category_1_key",
    },
    "category_multi_key": {
        "desc": "CREATE a brand-new master/category screen with COMPOSITE "
                "primary key (2+ key columns), no detail tab - ONLY for "
                "new-creation requests, NEVER for edits",
        "template": "category_multi_key",
    },
    "category_1_key_detail": {
        "desc": "CREATE a brand-new master/category with single PK plus a "
                "DETAIL tab (embedded Grid controller, ForeignKey link) - "
                "ONLY for new-creation requests",
        "template": "category_1_key_detail",
    },
    "category_multi_key_detail": {
        "desc": "CREATE a brand-new master/category with composite PK "
                "plus DETAIL tab(s) (embedded Grid controllers) - ONLY "
                "for new-creation requests",
        "template": "category_multi_key_detail",
    },
    "report_normal": {
        "desc": "CREATE a brand-new standard listing/detail report "
                "(Filter + Grid + Report controller, no pivot, no "
                "template-form) - ONLY for new-creation requests",
        "template": "report_normal",
    },
    "report_mau": {
        "desc": "CREATE a brand-new template-form report (Filter has "
                "'form' dropdown loading v20dmmaubc to pick report layout "
                "dynamically) - ONLY for new-creation requests",
        "template": "report_mau",
    },
    "report_pivot": {
        "desc": "CREATE a brand-new pivot/crosstab report (Grid has "
                "<pivot> rowField/columnField/dataFields) - ONLY for "
                "new-creation requests",
        "template": "report_pivot",
    },
    "voucher": {
        "desc": "CREATE a brand-new transaction voucher (chung tu: "
                "stt_rec, master-detail, phat hanh/hach toan) - ONLY for "
                "new-creation requests",
        "template": None,
    },
    "none": {
        "desc": "DEFAULT CHOICE for anything that is NOT creating a "
                "screen/report from scratch: edit/modify/add fields to an "
                "EXISTING controller, bug fix, data query, deploy, "
                "investigate - ALWAYS pick this when the target already "
                "exists or intent is ambiguous",
        "template": None,
    },
}

REQUIREMENT_TYPE_CATALOG = {k: v["desc"] for k, v in REQUIREMENT_TYPES.items()}


def template_block(req_type: str) -> dict | None:
    """Block template cho response: files + clone_call mẫu. None nếu loại
    yêu cầu chưa có mẫu."""
    tpl = REQUIREMENT_TYPES.get(req_type, {}).get("template")
    if not tpl:
        return None
    try:
        from clone_things.type4_template import template_root
        import yaml
        mf = template_root() / tpl / "manifest.yaml"
        files = []
        if mf.is_file():
            raw = (yaml.safe_load(mf.read_text(encoding="utf-8"))
                   or {}).get("files") or []
            # manifest v2: [{src, dst}] — trả dst pattern cho agent thấy
            # output shape; v1 fallback: list path string
            files = [(f.get("dst") if isinstance(f, dict) else f)
                     for f in raw]
    except Exception:
        files = []
    return {
        "dir": f"template/{tpl}",
        "files": files,
        "clone_call": {
            "tool": "clone_things", "type": 4, "object": tpl,
            "new_name": "<tên controller mới>",
            "project_target": "<abs path project>",
            "execute": False,
        },
    }

TASK_TYPE_CATALOG = {k: v["desc"] for k, v in TASK_TYPES.items()}

# Ví dụ giá trị param theo TỪNG tool — cùng tên param (vd `query`,
# `file_path`) mang nghĩa khác nhau giữa các tool nên ví dụ gắn theo tool,
# không gom theo tên param. Agent copy format này thay vì đoán.
_U = "\\\\172.168.5.14\\CustomerPro\\FBI\\CHUBB\\SP2264"
_CTR = _U + "\\App_Data\\Controllers"
TOOL_PARAM_EXAMPLES = {
    "read_local_file": {
        "file_path": _CTR + "\\Dir\\zccntttdcd.xml",
        "symbol": "fsd_TinhLai",
        "block": "command:Inserting",
        "start_line": 120, "end_line": 160,
    },
    "search_files": {
        "root": _CTR,
        "pattern": "dmku",
        "include_glob": "*kheuoc*",
        "symbol": "fn_TinhLai",
    },
    "compare_things": {
        "file_a": _CTR + "\\Dir\\zccntttdcd.xml",
        "file_b": "\\\\172.168.5.14\\CustomerPro\\FBI\\CHUBB\\SP2265"
                  "\\App_Data\\Controllers\\Dir\\zccntttdcd.xml",
        "folder_a": _CTR,
        "folder_b": "\\\\172.168.5.14\\CustomerPro\\FBI\\CHUBB\\SP2265"
                    "\\App_Data\\Controllers",
        "project_source": _U,
        "project_target": "\\\\172.168.5.14\\CustomerPro\\FBI\\CHUBB\\SP2265",
        "object": "Dir\\zccntttdcd.xml",
    },
    "clone_things": {
        "project_source": _U,
        "project_target": "\\\\172.168.5.14\\CustomerPro\\FBI\\CHUBB\\SP2265",
        "object": "dmkh",
        "table": "dmku",
        "where": "ma_cu LIKE 'TD%'",
        "path_to_pasted": _CTR + "\\Dir",
    },
    "query_database": {
        "file_path": _CTR + "\\Dir\\zccntttdcd.xml  # path BẤT KỲ trong "
                           "project — chỉ để resolve Web.config/connection",
        "query": "dmku  # tên object | 'SELECT * FROM dmku' | path .sql — "
                 "tùy query_type",
        "object_name": "%ttdcd%",
        "references": "dmku.so_ku",
        "keywords": ["cursor", "update"],
    },
    "get_xml_entities": {
        "file_path": _CTR + "\\Dir\\zccntttdcd.xml",
        "entities": ["filter", "dmdt"],
        "source_roots": [_U],
    },
    "query_radar": {
        "reference_file": _CTR + "\\Dir\\zccntttdcd.xml  # BẮT BUỘC abs",
    },
    "search_qlyc": {
        "query": "cập nhật tất toán TD CD",
        "fcode1": "YC.2024.00123",
        "ma_da": "SP2264",
    },
}


def card_for(task_type: str) -> dict | None:
    t = TASK_TYPES.get(task_type)
    if t is None or t["tool"] is None:
        return None
    card = {"tool": t["tool"], "call": t["call"],
            "required_params": t["required"]}
    if t["pitfalls"]:
        card["pitfalls"] = t["pitfalls"]
    return card
