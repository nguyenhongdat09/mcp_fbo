# Jev voucher-variant test payloads

Mỗi case: paste STATE vào ô state, QUESTIONS vào ô questions.
Chỉ cần trả lời `requirement_type`. Expected = cột mong đợi.

| Case | Expected | UR |
|---|---|---|
| A1 | `voucher_approval_currency` | Tạo chứng từ mới PLH phiếu đề nghị thanh toán, có chức năng … |
| A2 | `voucher_approval_currency` | Thêm voucher mới có luồng trình duyệt, hỗ trợ tỷ giá ngoại t… |
| A3 | `voucher_approval_currency` | Chứng từ mới đa tiền tệ và cần phê duyệt nhiều cấp… |
| B1 | `voucher_approval_no_currency` | Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ… |
| B2 | `voucher_approval_no_currency` | Tạo voucher mới có duyệt (kiểu duyệt 01501)… |
| B3 | `voucher_approval_no_currency` | Chứng từ mới cần qua bước ký duyệt trước khi hạch toán… |
| C1 | `voucher_normal_currency` | Tạo chứng từ mới không duyệt, có mã ngoại tệ và tỷ giá… |
| C2 | `voucher_normal_currency` | Voucher mới nhập theo nguyên tệ USD, không cần duyệt… |
| C3 | `voucher_normal_currency` | Chứng từ mới có ngoại tệ… |
| D1 | `voucher_normal_no_currency` | Tạo chứng từ mới đơn giản, không duyệt, không ngoại tệ… |
| D2 | `voucher_normal_no_currency` | Chứng từ mới bình thường, không duyệt không ngoại tệ… |
| E1 | `voucher` | Tạo chứng từ mới PLH… |
| E2 | `voucher` | Tạo voucher mới cho nghiệp vụ ký gửi… |
| F1 | `none` | Sửa chứng từ DDVTran thêm cột mã dự án vào grid chi tiết… |
| F2 | `retrieve_flow_parition_table` | Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR… |
| G1 | `report_normal` | Tạo báo cáo danh sách phiếu nhập kho theo điều kiện lọc… |
| G2 | `report_check` | Báo cáo có cột tick chọn dòng, nút in chỉ in các dòng đã chọ… |
| G3 | `report_pivot` | Báo cáo pivot doanh thu theo tháng x khách hàng… |
| H1 | `category_1_key` | Thêm danh mục mới loại phí, chỉ có mã + tên… |
| H2 | `category_multi_key` | Tạo danh mục mới có khóa ghép theo đơn vị và năm… |
| S1 | `none` | Kiểm tra dữ liệu và tạo dữ liệu mẫu test… |


## A1 — expected `voucher_approval_currency`

UR: Tạo chứng từ mới PLH phiếu đề nghị thanh toán, có chức năng duyệt và có mã ngoại tệ

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo chứng từ mới PLH phiếu đề nghị thanh toán, có chức năng duyệt và có mã ngoại tệ",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## A2 — expected `voucher_approval_currency`

UR: Thêm voucher mới có luồng trình duyệt, hỗ trợ tỷ giá ngoại tệ

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Thêm voucher mới có luồng trình duyệt, hỗ trợ tỷ giá ngoại tệ",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## A3 — expected `voucher_approval_currency`

UR: Chứng từ mới đa tiền tệ và cần phê duyệt nhiều cấp

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Chứng từ mới đa tiền tệ và cần phê duyệt nhiều cấp",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## B1 — expected `voucher_approval_no_currency`

UR: Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## B2 — expected `voucher_approval_no_currency`

UR: Tạo voucher mới có duyệt (kiểu duyệt 01501)

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo voucher mới có duyệt (kiểu duyệt 01501)",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## B3 — expected `voucher_approval_no_currency`

UR: Chứng từ mới cần qua bước ký duyệt trước khi hạch toán

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Chứng từ mới cần qua bước ký duyệt trước khi hạch toán",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## C1 — expected `voucher_normal_currency`

UR: Tạo chứng từ mới không duyệt, có mã ngoại tệ và tỷ giá

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo chứng từ mới không duyệt, có mã ngoại tệ và tỷ giá",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## C2 — expected `voucher_normal_currency`

