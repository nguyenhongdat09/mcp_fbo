# summary_xml — Fix Grid\Item.xml (`sql.failed` + `show$Form`)

> **Cho Gemini.** Baseline thật sau khi title đã OK:  
> `\\172.168.5.14\CustomerPro\FBO\KOYU-FBOR2\Program\App_Data\Controllers\Grid\Item.xml`  
> **Không** đổi MCP API / kiến trúc tầng. User **không** quan tâm `spec_version`.

---

## 1. Quan sát JSON (hiện tại)

| Mục | JSON | Thực tế file | Đánh giá |
|-----|------|--------------|----------|
| `title_v` / `title_e` | `Danh mục hàng hóa - vật tư` / `Item List` | `<title v=… e=…>` | OK |
| `db_table` / `code_field` | `dmvt` / `ma_vt` | root `<grid>` | OK |
| `js.calls` | `$message.show`, `g.request`, `g.showForm` | DownloadScript + `g.showForm(c)` | OK |
| `request_actions` | `Download` | khớp action + `g.request` | OK |
| `show_forms` | **thiếu / omit** | `show$Form(g, 'ItemImport')` | **P1** |
| `related_controllers` | thiếu | suy từ `ItemImport` | **P1** (theo sau show_forms) |
| `sql.parse_status` | **`failed`** | Có SQL (CreateTicket) nhưng 0 table/proc | **P1** |
| `sql.tables` | `[]` | `insert into @@sysDatabaseName..ticket` | **P1** |
| `sql.blocks` | Loading, Closing, Download | khớp | OK |
| `fields.lo_yn` / `nhieu_dvt` type `char` | XML không `type="Boolean"` | **OK** — đừng đoán |
| `parse_ms` | 1 | OK | OK |

---

## 2. P1 — `sql.parse_status: failed` + không ra bảng `ticket`

### 2.1. SQL thật (sau ENTITY expand)

ENTITY `CreateTicket` trong DOCTYPE:

```sql
insert into @@sysDatabaseName..ticket values(@ticket, @@userID, 'Item', @filename, @description, '@@appDatabaseName', getdate());
```

Loading / Download action đều nhúng `&CreateTicket;` rồi `select … as message` / `select @ticket as value`.

Closing chỉ `select 'dispose$Grid…' as message` — không có table (bình thường).

### 2.2. Nguyên nhân

1. Regex `SQL_TABLE_RE` bắt được `@@sysDatabaseName..ticket` sau `INTO`.
2. `is_plausible_table_name` **reject** mọi tên bắt đầu `@` / `#`:

```python
if low.startswith("#") or low.startswith("@"):
    return False
```

→ Mất `ticket` → `tables=[]` + `procs=[]` + `line_count > 0` → trong `analyze_sql_chunks`:

```python
if not tables_list and not procs_list:
    status = "empty" if total_lines == 0 else "failed"  # ← nhãn “failed” gây hiểu nhầm
```

Đây **không** phải ANTLR fail — chỉ là heuristic status khi không extract được object.

### 2.3. Fix

**A. Chuẩn hóa tên bảng FBO sys/app (bắt buộc)**

Trong `clean_table_name` (hoặc trước `is_plausible`):

- Strip prefix dạng:
  - `@@sysDatabaseName..`
  - `@@appDatabaseName..`
  - `@@sysDatabaseName.`
  - `@@appDatabaseName.`
- Giữ phần sau: `ticket`
- Vẫn reject biến `@ticket`, temp `#tmp`

```python
# sau khi strip [] và dbo.
# lặp bỏ @@sysDatabaseName.. / @@appDatabaseName.. (case-insensitive)
```

**B. Điều chỉnh `parse_status` (bắt buộc)**

Khi có `blocks` / `line_count > 0` nhưng không table/proc:

| Tình huống | Status đề xuất |
|------------|----------------|
| Chỉ `select '…' as message` / JS bridge, không DML/DDL object | **`ok`** hoặc **`empty`** — **cấm `failed`** nếu extract không lỗi |
| Regex/ANTLR thực sự lỗi có warning | `partial` / `failed` + `meta.warnings` |

Chốt v1 cho Grid Item sau khi A chạy:

- `tables` chứa `ticket`
- `parse_status`: **`ok`**
- Optional signal: không bắt buộc

Nếu sau A vẫn không có table (file chỉ Closing-style message): dùng `ok` khi blocks có mặt và không có warning parse — tránh `failed` giả.

### 2.4. Kỳ vọng Grid\Item.xml

```json
"sql": {
  "parse_status": "ok",
  "tables": ["ticket"],
  "procs": [],
  "views": [],
  "signals": []
}
```

---

## 3. P1 — `show_forms` bỏ sót wrapper `show$Form(g, 'ItemImport')`

