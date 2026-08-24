# Spec: FBO Runtime Page Classifier + Chrome Debug (cho Gemini implement)

> **Ngày:** 2026-08-23  
> **Nguồn:** Rule từ user + probe thực tế 3 URL BinhDienMK qua Chrome CDP  
> **Mục tiêu:** Implement `page_classifier.py` + gắn vào `chrome_debug` type=2; mở rộng type=3 fill/click theo FBO WebForms  
> **Không hardcode** client id dự án — pattern generic; id mẫu chỉ để minh họa
>
> **Kiến trúc tổng + checklist agent dynamic (ưu tiên đọc trước):**  
> [../doc_chrome_debug/13_fbo_runtime_agent_architecture.md](../doc_chrome_debug/13_fbo_runtime_agent_architecture.md)  
> Doc runtime đã verify: [../doc_chrome_debug/12_fbo_webforms_mainreport_runtime.md](../doc_chrome_debug/12_fbo_webforms_mainreport_runtime.md)

---

## 1. Bối cảnh

FBO Web chạy **ASP.NET AJAX** (`Sys.Application`, `$find`), **không** dùng object ExtJS `f`/`g` trên lớp MainReport.

- Source XML **không** chứa `$find('ctl00_...')` — client id sinh runtime.
- Agent cần **classify màn hình** + đọc `_fields` trước khi fill/click/lọc/lưu.
- Probe raw: `docs/doc_fix/_probe_three_screens_raw.json`

### 3 URL mẫu đã test

| Loại | URL | Title |
|------|-----|-------|
| Báo cáo | `.../rpt_bkctsstt.aspx?id=15.02.39` | Bảng kê chi tiết sổ sách, thực tế |
| Danh mục | `.../invt.aspx?id=15.70.06` | Danh mục hàng hóa, vật tư |
| Chứng từ | `.../socthda.aspx?id=09.10.06` | Hóa đơn bán hàng |

---

## 2. API runtime FBO (bắt buộc nắm)

### 2.1. `$find(clientId)`

Lookup component đã register trong `Sys.Application` (ASP.NET AJAX Control Toolkit pattern).

### 2.2. `_type` — phân loại màn hình

Đọc từ component **MainReport** hoặc **searchExtender**:

| `_type` | Loại FBO |
|---------|----------|
| `'Voucher'` | **Chứng từ** |
| `'Report'` | **Báo cáo** |
| `''` (chuỗi rỗng) | **Danh mục** |
| `null` / `undefined` | Chưa xác định — xem §3.2 |

**Ví dụ id mẫu (BinhDienMK):** `ctl00_FastBusiness_MainReport` — **không** copy cứng; tìm động (§4).

### 2.3. `_fields` — metadata cột/field

Trên **grid**, **filter**, hoặc **dirExtender form**:

```javascript
$find(componentId)._fields  // Array
```

Mỗi phần tử quan trọng:

| Property | Ý nghĩa |
|----------|---------|
| `Name` | Tên field (`ma_vt`, `ma_kh`, `tu_ngay`…) |
| `AliasName` | Alias SQL |
| `HeaderText` / `Label` | Nhãn UI |
| `Type` | `String`, `DateTime`, `Decimal`, `Boolean`… |
| `AllowNulls` | `false` → **bắt buộc nhập** trước Nhận/Lưu |
| `ReadOnly` | Không sửa |
| `Hidden` / `Visible` | Có hiển thị không |

### 2.4. `executeCommand` — toolbar

Pattern trong `onclick` nút toolbar:

```javascript
$find('...MainReport').executeCommand({ commandName: 'New', commandArgument: '0' });
```

| commandName | Nút thường gặp |
|-------------|----------------|
| `New` | Mới |
| `Edit` | Sửa |
| `Delete` | Xóa |
| `View` | Xem |
| `Search` | Tìm |
| `Clone` | Chép dữ liệu |