UR: Voucher mới nhập theo nguyên tệ USD, không cần duyệt

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## C3 — expected `voucher_normal_currency`

UR: Chứng từ mới có ngoại tệ

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Chứng từ mới có ngoại tệ",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## D1 — expected `voucher_normal_no_currency`

UR: Tạo chứng từ mới đơn giản, không duyệt, không ngoại tệ

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo chứng từ mới đơn giản, không duyệt, không ngoại tệ",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## D2 — expected `voucher_normal_no_currency`

UR: Chứng từ mới bình thường, không duyệt không ngoại tệ

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Chứng từ mới bình thường, không duyệt không ngoại tệ",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## E1 — expected `voucher`

UR: Tạo chứng từ mới PLH

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo chứng từ mới PLH",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## E2 — expected `voucher`

UR: Tạo voucher mới cho nghiệp vụ ký gửi

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo voucher mới cho nghiệp vụ ký gửi",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## F1 — expected `none`

UR: Sửa chứng từ DDVTran thêm cột mã dự án vào grid chi tiết

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Sửa chứng từ DDVTran thêm cột mã dự án vào grid chi tiết",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## F2 — expected `retrieve_flow_parition_table`

UR: Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## G1 — expected `report_normal`

UR: Tạo báo cáo danh sách phiếu nhập kho theo điều kiện lọc

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo báo cáo danh sách phiếu nhập kho theo điều kiện lọc",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## G2 — expected `report_check`

UR: Báo cáo có cột tick chọn dòng, nút in chỉ in các dòng đã chọn

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Báo cáo có cột tick chọn dòng, nút in chỉ in các dòng đã chọn",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## G3 — expected `report_pivot`

UR: Báo cáo pivot doanh thu theo tháng x khách hàng

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Báo cáo pivot doanh thu theo tháng x khách hàng",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## H1 — expected `category_1_key`

UR: Thêm danh mục mới loại phí, chỉ có mã + tên

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Thêm danh mục mới loại phí, chỉ có mã + tên",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## H2 — expected `category_multi_key`

UR: Tạo danh mục mới có khóa ghép theo đơn vị và năm

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Tạo danh mục mới có khóa ghép theo đơn vị và năm",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```


## S1 — expected `none`

UR: Kiểm tra dữ liệu và tạo dữ liệu mẫu test

