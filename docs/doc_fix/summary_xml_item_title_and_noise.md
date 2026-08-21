# summary_xml — Fix metadata `title` + nhiễu Item.xml (Dir + Grid)

> **Cho Gemini.** Baseline thật:  
> - `Dir\Item.xml` — `\\172.168.5.14\CustomerPro\FBO\KOYU-FBOR2\Program\App_Data\Controllers\Dir\Item.xml`  
> - `Grid\Item.xml` — `\\172.168.5.14\CustomerPro\FBO\KOYU-FBOR2\Program\App_Data\Controllers\Grid\Item.xml`  
> **Không** đổi MCP API / kiến trúc tầng. User **không** quan tâm `spec_version`.

---

## 1. Quan sát JSON — Dir\Item.xml

| Mục | JSON | Thực tế file | Đánh giá |
|-----|------|--------------|----------|
| `db_table` / `code_field` | `dmvt` / `ma_vt` | `<dir table="dmvt" code="ma_vt">` | OK |
| `title_v` / `title_e` | **null** | `<title v="vật tư" e="Item"></title>` | **P0 bug** |
| `id` | null | root **không** có `id=` | OK (đúng) |
| `js.calls` / `request_actions` | `[]` | script chính không `f.request` / `g.showForm` | OK |
| `sql.blocks` | Loading…Deleting + action Suggestion | khớp | OK |
| `sql.tables` | `cdvt`, `ct70`, `ct90`, `dmqddvt`, `zcctkhvt` | hợp lý | OK |
| `sql.procs` | **`nvarchar`**, `sp_executesql` | `nvarchar` = kiểu T-SQL, không phải proc | **P1 bug** |
| `signals` | `dynamic_sql`, `encrypted_skipped` | có sp_executesql + encrypted | OK |
| `fields.lo_yn` onchange | **thiếu** | `onclick="onChangeLot(this);"` | **P2** |
| `fields` lookup | UOM, Site, Account… | khớp | OK |
| `parse_ms` | ~5 | OK | OK |

---

## 1b. Quan sát JSON — Grid\Item.xml

| Mục | JSON | Thực tế file | Đánh giá |
|-----|------|--------------|----------|
| `db_table` / `code_field` | `dmvt` / `ma_vt` | `<grid table="dmvt" code="ma_vt">` | OK |
| `title_v` / `title_e` | **null** | `<title v="Danh mục hàng hóa - vật tư" e="Item List">` | **P0** (cùng bug §2) |
| `js.calls` | `$message.show`, `g.request`, `g.showForm` | khớp DownloadScript + show$Form | OK |
| `request_actions` | `Download` | khớp | OK |
| `show_forms` | **thiếu key / rỗng** | `show$Form(g, 'ItemImport')` → form `ItemImport` | **P2** |
| `sql.parse_status` | **`failed`** | SQL chủ yếu CreateTicket + `select … as message` | **P1** (nhãn sai) |
| `sql.tables` | `[]` | Sau expand: `insert into @@sysDatabaseName..ticket` | **P1** (không bắt `ticket`) |
| `fields.lo_yn` / `nhieu_dvt` type `char` | XML **không** `type="Boolean"` | OK theo rule hiện tại |
| `parse_ms` | 1 | OK | OK |

---

## 2. P0 — `title_v` / `title_e` luôn null

### Nguyên nhân

Trong `xml_controller_summary/analyze.py` hiện đang lấy title từ **attribute root**:

```python
title_v=root_attrs.get("title"),
title_e=root_attrs.get("title2"),
```

FBO **không** viết vậy. Chuẩn controller:

```xml
<dir table="dmvt" code="ma_vt" ...>
  <title v="vật tư" e="Item"></title>
```

(Grid / Filter / Report tương tự: child `<title v="..." e="...">`.)

Kuzu / FBOGraph đã làm đúng trong [`xml_fbograph/parsers/xml_parser.py`](../../xml_fbograph/parsers/xml_parser.py) ~194–203:

```python
for elem in root.iter():
    if etree.QName(elem.tag).localname == 'title':
        title_v = elem.get('v') or ''
        title_e = elem.get('e') or ''
        break
```

### Fix bắt buộc

Trong `extract_controller_blocks` (hoặc helper riêng gọi từ `analyze_flat_xml`):

1. Regex trên flat XML (đã strip encrypted), **ưu tiên child element**:

```python
TITLE_RE = re.compile(
    r"<title\b([^>]*)/?>",
    re.IGNORECASE,
)
# parse attrs → v, e
```

2. Gán:

```python
title_v = title_attrs.get("v") or None
title_e = title_attrs.get("e") or None
# rỗng "" → None
```

3. **Không** còn đọc `root_attrs["title"]` / `title2` (trừ fallback hiếm nếu gặp attribute — optional; child element thắng).

