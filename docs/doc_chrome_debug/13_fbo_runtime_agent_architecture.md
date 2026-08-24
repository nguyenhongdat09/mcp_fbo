# 13 — Kiến trúc FBO Runtime Agent (để Gemini implement)

> **Mục tiêu:** Sau khi Gemini code xong, Cursor Agent **tự** classify → lookup → fill → lưu → lọc → đọc grid **dynamic**, không cần user/coach chỉ từng bước như session probe thủ công.
>
> **Ngày:** 2026-08-23  
> **Kiến thức verify:** [12_fbo_webforms_mainreport_runtime.md](12_fbo_webforms_mainreport_runtime.md)  
> **Spec classifier cũ (bổ sung, không thay):** [../doc_fix/fbo_runtime_page_classifier_spec.md](../doc_fix/fbo_runtime_page_classifier_spec.md)

---

## 0. Vấn đề cần giải

| Hiện tại (probe thủ công) | Mục tiêu (agent dynamic) |
|---------------------------|---------------------------|
| Agent viết JS ad-hoc từng case | MCP trả **runtime_hints** + **action primitives** |
| Soft-hardcode `ctl00_...` trong script test | Discover id qua `Sys.Application` |
| Gõ tay mã lookup / gán thẳng input | Lookup: QuickFind → `quickFind()` → click dòng |
| Không biết field nào bắt buộc / AutoComplete | Đọc `_fields` (`AllowNulls`, `ItemStyle`) |
| Scrape HTML grid | `_getItemValue(row, col)` 1-based |

**Nguyên tắc:** Agent gọi `chrome_debug` với intent cao (inspect / fill / lookup / save / filter_grid / read_grid). Logic FBO nằm trong **Python package**, không bắt agent nhớ chữ ký runtime.

---

## 1. Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│  Cursor Agent                                                │
│  Intent: "thêm VT test", "lọc báo cáo ma_vt=…", "đọc grid" │
└───────────────────────────┬─────────────────────────────────┘
                            │ chrome_debug(type=1|2|3|4, …)
┌───────────────────────────▼─────────────────────────────────┐
│  tools.py / service.py  (đã có)                              │
│  dispatch → session → page                                   │
└───────┬───────────────────┬───────────────────┬─────────────┘
        │ type=2            │ type=3            │ type=4
        ▼                   ▼                   ▼
┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
│ page_classifier│  │ fbo_actions.py  │  │ fbo_scripts /    │
│ + runtime_hints│  │ lookup/fill/…   │  │ evaluate helpers │
└───────────────┘  └─────────────────┘  └──────────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            ▼
              Playwright CDP ↔ FBO ASP.NET AJAX
              ($find, MainReport, dirExtender, FormLookup*)
