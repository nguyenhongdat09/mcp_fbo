"""Task-type catalog + usage cards tĩnh.

- `desc`  : doc người đọc + fallback — giữ nguyên khi thêm/sửa type.
- `jev_desc` (trong _JEV_TASK_DESCS / _JEV_REQ_DESCS): bản telegraphic
  gửi Jev — CÙNG option set + CÙNG discriminator/signal keywords của
  desc, chỉ bỏ prose để nén token. Convention: mọi từ khóa VN và mọi
  mệnh đề "NOT for X" của desc phải xuất hiện dạng dense trong jev_desc
  (not:<type>). Khi thêm task/requirement type mới: thêm jev_desc vào
  dict tương ứng (test coverage bắt buộc đủ key).
- `call`  : template call mặc định — placeholder "<...>" agent tự điền.
- `required`: param bắt buộc agent phải cung cấp.
- `pitfalls`: cạm bẫy hay gặp của tool/mode đó.

Task_type map 1-1 -> (tool + mode/param mặc định). Jev chỉ chọn label;
KHÔNG generate giá trị param.
"""
from .balance_catalog import render_map as _balance_map


def _balance_map_hint() -> str:
    """Map chiều→proc nhúng vào pitfall đầu của card db_balance."""
    return _balance_map().replace("\n", " | ")