Filter báo cáo: nút **Nhận** — id pattern `*searchExtender*updateDlgOk` (không qua MainReport.executeCommand).

### 2.5. `setItemValue` (component)

Trên `searchExtender` / form component:

```javascript
$find('...searchExtender').setItemValue('ma_vt', '001');
```

- **String:** thường OK.
- **DateTime:** cần format đúng — probe ghi nhận lỗi `n.format is not a function` khi truyền chuỗi `'2025-01-01'` thô; cần fallback DOM + `onchange` hoặc format FBO.

### 2.6. DOM input (dirExtender popup)

Khi popup form mở, input id pattern:

```text
{mainReportId}_dirExtender_form_{fieldName}
```

Ví dụ: `ctl00_FastBusiness_MainReport_dirExtender_form_ma_kh`

Fill user-like: Playwright `fill` + `dispatch change/blur` + `el.onchange()` nếu có.

---

## 3. Thuật toán classify (page_classifier)

### 3.1. Tìm client id động

```javascript
// Pseudo — implement trong page_classifier.py (page.evaluate)
function findMainReportId() {
  for (var c of Sys.Application.getComponents()) {
    var id = c.get_id();
    // MainReport gốc: chứa MainReport, KHÔNG chứa searchExtender, dirExtender, FormLookup, DropShadow, ToolbarButton
    if (/MainReport/.test(id) && !/searchExtender|dirExtender|FormLookup|DropShadow|ToolbarButton|FormGrid/.test(id)) {
      if (/MainReport$/.test(id) || /_MainReport$/.test(id)) return id;
    }
  }
  return null;
}

function findSearchExtenderId(mainReportId) {
  // id kết thúc bằng MainReport_searchExtender (exact suffix)
  for (var c of Sys.Application.getComponents()) {
    var id = c.get_id();
    if (id && id === mainReportId + '_searchExtender') return id;
  }
  return null;
}

function findDirExtenderId(mainReportId) {
  for (var c of Sys.Application.getComponents()) {
    var id = c.get_id();
    if (id === mainReportId + '_dirExtender') return id;
  }
  return null;
}
```

### 3.2. Cây quyết định `_type`

```
mr = $find(mainReportId)

if mr._type === 'Voucher'  → page_kind = 'voucher'
if mr._type === 'Report'   → page_kind = 'report', phase = 'grid' (đã qua filter)
if mr._type === ''         → page_kind = 'category'

if mr._type == null:
    se = $find(mainReportId + '_searchExtender')
    if se && se._type === 'Report':
        → page_kind = 'report', phase = 'filter'
    else if modal dirExtender visible:
        → page_kind = 'voucher', phase = 'form_popup'
    else:
        → page_kind = 'unknown' (+ wait/retry §3.4)
```

### 3.3. Phase (sub-state)

| page_kind | phase | UI |
|-----------|-------|-----|
| `report` | `filter` | Popup filter, chưa có grid data |
| `report` | `grid` | MainReport._type === 'Report', `_fields` là cột grid |
| `voucher` | `browse` | List chứng từ, chưa popup |
| `voucher` | `form_popup` | dirExtender modal, nhập liệu |
| `category` | `browse` | Grid danh mục |

### 3.4. Timing

Probe báo cáo: **`_fields` filter = 0 nếu wait < ~8s** sau load.  
→ Classifier **retry** 2–3 lần, interval 2s, trước khi trả `unknown`.

---

## 4. Kết quả probe 3 màn hình (thực tế)

### 4.1. Báo cáo — `rpt_bkctsstt.aspx`

**Initial (filter phase):**

| Probe | Giá trị |
|-------|---------|
| `MainReport._type` | `null` |
| `searchExtender._type` | `'Report'` |
| `searchExtender._fields` | 10 fields |

**Filter fields (rút gọn):**

| Name | Header | AllowNulls |
|------|--------|------------|
| `tu_ngay` | Từ ngày | **false** |
| `den_ngay` | Đến ngày | **false** |
| `ma_kho` | Mã kho | true |
| `ma_vt` | Mã vật tư | **false** |
| `ma_dvcs` | Đơn vị | true |