```

### 1.1. Module mới (Gemini tạo)

| File | Vai trò |
|------|---------|
| `chrome_debug/page_classifier.py` | Discover MainReport / searchExtender / dirExtender; `_type` → `page_kind` + `phase`; tóm tắt `_fields` |
| `chrome_debug/fbo_ids.py` | Hàm JS + Python resolve id động (cấm hardcode prefix dự án) |
| `chrome_debug/fbo_actions.py` | Primitives: `lookup_select`, `fill_form_fields`, `dismiss_message`, `toolbar_command`, `click_nhan_luu`, `filter_grid_column`, `read_grid_rows` |
| `chrome_debug/fbo_scripts.py` | Chuỗi `page.evaluate` canonical (1 nguồn sự thật) |

### 1.2. Module hiện có (Gemini sửa)

| File | Việc cần làm |
|------|--------------|
| `service.py` | type=2 gắn `runtime_hints`; type=3 nhận action mới |
| `actions.py` | Fill ưu tiên `dirExtender_form_*` / `searchExtender_form_*`; DateTime DOM `dd/MM/yyyy` |
| `tools.py` | Mở rộng params type=3 (xem §3) — giữ 1 tool `chrome_debug` |
| `snapshot.py` | (tuỳ chọn) gắn label field từ `_fields` nếu có |

### 1.3. Không làm

- Không hardcode `ctl00_FastBusiness_*` trong production code (chỉ trong test script / comment minh họa).
- Không yêu cầu agent tự viết Cypher/`page.evaluate` dài cho lookup/CRUD.
- Không thay 5 tool static (SQL/XML/Graph).

---

## 2. Runtime model (agent phải “thấy” qua type=2)

### 2.1. `runtime_hints` (type=2 luôn trả khi có Sys.Application)

```json
{
  "runtime_hints": {
    "page_kind": "category|report|voucher|unknown",
    "phase": "browse|filter|grid|form_popup|unknown",
    "ids": {
      "main_report": "...MainReport",
      "search_extender": "...MainReport_searchExtender|null",
      "dir_extender": "...MainReport_dirExtender|null"
    },
    "mr_type": "Voucher|Report||null",
    "required_fields": [
      {"name": "dvt", "header": "Đơn vị tính", "item_style": "AutoComplete", "category_index": 1}
    ],
    "autocomplete_fields": [
      {"name": "dvt", "item_style": "AutoComplete", "item_controller": "UOM", "category_index": 1}
    ],
    "grid_columns": [{"name": "ma_vt", "header": "Mã vật tư", "col_index": 1}],
    "toolbar": {"has_search": true, "has_new": true},
    "open_dialogs": ["dirExtender", "FormLookupdvt", "message"]
  }
}
```

**Rule classify** (đã verify):

```
mr._type == 'Voucher' → voucher
mr._type == 'Report'  → report / grid
mr._type == ''        → category
mr._type == null && searchExtender._type == 'Report' → report / filter
```

**Field metadata quan trọng:**

| Property | Dùng để |
|----------|---------|
| `AllowNulls === false` | Bắt buộc trước Lưu/Nhận |
| `ItemStyle` ∈ `AutoComplete` \| `Lookup` | **Bắt buộc** đi qua FormLookup — không gõ tay |
| `Type === DateTime` | Fill DOM `dd/MM/yyyy`, không tin `setItemValue` |
| `CategoryIndex` | Tab form (1=Thông tin chính, 2=Tài khoản, …) |

---

## 3. Mở rộng `chrome_debug` API (vẫn 1 tool)

### 3.1. type=1 — giữ nguyên

CDP ping + list tabs.

### 3.2. type=2 — inspect + `runtime_hints`

Ngoài errors + snapshot: **luôn** gọi `page_classifier.classify(page)` (retry 2–3× nếu `_fields` rỗng sau load).

### 3.3. type=3 — interact (mở rộng `action`)

Thêm param (optional, backward compatible):

| Param | Ý nghĩa |
|-------|---------|
| `action` | `""` (legacy fill/click) \| `lookup` \| `toolbar` \| `dismiss` \| `filter_grid` \| `save_form` \| `nhan_filter` |
| `fields_json` | Fill text/Mask/DateTime (không dùng cho AutoComplete) |
| `lookup_json` | `{"field":"dvt","search":"khối","prefer":"Khối"}` — optional prefer / first row |
| `toolbar_command` | `New` \| `Edit` \| `Delete` \| `View` \| `Search` |
| `filter_json` | `{"ma_vt":"ZTEST123"}` → `FilterPanelText{field}` + Playwright Enter |
| `click` | Giữ: ref / selector / text |

**Legacy:** `fields_json` + `click` không có `action` → hành vi cũ (fill DOM selectors mở rộng).

### 3.4. type=4 — execute_js (giữ) + helper presets (optional)

Param mới optional: `preset`

| preset | Trả về |
|--------|--------|
| `read_grid` | `{row_count, rows[{field:value}]}` qua `_getItemValue` |
| `classify` | Cùng shape `runtime_hints` |
| `""` | Chạy `script` như hiện tại |

Agent ưu tiên **preset** thay vì tự viết loop `_getItemValue`.

---

## 4. Primitives FBO (implement trong `fbo_actions.py`)

### 4.1. `lookup_select(page, field, search=None, prefer=None)`

**Chuẩn đã PASS (dvt → Khối):**

1. Resolve `dirExtender` / `searchExtender` đang mở (form vs filter báo cáo).
2. Click `img.CellImgLookup` cạnh `*[id*="form_{field}"]`.
3. Nếu `search`: gõ vào `{FormLookup{field}}_Button_Lookup_QuickFind`.
4. Lọc:
   ```javascript
   FastBusiness.AjaxControlExtender.AutoCompleteExtender
     .find('{prefix}_FormLookup{field}_Button_Lookup')
     .quickFind();
   ```
5. Chờ banner lọc / rows.
6. Click dòng data trong `#...FormLookup{field}_Button_Lookup_Table`:
   - `prefer` exact link text nếu có
   - else **first data row** (bỏ Đóng / header / Làm tươi / banner)