TASK_TYPES = {
    # ---------------- read_local_file ----------------
    "read_summary": {
        "desc": "Overview map of ONE WHOLE known file (JS funcs, SQL "
                "objects, fields) when you do NOT yet know which region "
                "matters. NOT for reading around a specific named "
                "field/action/symbol — that is read_snippet",
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
        "desc": "Read AROUND ONE named thing in a known file: 'quanh/around "
                "field X', action Y, JS function Z, or a line range - when "
                "the step already names the specific region to look at",
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
        "desc": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two "
                "project databases -> one .sql file of only the MISSING "
                "objects. Pick when the step says mang/kéo/copy/clone proc "
                "hoặc object từ project/DB này sang project/DB khác, hoặc "
                "'check còn thiếu object nào'",
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
        "desc": "Export a SQL object BODY (proc/func/view) - the RIGHT way "
                "to READ a whole proc or to EDIT it. Pick whenever the "
                "step is xem/lấy/sửa/chỉnh/đọc TOÀN BỘ nội dung proc - "
                "mode_read=3 trả full body JSON (không ghi file) cho "
                "đọc/phân tích, mode_read=0 ghi .sql ALTER để sửa; NOT "
                "read summary then hand-rewrite the whole proc. Also for "
                "'dump proc ra file'",
        "tool": "clone_things",
        "call": {"type": 1, "object": "<tên proc/func/view>",
                 "project_source": "<abs path>", "mode_read": 0},
        "required": ["type", "object", "project_source"],
        "pitfalls": [
            "mode_read: 1=summary+deps không ghi file, 0=ghi .sql ALTER để "
            "sửa, 3=full body JSON (<=3 object)",
        ],
    },
    "new_sql_file": {
        "desc": "Create a NEW EMPTY .sql scratch file (UTF-8 BOM) in the "
                "configured sql_temp_folder to hand-write SQL into (new "
                "proc, deploy/test script for user to F5). Pick whenever "
                "the step is tạo/mở file .sql mới, cần file .sql để viết "
                "script, viết proc/script ra file sql - NOT for exporting "
                "existing DB objects (paste_sql), cloning rows "
                "(clone_data), or running an existing .sql file "
                "(db_run_file)",
        "tool": "clone_things",
        "call": {"type": 5, "project_source": "<abs path project>"},
        "required": ["type", "project_source"],
        "pitfalls": [
            "Trả về path_to_pasted = file .sql temp (UTF-8 BOM) trong "
            "sql_temp_folder — agent Edit/Write SQL vào file đó, TUYỆT "
            "ĐỐI không tạo .sql trong workspace/project",
            "object không bắt buộc; path_to_pasted để trống = auto-temp "
            "tên theo project",
        ],
    },
    "clone_data": {
        "desc": "Export/clone table ROWS matching a condition into a "
                "DELETE+INSERT .sql script. Pick whenever the step wants "
                "data written into a .sql file: clone/copy/dump rows, tạo "
                "dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết "
                "dữ liệu vào file .sql'",
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
    "save_as_existing": {
        "desc": "SAVE-AS / copy-from-existing: create a new screen/report/"
                "voucher suite by cloning an EXISTING named function the "
                "UR references by display title or controller name "
                "(signals: 'save as', 'copy từ', 'clone từ', 'làm giống/"
                "tương tự chức năng X'). Resolves source (title search "
                "-> controller), clones the whole suite AND exports its "
                "procs to a .sql temp file. NOT for from-scratch "
                "creation (clone_template) or plain edits",
        "tool": "clone_things",
        "call": {"type": 6,
                 "object": "saveas:<ctrl|title>-><new_ctrl>",
                 "project_source": "<abs path>",
                 "project_target": "<rỗng=cùng project>",
                 "execute": False},
        "required": ["type", "object", "project_source"],
        "pitfalls": [
            "src là title tiếng Việt → 'saveas:title:<tiêu đề>-><new>'; "
            "đã biết tên controller → 'saveas:ctrl:<tên>-><new>' (hoặc "
            "tên trần)",
            "tool tự quét <title> trên disk; không thấy → HỎI USER file "
            "nguồn, đừng đoán",
            "Nhiều controller match cùng title → trả candidates, không "
            "auto-pick — hỏi user chọn rồi gọi lại bằng ctrl:",
            "Proc export ra .sql GIỮ NGUYÊN tên nguồn — agent tự đổi "
            "tên trong file (vd zc_lctt → zc_bcdt) + sửa <title v> + "
            "đăng ký menu; các yêu cầu thêm của UR (đồ thị, cách tính "
            "mới...) sửa trên bản clone sau",
            "Suite clone bắt theo tên/prefix + parse templateFile/"
            "reportFile trong Report XML + detect Main/*.aspx qua "
            "Controller=\"<ctrl>\"; .xsd luôn denied (designer sinh lại); "
            "file *Graph.xml chỉ đổi TÊN — nội dung vẫn trỏ entity nguồn, "
            "sửa tay sau clone; aspx/mẫu Excel tên lệch trong same-project "
            "save-as bị skip same-name → copy tay + đổi tên",
            "execute=False (mặc định) = dry-run; execute=True mới copy",
        ],
    },
    # ---------------- query_database ----------------
    "db_object": {
        "desc": "Inspect ONE DB object: table schema (CREATE TABLE) or "
                "proc/view/func SUMMARY (params, tables, calls) - knows "
                "the object name and only needs overview, NOT the full "
                "body to edit (that is paste_sql)",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<tên object>", "query_type": 0,
                 "mode": "summary"},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": [
            "mode=summary/snippet OK để xem overview/trích ĐOẠN; chỉ cấm "
            "mode=full để đọc — đọc TOÀN BỘ proc để phân tích/sửa → "
            "clone_things type=1 (mode_read=3 trả JSON không ghi file, "
            "mode_read=0 ghi .sql ALTER)",
            "file_path BẮT BUỘC dù chỉ query thuần DB — truyền path bất "
            "kỳ trong project để resolve connection",
        ],
    },
    "db_snippet": {
        "desc": "Extract code blocks of a known proc by keywords/zones",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<tên proc>", "query_type": 0,
                 "mode": "snippet", "keywords|zones": "<list>"},
        "required": ["file_path", "query", "query_type", "mode"],
        "pitfalls": [
            "Chỉ trích ĐOẠN theo keywords/zones — đọc TOÀN BỘ proc hoặc "
            "đọc để SỬA → clone_things type=1 (paste_sql)",
        ],
    },
    "db_run_sql": {
        "desc": "Execute a short inline SQL DIRECTLY on the DB - SELECT "
                "check data, INSERT/UPDATE/DELETE rows, run/test an "
                "existing proc (exec proc_name), deploy small DDL. NOT "
                "for: exporting/viewing proc source to edit (use "
                "paste_sql), cloning rows or test data into a .sql file "
                "(use clone_data), copying objects between projects "
                "(use clone_sql), running a long .sql FILE (use "
                "db_run_file). NOT for computing balances/stock "
                "(tinh so du, ton kho, cong no -> db_balance)",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<SQL inline>", "query_type": 1},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": [
            "file_path BẮT BUỘC dù chỉ query thuần DB — truyền path bất "
            "kỳ trong project để resolve connection",
        ],
    },
    "db_run_file": {
        "desc": "Execute a .sql FILE (long script)",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "<path file .sql>", "query_type": 2},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": [
            "Script dài dùng type=2 thay vì paste inline",
            "File .sql chưa có → tạo trước bằng clone_things type=5 "
            "(new_sql_file), không tự tạo file trong workspace",
        ],
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
            "File .sql chưa có → tạo trước bằng clone_things type=5 "
            "(new_sql_file), không tự tạo file trong workspace",
        ],
    },
    "db_balance": {
        "desc": "Compute/read BALANCES via FastBusiness INTERNAL procs "
                "(FastBusiness$Balance$<Dim>, $OpeningBalance$*) INSTEAD "
                "OF hand-writing SUM/JOIN over raw tables "
                "(r00$/cdtk$/cdkh/r70$/r90$/wrkgl/dmtk0). Pick whenever a "
                "step says tinh/lay so du, ton kho, du dau|cuoi ky, cong "
                "no, du no|du co, dao han/maturity, so du theo kho|lo|vi "
                "tri|TK|KH|hop dong|vu viec|NVBH|dau tu — including "
                "inside report/voucher procs being written. NOT for "
                "inspecting one known object (db_object), generic data "
                "check (db_run_sql), or voucher posting (fs_Post* "
                "family, different)",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>", "mode": "search",
                 "object_name": "FastBusiness$Balance$%",
                 "object_types": "P"},
        "required": ["file_path", "mode"],
        "pitfalls": [
            "Chọn proc theo chiều — " + _balance_map_hint(),
            "Params khác theo proc & version (variant *_KhanhTd, z*, "
            "_goc) → mode=summary trên DB đích verify trước khi EXEC; "
            "thiếu proc đúng chiều → báo user, đừng tự SUM bảng raw",
            "Hầu hết proc ĐỔ KẾT QUẢ VÀO #t qua dynamic SQL — caller "
            "phải CREATE TABLE #t đúng schema rồi EXEC (+SELECT * FROM "
            "#t cùng batch nếu test tay); KHÔNG đoán schema — "
            "mode=search references='<proc>' tìm report/proc đang gọi "
            "để chép call convention (@BalanceType/@ResultType/@DataType, "
            "@JoinClause/@WhereClause)",
            "Số dư ĐẦU KỲ/ghi dư = FastBusiness$OpeningBalance$* "
            "(UpdateCurrentStock/UpdateCurrentCustomerBalance/"
            "ConvertLot2Stock/ConvertCustomer2Account); helper "
            "GetBalanceDateAndPeriod — search '%$OpeningBalance$%'",
            "Post sổ chứng từ = fs_Post*Tran / Voucher$Posting$* — "
            "nhóm khác, thường do framework gọi qua flow post chứng từ",
        ],
    },
    "db_search": {
        "desc": "Search DB code objects (proc/view/func/trigger) by name "
                "LIKE or by references ('which proc uses table/field X'). "
                "NOT for listing TABLES by name (that is db_list_tables)",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>", "mode": "search",
                 "object_name|references": "<pattern>"},
        "required": ["file_path", "mode"],
        "pitfalls": [
            "references = literal trong definition; object_name = LIKE "
            "pattern; cần ít nhất 1 trong 2",
            "file_path BẮT BUỘC dù chỉ query thuần DB — truyền path bất "
            "kỳ trong project để resolve connection",
            "Whitelist mặc định KHÔNG có bảng — tìm bảng theo tên truyền "
            "object_types='U' (hoặc route db_list_tables)",
        ],
    },
    "db_list_tables": {
        "desc": "List DB TABLES (type U) by name LIKE pattern - 'liệt kê "
                "bảng tên kết thúc/bắt đầu/chứa X', 'những bảng nào dạng "
                "m81$%', 'tìm bảng *log'. NOT for schema of ONE known "
                "table (db_object), NOT for which proc uses a table "
                "(db_search)",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>", "mode": "search",
                 "object_name": "<LIKE pattern vd %$log hoặc m81$%>",
                 "object_types": "U"},
        "required": ["file_path", "mode", "object_name", "object_types"],
        "pitfalls": [
            "Chỉ tìm theo TÊN trong sys.objects — tìm bảng CHỨA CỘT X → "
            "db_run_sql query sys.columns/sys.tables",
            "Bảng không có definition → đừng truyền references (sẽ rỗng)",
            "object_name là LIKE pattern — phải tự thêm % (vd '%$log'), "
            "không truyền trần 'log'",
            "file_path BẮT BUỘC — path bất kỳ trong project để resolve "
            "connection",
        ],
    },
    "db_add_field": {
        "desc": "Add a NEW column/field to an existing DB table (thêm "
                "trường/cột vào bảng, chứng từ, danh mục). ALSO pick this "
                "whenever a step mentions writing ALTER TABLE / adding "
                "columns via SQL - redirect to proc fsd_addFields, NEVER "
                "raw ALTER TABLE",
        "tool": "query_database",
        "call": {"file_path": "<path trong project>",
                 "query": "exec fsd_addFields '<table|partition$>',"
                          "'<field>','<type>'",
                 "query_type": 1},
        "required": ["file_path", "query", "query_type"],
        "pitfalls": [
            "Bảng PHÂN KỲ (m**/d**/c**$YYYYMM): exec fsd_addFields "
            "'d21$','dvt_ebs','varchar(16)' — pattern có $ add vào mọi "
            "bảng kỳ",
            "Bảng thường (dmkh, dmvt...): exec fsd_addFields "
            "'dmkh','dvt_ebs','varchar(16)'",
            "KHÔNG viết ALTER TABLE tay — fsd_addFields xử lý phân kỳ + "
            "chuẩn hệ thống",
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
    # ---------------- find_by_title (search_files) ----------------
    "find_by_title": {
        "desc": "Locate WHICH controller files implement an existing "
                "screen/report named by DISPLAY TITLE (tiêu đề tiếng "
                "Việt trong <title v=...>, vd 'Báo cáo lưu chuyển tiền "
                "tệ theo phương pháp trực tiếp') - when the step only "
                "needs to FIND the source, not clone it yet (cloning = "
                "save_as_existing)",
        "tool": "search_files",
        "call": {"root": "<abs path>\\App_Data\\Controllers",
                 "pattern": "<cụm title>", "mode": "content",
                 "include_glob": "*.xml"},
        "required": ["root", "pattern"],
        "pitfalls": [
            "root rộng (~5k file) bị truncated max_files — ưu tiên thư "
            "mục Dir/Report/Filter, pattern ngắn đặc trưng của title",
            "Không thấy → project có thể chỉ có .f (encrypted, title "
            "không đọc được) — báo user hỏi file .xml nguồn",
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
                "renames + rewrites controller/table tokens inside. ALSO "
                "pick this when the step is 'tạo mới báo cáo/màn hình/"
                "danh mục/chức năng/chứng từ (controller suite mới)' - "
                "kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+"
                "MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/"
                "Filter/Query/Report/Approval + aspx + sql) - new suites "
                "come from a template, not hand-written files. NOT for "
                "save-as/copy-from-existing (UR names a source function "
                "-> save_as_existing)",
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
        "desc": "NONE of the above fits - ONLY for pure manual work with "
                "no tool: business reasoning, writing file content by "
                "hand. NOT for SQL authoring/execution (db_run_sql/"
                "db_run_file), NOT for creating a new empty .sql file "
                "(new_sql_file), NOT for creating a new screen/report "
                "suite (clone_template), NOT for save-as/copying an "
                "existing function (save_as_existing), NOT for editing "
                "XML files (read_suggest_edit), NOT for computing "
                "balances via internal procs (db_balance)",
        "tool": None,
        "call": None,
        "required": [],
        "pitfalls": [],
    },
}

# Bản nén (telegraphic) của desc gửi lên Jev — cùng discriminator/signal
# set, không thêm/bớt option. Chi tiết convention xem docstring đầu file.
_JEV_TASK_DESCS = {
    "read_summary": "whole known file overview map: JS funcs/SQL objects/"
                    "fields when region unknown; not:named symbol/region "
                    "(read_snippet)",
    "read_flat": "full expanded content of one known XML (entities "
                 "resolved), every line",
    "read_raw": "raw content of one known file: non-controller .sql/.js/"
                ".ent/.aspx or XML outside Dir/Grid/Filter (Templates/"
                "Report)",
    "read_snippet": "read around ONE named thing in known file: quanh/"
                    "around field|action|JS func|line range — step "
                    "already names the region",
    "read_suggest_edit": "before editing XML/source file on disk: "
                         "locate region -> exact old_string + "
                         "diff_preview for str_replace; not:DB proc "
                         "edit (paste_sql exports to .sql first)",
    "grep_content": "which files contain string/keyword inside content "
                    "(grep) or match criterion; target files unknown",
    "find_definition": "where a JS symbol/function is defined",
    "find_references": "all usage sites of a symbol (rename/refactor)",
    "match_filename": "files by NAME/glob (Filter/*Import*, Templates/"
                      "*.xml); does not read content",
    "diff_file": "diff TWO known files line-by-line",
    "diff_folder": "diff TWO folders/projects: missing|different",
    "list_folder": "list children of ONE known folder (ls/dir); "
                   "not:search by name/content",
    "diff_xml": "diff XML controllers across projects by relative path|"
                "keyword seed",
    "diff_sql_table": "diff SQL objects|table schemas across project DBs",
    "clone_sql": "copy SQL objects (proc/func/view/table) project->"
                 "project -> .sql of only MISSING objects; signals:mang/"
                 "keo/copy/clone proc|object sang project/DB khac, check "
                 "thieu object",
    "paste_sql": "read WHOLE proc body or export proc/func/view -> .sql "
                 "ALTER to edit; signals:xem/lay/sua/chinh/doc TOAN BO noi "
                 "dung proc, dump proc ra file; mode_read=3 JSON-only for "
                 "read, 0 writes .sql; not:summary-only (db_object), "
                 "extract section (db_snippet)",
    "new_sql_file": "create NEW EMPTY .sql (UTF-8 BOM) in sql_temp_"
                    "folder to hand-write proc/deploy/test script; "
                    "signals:tao/mo file .sql moi, can file .sql de viet "
                    "script, viet proc/script ra file sql; not:export "
                    "existing object (paste_sql), clone rows "
                    "(clone_data), run existing file (db_run_file)",
    "clone_data": "export table ROWS by condition -> DELETE+INSERT .sql "
                  "script; signals:clone/copy/dump rows, tao du lieu "
                  "mau/test data, move data DB->DB, viet du lieu vao "
                  "file .sql",
    "copy_files": "copy/rename files or whole controller suite between|"
                  "within projects",
    "save_as_existing": "save-as/copy EXISTING named function -> new "
                        "suite: resolve title|ctrl -> clone suite + "
                        "export procs .sql temp; signals:save as, copy "
                        "tu, clone tu, giong/tuong tu chuc nang X; "
                        "not:from-scratch (clone_template), plain edits",
    "db_object": "inspect ONE known DB object: table schema (CREATE "
                 "TABLE)|proc/view/func summary (params, tables, "
                 "calls); not:full body to edit (paste_sql)",
    "db_snippet": "extract code blocks of a known proc by keywords|"
                  "zones",
    "db_run_sql": "run short inline SQL on DB: SELECT check, INSERT/"
                  "UPDATE/DELETE rows, exec existing proc, small DDL; "
                  "not:export proc source (paste_sql), clone rows/"
                  "test data (clone_data), copy objects across "
                  "projects (clone_sql), long .sql FILE (db_run_file), "
                  "so du/ton kho/cong no (db_balance)",
    "db_run_file": "execute a .sql FILE (long script)",
    "db_check_syntax": "PARSEONLY syntax-check a .sql file; not execute",
    "db_balance": "balances/stock via internal procs FastBusiness$"
                  "Balance$<Dim>/$OpeningBalance$* INSTEAD of hand "
                  "SUM/JOIN raw tables (r00$/cdtk$/cdkh/r70$/r90$/wrkgl/"
                  "dmtk0); signals:tinh/lay so du, ton kho, du dau|"
                  "cuoi ky, cong no, du no|du co, dao han/maturity, so "
                  "du theo kho|lo|vi tri|TK|KH|hop dong|vu viec|NVBH|"
                  "dau tu — incl. inside report/voucher procs; not:"
                  "one known object (db_object), generic check "
                  "(db_run_sql), fs_Post* posting",
    "db_search": "search DB code objects (proc/view/func/trigger) by "
                 "name LIKE|references ('which proc uses table/field "
                 "X'); not:list tables by name (db_list_tables)",
    "db_list_tables": "list DB TABLES (type U) by name LIKE — signals: "
                      "liet ke/danh sach/tim bang ten ket thuc|bat dau|"
                      "chua X, nhung bang nao dang m81$%, tim bang *log; "
                      "not:schema one known table (db_object), proc "
                      "using table (db_search)",
    "db_add_field": "add column/field to existing table (them truong/"
                    "cot vao bang); also when step writes ALTER TABLE/"
                    "adds columns -> fsd_addFields, never raw ALTER",
    "entity_content": "content of named DOCTYPE entities in XML",
    "entity_path": "where (file:line) entities declared",
    "entity_list": "list all entities declared in XML",
    "entity_check": "lint XML: undeclared &entity; used|SYSTEM entity->"
                    "missing files",
    "find_by_title": "find controller files by DISPLAY TITLE (tieu de "
                     "VN trong <title v=...>) — only when step names a "
                     "VN display title; find only, cloning="
                     "save_as_existing",
    "ur_semantic": "semantic search past user requests/tickets by "
                   "description",
    "ur_exact": "exact ticket(s) by fcode1 (YC)|ma_da; bypass semantic",
    "clone_template": "paste bundled template suite into project "
                      "(copy+rename+rewrite tokens); signals:tao moi "
                      "bao cao/man hinh/danh muc/chuc nang/chung tu "
                      "(controller suite moi), retrieve flow (Filter+"
                      "MultiForm+MultiGrid+Lookup), voucher_* suite — "
                      "new suites come from template not hand-written; "
                      "not:save-as from existing (save_as_existing)",
    "no_match": "no tool fits — manual work only: business reasoning, "
                "hand-writing content; not:SQL (db_run_sql/db_run_"
                "file), new .sql file (new_sql_file), new screen/"
                "report suite (clone_template), save-as existing "
                "(save_as_existing), XML edit (read_suggest_edit), "
                "balances (db_balance)",
}

# Loại yêu cầu -> template dir tương ứng (None = chưa có mẫu).
# Dùng cho question 'requirement_type' khi context.task_requirement có UR.
REQUIREMENT_TYPES = {
    "category_1_key": {
        "desc": "CREATE a brand-new master/category screen with SINGLE "
                "identity PK (id column), no detail tab, optional Excel "
                "import - ONLY when the request ADDS a new category, "
                "NEVER for editing an existing one",
                "examples": ["Thêm danh mục mới 1 khóa chính (mã)"],
        "template": "category_1_key",
    },
    "category_multi_key": {
        "desc": "CREATE a brand-new master/category screen with COMPOSITE "
                "primary key (2+ key columns), no detail tab - ONLY for "
                "new-creation requests, NEVER for edits",
                "examples": ["Thêm danh mục mới khóa ghép nhiều cột"],
        "template": "category_multi_key",
    },
    "category_1_key_detail": {
        "desc": "CREATE a brand-new master/category with single PK plus a "
                "DETAIL tab (embedded Grid controller, ForeignKey link) - "
                "ONLY for new-creation requests",
                "examples": ["Danh mục mới 1 khóa + tab chi tiết"],
        "template": "category_1_key_detail",
    },
    "category_multi_key_detail": {
        "desc": "CREATE a brand-new master/category with composite PK "
                "plus DETAIL tab(s) (embedded Grid controllers) - ONLY "
                "for new-creation requests",
                "examples": ["Danh mục khóa ghép + tab chi tiết"],
        "template": "category_multi_key_detail",
    },
    "report_normal": {
        "desc": "CREATE a brand-new standard listing/detail report "
                "(Filter + Grid + Report controller, no pivot, no "
                "template-form) - ONLY for new-creation requests",
                "examples": ["Tạo báo cáo danh sách mới", "Làm báo cáo chi tiết theo điều kiện lọc"],
        "template": "report_normal",
    },
    "report_check": {
        "desc": "CREATE a new listing report whose Grid has a check-box "
                "'tag' column to SELECT ROWS - toolbar buttons process "
                "the checked rows (g.request + response.action server "
                "SQL) and/or print exports ONLY checked rows (@$keys + "
                "fsd_StringToTable). Pick this OVER report_normal when "
                "UR mentions tick/check chọn/tag dòng + nút xử lý hoặc "
                "in theo dòng đã chọn - ONLY for new-creation requests",
                "examples": ["Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"],
        "template": "report_check",
    },
    "report_mau": {
        "desc": "CREATE a brand-new template-form report (Filter has "
                "'form' dropdown loading v20dmmaubc to pick report layout "
                "dynamically) - ONLY for new-creation requests",
                "examples": ["Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"],
        "template": "report_mau",
    },
    "report_pivot": {
        "desc": "CREATE a brand-new pivot/crosstab report (Grid has "
                "<pivot> rowField/columnField/dataFields) - ONLY for "
                "new-creation requests",
                "examples": ["Tạo báo cáo pivot/crosstab theo chiều hàng-cột"],
        "template": "report_pivot",
    },
    "voucher": {
        "desc": "GENERIC brand-new transaction voucher request (chung tu "
                "moi: stt_rec, master-detail) when approval/currency "
                "needs are UNCLEAR - prefer the specific voucher_* "
                "variants below whenever the UR says co/khong duyet or "
                "co/khong ma_nt/ngoai te. ONLY for new-creation requests",
        "template": None,
        "examples": ["Tạo chứng từ mới PLH",
                     "Tạo voucher mới cho nghiệp vụ ký gửi"],
        "clarify": {
            "questions": [
                "Chứng từ có luồng duyệt/trình duyệt/phê duyệt không? "
                "(yes/no)",
                "Chứng từ có mã ngoại tệ/tỷ giá không? (yes/no)",
            ],
            "map": {
                "yes_yes": "voucher_approval_currency",
                "yes_no": "voucher_approval_no_currency",
                "no_yes": "voucher_normal_currency",
                "no_no": "voucher_normal_no_currency",
            },
            "note": "Hỏi user 2 câu trên → ghép yes_yes/yes_no/... tra "
                    "map ra variant → gọi lại tool_help với UR đã rõ",
        },
    },
    "voucher_normal_no_currency": {
        "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO "
                "approval flow and NO foreign currency: Dir/Grid/Filter/"
                "Query/Report/Detail controllers + Include/Extender + "
                "Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao "
                "chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet "
                "AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi "
                "ro 'chung tu binh thuong/thuong/don gian, khong duyet, "
                "khong ngoai te') - NOT for editing existing vouchers "
                "(use none)",
                "examples": ["Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
                     "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"],
        "template": "voucher_normal_no_currency",
    },
    "voucher_normal_currency": {
        "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO "
                "approval flow but WITH foreign currency - signals: "
                "ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, "
                "nguyen te, da tien te/multi-currency, _nt column pairs, "
                "USD/EUR, Currency JS behavior. NOT for editing existing "
                "vouchers (use none), NOT when UR mentions duyet/phe "
                "duyet (use voucher_approval_currency)",
                "examples": ["Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
                     "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"],
        "template": "voucher_normal_currency",
    },
    "voucher_approval_no_currency": {
        "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an "
                "approval flow - signals: duyet, phe duyet, trinh duyet, "
                "luong duyet, ky duyet, qua buoc duyet, APV, approval, "
                "kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files "
                "+ a{x}$ history table) - but WITHOUT foreign currency/"
                "ngoai te/ma_nt/ty gia - NOT for editing existing "
                "vouchers (use none)",
                "examples": ["Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
                     "Voucher mới có duyệt (kiểu duyệt 01501)"],
        "template": "voucher_approval_no_currency",
    },
    "voucher_approval_currency": {
        "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH "
                "BOTH an approval flow (duyet/phe duyet/trinh duyet/APV "
                "+ ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND "
                "foreign currency (ngoai te, ma_nt, ty gia, nguyen te, "
                "_nt pairs, Currency JS) - the FULL suite: pick when UR "
                "asks tao chung tu/voucher moi WITH duyet AND ma_nt/"
                "ngoai te. NOT for editing existing (use none)",
        "examples": ["Tạo chứng từ mới có duyệt và có mã ngoại tệ",
                     "Thêm voucher mới có luồng trình duyệt, hỗ trợ tỷ "
                     "giá ngoại tệ",
                     "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"],
        "template": "voucher_approval_currency",
    },
    "retrieve_flow_parition_table": {
        "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an "
                "EXISTING voucher: creates a NEW controller suite "
                "{X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty "
                "tracking proc; SOURCE voucher tables are PARTITIONED "
                "(m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du "
                "lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, "
                "phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it "
                "attaches to an existing voucher but CREATES new controllers",
                "examples": ["Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
                     "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"],
        "template": "retrieve_flow_parition_table",
    },
    "retrieve_flow_single_table": {
        "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an "
                "EXISTING voucher where the SOURCE voucher is a FIXED "
                "(non-partitioned) table, no $YYYYMM suffix - same new "
                "suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as "
                "retrieve_flow_parition_table but for fixed source tables",
                "examples": ["Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"],
        "template": "retrieve_flow_single_table",
    },
    "clone_existing": {
        "desc": "CREATE a new screen/report/voucher by SAVE-AS / copying "
                "an EXISTING named function - signals: 'save as', "
                "'save-as', 'copy từ', 'clone từ', 'dựa trên', 'giống/"
                "tương tự chức năng/báo cáo X', or the UR names an "
                "existing feature by its title and asks for a new one "
                "based on it. NOT for from-scratch creation (template "
                "types) and NOT for plain edits of an existing "
                "controller (none)",
        "examples": ["Thêm báo cáo dòng tiền save as từ Báo cáo lưu "
                     "chuyển tiền tệ theo phương pháp trực tiếp",
                     "Tạo chứng từ mới copy từ phiếu X có sẵn"],
        "template": None,
        "workflow": [
            "1. Xác định chức năng nguồn: UR cho title → clone_things "
            "type=6 object='saveas:title:<tiêu đề>-><new_ctrl>'; UR cho "
            "sẵn tên controller/file (vd zclctt) → 'saveas:ctrl:<tên>"
            "-><new_ctrl>'. Không tìm thấy hoặc ambiguous → hỏi user",
            "2. type=6 clone toàn bộ suite file (Filter/Grid/Dir/Report"
            "/aspx...) + export proc nguồn ra .sql temp — mặc định "
            "dry-run, execute=True mới ghi file",
            "3. Đổi tên proc trong .sql thành tên mới user gửi (vd "
            "zc_lctt → zc_bcdt), sửa <title v> trong XML mới, đăng ký "
            "menu/aspx nếu cần",
            "4. Sửa bản clone theo các yêu cầu phụ của UR (cột, cách "
            "tính, toolbar, đồ thị...)",
            "4b. Save-as KHÔNG tự đăng ký config chung — grep tên "
            "controller NGUỒN trong các file dùng chung rồi APPEND "
            "dòng tương ứng đổi sang tên mới. Với chứng từ: "
            "Post/Post.xml (<view controller table key stt_rec>), "
            "Filter/Config/Initialize.xml, Grid/Config/Aggregation.* "
            "(.v/.q — theo file chứa nguồn), Grid/Config/Include/"
            "Voucher.Controller.* (đúng file .00x chứa nguồn), "
            "Include/Extender.ent (cả nhánh List lẫn Post)",
            "5. Nếu chức năng nguồn/UR có nút Đồ thị: cần đủ bộ "
            "{X}Graph.xml (Filter/Grid) + entity Identification/GraphMa* "
            "+ aspx có LoadControl(\"Chart.ascx\") — thiếu → lỗi JS "
            "'chart$Graph$InitObject is not defined'",
            "6. Verify: query_database query_type=3 (PARSEONLY) file "
            ".sql + get_xml_entities checking các XML đã sửa",
        ],
    },
    "none": {
        "desc": "DEFAULT CHOICE for anything that is NOT creating a "
                "screen/report from scratch, NOT adding a data-retrieval "
                "(lay du lieu) suite onto an existing voucher, and NOT "
                "save-as/copying a named existing function (that is "
                "clone_existing): edit/modify/add fields to an EXISTING "
                "controller, bug fix, data query, deploy, investigate - "
                "ALWAYS pick this when the target already exists or "
                "intent is ambiguous",
        "template": None,
    },
}

# Bản nén của desc cho question requirement_type — cùng quy tắc
# _JEV_TASK_DESCS. examples (VN) giữ nguyên trong catalog entry.
_JEV_REQ_DESCS = {
    "category_1_key": "new category screen: single identity PK, no "
                      "detail tab, optional Excel import; only new-"
                      "create, never edit",
    "category_multi_key": "new category screen: composite PK (2+ key "
                          "cols), no detail tab; only new-create",
    "category_1_key_detail": "new category: single PK + DETAIL tab "
                             "(embedded Grid, ForeignKey link); only "
                             "new-create",
    "category_multi_key_detail": "new category: composite PK + DETAIL "
                                 "tab(s) (embedded Grids); only new-"
                                 "create",
    "report_normal": "new standard listing/detail report (Filter+Grid+"
                     "Report; no pivot, no template-form); only new-"
                     "create",
    "report_check": "new listing report with checkbox 'tag' column: "
                    "toolbar buttons process checked rows (g.request+"
                    "response.action server SQL) and/or print only "
                    "checked (@$keys+fsd_StringToTable); pick OVER "
                    "report_normal when UR mentions tick/check chon/"
                    "tag dong + xu ly hoac in theo dong da chon; only "
                    "new-create",
    "report_mau": "new template-form report: Filter 'form' dropdown "
                  "loads v20dmmaubc to pick layout dynamically; only "
                  "new-create",
    "report_pivot": "new pivot/crosstab report (Grid <pivot> rowField/"
                    "columnField/dataFields); only new-create",
    "voucher": "generic new voucher (chung tu moi: stt_rec, master-"
               "detail) when approval/currency UNCLEAR — prefer "
               "voucher_* variants when UR says co/khong duyet or co/"
               "khong ma_nt/ngoai te; only new-create",
    "voucher_normal_no_currency": "new voucher suite: NO approval + NO "
        "currency; signals: tao chung tu/voucher moi WITHOUT duyet/phe "
        "duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te, "
        "or UR says 'chung tu binh thuong/thuong/don gian, khong duyet, "
        "khong ngoai te'; not:editing existing (none)",
    "voucher_normal_currency": "new voucher suite: currency, NO "
        "approval; signals: ngoai te, ma_nt/ma ngoai te, ty gia/"
        "exchange rate, nguyen te, da tien te/multi-currency, _nt "
        "column pairs, USD/EUR, Currency JS; not:editing (none), duyet "
        "-> voucher_approval_currency",
    "voucher_approval_no_currency": "new voucher suite: approval flow "
        "(duyet/phe duyet/trinh duyet/luong duyet/ky duyet/qua buoc "
        "duyet/APV/kieu duyet 015xx/{X}Approval+a{x}$ history) WITHOUT "
        "ngoai te/ma_nt/ty gia; not:editing existing (none)",
    "voucher_approval_currency": "new voucher suite: approval (duyet/"
        "phe duyet/trinh duyet/APV+kieu duyet 015xx+a{x}$) AND currency "
        "(ngoai te/ma_nt/ty gia/nguyen te/_nt pairs/Currency JS) — "
        "full suite; not:editing existing (none)",
    "retrieve_flow_parition_table": "ADD retrieve (lay du lieu) flow "
        "ONTO existing voucher -> NEW suite {X}Filter/{X}MultiForm/"
        "{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE "
        "tables PARTITIONED (m/d/i<ext>$YYYYMM); signals: chuc nang lay "
        "du lieu/retrieve tu chung tu nguon, theo doi da lay/con lai, "
        "phieu da lay het khong lay nua, lay nhieu phieu 1 lan",
    "retrieve_flow_single_table": "ADD retrieve flow ONTO existing "
        "voucher; SOURCE = FIXED non-partitioned table (no $YYYYMM "
        "suffix); same new suite as retrieve_flow_parition_table",
    "clone_existing": "new screen/report/voucher by save-as/copy of "
        "EXISTING named function; signals: save as, copy tu, clone tu, "
        "dua tren, giong/tuong tu chuc nang/bao cao X, or UR names "
        "existing feature by title; not:from-scratch (template types), "
        "plain edits (none)",
    "none": "DEFAULT: not creating from scratch, not retrieve-flow add-"
            "on, not save-as (clone_existing) — edit/modify/add fields "
            "to EXISTING controller, bug fix, data query, deploy, "
            "investigate; pick when target exists or intent ambiguous",
}


def _req_catalog_entry(k: str, v: dict):
    desc = _JEV_REQ_DESCS.get(k) or v["desc"]
    if v.get("examples"):
        return {"desc": desc, "examples": v["examples"]}
    return desc


REQUIREMENT_TYPE_CATALOG = {k: _req_catalog_entry(k, v)
                            for k, v in REQUIREMENT_TYPES.items()}


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

# Jev 1.13 thiên vị option đứng đầu (docs jaggedness #8). Đo
# `jev_eval.py --steps-set --shuffle 2`: read_flat ở vị trí 2 thắng oan
# read_summary ở 3/67 step → dời xuống sau các mode read_* khác.
_CATALOG_DEFER_AFTER = {"read_flat": "read_suggest_edit"}


def _catalog_order() -> list[str]:
    keys = [k for k in TASK_TYPES if k not in _CATALOG_DEFER_AFTER]
    for k, after in _CATALOG_DEFER_AFTER.items():
        keys.insert(keys.index(after) + 1, k)
    return keys


TASK_TYPE_CATALOG = {k: _JEV_TASK_DESCS.get(k) or TASK_TYPES[k]["desc"]
                     for k in _catalog_order()}

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


def _int(v, default=None):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def task_type_for_call(tool: str, args: dict | None) -> str | None:
    """Ngược của card: 1 tool call thật (tool + args) → task_type.

    Dùng cho context.failed (biết option nào vừa fail) và scripts/
    jev_feedback (gán nhãn step↔call từ log). None nếu không xác định.
    Args trong log có thể là string ("3") — ép int khi cần.
    """
    a = args or {}
    mode = str(a.get("mode") or "").strip().lower()
    if tool == "read_local_file":
        ro = _int(a.get("read_option"))
        if ro == 4:
            return "read_suggest_edit"
        if ro in (2, 3):
            return {2: "read_flat", 3: "read_summary"}[ro]
        if any(a.get(k) for k in ("symbol", "block", "start_line")):
            return "read_snippet"
        return "read_raw" if ro == 1 else "read_summary"
    if tool == "search_files":
        return {"definition": "find_definition",
                "references": "find_references",
                "files_only": "match_filename"}.get(mode, "grep_content")
    if tool == "compare_things":
        kind = str(a.get("kind") or "").lower()
        if kind == "folder" and str(a.get("inventory")).lower() == "true":
            return "list_folder"
        return {"file": "diff_file", "folder": "diff_folder",
                "xml": "diff_xml", "sql": "diff_sql_table",
                "table": "diff_sql_table"}.get(kind)
    if tool == "clone_things":
        return {0: "clone_sql", 1: "paste_sql", 2: "clone_data",
                3: "copy_files", 4: "clone_template", 5: "new_sql_file",
                6: "save_as_existing"}.get(_int(a.get("type")))
    if tool == "query_database":
        if mode == "search":
            if "U" in str(a.get("object_types") or "").upper().split(","):
                return "db_list_tables"
            if str(a.get("object_name") or "").lower().startswith(
                    "fastbusiness$balance"):
                return "db_balance"
            return "db_search"
        qt = _int(a.get("query_type"), 1)
        if qt == 0:
            return "db_snippet" if mode == "snippet" else "db_object"
        if qt == 1 and "fsd_addfields" in str(a.get("query") or "").lower():
            return "db_add_field"
        return {1: "db_run_sql", 2: "db_run_file",
                3: "db_check_syntax"}.get(qt)
    if tool == "get_xml_entities":
        return {"content": "entity_content", "path": "entity_path",
                "list": "entity_list", "checking": "entity_check"}.get(mode)
    if tool == "search_qlyc":
        return "ur_exact" if (a.get("fcode1") or a.get("ma_da")) \
            else "ur_semantic"
    return None
