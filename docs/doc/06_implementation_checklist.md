# 06 — Implementation Checklist (3 lớp)

> **Kiến trúc:** [07_architecture_layers.md](./07_architecture_layers.md)  
> Làm **tuần tự**: `tsql_engine` → `sql_object_summary` → `queryDatabase` bridge → MCP.

---

## Phase 0 — Đọc & setup
 
-- [x] **0.1.** Đọc `07_architecture_layers.md` + quy tắc dependency
-- [x] **0.2.** Thêm `antlr4-python3-runtime==4.13.2` vào `requirements.txt`
-- [x] **0.3.** `scripts/check_imports.py` — fail nếu `tsql_engine` import `queryDatabase` hoặc `sql_object_summary` import `queryDatabase`
 
---
 
## Phase A — `tsql_engine/` (ANTLR thuần)
 
-- [x] **A1.** Tạo `tsql_engine/` — `engine.py`, `preprocess.py`, `errors.py`
-- [x] **A2.** Verify `grammar/TSqlLexer.g4` + `TSqlParser.g4` **đã có trong repo** (hoặc `python tools/download_grammar.py`)
-- [x] **A2b.** Tải `antlr-4.13.2-complete.jar` → `tools/`; chạy `generate.bat` → `generated/`
-- [x] **A3.** Public API: `parse(source) -> ParseResult`
-- [x] **A4.** Hỗ trợ identifier `$` (FBO)
-- [x] **A5.** `tests/tsql_engine/test_parse_basic.py` — **không DB**
-- [x] **A6.** `tsql_engine/README.md` — hướng dẫn thêm visitor ở package khác
 
**Done khi:** parse được fixture proc đơn giản, zero import từ `queryDatabase`.
 
---
 
## Phase B — `sql_object_summary/` (pure logic)
 
-- [x] **B1.** `models.py`, `options.py` (`DEFAULT_EXCLUDE_LIKE`), `classifier.py`
-- [x] **B2.** `visitors/summary_visitor.py` — dùng `tsql_engine.parse()`, tích hợp 2-tier `param_effects.py` (Generic AST + FBO rules)
-- [x] **B3.** `analyze.py` — `analyze_definition(definition: str, ...)`
-- [x] **B4.** `snippet.py` — `extract_snippet(definition, keywords, zones)`
-- [x] **B5.** `call_graph.py` — `build_call_graph(root, definitions: dict[str,str], truncated_objects=[])`
-- [x] **B6.** `formatter.py` — `result_to_dict(SummaryResult)` (JSON thuần, **không** markdown MCP)
-- [x] **B7.** `tests/sql_object_summary/` — fixture `.sql`, không DB
 
**Done khi:** analyze fixture `rs_rpt*` mock string ra JSON đúng schema.
 
**Cấm:** `pyodbc`, `file_path`, `get_connection_config` trong package này.
 
---
 
## Phase C — `queryDatabase/object_catalog/`
 
-- [x] **C1.** `models.py` — `DbObjectMeta`, `ParameterMeta`
-- [x] **C2.** `fetcher.py` — `fetch_one`, `fetch_many`, `fetch_callers(object_id, ...)` (timeout 10s/15s)
-- [x] **C3.** SQL files: `fetch_callers.sql` dùng `sys.sql_expression_dependencies` (không dùng `dm_sql_referenced_entities` cho inbound)
-- [x] **C4.** Reuse `execute_query` + `sanitize_sql_identifier` (pattern giống `query_resolver.py`)
-- [x] **C5.** `tests/queryDatabase/test_object_catalog.py` — mock executor
 
---
 
## Phase D — `queryDatabase/bridges/summary_bridge.py`
 