### STATE
```json
{
 "agent_context": "Agent on FastBusiness ERP. Code = XML controllers on UNC paths; data = SQL Server. MCP tools available.",
 "task_type_catalog": {
  "read_summary": "Overview map of ONE WHOLE known file (JS funcs, SQL objects, fields) when you do NOT yet know which region matters. NOT for reading around a specific named field/action/symbol — that is read_snippet",
  "read_flat": "Read FULL expanded content of one known XML file (entities resolved) to see every line",
  "read_raw": "Read raw content of one known file untouched - non-controller files (.sql/.js/.ent/.aspx) or XML not directly under Dir/Grid/Filter (Templates, Report)",
  "read_snippet": "Read AROUND ONE named thing in a known file: 'quanh/around field X', action Y, JS function Z, or a line range - when the step already names the specific region to look at",
  "read_suggest_edit": "Before editing a file: locate region and get exact old_string + diff_preview for str_replace",
  "grep_content": "Find WHICH files contain a string/keyword inside file content (grep), or which files match a criterion (e.g. controllers having an import filter). Target files unknown",
  "find_definition": "Find WHERE a JS symbol/function is defined",
  "find_references": "List ALL usage sites of a symbol for rename/refactor",
  "match_filename": "Find files by NAME/glob pattern across the project (e.g. Filter/*Import*, *.xml in Templates/Upload) - does not read content",
  "diff_file": "Compare TWO known files line-by-line",
  "diff_folder": "Compare TWO folders/projects - what is missing or different",
  "list_folder": "ONLY list children of ONE ALREADY-KNOWN folder (like ls/dir). NOT a search tool - cannot find files by name pattern or content criteria",
  "diff_xml": "Compare XML controllers between two projects by relative path or keyword seed",
  "diff_sql_table": "Compare SQL objects or table schemas between two project databases",
  "clone_sql": "Copy/clone SQL objects (proc/func/view/table) BETWEEN two project databases -> one .sql file of only the MISSING objects. Pick when the step says mang/kéo/copy/clone proc hoặc object từ project/DB này sang project/DB khác, hoặc 'check còn thiếu object nào'",
  "paste_sql": "Export a SQL object BODY (proc/func/view) out to a .sql ALTER file to VIEW or EDIT it. Pick whenever the step is xem/lấy/sửa/chỉnh nội dung proc - the right workflow is export to file then edit, NOT read summary then hand-rewrite the whole proc. Also for 'dump proc ra file'",
  "clone_data": "Export/clone table ROWS matching a condition into a DELETE+INSERT .sql script. Pick whenever the step wants data written into a .sql file: clone/copy/dump rows, tạo dữ liệu mẫu/test data, di chuyển dữ liệu giữa DB, 'viết dữ liệu vào file .sql'",
  "copy_files": "Copy/rename files or a whole controller set (suite) between or within projects",
  "db_object": "Inspect ONE DB object: table schema (CREATE TABLE) or proc/view/func SUMMARY (params, tables, calls) - knows the object name and only needs overview, NOT the full body to edit (that is paste_sql)",
  "db_snippet": "Extract code blocks of a known proc by keywords/zones",
  "db_run_sql": "Execute a short inline SQL DIRECTLY on the DB - SELECT check data, INSERT/UPDATE/DELETE rows, run/test an existing proc (exec proc_name), deploy small DDL. NOT for: exporting/viewing proc source to edit (use paste_sql), cloning rows or test data into a .sql file (use clone_data), copying objects between projects (use clone_sql), running a long .sql FILE (use db_run_file)",
  "db_run_file": "Execute a .sql FILE (long script)",
  "db_check_syntax": "PARSEONLY syntax-check a .sql file before deploy - does not execute",
  "db_search": "Search DB objects by name LIKE or by references ('which proc uses table/field X')",
  "db_add_field": "Add a NEW column/field to an existing DB table (thêm trường/cột vào bảng, chứng từ, danh mục). ALSO pick this whenever a step mentions writing ALTER TABLE / adding columns via SQL - redirect to proc fsd_addFields, NEVER raw ALTER TABLE",
  "entity_content": "View the CONTENT of named DOCTYPE entities in an XML file",
  "entity_path": "Find WHERE (file:line) entities are declared",
  "entity_list": "List all entities declared in an XML file",
  "entity_check": "Lint XML: undeclared &entity; used or SYSTEM entity pointing to missing files",
  "graph_query": "Query the XML controller graph (Kuzu): which controller calls/retrieves/uses a lookup, table or file; master-detail relations, neighbors, clusters - via fixed Cypher templates",
  "ur_semantic": "Semantic search of past user requests/tickets by description",
  "ur_exact": "Fetch exact ticket(s) by fcode1 (YC number) or ma_da (project code) - bypass semantic",
  "clone_template": "Paste a BUNDLED template suite (template/<name>/ shipped with the server) into target project - copies files + renames + rewrites controller/table tokens inside. ALSO pick this when the step is 'tạo mới báo cáo/màn hình/danh mục/chức năng/chứng từ (controller suite mới)' - kể cả bộ lấy dữ liệu/retrieve flow (Filter+MultiForm+MultiGrid+Lookup) và chứng từ mới voucher_* (Dir/Grid/Filter/Query/Report/Approval + aspx + sql) - new suites come from a template, not hand-written files",
  "no_match": "NONE of the above fits - ONLY for pure manual work with no tool: business reasoning, writing file content by hand. NOT for SQL authoring/execution (db_run_sql/db_run_file), NOT for creating a new screen/report suite (clone_template), NOT for editing XML files (read_suggest_edit)"
 },
 "steps": [
  "Khảo sát chứng từ mẫu tương thích trong project",
  "Clone bộ controller + sửa nội dung theo mã chứng từ mới",
  "Viết SQL đăng ký SYS/APP + tạo bảng vật lý"
 ],
 "task_requirement": "Kiểm tra dữ liệu và tạo dữ liệu mẫu test",
 "requirement_type_catalog": {
  "category_1_key": {
   "desc": "CREATE a brand-new master/category screen with SINGLE identity PK (id column), no detail tab, optional Excel import - ONLY when the request ADDS a new category, NEVER for editing an existing one",
   "examples": [
    "Thêm danh mục mới 1 khóa chính (mã)"
   ]
  },
  "category_multi_key": {
   "desc": "CREATE a brand-new master/category screen with COMPOSITE primary key (2+ key columns), no detail tab - ONLY for new-creation requests, NEVER for edits",
   "examples": [
    "Thêm danh mục mới khóa ghép nhiều cột"
   ]
  },
  "category_1_key_detail": {
   "desc": "CREATE a brand-new master/category with single PK plus a DETAIL tab (embedded Grid controller, ForeignKey link) - ONLY for new-creation requests",
   "examples": [
    "Danh mục mới 1 khóa + tab chi tiết"
   ]
  },
  "category_multi_key_detail": {
   "desc": "CREATE a brand-new master/category with composite PK plus DETAIL tab(s) (embedded Grid controllers) - ONLY for new-creation requests",
   "examples": [
    "Danh mục khóa ghép + tab chi tiết"
   ]
  },
  "report_normal": {
   "desc": "CREATE a brand-new standard listing/detail report (Filter + Grid + Report controller, no pivot, no template-form) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo danh sách mới",
    "Làm báo cáo chi tiết theo điều kiện lọc"
   ]
  },
  "report_check": {
   "desc": "CREATE a new listing report whose Grid has a check-box 'tag' column to SELECT ROWS - toolbar buttons process the checked rows (g.request + response.action server SQL) and/or print exports ONLY checked rows (@$keys + fsd_StringToTable). Pick this OVER report_normal when UR mentions tick/check chọn/tag dòng + nút xử lý hoặc in theo dòng đã chọn - ONLY for new-creation requests",
   "examples": [
    "Báo cáo có cột tick chọn dòng, nút duyệt/in theo dòng đã chọn"
   ]
  },
  "report_mau": {
   "desc": "CREATE a brand-new template-form report (Filter has 'form' dropdown loading v20dmmaubc to pick report layout dynamically) - ONLY for new-creation requests",
   "examples": [
    "Báo cáo tạo mẫu — dropdown chọn mẫu rồi render theo mẫu"
   ]
  },
  "report_pivot": {
   "desc": "CREATE a brand-new pivot/crosstab report (Grid has <pivot> rowField/columnField/dataFields) - ONLY for new-creation requests",
   "examples": [
    "Tạo báo cáo pivot/crosstab theo chiều hàng-cột"
   ]
  },
  "voucher": {
   "desc": "GENERIC brand-new transaction voucher request (chung tu moi: stt_rec, master-detail) when approval/currency needs are UNCLEAR - prefer the specific voucher_* variants below whenever the UR says co/khong duyet or co/khong ma_nt/ngoai te. ONLY for new-creation requests",
   "examples": [
    "Tạo chứng từ mới PLH",
    "Tạo voucher mới cho nghiệp vụ ký gửi"
   ]
  },
  "voucher_normal_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow and NO foreign currency: Dir/Grid/Filter/Query/Report/Detail controllers + Include/Extender + Revert + Main aspx + SYS/APP SQL. Pick when UR asks tao chung tu/voucher moi WITHOUT duyet/phe duyet/trinh duyet AND WITHOUT ma_nt/ngoai te/ty gia/nguyen te (hoac UR noi ro 'chung tu binh thuong/thuong/don gian, khong duyet, khong ngoai te') - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới đơn giản, không duyệt không ngoại tệ",
    "Chứng từ mới bình thường (không duyệt, không ngoại tệ)"
   ]
  },
  "voucher_normal_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) with NO approval flow but WITH foreign currency - signals: ngoai te, ma_nt/ma ngoai te, ty gia/exchange rate, nguyen te, da tien te/multi-currency, _nt column pairs, USD/EUR, Currency JS behavior. NOT for editing existing vouchers (use none), NOT when UR mentions duyet/phe duyet (use voucher_approval_currency)",
   "examples": [
    "Voucher mới nhập theo nguyên tệ USD, không cần duyệt",
    "Chứng từ mới có mã ngoại tệ và tỷ giá, không duyệt"
   ]
  },
  "voucher_approval_no_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH an approval flow - signals: duyet, phe duyet, trinh duyet, luong duyet, ky duyet, qua buoc duyet, APV, approval, kieu duyet 015xx ({X}Approval grid + ApprovalItem/Files + a{x}$ history table) - but WITHOUT foreign currency/ngoai te/ma_nt/ty gia - NOT for editing existing vouchers (use none)",
   "examples": [
    "Tạo chứng từ mới có chức năng phê duyệt, không cần ngoại tệ",
    "Voucher mới có duyệt (kiểu duyệt 01501)"
   ]
  },
  "voucher_approval_currency": {
   "desc": "CREATE a brand-new voucher suite (chung tu moi) WITH BOTH an approval flow (duyet/phe duyet/trinh duyet/APV + ApprovalItem/Files + kieu duyet 015xx + a{x}$) AND foreign currency (ngoai te, ma_nt, ty gia, nguyen te, _nt pairs, Currency JS) - the FULL suite: pick when UR asks tao chung tu/voucher moi WITH duyet AND ma_nt/ngoai te. NOT for editing existing (use none)",
   "examples": [
    "Tạo chứng từ mới có duyệt và có mã ngoại tệ",
    "Chứng từ mới đa tiền tệ, cần phê duyệt nhiều cấp"
   ]
  },
  "retrieve_flow_parition_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher: creates a NEW controller suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup + taken-qty tracking proc; SOURCE voucher tables are PARTITIONED (m/d/i<ext>$YYYYMM). Pick when UR asks chuc nang lay du lieu / retrieve tu chung tu nguon, theo doi da lay/con lai, phieu da lay het khong lay nua, lay nhieu phieu 1 lan - it attaches to an existing voucher but CREATES new controllers",
   "examples": [
    "Thêm chức năng lấy dữ liệu vào chứng từ DDV từ phiếu MR",
    "Chứng từ X lấy dữ liệu từ phiếu Y, theo dõi đã lấy/còn lại"
   ]
  },
  "retrieve_flow_single_table": {
   "desc": "ADD a data-retrieval (lay du lieu / Retrieve) flow ONTO an EXISTING voucher where the SOURCE voucher is a FIXED (non-partitioned) table, no $YYYYMM suffix - same new suite {X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup as retrieve_flow_parition_table but for fixed source tables",
   "examples": [
    "Chứng từ lấy dữ liệu từ phiếu nguồn bảng cố định không partition"
   ]
  },
  "none": "DEFAULT CHOICE for anything that is NOT creating a screen/report from scratch and NOT adding a data-retrieval (lay du lieu) suite onto an existing voucher: edit/modify/add fields to an EXISTING controller, bug fix, data query, deploy, investigate - ALWAYS pick this when the target already exists or intent is ambiguous"
 }
}
```
### QUESTIONS
```json
{
 "requirement_type": {
  "type": "choice",
  "instructions": "Classify the user requirement in state.task_requirement into ONE requirement type. IMPORTANT: template types (category_*, report_*, voucher) are ONLY for requests that CREATE a brand-new screen/report/category from scratch. EXCEPTION: 'retrieve_flow_*' types DO apply when the request ADDS a data-retrieval (lay du lieu) feature onto an existing voucher - they still create new controllers ({X}Filter/{X}MultiForm/{X}MultiGrid/{X}Lookup). For NEW voucher requests pick the voucher_* variant matching BOTH signals explicitly stated in the UR: duyet/phe duyet/trinh duyet -> approval variant; ngoai te/ma_nt/ty gia/nguyen te -> currency variant; both -> voucher_approval_currency; UR says khong/none of them -> the matching no_* variant; signals not mentioned at all -> generic 'voucher'. Otherwise, if the request edits/modifies/fixes/queries something that already exists, or intent is ambiguous, choose 'none' with high probability. Type meanings are in state.requirement_type_catalog.",
  "criteria": {
   "category_1_key": null,
   "category_multi_key": null,
   "category_1_key_detail": null,
   "category_multi_key_detail": null,
   "report_normal": null,
   "report_check": null,
   "report_mau": null,
   "report_pivot": null,
   "voucher": null,
   "voucher_normal_no_currency": null,
   "voucher_normal_currency": null,
   "voucher_approval_no_currency": null,
   "voucher_approval_currency": null,
   "retrieve_flow_parition_table": null,
   "retrieve_flow_single_table": null,
   "none": null
  }
 }
}
```