4. Namespace: flat có thể giữ `xmlns` trên root; thẻ vẫn là `title` local — regex `<title\b` đủ (giống cách extract field hiện tại).

### Kỳ vọng Item.xml

```json
"controller": {
  "folder_type": "Dir",
  "db_table": "dmvt",
  "code_field": "ma_vt",
  "title_v": "vật tư",
  "title_e": "Item",
  "id": null
}
```

### Test

- Fixture mini: `<dir table="t" code="c"><title v="A" e="B"/></dir>` → titles đúng.
- Regression: file **không** có `<title>` → vẫn `null` (không crash).
- Optional UNC: Item.xml + 1 Tran có title (vd. SVTran / PVTran nếu có).

---

## 3. P1 — `procs` chứa `nvarchar` (và kiểu T-SQL tương tự)

### Nguyên nhân

Extract `EXEC|EXECUTE <name>` / visitor proc nhầm **kiểu dữ liệu** hoặc identifier không phải proc.  
`sp_executesql` giữ được (đã có test + signal `dynamic_sql`) — **OK**.  
`nvarchar` **không** được nằm trong `sql.procs`.

### Fix

Mở rộng denylist dùng khi add proc (không chỉ table), ví dụ trong `is_plausible_table_name` hoặc `is_plausible_proc_name` riêng:

```python
SQL_TYPE_NOISE = {
    "nvarchar", "varchar", "nchar", "char", "int", "bigint", "smallint",
    "tinyint", "bit", "decimal", "numeric", "money", "smallmoney",
    "float", "real", "datetime", "smalldatetime", "date", "time",
    "uniqueidentifier", "xml", "text", "ntext", "image", "sysname",
}
```

- Áp khi push vào `procs` (và ideally tables nếu chưa).
- `sp_executesql` **không** denylist.

### Kỳ vọng Item.xml

```json
"procs": ["sp_executesql"]
```

(hoặc `[]` nếu team muốn chỉ giữ proc nghiệp vụ — **chốt: bỏ `nvarchar`; giữ `sp_executesql`** như test hiện có.)

---

## 4. P2 — `onchange` bỏ sót `onclick=`

`lo_yn`:

```xml
<clientScript><![CDATA[onclick="onChangeLot(this);"]]></clientScript>
```

`extract_onchange` chỉ match `onchange=` → field không có `onchange: "onChangeLot"`.

### Fix

Mở regex (cùng nhóm handler UI):

```python
r"(?:onchange|onclick)\s*=\s*[\"']\s*([a-zA-Z0-9_$]+)\s*\("
```

Emit key JSON vẫn là **`onchange`** (contract cũ) — giá trị = tên hàm (`onChangeLot`).

### Kỳ vọng

```json
{ "name": "lo_yn", "type": "checkbox", "onchange": "onChangeLot" }
```

---

## 5. Không phải lỗi (đừng “fix”)

| Hiện tượng | Lý do |
|------------|--------|
| `id: null` | Dir Item không khai `id` trên root |
| `calls` / `request_actions` rỗng | Không có call whitelist trong script chính |
| Grid `title_*` null trước đây | Nhiều Grid không có `<title>` — sau P0 chỉ fill khi có thẻ |
| `hidden` thiếu trên một số `%l` | Item: một số `ten_*%l` không `hidden="true"` trong XML gốc |

---

## 6. Thứ tự làm

```
1) Extract <title v e> → ControllerMeta (P0)
2) Denylist kiểu T-SQL khỏi procs (P1)
3) onclick → onchange handler (P2)
4) Tests + cập nhật ngắn 04_extract / 03_schema nếu cần ví dụ
```

---

## 7. Definition of Done

- [x] Item.xml: `title_v="vật tư"`, `title_e="Item"` (đo thực tế trên UNC Item.xml)
- [x] Item.xml: `procs` không còn `nvarchar`
- [x] Item.xml: `lo_yn.onchange == "onChangeLot"` (bắt qua `onclick=`)
- [x] Unit tests xanh; không regress SVTran/PVDetail (15 passed, 1 skipped UNC)

---

## Changelog

| Ngày | Việc |
|---|---|
| 2026-08-21 | **P0:** Trích xuất `title_v`, `title_e` từ child element `<title v="..." e="...">` trong `extract.py` và gán vào `ControllerMeta` trong `analyze.py`. |
| 2026-08-21 | **P1:** Thêm `SQL_TYPE_NOISE` và `is_plausible_proc_name` trong `fallback_regex.py` loại bỏ `nvarchar` và các kiểu dữ liệu T-SQL khỏi danh sách `procs`. |
| 2026-08-21 | **P2:** Mở rộng `_ONCHANGE_RE` trong `field_classifier.py` hỗ trợ cả `onclick=` và `onchange=` cho các trường checkbox. |