-- [x] **D1.** `summary_object(...)` — orchestration; `resolve_object_ref()`; validate snippet params
-- [x] **D2.** Gọi catalog fetch → `analyze_definition` / `extract_snippet`
-- [x] **D3.** Call graph: `fetch_many` + `build_call_graph` có kiểm soát `max_objects` & `truncated_objects`
-- [x] **D4.** Thread-safe LRU cache trong bridge (MVP: key theo `modify_date`; TTL 3600s optional)
-- [x] **D5.** `summary_format.py` — `format_summary_result()`; export từ `queryDatabase/__init__.py`
-- [x] **D6.** `tests/queryDatabase/test_summary_bridge.py` — mock fetcher
 
**Cấm:** ANTLR / visitor trực tiếp trong bridge — chỉ import `sql_object_summary`.
 
---
 
## Phase E — MCP & repo wiring
 
-- [x] **E1.** `mcp_app.py` — tool `summary_object` gọi **chỉ** `summary_bridge` (pattern `MCPServer` + `Annotated`/`Field` như `query_database_tool`)
-- [x] **E2.** Không import `tsql_engine` trong `mcp_app.py`
-- [x] **E3.** Cập nhật docs vận hành:
  - `README.md` (root) — liệt kê 6 tools
  - `.cursorrules` — thêm `summary_object` + quy tắc Agent (*ưu tiên summary trước `query_database type=0`*)
  - `requirements.txt` — `antlr4-python3-runtime==4.13.2`
-- [x] **E4.** PyInstaller hidden imports (`fastbusiness_mcp.spec`)

---

## Phase F — Integration FBISP242

| # | Test | Assert |
|---|------|--------|
| F1 | `rs_rptInterestDetailedByLoanContract` summary | `@Status`, `ctdmku`, cursor |
| F2 | `zc_bcthlv` summary | pivot signals, `#pivot` |
| F3 | snippet keywords `tl_th`, `@Status` | < 150 lines |
| F4 | infra `ff_*` | depth 0 |
| F5 | VIEW bất kỳ | `object_type=VIEW`, không expand call graph |
| F6 | `max_objects=2` trên proc gọi nhiều con | `truncated: true`, `truncated_objects` không rỗng |
| F7 | `include_called_by` | `called_by` có dữ liệu hoặc `meta.warnings` nếu lỗi |
| F8 | `query_database` type 0/1/2 | không regression |
| F9 | `object_name=dbo.zc_bcthlv` vs `zc_bcthlv` + `schema=dbo` | cùng kết quả |
| F10 | `mode=snippet` không keywords/zones | error `snippet_params_required` |

### MVP vs nice-to-have (v1)

| MVP (bắt buộc) | Nice-to-have (có thể phase 1.1) |
|----------------|----------------------------------|
| `tsql_engine.parse` + SummaryVisitor cơ bản | Generic param detector đủ 4 role |
| `analyze_definition` + snippet keywords | TTL cache 3600s |
| Bridge + catalog fetch | `execute_query` parameterized |
| `max_objects` truncate | Request timeout 30s strict abort |

---

## Acceptance criteria

1. Ba folder tách rõ: `tsql_engine`, `sql_object_summary`, `queryDatabase/{object_catalog,bridges}`
2. Dependency một chiều (xem doc 07)
3. `tsql_engine` dùng được độc lập (test parse không cần MCP/DB)
4. Tool MCP `summary_object` hoạt động qua bridge
5. `pytest tests/` pass
6. `scripts/check_imports.py` pass (dependency một chiều)

---

## Prompt Gemini (cập nhật)

```
Implement summary_object for E:\PythonProject\mcp_fbo\
Follow docs/doc/ especially 07_architecture_layers.md.

Layer 1: tsql_engine/ — ANTLR only, no DB
Layer 2: sql_object_summary/ — pure analyze, imports tsql_engine only
Layer 3: queryDatabase/object_catalog + bridges/summary_bridge.py
MCP: thin wrapper in mcp_app.py

Do NOT put ANTLR inside queryDatabase/executor.py or sql_object_summary/parser/.
Run pytest per layer.
```