7. Verify `getItemValue(field)` — **chỉ lúc này** field mới có giá trị.

**Cấm:** `setItemValue(field, code)` cho `ItemStyle=AutoComplete|Lookup`.

**Lưu ý QuickFind:** lọc theo **tên/diễn giải**, không phải luôn theo mã. Nếu search theo mã không ra → mở list không lọc → chọn dòng 1 hoặc prefer.

### 4.2. `fill_smart(page, fields: dict)`

Với mỗi field trong `fields`:

1. Lấy meta từ `_fields` (dirExtender hoặc searchExtender).
2. Nếu AutoComplete/Lookup → **reject** hoặc auto-call `lookup_select` nếu value có dạng `{search, prefer?}`.
3. Nếu DateTime → DOM `dd/MM/yyyy` + change/blur.
4. Else → `setItemValue` rồi fallback DOM `..._form_{name}`.

### 4.3. `dismiss_message(page)` + `parse_validation_message(page)`

Click nút **Nhận** trên alert FBO (`Trường … chưa nhập…`).

**Đọc lỗi trước khi dismiss:**

```python
def parse_validation_message(page, component_id):
    """Trả { raw, header, field_name, scope } hoặc None."""
    # DOM: popup title "Fast Business Online", body chứa "Trường {header} chưa nhập..."
    # Map header → field qua $find(component_id)._fields[].HeaderText
```

**Quy tắc:** `dismiss` chỉ là bước 2 — bước 1 parse, bước 3 fix field, bước 4 `save_form` lại. **Cấm** `toolbar New` khi đang sửa lỗi validation trên form mở.

### 4.3b. `save_with_retry(page, max_rounds=8)`

```
loop:
  click dirExtender_updateDlgOk
  wait popup | form close
  if form closed → success
  msg = parse_validation_message()
  if not msg → fail unknown
  dismiss_message()
  if msg.scope == master → lookup_select / fill_smart(msg.field_name)
  if msg.scope == detail → lookup_grid_cell(active_row, col_of(msg.field_name))
  verify value non-empty
```

Implement trong `fbo_actions.py`; recipe §5.4.

### 4.4. `toolbar_command(page, commandName)`

**Trước Edit/Delete:** phải `focus_row` — click `#...gridCell_{row}.1` tới khi `mr._rowSelected()===true`.

```javascript
$find(mainReportId).executeCommand({ commandName, commandArgument: '0' });
// hoặc click #...ToolbarButton_Edit / _Delete
```

Xóa: confirm nút **Có**.

### 4.5. `nhan_filter` / `save_form`

- Báo cáo filter: click `#...searchExtender_updateDlgOk` rồi (grid phase) click `#...ToolbarButton_Search` hoặc `mr.search()`.
- Form: click `#...dirExtender_updateDlgOk`.

### 4.6. `filter_grid_column(page, field, value)`

