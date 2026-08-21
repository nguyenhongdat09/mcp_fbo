# 01 — Overview: `summary_xml` (qua `read_local_file`)

## 1. Bối cảnh

Dự án **FastBusiness MCP** (`E:\PythonProject\mcp_fbo\`) đã có:

| Tool | Vai trò liên quan XML / SQL |
|------|------------------------------|
| `query_database` + `summary_object` (mode) | Tóm tắt proc/view SQL Server (ANTLR T-SQL) |
| `query_radar` | Graph XML (metadata, không thay body đầy đủ) |
| `read_local_file` | Đọc file raw (`1`) hoặc flat entity (`2`) |
| `get_xml_entities` | ENTITY Include — Agent vẫn phải tự đọc nhiều vòng |

Trong thực tế Agent FBO khi sửa chứng từ (`Dir/*Tran.xml`):

1. Gọi `read_local_file(read_option=2)` → nhận **full flat XML** (~2.000–5.000 dòng).
2. Tự lọc hàm JS, bảng SQL, field lookup → token tăng rất nhanh.
3. Graph (`query_radar`) có `js_text`/`sql_text` đã nối nhưng **không** có cấu trúc hàm / bảng / type field gọn.

Đã có sẵn nền tảng (**reuse / nhúng nhẹ — không copy vào MCP**):

- `find_entity_by_xml.facade.flat_xml` — expand ENTITY (giữ ở lớp I/O)
- `extract_expanded_blocks` — regex tách block (chuyển logic vào `xml_controller_summary/extract`; facade chỉ delegate)
- `tsql_engine` — nhúng `parse()` cho SQL trong XML (không fork)
- Pattern kiến trúc `summary_object`: engine → pure feature → bridge mỏng → MCP (xem `docs/doc/07` + `docs/doc_summary_xml/07`)
## 2. Mục tiêu

Thêm chế độ **`summary_xml`** trên tool hiện có `read_local_file` (`read_option=3`) trả **JSON có cấu trúc**, đủ để Agent:

| Việc Agent hay làm | Summary |
|--------------------|---------|
| Biết XML có những hàm JS nào | ✅ `js.functions` |
| Biết `f.request('X')` map action nào | ✅ `js.request_actions` |
| Biết command/action đụng bảng / proc nào | ✅ `sql.tables` / `sql.procs` |
| Biết field type + lookup + onChange | ✅ `fields[]` |
| Đọc full flat để sửa từng dòng | Dùng `read_option=2` |

**Nguyên tắc tier (song song summary_object):**

```
summary (read_option=3)  →  flat (2)  →  raw (1)
(mặc định khi chỉ cần bản đồ)   (sửa code)   (debug entity)
```

Agent rule (ghi trong tool description): **ưu tiên** `read_option=3` trước khi flat full khi chỉ cần định hướng.

## 3. Phạm vi v1

### Làm

- Input: file controller FBO `.xml` (sandbox theo `reference_file` như hiện tại). Cũng nhận path `.f` nhưng xem bullet riêng bên dưới.
- Bước 1: **flat** toàn bộ ENTITY / Include (`flat_xml`) — **không** quan tâm `%Entity` trong DOCTYPE sau flat
- Bước 2: Strip khối `<encrypted>` / `<Encrypted>` (không cố decrypt)
- Bước 3: Tách nội dung:
  - **JS:** CDATA của `<script>` + `<command event="Checking">` (mặc định); nối rồi ANTLR một lần
  - **SQL:** CDATA của mọi `<command>` khác Checking + mọi `<action>` + `<query>` (nếu có)
  - **Fields:** mọi `<field>` trong flat — type bucket + lookup + onChange ngắn
- Parse JS bằng ANTLR4 ECMAScript (package `js_engine/`), hỗ trợ identifier có `$` (`onChange$Voucher$Customer`)
- Parse SQL bằng **reuse** `tsql_engine` (visitor nhẹ / reuse pattern `sql_object_summary`) — **không** call graph DB
- Trả JSON theo `03_json_schema.md`
- Fallback regex nếu ANTLR fail → `parse_status: partial|failed` + vẫn trả field summary nếu extract được
- **File `.f` (mã hóa toàn phần):** cố `flat_xml` như `.xml`. Nếu nội dung rỗng / binary encrypted / flat fail → trả JSON `success: false` + `meta.warnings` chứa `encrypted_file_not_supported` — **không** cố decrypt. Agent nên gọi lại path `.xml` cặp (nếu có) hoặc báo user.
- **Grid / Filter / Report / Lookup:** cùng pipeline. Thường **không** có `<script>` / Checking → `js.parse_status: "empty"` là **expected** (không phải lỗi). SQL chủ yếu từ `<query>` (+ command nếu có). Xem ví dụ Filter trong `03_json_schema.md` §7b.

### Không làm v1

- Tool MCP riêng tên `summary_xml` (chỉ mở rộng `read_local_file`)
- Decrypt nội dung encrypted / decrypt file `.f`
- Call graph đệ quy SQL Server / đọc definition proc từ DB (dùng `query_database` / summary_object khi cần)
- Sync kết quả vào Kùzu / `query_radar`
- Snippet mode / full mode riêng (v1 chỉ summary; flat vẫn là `read_option=2`)
- Parse perfect mọi dynamic SQL / string JS phức tạp (chỉ signal + extract tốt nhất có thể)
- Sửa / ghi file XML

## 4. Quy tắc nguồn JS / SQL (FastBusiness Dir)

### JS — đúng 2 chỗ mặc định (đã xác nhận SVTran)

| Nguồn | Ví dụ SVTran (flat) | Nội dung điển hình |
|-------|---------------------|-------------------|
| `<script><text><![CDATA[...]]>` | ~dòng 2452 | `function init$Voucher$`, `onChange$Voucher$*`, handler |
| `<command event="Checking"><text><![CDATA[...]]>` | ~dòng 2332 | Validation JS trước save (`f._checked`, `$message.show`) |

**Không** đưa `<clientScript>` vào ANTLR concat — chỉ gắn vào field summary.

### SQL — các thẻ còn lại

| Nguồn | Ví dụ | Nội dung điển hình |
|-------|-------|-------------------|
| `<command event="Loading">` | ~855 | `declare`, `from options`, `@@prime$partition$current` |
| `<command event="Scattering">` | ~944 | SQL scatter form |
| `<command event="Inserting|Updating|...">` | … | CRUD SQL |
| `<action id="TaxAccount">` | ~3288 | Lookup SQL ngắn |
| `<query>` | Filter/Report | SQL listing |

### Language sniff — `Checking`

Mặc định: **Checking = JS**.

Chuyển sang SQL bucket **chỉ khi** body (sau strip comment/encrypted) thỏa:

1. Trim bắt đầu bằng token SQL: `declare` | `select` | `if exists` | `exec` | `execute` | `with` (CTE), **và**
2. **Không** chứa `function ` hoặc `var f = this` trong ~200 ký tự đầu (sau trim)

Ghi `meta.warnings` nếu sniff đổi bucket (`checking_routed_to_sql`).

## 5. Fields — chỉ bucket type

Agent không cần full attribute field. Map:

| Bucket | Điều kiện FBO |
|--------|----------------|
| `date` | `type="DateTime"` hoặc tên type chứa `Date` |
| `number` | `type` ∈ Decimal, Int16, Int32, Int64, Numeric, Double, Single, … |
| `checkbox` | `type` CheckBox/Boolean **hoặc** `items/@style="CheckBox"` |
| `char` | mặc định (không type, TextBox, Mask, AutoComplete…) |

Lookup ngắn: `items/@controller` → `lookup`.  
OnChange: extract tên hàm từ `clientScript` CDATA (`onchange="Fn(this);"` → `Fn`).

## 6. Vì sao ANTLR4 (JS + SQL)

| Phương án | Ưu | Nhược |
|-----------|-----|-------|
| Regex thuần (js_parser hiện có) | Đã có trong FBOGraph | Dễ miss nested / string / `$` phức tạp |
| **ANTLR ECMAScript** | Cây cú pháp, function decl rõ | Cần grammar + `$` identifier |
| **Reuse tsql_engine** | Đã ổn định từ summary_object | Fragment XML không có CREATE PROCEDURE — cần entry/preprocess |

**Fallback:** parse fail → regex (`xml_fbograph` patterns) + `parse_status: partial`.

## 7. Liên hệ research thực tế (SVTran LIKSIN)

File golden:

`\\172.168.5.14\CustomerPro\HRM\LIKSIN\FBISP23\App_Data\Controllers\Dir\SVTran.xml`

Quan sát flat MCP (`read_option=2`):

- Checking chứa JS (`/* <flatten type="Javascript"> */`), không phải SQL
- Loading/Scattering/TaxAccount chứa SQL
- `ma_kh`: AutoComplete `controller="Customer"` + `onChange$Voucher$Customer`
- Script có khối `<encrypted>...</encrypted>` — phải skip
- DOCTYPE `%CheckTaxCode` — sau flat không cần quan tâm entity

## 8. Thành công / KPI

- Response `read_option=3` cho SVTran-class (~3k dòng flat): **< 20 KB JSON** (ưu tiên < 15 KB)
- Parse JS thành công ≥ 85% Dir Tran sample (có `$` trong tên hàm)
- Parse SQL thành công ≥ 80% block (partial chấp nhận với `#IF` / preprocessor FBO)
- `read_option` 1 và 2 **không regress**
- Test fixture mock + (optional) UNC SVTran pass checklist `06`
