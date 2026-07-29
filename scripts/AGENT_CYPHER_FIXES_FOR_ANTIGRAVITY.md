# Agent + Kuzu Cypher — Bug/Gap report cho Antigravity

## Kết luận test

- ok=5 fail=11 warn=1
- `query_radar` **đủ khả năng** nếu agent viết Cypher đúng schema.
- Thực tế agent FBO **dễ fail** ở path slash, SHARED_INCLUDE, synonym, needs_xml, schema guess.

## Evidence (auto test `scripts/test_agent_cypher_traps.py`)

### [ok] path_slash_docstring

slash=15 bslash=5 sample=[{'f.relative_path': 'Dir\\CPTran.xml'}, {'f.relative_path': 'Filter\\CPTran.xml'}, {'f.relative_path': 'Filter\\rptPrintCPTran.xml'}, {'f.relative_path': 'Grid\\CPTran.xml'}, {'f.relative_path': 'Grid\\rptPrintCPTran.xml'}]

### [FAIL] shared_include_flood

CPTran outgoing by type: [{'r.edge_type': 'SHARED_INCLUDE', 'c': 4173}, {'r.edge_type': 'COMPANION_FILE', 'c': 18}, {'r.edge_type': 'ENTITY_INCLUDE', 'c': 12}, {'r.edge_type': 'LOOKUP_REFERENCE', 'c': 7}, {'r.edge_type': 'GRID_MASTER_DETAIL', 'c': 5}, {'r.edge_type': 'PARAM_ENTITY_USE', 'c': 2}]. SHARED_INCLUDE=4173 >> GRID_MASTER=5. Agent MATCH (a)-[r]->(b) không filter sẽ nhận toàn Include chung.

### [FAIL] wrong_rel_label

Agent viết MATCH ()-[:GRID_MASTER_DETAIL]->() sẽ lỗi (schema thật: :Rel + edge_type property). err=Binder exception: Table GRID_MASTER_DETAIL does not exist.

### [FAIL] no_synonym_in_cypher

Cypher literal 'gia ban'/'giá bán' = 0 hits. expand_keyword=['giá bán', 'gia2', 'gia_nt2', 'gia_ban', 'gia21', 'price', 't_tien2', 't_tien_nt2']. Engine search có ~10 hits. Agent không biết gọi expand_keyword.

### [FAIL] handler_search_wrong_property

Agent hay search fields_names → 0. Đúng là js_text → [{'f.relative_path': 'Grid\\CPDetail - Copy.xml'}, {'f.relative_path': 'Grid\\GLTax.xml'}]. Engine code search paths≈['Grid\\CPDetail - Copy.xml', 'Grid\\GLTax.xml']

### [FAIL] needs_xml_ignored

CPTax nodes=[{'f.relative_path': 'Grid\\CPTax.xml', 'f.needs_xml': True, 'f.source_extension': '.f', 'f.is_encrypted': True, 'f.paired_f_path': 'Grid\\CPTax.f'}]. Engine context needs_xml=['Grid\\CPTax.xml'] source=Grid\CPTax.f. Agent Cypher lấy relative_path rồi read_local_file('.xml') sẽ fail/empty nếu không đọc hint needs_xml.

### [ok] no_folder_filter

n=15 templates=0

### [FAIL] navigate_without_needs_xml

Cypher 'đúng' về edge vẫn có thể bỏ RETURN needs_xml. paths=['Grid\\CPCharge.xml', 'Grid\\CPChiHoGrid.xml', 'Grid\\CPDeductible.xml', 'Grid\\CPDetail.xml', 'Grid\\CPTax.xml']; nodes needs_xml=true: [{'path': 'Grid\\CPCharge.xml', 'needs_xml': True, 'db_table': None}, {'path': 'Grid\\CPDeductible.xml', 'needs_xml': True, 'db_table': None}, {'path': 'Grid\\CPTax.xml', 'needs_xml': True, 'db_table': None}]. Engine needs_xml=['Grid\\Account.xml', 'Grid\\CPCharge.xml', 'Grid\\CPDeductible.xml', 'Grid\\CPTax.xml', 'Grid\\Currency.xml']

### [FAIL] token_blowup_unlimited_rel

MATCH all Rel from CPTran = 4217 rows, json≈371926 chars. query_radar không default LIMIT/filter → agent dễ nổ context.

### [FAIL] schema_guess:File instead of XmlFile