```
#...FilterPanelText{field}  → Playwright fill + press('Enter')
```

**Đã verify:** synthetic `KeyboardEvent` Enter **không ổn định**; dùng Playwright `locator.fill` + `press("Enter")`.

Sau Lưu trên cùng session, filter có thể không ăn → **reload tab URL** rồi filter (recipe danh mục).

### 4.7. `read_grid_rows(page, max_rows=50)`

```javascript
// row & col 1-based
for (r = 1; r <= mr._rows.length; r++)
  for (c = 0; c < mr._fields.length; c++)
    row[mr._fields[c].Name] = mr._getItemValue(r, c + 1);
```

Áp dụng **mọi** MainReport grid (danh mục / báo cáo / browse chứng từ).

---

## 5. Recipe agent (sau khi Gemini xong — không coach tay)

### 5.1. Thêm mới danh mục (vd. vật tư)

```
type=1
type=2  → page_kind=category, required + autocomplete_fields
type=3  action=toolbar toolbar_command=New
type=2  → phase=form_popup, dirExtender fields
type=3  fields_json={"ma_vt":"…","ten_vt":"…"}     # text only
type=3  action=lookup lookup_json={"field":"dvt","search":"khối","prefer":"Khối"}
type=3  action=lookup lookup_json={"field":"loai_vt"}  # first row nếu không search
type=3  action=toolbar hoặc click tab Tài khoản (nếu CategoryIndex=2)
type=3  action=lookup lookup_json={"field":"tk_vt"}
type=3  action=save_form
type=2  → dismiss nếu message
(reload optional)
type=3  action=filter_grid filter_json={"ma_vt":"…"}
type=4  preset=read_grid
```

### 5.2. Lọc báo cáo

```
type=2 → report/filter + required_fields
type=3 fill DateTime DOM + lookup ma_vt (không gõ tay)
type=3 action=nhan_filter
type=3 click ToolbarButton_Search (hoặc action=toolbar Search)
type=4 preset=read_grid
```

### 5.3. Agent decision rule (ngắn — append `.cursorrules` sau)

1. Luôn `type=2` trước khi fill/lưu → đọc `runtime_hints`.
2. Mọi field `autocomplete_fields` / `ItemStyle` Lookup → `action=lookup`.
3. Verify grid → `preset=read_grid`, không scrape HTML.
4. Lỗi popup → **parse header → fix field trên form hiện tại → Lưu lại** (xem doc 12 §8e). **Không** Hủy/Mới lại.

### 5.4. Lưu chứng từ (socthda) — save retry

```
type=3  action=toolbar toolbar_command=New
type=3  action=lookup  ma_kh, tk, ma_tt
(tab Chi tiết — KHÔNG Insert; dòng 1 có sẵn)
type=3  action=lookup  grid ma_vt row 1
(dvt giữ auto sau ma_vt — không lọc Khối)
type=3  fill so_luong row 1
type=3  action=save_with_retry   # loop parse → Nhận → fix → Lưu
type=4  preset=read_grid filter so_ct
```

Nếu popup *Mã lô* / *Mã nx* → lookup đúng cột detail row 1 → `save_with_retry` tiếp.

---

## 6. Checklist implement Gemini

### Phase A — Classifier (P0)

- [ ] `page_classifier.py` + `fbo_ids.py` discover ids
- [ ] type=2 merge `runtime_hints` (required / autocomplete / columns / phase)
- [ ] Retry classify khi fields rỗng (load chậm)

### Phase B — Actions (P0)

- [ ] `lookup_select` đúng luồng QuickFind + `AutoCompleteExtender.quickFind` + click table
- [ ] `fill_smart` DateTime DOM; reject AutoComplete gõ tay
- [ ] `dismiss_message`, `toolbar_command`, `save_form`, `nhan_filter`
- [ ] `filter_grid_column` Playwright Enter
- [ ] `read_grid_rows` / type=4 `preset=read_grid`

