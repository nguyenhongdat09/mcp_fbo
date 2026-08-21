# Review triển khai `summary_xml` (post-implement)

> **Ngày review:** 2026-08-21  
> **Phạm vi:** Code sau walkthrough hoàn thành Phase A–E (`js_engine`, `xml_controller_summary`, bridges, MCP `read_option=3`).  
> **Đối chiếu:** [`docs/doc_summary_xml/`](../doc_summary_xml/)  
> **Test chạy lại khi review:** `tests/js_engine` + `tests/xml_controller_summary` + `tests/find_entity_by_xml/test_summary_xml_bridge.py` → **8 passed**.

---

## 1. Đánh giá tổng quan

| Mức | Kết luận |
|-----|----------|
| Kiến trúc tách lớp | **Đạt** — dependency một chiều; `js_engine` / `xml_controller_summary` không leak MCP/DB/flat |
| Contract MCP `read_option=3` | **Đạt** — wiring đúng, docstring Agent, reject opt khác qua Pydantic |
| Schema JSON Spec 1.0 | **Đạt phần lớn** — `controller` luôn có; field bucket + lookup/onchange đúng fixture |
| Golden / production edge | **Chưa verify UNC SVTran** (share không mount được môi trường review) |
| Sẵn sàng dùng Agent | **Có** — unit + bridge OK; nên xử lý các mục §3 trước khi coi là “đóng” hoàn toàn |

**Verdict:** Triển khai **đúng hướng docs**, chất lượng tốt để Agent bắt đầu dùng `read_option=3`. Còn một số **sót kiến trúc/migration** và **heuristic SQL views** nên sửa trong PR follow-up.

---

## 2. Điểm đã làm tốt

1. **`js_engine` thuần** — `parse()` + SLL/LL fallback; identifier `$` (fixture `onChange$Voucher$Customer` pass).
2. **`xml_controller_summary` pure** — nhận flat string; không `open`/`flat_xml`/`pyodbc`.
3. **Extract Checking** — sniff JS mặc định; route SQL + warning `checking_routed_to_sql`.
4. **SQL wrap fragment** — thử `tsql_file` rồi wrap `CREATE PROCEDURE dbo.#xml_frag` đúng hướng docs §5.5.
5. **Field classifier** — `char/number/checkbox/date`, lookup, onchange, self-closing `<field …/>`.
6. **Bridge mỏng** — `flat_xml` + `analyze_flat_xml` + `result_to_dict`; xử lý `.f` / `flat_failed`.
7. **MCP** — `mcp_tools` chỉ gọi bridge; `Literal[1,2,3]`; README + `.cursorrules` ưu tiên opt 3.
8. **PyInstaller hiddenimports** — đã thêm `js_engine*` / `xml_controller_summary*` / bridges.
9. **Test tầng** — Dir fixture (JS+SQL+fields+encrypted), Filter (`js` empty), empty input, bridge temp file.

---

## 3. Góp ý / thiếu sót (ưu tiên sửa)

### P1 — Nên sửa sớm

#### 3.1. `extract_expanded_blocks` facade **chưa** delegate (dual logic)

Docs (`04` / checklist **B0**) yêu cầu: logic extract chuyển vào `xml_controller_summary/extract.py`, facade **giữ API** và **delegate** để Graph không lệch.

**Hiện trạng:** [`find_entity_by_xml/facade.py`](../../find_entity_by_xml/facade.py) vẫn giữ bản regex cũ:

- Mọi `<command>` (kể cả **Checking JS**) → `sql_blocks`
- Không sniff Checking
- Caller: [`xml_fbograph/parsers/xml_parser.py`](../../xml_fbograph/parsers/xml_parser.py) (FBOGraph build)

→ Graph index và `summary_xml` **hai nguồn sự thật** khác nhau về JS/SQL của Checking.

**Đề xuất:**

```text
extract_expanded_blocks(path):
  flat = flat_xml(...)
  entities = ... (giữ như cũ)
  blocks = extract_controller_blocks(flat)   # từ xml_controller_summary
  map JsChunk/SqlChunk → js_blocks/sql_blocks format cũ (content/line/tag)
  return {..., flat_text, system_entities, param_entities}
```

Giữ shape dict cũ để không phá Graph.

---

#### 3.2. Heuristic `views` lệch docs + không dùng `SqlFragmentVisitor.get_views()`

Trong [`analyze.py`](../../xml_controller_summary/analyze.py):

```python
views_list = [t for t in tables_list if t.lower().startswith("v") or t.lower().startswith("zv")]
```

Vấn đề:

- `startswith("v")` quá rộng (`val`, `voucher`, … nếu xuất hiện trong FROM).
- `SqlFragmentVisitor.get_views()` đã có regex riêng nhưng **không được gọi**.
- Regex trong visitor hiện tại `^(v[0-9a-zA-Z_]|zv[0-9a-zA-Z_])` cũng **chỉ khớp 1 ký tự** sau `v`/`zv` — gần như luôn fail với `v20dmctnk` (test pass vì analyze dùng `startswith`, không phải `get_views`).

**Đề xuất chốt:**

```python
_VIEW_RE = re.compile(r"^(v\d|zv)", re.I)  # v20..., zv...
# hoặc: r"^v[0-9]" | r"^zv"
views = [t for t in tables if _VIEW_RE.match(t)]
# bảo đảm views ⊆ tables (đã đúng nếu lọc từ tables)
```