Cypher agent-sai → error: Binder exception: Table File does not exist.

### [FAIL] schema_guess:fields instead of fields_names

Cypher agent-sai → error: Binder exception: Cannot find property fields for f.

### [FAIL] schema_guess:Edge instead of Rel

Cypher agent-sai → error: Binder exception: Table Edge does not exist.

### [FAIL] schema_guess:AS table reserved keyword

Cypher agent-sai → error: Parser exception: mismatched input 'table' expecting {ADD, ALTER, AS, ATTACH, BEGIN, BY, CALL, CHECKPOINT, COMMENT, COMMIT, CONTAINS, COPY, COUNT, CYCLE, DATABASE, DELETE, DETACH, DROP, EXPLAIN, EXPOR

### [WARN] cypher_can_work_if_expert

engine=[] cypher=['Grid\\CPCharge.xml', 'Grid\\CPChiHoGrid.xml', 'Grid\\CPDeductible.xml', 'Grid\\CPDetail.xml', 'Grid\\CPTax.xml']

### [ok] mcp_tool:search_nodes_synonyms

Found synonyms: "giá bán" OR "gia2" OR "gia_nt2" OR "gia_ban" OR "gia21" OR "price" OR "t_tien2" OR "t_tien_nt2"

### [ok] mcp_tool:get_related_nodes_navigate

Grids=5 (CPTax has needs_xml: True, no SHARED_INCLUDE)

### [ok] mcp_tool:query_node_details_cptax

needs_xml=['Grid\\CPTax.xml'] source=Grid\CPTax.f

## Hướng chỉnh (bắt buộc làm)

### A. MCP: thêm 3 tool mỏng wrap QueryEngine (không bỏ query_radar)

1. `search_nodes(query, reference_file, match_type='all|field|code|file', folder_filter=None, limit=20)`
   - Gọi `handle_query('search', ...)` + `expand_keyword`
   - Default ưu tiên folder Dir/Grid/Filter (loại Templates nếu không hỏi)
2. `get_related_nodes(target, reference_file, mode='navigate'|'dependencies'|'dependents')`
   - `navigate` = GRID_MASTER_DETAIL + needs_xml + source_on_disk
   - **Không** trả SHARED_INCLUDE trừ khi `include_shared=true`
3. `query_node_details(target, reference_file, view='context'|'blocks')`
   - Trả JSON có `needs_xml`, `agent_hint`, `source_on_disk`, fields compact

### B. Sửa docstring `query_radar` (giảm đoán sai)

1. Document schema thật:
   - Node: `XmlFile` (PK `node_id`)
   - Rel: **chỉ** `:Rel` với property `edge_type` — KHÔNG có typed rel Neo4j
   - `relative_path` dùng backslash `Dir\CPTran.xml` (hoặc normalize cả hai)
2. Liệt kê `edge_type` values + cảnh báo: `SHARED_INCLUDE` ≈ 99% edges → **PHẢI filter**
3. Ví dụ Cypher **đã verify** (copy-paste được):
   - Grids của form: filter `edge_type = 'GRID_MASTER_DETAIL'`, RETURN `needs_xml`
   - Search field: dùng tool search_nodes, không khuyến khích list_contains thuần
   - Search JS handler: `f.js_text CONTAINS '...'` (không dùng fields_names)
4. Thêm `LIMIT` mặc định / reject query không LIMIT khi MATCH Rel

### C. Normalize path trong execute_cypher hoặc helper

- Accept cả `Dir/CPTran.xml` và `Dir\CPTran.xml`
- Hoặc rewrite relative_path lookup trước khi chạy
- Docstring MCP hiện dùng `/` — **đang gây fail** (đã chứng minh bằng test)

### D. Không cần SQLite

- Mọi logic trên đã có trong `xml_fbograph/query/engine.py` + Kuzu
- Chỉ expose lại qua MCP tools

## Acceptance

- [ ] 3 tool high-level có trên MCP
- [ ] Case CPTran navigate trả đủ grids + needs_xml (CPTax.f) không cần Cypher tay
- [ ] Case search `gia ban` / `giay bao no` / `TenVtFromDienGiai` qua search_nodes OK
- [ ] Docstring query_radar không còn ví dụ `/` sai hoặc đã normalize
- [ ] `scripts/test_agent_cypher_traps.py` fail giảm; thêm test MCP high-level pass
