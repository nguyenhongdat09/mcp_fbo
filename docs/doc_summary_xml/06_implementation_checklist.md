# 06 — Implementation Checklist (`summary_xml`)

> **Kiến trúc:** [07_architecture_layers.md](./07_architecture_layers.md)  
> Làm **tuần tự**: `js_engine` → `xml_controller_summary` → bridge → MCP.  
> Reuse `tsql_engine` — **không** viết lại grammar T-SQL.

---

## Phase 0 — Đọc & setup

- [ ] **0.1.** Đọc `07_architecture_layers.md` **trước** — tách biệt / reuse / nhúng nhẹ / anti-pattern
- [ ] **0.2.** Đọc `04_extract_and_antlr.md` (extract + sniff Checking)
- [ ] **0.3.** Confirm `antlr4-python3-runtime==4.13.2` đã có trong `requirements.txt`
- [ ] **0.4.** `scripts/check_imports.py` (hoặc tương đương) — fail nếu:
  - `js_engine` import `xml_controller_summary` / MCP / `find_entity_by_xml`
  - `xml_controller_summary` import `fastbusiness_mcp` / `pyodbc` / `xml_fbograph.mcp_tools` / `flat_xml`
  - `mcp_app` import `js_engine` / `tsql_engine` / visitors
- [ ] **0.5.** Khắc ghi 3 cấp API: `parse` (engine) → `analyze_flat_xml` (feature) → `summary_xml(path)` (I/O)
---

## Phase A — `js_engine/` (ANTLR JS thuần)

- [ ] **A1.** Tạo `js_engine/` — `engine.py`, `preprocess.py`, `errors.py`
- [ ] **A2.** Download / copy ECMAScript/JavaScript `.g4` vào `grammar/` (commit)
- [ ] **A3.** Verify Identifier cho phép `$` (FBO `onChange$Voucher$Customer`)
- [ ] **A4.** `tools/generate.bat` → `generated/` (commit generated)
- [ ] **A5.** Public API: `parse(source) -> ParseResult` status ok|partial|failed
- [ ] **A6.** `tests/js_engine/test_parse_basic.py` — parse `function onChange$Voucher$Customer(o){}` — **không** XML
- [ ] **A7.** `js_engine/README.md` — hướng dẫn visitor ở package khác

**Done khi:** parse fixture JS có `$` trong tên hàm; zero import project FBO khác.

---

## Phase B — `xml_controller_summary/` (pure logic)

- [ ] **B0.** Scan callers `extract_expanded_blocks` — đã biết: `xml_fbograph/parsers/xml_parser.py`. Khi move logic → **giữ facade delegate**, không xóa API.
- [ ] **B0.5.** Spike `tsql_engine.parse` trên SQL fragment XML (không CREATE PROC): thử `tsql_file` trực tiếp; nếu kém → chốt wrap `CREATE PROCEDURE dbo.#xml_frag AS BEGIN … END` (xem `04` §5.5). Ghi kết quả spike vào comment code.
- [ ] **B1.** `models.py` — `SummaryXmlResult`, `JsSummary`, `SqlSummary`, `FieldSummary`, `Meta`
- [ ] **B2.** `extract.py` — strip encrypted; script / command / action / query / field
- [ ] **B3.** Checking language sniff (default JS)
- [ ] **B4.** `visitors/js_summary_visitor.py` — functions, request_actions, calls whitelist **cứng** (§3.1 / `04` §4.5)
- [ ] **B5.** `visitors/sql_fragment_visitor.py` — tables, procs, signals (qua `tsql_engine.parse` + wrap nếu cần); `views ⊆ tables`
- [ ] **B6.** `fallback_regex.py` — JS + SQL regex khi ANTLR partial/failed
- [ ] **B7.** `field_classifier.py` — char|number|checkbox|date + lookup + onchange
- [ ] **B8.** `analyze.py` — `analyze_flat_xml(flat_text, source_path=...)`; xử lý `.f` encrypted → warning `encrypted_file_not_supported` (khi bridge phát hiện flat rỗng/binary)
- [ ] **B9.** `formatter.py` — `result_to_dict` (JSON thuần); **luôn** có key `controller`
- [ ] **B10.** `tests/xml_controller_summary/` — fixture mini Dir (ma_kh, Checking JS, Loading SQL, encrypted) **và** fixture mini Filter (`js` empty + `query`)