Sửa cả visitor + analyze cho một nguồn.

---

#### 3.3. Signal `checking_routed_to_sql` thiếu trên `sql.signals`

Extract chỉ `warnings.append("checking_routed_to_sql")`. Schema docs liệt kê signal cùng tên trong `sql.signals` enum.

**Đề xuất:** khi warning có mặt, `sql.signals` cũng thêm `"checking_routed_to_sql"` (và giữ warning).

---

#### 3.4. Tham số `use_cache` trong bridge **không dùng**

[`summary_xml_bridge.summary_xml(..., use_cache=True)`](../../find_entity_by_xml/bridges/summary_xml_bridge.py) — signature có, body bỏ qua.

**Đề xuất (chọn 1):**

- Implement LRU theo `(abspath, mtime, size, spec_version)` như docs optional, **hoặc**
- Xóa param / `# noqa` + ghi docs “cache chưa làm v1” để tránh API giả.

---

### P2 — Nên cải thiện

#### 3.5. `file` trong JSON thường là **absolute path**

MCP gọi `summary_xml(str(p))` với path đã resolve → JSON `file` dài (UNC/local), tốn token; `folder_type` vẫn suy được nếu path chứa `Controllers`.

**Đề xuất:** trong bridge hoặc `mcp_read_local_file`, normalize:

- Nếu path chứa `...\Controllers\`, cắt relative từ `Controllers\` trở đi (`Dir\SVTran.xml`).
- Giữ absolute chỉ khi không suy được.

---

#### 3.6. Fallback JS không bổ sung `calls`

`fallback_extract_js` chỉ trả `functions` + `request_actions`. Khi ANTLR fail hoàn toàn, `calls` có thể rỗng dù có `f.request` / `$message.show`.

**Đề xuất:** regex nhẹ cho whitelist calls (đồng bộ §3.1 docs) khi `parse_status` failed/partial.

---

#### 3.7. Test coverage còn mỏng so với checklist F / edge docs

Thiếu (hoặc chỉ gián tiếp):

| Case | Trạng thái |
|------|------------|
| Checking body SQL → route SQL + signal | Chưa có test riêng |
| File `.f` / binary → `encrypted_file_not_supported` | Chưa |
| `#IF` / `fbo_ifdef` signal | Chưa |
| Facade delegate không phá Graph shape | Chưa (sau khi làm 3.1) |
| Live SVTran UNC / golden asserts tên hàm | Chưa chạy được (env) |

---

#### 3.8. Import thừa / sạch code nhỏ

- [`analyze.py`](../../xml_controller_summary/analyze.py): `import json` không dùng.
- Có thể dedupe view heuristic vào một helper shared trong package.

---

### P3 — Ghi nhận / không chặn

| Mục | Ghi chú |
|-----|---------|
| Live SVTran | Review env `exists False` trên UNC — cần máy mount share để assert golden README |
| Cache LRU | Docs optional — chấp nhận v1 không có nếu xóa/`use_cache` documented |
| Arrow / function expression | FBO ES5 `function name()` — OK bỏ qua |
| `items style="AutoComplete"` thiếu trên fixture | Production có; classifier chỉ cần `controller` — OK |

---

## 4. Kiểm tra kiến trúc (nhanh)

| Quy tắc | Kết quả |
|---------|---------|
| `js_engine` → không import FBO packages | OK (AST scan) |
| `xml_controller_summary` → không import facade/MCP/DB | OK |
| MCP không chứa extract/ANTLR | OK (`mcp_tools` chỉ bridge) |
| Reuse `tsql_engine.parse` | OK |
| Facade extract = một nguồn sự thật với summary | **FAIL** — xem §3.1 |

---

## 5. Checklist follow-up đề xuất (PR tiếp)

- [ ] **F1.** Delegate `extract_expanded_blocks` → `extract_controller_blocks` + map format cũ
- [ ] **F2.** Sửa heuristic `views` (một regex; dùng chung visitor/analyze); `views ⊆ tables`
- [ ] **F3.** Thêm `checking_routed_to_sql` vào `sql.signals`
- [ ] **F4.** `use_cache`: implement hoặc bỏ/document
- [ ] **F5.** Normalize `file` relative từ `Controllers\`
- [ ] **F6.** Test: Checking-SQL, `.f` encrypted, `#IF`, facade shape cho Graph
- [ ] **F7.** (Optional) Fallback regex cho `js.calls` whitelist
- [ ] **F8.** Smoke UNC SVTran khi có mạng nội bộ — assert `onChange$Voucher$Customer`, `ma_kh.lookup`, tables partition

---

## 6. Kết luận gửi team

Implementation **đạt mục tiêu v1** (Agent gọi `read_option=3` nhận JSON gọn, tầng tách đúng). Điểm phải ưu tiên nhất là **§3.1 dual extract** (Graph vs summary_xml) và **§3.2 views heuristic** — nếu không, lâu dài index Kùzu và summary tool sẽ “nói khác nhau” về cùng một file Checking/JS.

Các mục P2/P3 không chặn ship nội bộ, nhưng nên đóng trong sprint follow-up trước khi quảng bá rộng cho mọi Agent.