### 3.1. Code trong file

```javascript
case 'ImportData':
  show$Form(g, 'ItemImport');
  break;

function show$Form(g, c) {
  (g._authorize == 1) ? g.showForm(c) : $message.show(...);
}
```

- `g.showForm(c)` — arg là **biến** → regex `g.showForm('…')` không bắt literal.
- Literal nằm ở **`show$Form(g, 'ItemImport')`**.

Pattern này phổ biến trên Grid listing (ImportData toolbar).

### 3.2. Fix

Bổ sung extract (cùng chỗ `extract_show_forms_and_related` / `JsBlockParser` fallback summary):

```python
# Wrapper FBO Grid listing
re.compile(
    r"\bshow\$Form\s*\(\s*[^,]+,\s*['\"]([a-zA-Z0-9_$]+)['\"]\s*\)"
)
```

Union với list từ `g.showForm('…')` (giữ nguyên regex Kuzu).

Sau đó chạy lại `derive_related_from_show_form` như hiện có:

- `ItemImport` không endswith `Filter` → chỉ thêm đúng `ItemImport` vào `show_forms` + `related_controllers`.

### 3.3. Kỳ vọng

```json
"show_forms": ["ItemImport"],
"related_controllers": ["ItemImport"]
```

`js.calls` đã có `g.showForm` — giữ nguyên.

---

## 4. Không phải lỗi

| Hiện tượng | Lý do |
|------------|--------|
| `lo_yn` / `nhieu_dvt` type `char` | XML không khai `type="Boolean"` |
| `id: null` | root không có `id` |
| Closing không góp table | Chỉ `select 'dispose…' as message` |
| Không có `grid_formulas` | Không khai `g.$a` |

---

## 5. Tests

### T1 — fixture CreateTicket-like

```sql
insert into @@sysDatabaseName..ticket values(@ticket, 1, 'Item', 'a', N'b', '@@appDatabaseName', getdate());
select @ticket as value
```

Assert: `"ticket" in tables`, `parse_status == "ok"`.

### T2 — fixture show$Form wrapper

```js
function show$Form(g, c) { g.showForm(c); }
show$Form(g, 'ItemImport');
```

Assert: `show_forms == ["ItemImport"]`.

### T3 — UNC Grid\Item.xml (optional)

```python
d = summary_xml(r"\\...\Grid\Item.xml", use_cache=False)
assert d["controller"]["title_v"]
assert "ticket" in d["sql"]["tables"]
assert d["sql"]["parse_status"] == "ok"
assert "ItemImport" in d["show_forms"]
```

### T4 — Regression

Dir Item / PVDetail / SVTran không đổi xấu; `pytest` package summary xanh.

---

## 6. Thứ tự làm

```
1) clean_table_name / is_plausible — strip @@sysDatabaseName.. / @@appDatabaseName..
2) parse_status: không gắn failed chỉ vì 0 table khi SQL là message-only; sau (1) Grid Item → ok + ticket
3) Regex show$Form(g, 'Name') → show_forms + related
4) Tests T1–T4
```

---

## 7. Definition of Done

- [x] Grid\Item.xml: `sql.tables` chứa `ticket`, `parse_status` ≠ `failed` (kỳ vọng `ok` — đo thực tế đạt `ok` + `ticket`)
- [x] Grid\Item.xml: `show_forms` chứa `ItemImport` (bắt qua `show$Form(g, 'ItemImport')`)
- [x] Unit tests T1/T2 xanh (16 passed, 1 skipped UNC)
- [x] Changelog dưới đây

---

## 8. Anti-pattern

- ❌ Đánh `failed` mọi khi `tables==[]` dù SQL chỉ là `select 'fn()' as message`
- ❌ Reject cả chuỗi `@@sysDatabaseName..ticket` thay vì strip prefix
- ❌ Chỉ dựa `g.showForm('…')` — bỏ wrapper `show$Form(g, '…')` chuẩn Grid listing
- ❌ Đoán `lo_yn` → checkbox khi XML không có `type`

---

## Changelog

| Ngày | Việc |
|---|---|
| 2026-08-21 | Cập nhật `clean_table_name` trong `fallback_regex.py` tự động bóc tách các tiền tố database FBO (`@@sysDatabaseName..`, `@@appDatabaseName..`) để trích xuất đúng bảng `ticket`. |
| 2026-08-21 | Điều chỉnh `parse_status` của `SqlSummary` trong `analyze.py` không đánh nhãn `failed` cho các khối SQL chỉ trả về message khi không có lỗi phân tích. |
| 2026-08-21 | Thêm regex `SHOW_DOLLAR_FORM_RE` trong `grid_formulas.py` để trích xuất hàm wrapper `show$Form(g, '...')` phổ biến trên các màn hình Grid listing. |