**Nút filter:** `updateDlgOk` = **Nhận**, `updateDlgCancel` = Hủy

**Workflow test báo cáo:**

1. Classify → `report` / `filter`
2. Đọc `_fields` → list `required_fields` (`AllowNulls === false`)
3. Fill required (ưu tiên `setItemValue`; DateTime cần xử lý riêng)
4. Click **Nhận** (`#...searchExtender_updateDlgOk`)
5. Classify lại → `report` / `grid`
6. `MainReport._type` → `'Report'`, `_fields` ~13 cột (Ngày ct, Mã ct, Số ct…)

**Sau Nhận (probe OK):** `mr_type: Report`, `mr_fields_count: 13`

### 4.2. Danh mục — `invt.aspx`

| Probe | Giá trị |
|-------|---------|
| `MainReport._type` | `''` (rỗng) → **danh mục** |
| `searchExtender` | không có |
| `MainReport._fields` | 21 cột grid (`ma_vt`, `ten_vt`, `dvt`…) |

**Toolbar:** Mới, Sửa, Xóa, Xem — `executeCommand` New/Edit/Delete/View

**Workflow test danh mục:**

1. Classify → `category` / `browse`
2. Optional: click **Mới** → dirExtender popup (nếu có) → fill form
3. Grid filter: dùng `_fields` + column filter nếu có

### 4.3. Chứng từ — `socthda.aspx`

**Browse (trước Mới):**

| Probe | Giá trị |
|-------|---------|
| `MainReport._type` | `'Voucher'` |
| `MainReport._fields` | cột list (`ma_kh`, `ngay_ct`, `so_ct`…) |
| `typeof f` | **undefined** (không dùng ExtJS Dir) |

**Toolbar:** Mới, Sửa, Xóa, Chép dữ liệu, Tìm, Xem, In

**Sau click Mới:**

| Probe | Giá trị |
|-------|---------|
| `dirExtender._type` | `'Voucher'` |
| `dirExtender._fields` | ~90+ field form |
| `modal_visible` | true |
| DOM | `...dirExtender_form_ma_kh` |

**Required form fields (mẫu):** `ma_kh`, `tk`, `ma_gd`, `ma_tt`, `so_ct`, `so_seri`, `ngay_lct`, `ngay_ct`, `ma_nt`, `d81`, `tk_thue_no` — `AllowNulls: false`

**Detail grid khai báo (BinhDienMK / socthda — cố định):**

`\\172.168.5.14\CustomerPro\FBI\BINHDIENMK\SP2264\App_Data\Controllers\Grid\SVDetail.xml`