### Phase C — tools.py wire-up (P0)

- [ ] Params `action`, `lookup_json`, `filter_json`, `toolbar_command`, `preset`
- [ ] Docstring tool cập nhật (agent đọc được)
- [ ] Backward compatible khi params trống

### Phase D — Tests (P1)

Tái sử dụng / chuẩn hóa scripts (không commit secrets):

| Script hiện có | Cover |
|----------------|-------|
| `_test_invt_lookup_dvt_khoi_prove.py` | Lookup Khối |
| `_test_invt_create.py` | CRUD create + filter verify |
| `_test_report_lookup_ma_vt.py` | Báo cáo lookup |
| `_probe_grid_getItemValue*.py` | `_getItemValue` 1-based |

Gemini thêm: `tests/chrome_debug/test_fbo_actions_unit.py` (mock evaluate) + 1 smoke E2E khi CDP available.

### Phase E — Docs agent (P1)

- [ ] Cập nhật [05_agent_workflow.md](05_agent_workflow.md) recipe §5.1–5.2
- [ ] Đoạn ngắn `.cursorrules` Chrome runtime (classify → lookup → verify)

---

## 7. Contract JSON (để agent parse ổn định)

### `lookup` result

```json
{
  "ok": true,
  "field": "dvt",
  "search": "khối",
  "picked": "Khối",
  "value_after": "Khối",
  "method": "prefer|first_data_row"
}
```

### `read_grid` result

```json
{
  "ok": true,
  "row_count": 1,
  "columns": ["ma_vt", "ten_vt", "dvt"],
  "rows": [{"ma_vt": "ZTEST…", "ten_vt": "…", "dvt": "Khối"}]
}
```

Mọi lỗi: `{"ok": false, "error": "…", "hint": "…"}` — không throw nuốt silent.

---

## 8. Sai lầm đã gặp (Gemini / agent tránh)

| Sai | Đúng |
|-----|------|
| `setItemValue('dvt','Cai')` | Lookup + quickFind + click |
| Chỉ Nhận báo cáo, không Tìm | Nhận → Toolbar Search |
| Scrape `<td>` | `_getItemValue(r,c)` |
| Hardcode client id | `fbo_ids.discover()` |
| JS `KeyboardEvent` Enter trên FilterPanel | Playwright `press('Enter')` |
| QuickFind mã `08` khi filter theo **tên** | Đổi search tên, hoặc first row |
| Click link đầu popup (= Đóng) | Scope `Button_Lookup_Table`, skip chrome rows |

---

## 9. Definition of Done

Gemini xong khi:

1. Agent chỉ cần `type=2` → biết kind/phase/required/autocomplete **không** hỏi user cấu trúc form.
2. Agent thêm VT (hoặc danh mục tương tự) bằng chuỗi type=3 `lookup` / `save_form` / `filter_grid` + type=4 `read_grid` — **PASS** trên BinhDienMK `invt.aspx`.
3. Không còn script ad-hoc bắt buộc trong workflow agent thường ngày (script chỉ regression).

---

## 10. Liên kết

| Doc | Nội dung |
|-----|----------|
| [12_…](12_fbo_webforms_mainreport_runtime.md) | Kiến thức runtime đã probe |
| [../doc_fix/fbo_runtime_page_classifier_spec.md](../doc_fix/fbo_runtime_page_classifier_spec.md) | Spec classifier chi tiết |
| [04_tool_api.md](04_tool_api.md) | Tool API gốc — cập nhật sau implement |
| [05_agent_workflow.md](05_agent_workflow.md) | Workflow agent |
| [02_architecture_layers.md](02_architecture_layers.md) | Layer MCP chrome_debug |

---

## Changelog

| Ngày | Nội dung |
|------|----------|
| 2026-08-23 | Khởi tạo kiến trúc agent dynamic: modules, API action/preset, recipes, checklist Gemini, DoD |