**Done khi:** analyze fixture ra JSON đúng schema `03`; không đọc disk trong package.

**Cấm:** `flat_xml`, `open()`, MCP, pyodbc trong package này.

---

## Phase C — Bridge `find_entity_by_xml`

- [ ] **C0.** Tạo folder mới `find_entity_by_xml/bridges/` + `__init__.py` (hiện **chưa** có)
- [ ] **C1.** `bridges/summary_xml_bridge.py` — `summary_xml(path)` = flat_xml + analyze + dict; `.f`/encrypted → `success: false` + warning
- [ ] **C2.** `bridges/summary_xml_format.py` — markdown MCP
- [ ] **C3.** (Optional) LRU cache theo mtime
- [ ] **C4.** Tests bridge với temp file XML nhỏ trên disk

**Cấm:** ANTLR visitor trực tiếp trong bridge — chỉ gọi `xml_controller_summary` + `flat_xml`.

---

## Phase D — MCP wiring (chỉ nhúng nhẹ bridge)

- [ ] **D1.** `mcp_app.py` — `read_option: Literal[1, 2, 3]` + cập nhật Field description / docstring
- [ ] **D2.** `xml_fbograph/mcp_tools.py` — nhánh `read_option == 3` **chỉ** `format_summary_xml_result(summary_xml(path))`
- [ ] **D3.** Không import `js_engine` / `tsql_engine` / extract / visitor trong `mcp_app.py` **và** không viết extract trong `mcp_tools.py`
- [ ] **D4.** Regression: opt 1 và 2 không đổi
- [ ] **D5.** Test reject `read_option=99` vẫn pass
- [ ] **D6.** Xác nhận không có bản copy logic summary thứ hai trong `xml_fbograph/builder`
---

## Phase E — Repo docs & packaging

- [ ] **E1.** Root `README.md` — `read_local_file` ghi opt 3 summary_xml
- [ ] **E2.** `.cursorrules` — ưu tiên `read_option=3` khi chỉ cần bản đồ controller
- [ ] **E3.** PyInstaller hiddenimports (`js_engine`, `xml_controller_summary`, bridges)
- [ ] **E4.** (Optional) live test UNC SVTran nếu môi trường mount được share

---

## Phase F — Acceptance (golden rules)

Từ fixture hoặc UNC SVTran:

- [ ] `js.sources` chứa `script` và `command:Checking` (khi Checking là JS)
- [ ] `js.functions` chứa `onChange$Voucher$Customer` (SVTran / fixture tương đương)
- [ ] `js.request_actions` chứa ít nhất một action (`Customer` / `TaxAccount`…)
- [ ] `sql.blocks` có `command` Loading (hoặc tương đương) và ít nhất một `action`
- [ ] `sql.tables` không rỗng trên Tran có SQL
- [ ] Field `ma_kh`: `type=char`, `lookup=Customer`, `onchange=onChange$Voucher$Customer`
- [ ] Field Decimal → `number`; DateTime → `date`
- [ ] Encrypted không xuất hiện plaintext trong JSON
- [ ] JSON response ước lượng < 20 KB trên SVTran-class (spot-check)

---

## Thứ tự tuyệt đối (đừng đảo)

```
0 → A (js_engine)
  → B (xml_controller_summary + tsql_engine reuse)
  → C (bridge flat)
  → D (MCP)
  → E (docs/rules/spec)
  → F (acceptance)
```