- Alias embed trên Dir: `d81` → runtime `{dirExtender}_FormGridd81`
- Required detail: `ma_vt`, `dvt`, `tk_dt`, `tk_vt`, `tk_gv`, `ma_nx` (+ `ma_kho`)
- Runtime fill: lookup cell `GridLookup{row}.{col}` — xem [12 §8d](../doc_chrome_debug/12_fbo_webforms_mainreport_runtime.md#8d-grid-chi-tiết-embed--d81--svdetail-probe-2026-08-23)

**Fill ma_kh test:** DOM id `...dirExtender_form_ma_kh` = `TKH001` + `onchange` → OK

**Lưu ý:** `typeof g === 'boolean'` khi popup mở — **không** phải grid controller FBO JS.

**Lưu + validation popup:** Agent **không** đóng form khi gặp lỗi. Parse `Trường {header} chưa nhập…` → map `header` ↔ `_fields[].HeaderText` → **Nhận** → fill/lookup field → **Lưu lại**. Chi tiết: [12 §8e](../doc_chrome_debug/12_fbo_webforms_mainreport_runtime.md#8e-popup-validation--sửa-tại-chỗ-không-mở-lại-form-bắt-buộc-agent).

---

## 5. Output `runtime_hints` (gắn type=2)

Sau `build_page_snapshot`, merge block:

```json
{
  "runtime_hints": {
    "page_kind": "voucher",
    "phase": "form_popup",
    "main_report_id": "ctl00_FastBusiness_MainReport",
    "active_component_id": "ctl00_FastBusiness_MainReport_dirExtender",
    "component_type": "Voucher",
    "required_fields": [
      { "name": "ma_kh", "header": "Mã khách", "type": "String" }
    ],
    "toolbar_actions": [
      { "text": "Mới", "command": "New", "button_id_suffix": "ToolbarButton_New" }
    ],
    "fill_strategy": "dirExtender_form_suffix",
    "fill_suffix_pattern": "*_dirExtender_form_{field_name}",
    "next_steps": [
      "Fill required_fields trong popup",
      "Không gọi f.setItemValue — không có f"
    ]
  }
}
```

**Rút gọn field trả agent:** chỉ `name`, `header`, `allowNulls`, `type`, `readOnly` — **không** dump full `_fields` 90 item (token).

---

## 6. Mở rộng `actions.py` (type=3)

### 6.1. Thứ tự selector fill (bổ sung)

Sau selector hiện tại (`name=`, `#id`, …), thêm:

```text
[id*="_dirExtender_form_{field_name}"]
[id*="_searchExtender"][id*="{field_name}"]
```

Sau fill ASP.NET input: `dispatch change`, `blur`, gọi `el.onchange()` nếu có.

### 6.2. Fill qua component (type=4 helper hoặc type=3 nội bộ)

```javascript
$find(activeComponentId).setItemValue(fieldName, value)
```

Chỉ khi component có `setItemValue`.

### 6.3. Click toolbar

| Mục tiêu | Cách |
|----------|------|
| Mới/Sửa/Xóa | `click="Mới"` hoặc `#...ToolbarButton_New` |
| Nhận (báo cáo) | `#...searchExtender_updateDlgOk` |
| Ref snapshot | `e17` như hiện tại |

### 6.4. DateTime fields

Probe lỗi `n.format is not a function` — cần:

- Thử format ngày FBO (vd `dd/MM/yyyy`) hoặc
- DOM input date picker + Tab blur

Ghi TODO trong code nếu chưa resolve.

---

## 7. Workflow agent (sau classify)

### Chứng từ

```
type=2 → voucher/browse
type=3 click="Mới"                    (user simulation)
type=2 → voucher/form_popup + required_fields
type=3 fill ma_kh (+ required)       (dirExtender_form_*)
type=4 verify ten_kh                  (optional, ngắn)
```

### Báo cáo

```
type=2 → report/filter + required_fields
type=3 fill tu_ngay, den_ngay, ma_vt
type=3 click Nhận (updateDlgOk)
type=2 → report/grid
```

### Danh mục

```
type=2 → category/browse + grid columns
type=3 click Mới / fill filter row (nếu cần)
```

**Rule:** type=3 = user simulation **bắt buộc** cho QA; type=4 chỉ setup/verify.

---

## 8. File cần tạo/sửa (Gemini)

| File | Việc |
|------|------|
| `chrome_debug/page_classifier.py` | **Mới** — `classify_page(page) -> dict` |
| `chrome_debug/service.py` | `handle_type_2_inspect` merge `runtime_hints` |
| `chrome_debug/actions.py` | Fallback selector dirExtender/searchExtender |
| `docs/doc_chrome_debug/05_agent_workflow.md` | Thêm § classify + workflow 3 loại |
| `scripts/probe_fbo_three_screens.py` | Giữ làm regression probe (optional) |

**Không** tạo skill dài — logic nằm trong `.py`.

---

## 9. JS classify mẫu (copy vào page_classifier.py)

```javascript
(() => {
  function getComponents() {
    if (typeof Sys === 'undefined' || !Sys.Application) return [];
    return Sys.Application.getComponents() || [];
  }
  function findId(re) {
    for (var c of getComponents()) {
      var id = c.get_id && c.get_id();
      if (id && re.test(id)) return id;
    }
    return null;
  }
  function summarizeFields(fields, limit) {
    if (!fields || !fields.length) return [];
    return fields.slice(0, limit || 50).map(function (f) {
      return {
        name: f.Name || '',
        header: (f.HeaderText || f.Label || '').substring(0, 80),
        type: f.Type || '',
        allowNulls: f.AllowNulls,
        readOnly: f.ReadOnly,
        hidden: f.Hidden,
        visible: f.Visible
      };
    });
  }
  function comp(id) {
    try { return id ? $find(id) : null; } catch (e) { return null; }
  }

  var mrId = findId(/MainReport$/);
  var seId = mrId ? mrId + '_searchExtender' : null;
  var deId = mrId ? mrId + '_dirExtender' : null;
  var mr = comp(mrId);
  var se = comp(seId);
  var de = comp(deId);

  var page_kind = 'unknown';
  var phase = 'unknown';
  var activeId = mrId;
  var activeFields = [];

  var mrType = mr ? mr._type : null;
  if (mrType === 'Voucher') {
    page_kind = 'voucher';
    phase = de && de._fields && de._fields.length ? 'form_popup' : 'browse';
    activeId = phase === 'form_popup' ? deId : mrId;
    activeFields = phase === 'form_popup' ? de._fields : (mr._fields || []);
  } else if (mrType === 'Report') {
    page_kind = 'report';
    phase = 'grid';
    activeFields = mr._fields || [];
  } else if (mrType === '') {
    page_kind = 'category';
    phase = 'browse';
    activeFields = mr._fields || [];
  } else if (se && se._type === 'Report') {
    page_kind = 'report';
    phase = 'filter';
    activeId = seId;
    activeFields = se._fields || [];
  } else if (de && de._fields && de._fields.length) {
    page_kind = 'voucher';
    phase = 'form_popup';
    activeId = deId;
    activeFields = de._fields;
  }

  var required = (activeFields || []).filter(function (f) {
    return f.AllowNulls === false && f.Name && !f.Hidden;
  }).map(function (f) { return f.Name; });

  return {
    main_report_id: mrId,
    page_kind: page_kind,
    phase: phase,
    active_component_id: activeId,
    main_report_type: mrType,
    search_extender_type: se ? se._type : null,
    dir_extender_type: de ? de._type : null,
    field_count: (activeFields || []).length,
    fields_sample: summarizeFields(activeFields, 20),
    required_field_names: required,
    modal_visible: !!document.querySelector('.ModalBackground, [id*=ModalPopupBehavior_backgroundElement]')
  };
})()
```

---

## 10. Checklist Gemini trước khi merge

- [ ] Classify 3 URL mẫu đúng `page_kind` + `phase`
- [ ] Báo cáo: detect `required` (`tu_ngay`, `den_ngay`, `ma_vt`)
- [ ] Chứng từ: sau Mới có `dirExtender` + `ma_kh` required
- [ ] Danh mục: `_type === ''`
- [ ] type=2 output có `runtime_hints`, không trả full 90 fields
- [ ] type=3 fill `ma_kh` qua `dirExtender_form_ma_kh` không cần agent đoán
- [ ] Wait/retry `_fields` empty (< 8s load)
- [ ] Không hardcode `ctl00_FastBusiness` ngoài fallback tìm pattern

---

## 11. Phụ lục — không dùng làm tiêu chí classify

| Signal | Kết luận probe |
|--------|----------------|
| `typeof f` | **undefined** trên cả 3 màn — bỏ qua cho MainReport |
| `typeof g === 'boolean'` | Không phải grid — bỏ qua |
| `Ext.getCmp` | Không có Ext |

---

*Tài liệu này thay thế việc agent probe mù. Implement theo §8–9; test regression bằng `scripts/probe_fbo_three_screens.py`.*
