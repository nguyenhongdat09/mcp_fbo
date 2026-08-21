# summary_xml — Extract `g.$a` + `g.showForm` (relate) + fix `grid.request`

> **Cho Gemini.** Bổ sung JSON summary khi file có `g.$a` và/hoặc `g.showForm(...)` (chuẩn FBO Grid).  
> Tham chiếu nghiệp vụ JS: skill `fbo_js_skill` → [`js-grid-expression.md`](file:///c:/Users/Windows%2010/.cursor/skills/fbo_js_skill/js-grid-expression.md), [`js-currency-amount.md`](file:///c:/Users/Windows%2010/.cursor/skills/fbo_js_skill/js-currency-amount.md).  
> **Reuse Kuzu build:** cùng logic `showForm` đang dùng khi build FBOGraph — xem §2 P1c.  
> Golden sample: `\\172.168.5.14\CustomerPro\FBO\KOYU-FBOR2\Program\App_Data\Controllers\Grid\PVDetail.xml`  
> (`g.showForm('PVOrderFilter')`, `g.showForm('PVDetailImport')`, …)  
> **Không** đụng MCP API / kiến trúc tầng. User **không** quan tâm `spec_version`.
---

## 1. Bối cảnh nghiệp vụ (đọc skill trước khi code)

Trên **Grid Detail**, công ty FBO quy định:

1. Trong `load$Grid...` khai báo **`g.$a = { ... }`**
2. Hai kiểu giá trị (bắt buộc phân loại đúng):

| Kiểu | Cú pháp JS | Vai trò | API runtime thường dùng |
|------|------------|---------|-------------------------|
| **Expression** | `'[col]:=...'` (string) | Tính cột **cùng dòng** | `g.executeExpression` / arg1 của `g.validExpression` |
| **Aggregate** | `['t_xxx', 'col']` (array 2 phần tử) | Cộng dồn cột grid → field **master** | `g.executeAggregate` / arg tổng của `validExpression` |

Ví dụ PVDetail:

```javascript
g.$a = {
  gia0_tg: '[gia0]:=[gia_nt0]*[$ty_gia]',
  tien_nt0: '[tien_nt0]:=[so_luong]*[gia_nt0]',
  tien0: '[tien0]:=[so_luong]*[gia0]',
  tien0_tg: '[tien0]:=[tien_nt0]*[$ty_gia]',

  t_so_luong: ['t_so_luong', 'so_luong'],
  t_tien_nt0: ['t_tien_nt0', 'tien_nt0'],
  t_tien0: ['t_tien0', 'tien0'],

  t_tt_nt: '[t_tt_nt]:=[t_tien_nt0]+[t_cp_nt]+[t_thue_nt]',
  t_tt: '[t_tt]:=[t_tien0]+[t_cp]+[t_thue]'
};
```

- `[$ty_gia]` = tỷ giá master (xem currency skill) — **giữ nguyên** trong chuỗi expression khi dump JSON.
- Tên trong `[...]` khớp `fields[].name` trên grid.
- `dispose$Grid...` thường `g.$a = null` — **không** cần extract.

**Không** nhầm với:

- SUM **chéo dòng** (không nằm trong `g.$a`) — skill `js-grid-cross-row.md`
- Chỉ copy `_setItemValue` — không phải expression

Agent cần thấy `g.$a` trong summary để biết **cột nào tính từ cột nào**, không phải đọc full script.

---

## 2. Phạm vi v1 (làm)

### P1 — Extract `g.$a` → JSON `grid_formulas`

- Nguồn: JS đã nối từ `<script>` (+ Checking nếu có) — **cùng** chuỗi dùng cho ANTLR JS hiện tại, hoặc scan riêng trên script chunks trước dispose.
- Emit khi parse được object `g.$a = { ... }` (thường Grid; Dir hiếm — nếu có vẫn emit).
- Không có `g.$a` → **không** bắt buộc key, hoặc `"grid_formulas": null` — **chốt: omit key** nếu empty (tiết kiệm token).

### P1b — Fix `request_actions` cho Grid `g.request` / `o.grid.request`

Hiện visitor/fallback lấy **string arg đầu** của `request(` — đúng Dir:

```js
f.request('Customer', 'Customer', [...], o);
```

Sai Grid:

```js
o.grid.request(o, 'Item', 'Item', ['ma_vt'], o.grid.$h, true);
g.request(g, 'Download', a, []);
```

→ Action nằm **arg string đầu tiên là tên action** khi arg0 không match `^[A-Za-z_][A-Za-z0-9_$]*$` kiểu action đơn (object `o`/`g`), tức lấy **literal string đầu tiên** trong danh sách argument.

**Chốt thuật toán `request_actions`:**

1. Tìm mọi call `*.request(` / `request(`
2. Lấy tất cả string literal trong argument list theo thứ tự
3. Thêm vào `request_actions` các literal match `^[A-Za-z_][A-Za-z0-9_$]*$` (thường arg action + context trùng tên — dedupe)
4. Không thêm mảng field names trong `['ma_vt', ...]` nếu đã parse được là ArrayExpression — chỉ string literal **không** nằm trong array (hoặc: lấy string literal là sibling args của CallExpression, bỏ elements của ArrayLiteral)

Đơn giản regex fallback bổ sung:

```python
# Dir-style
r"\brequest\s*\(\s*['\"]([A-Za-z_][\w$]*)['\"]"
# Grid-style: request( anything , 'Action'
r"\brequest\s*\(\s*[^,'\"]+,\s*['\"]([A-Za-z_][\w$]*)['\"]"
```

Chạy cả hai, union + sort.

`calls`: nếu callee chứa `.request` → ghi `o.grid.request` / `g.request` / `f.request` tương ứng (whitelist mở thêm `g.request`, `o.grid.request`).

### P1c — Extract `g.showForm` → related controllers (**copy từ Kuzu build**)

Khi build DB Kuzu, FBOGraph đã phân tích `g.showForm('FormName')` để nối file liên quan. **summary_xml phải reuse đúng đoạn đó** — không invent regex mới.

#### Nguồn code hiện có (BẮT BUỘC đọc + copy/reuse)

| File | Việc |
|------|------|
| [`xml_fbograph/parsers/js_parser.py`](../../xml_fbograph/parsers/js_parser.py) | `JsBlockParser.parse` — strip comment → regex `g.showForm('...')` → `show_form_calls: list[str]` |
| [`xml_fbograph/builder/graph_builder.py`](../../xml_fbograph/builder/graph_builder.py) ~478–503 và ~842–861 | Với mỗi `target_form`: edge tới controller cùng tên; nếu tên **endswith `Filter`** thì suy ra thêm `{prefix}Grid`, `MultiGrid`, `Form`, `MultiForm`, `Lookup` |

**Regex gốc (giữ nguyên):**

```python
re.compile(r"\bg\s*\.\s*showForm\s*\(\s*['\"]([a-zA-Z0-9_\$]+)['\"]\s*\)")
```

Ví dụ PVDetail:

```js
g.showForm('PVOrderFilter');   // → Filter + derived PVOrderGrid / MultiGrid / …
g.showForm('PVDetailImport');  // → chỉ tên form (không Filter → không expand suffix)
```

#### Cách wire vào summary (chọn 1 — ưu tiên A)

**A (ưu tiên):** Import reuse

```python
from xml_fbograph.parsers.js_parser import JsBlockParser
parsed = JsBlockParser.parse(js_source)
show_forms = parsed.get("show_form_calls", [])
```

Rồi **copy nguyên** vòng expand Filter từ `graph_builder` (chỉ phần tên candidate — **không** cần `find_node` / Kuzu):

```python
FILTER_SUFFIXES = ("Grid", "MultiGrid", "Form", "MultiForm", "Lookup")

def derive_related_from_show_form(target_form: str) -> list[str]:
    related = [target_form]
    if target_form.endswith("Filter"):
        prefix = target_form[:-6]  # bỏ "Filter"
        for suffix in FILTER_SUFFIXES:
            related.append(f"{prefix}{suffix}")
    return related
```

Gộp mọi `show_form` → `related_controllers` = sorted unique.

**B:** Copy paste regex + logic vào `xml_controller_summary/` nếu muốn tránh import `xml_fbograph` (không khuyến khích — dễ lệch bản sau).

> **Khác Kuzu:** summary **không** resolve path XML / không tạo edge. Chỉ emit **tên controller** để agent biết file relate (`PVOrderFilter`, `PVOrderGrid`, …) rồi tự `query_radar` / đọc file nếu cần.

#### JSON emit

Trong root summary (cùng cấp `js` / `fields`), omit nếu rỗng:

```json
"show_forms": ["PVDetailImport", "PVOrderFilter"],
"related_controllers": [
  "PVDetailImport",
  "PVOrderFilter",
  "PVOrderForm",
  "PVOrderGrid",
  "PVOrderLookup",
  "PVOrderMultiForm",
  "PVOrderMultiGrid"
]
```

| Key | Ý nghĩa |
|-----|---------|
| `show_forms` | Đúng list `show_form_calls` từ parser (literal trong `g.showForm`) |
| `related_controllers` | `show_forms` ∪ candidates suy từ `*Filter` (cùng luật graph_builder) |

`js.calls`: thêm `g.showForm` vào whitelist nếu chưa có.

### P2 (optional cùng PR nếu dễ) — `formula_triggers` sơ bộ

Từ `switch (name) { case 'so_luong': ... g.validExpression(o, [g.$a.tien_nt0, ...], ...)`  
map field nguồn → list key `g.$a.*` được reference.

```json
"formula_triggers": {
  "so_luong": ["tien_nt0", "tien0", "t_so_luong", "t_tien_nt0", "t_tien0", "t_tt_nt", "t_tt"],
  "gia_nt0": ["gia0_tg", "tien_nt0", "tien0", "t_tien_nt0", "t_tien0", "t_tt_nt", "t_tt"]
}
```

**Không bắt buộc v1** nếu tốn thời gian — ưu tiên **P1 + P1b + P1c**. Nếu làm: regex `case\s+'([^']+)'` trong cùng function `onChange$Grid...` + `g.\$a\.(\w+)` trong body case (heuristic).

---

## 3. JSON schema bổ sung

Trong object root summary (cùng cấp `js` / `sql` / `fields`):

```json
"grid_formulas": {
  "expressions": {
    "<key>": "<expression string>"
  },
  "aggregates": {
    "<key>": ["<master_field>", "<grid_column>"]
  }
},
"show_forms": ["<ControllerName>", "..."],
"related_controllers": ["<ControllerName>", "..."]
```
### Phân loại từng property của `g.$a`

| Giá trị sau parse | Đưa vào |
|-------------------|---------|
| String bắt đầu bằng `[` hoặc chứa `]:=` | `expressions` |
| Array length 2, cả hai string | `aggregates` |
| Khác (hiếm) | bỏ qua + optional warning `grid_formulas_unparsed:<key>` |

### Ví dụ kỳ vọng PVDetail

```json
"grid_formulas": {
  "expressions": {
    "gia0_tg": "[gia0]:=[gia_nt0]*[$ty_gia]",
    "tien_nt0": "[tien_nt0]:=[so_luong]*[gia_nt0]",
    "tien0": "[tien0]:=[so_luong]*[gia0]",
    "tien0_tg": "[tien0]:=[tien_nt0]*[$ty_gia]",
    "t_tt_nt": "[t_tt_nt]:=[t_tien_nt0]+[t_cp_nt]+[t_thue_nt]",
    "t_tt": "[t_tt]:=[t_tien0]+[t_cp]+[t_thue]"
  },
  "aggregates": {
    "t_so_luong": ["t_so_luong", "so_luong"],
    "t_tien_nt0": ["t_tien_nt0", "tien_nt0"],
    "t_tien0": ["t_tien0", "tien0"]
  }
}
```

Và sau P1b + P1c:

```json
"js": {
  "request_actions": ["Download", "Item", "Site", "UOM"],
  "calls": ["$message.show", "f.executeExpression", "g.request", "g.showForm", "o.grid.request"]
},
"show_forms": ["PVDetailImport", "PVOrderFilter"],
"related_controllers": [
  "PVDetailImport",
  "PVOrderFilter",
  "PVOrderForm",
  "PVOrderGrid",
  "PVOrderLookup",
  "PVOrderMultiForm",
  "PVOrderMultiGrid"
]
```

(`f.executeExpression` có thể xuất hiện từ master helper; Grid chủ yếu `g.validExpression` — **không bắt** thêm `validExpression` vào whitelist calls trừ khi đã có sẵn; v1 giữ whitelist cũ + `g.request` / `o.grid.request` / `g.showForm`.)
---

## 4. Cách extract `g.$a` (implement)

### 4.1. Vị trí code

| Việc | Package |
|------|---------|
| Parse object `g.$a` | `xml_controller_summary/` — module mới vd. `grid_formulas.py` |
| `g.showForm` + Filter expand | Reuse `JsBlockParser` + helper `derive_related_from_show_form` (copy luật từ `graph_builder`) |
| Gọi từ | `analyze_flat_xml` sau khi có JS source (script chunks) |
| Formatter | `result_to_dict` — thêm `grid_formulas` / `show_forms` / `related_controllers` nếu non-empty |
| Models | optional dataclass `GridFormulas` |

**Cấm** nhét vào `mcp_app` / fork extract trong facade.
### 4.2. Thuật toán đề xuất (regex-first, ổn định ES5)

JS FBO trong CDATA thường **không** minify phức tạp — regex đủ cho v1:

1. Tìm `g.$a\s*=\s*\{` (cho phép `g['$a']` nếu gặp — hiếm).
2. Brace-match lấy body object (đếm `{`/`}`, bỏ qua string).
3. Parse từng entry `key\s*:\s*value` với:
   - `key`: identifier
   - `value`: string `'...'` / `"..."` **hoặc** array `[ 'a', 'b' ]`
4. Phân loại expression vs aggregate như bảng trên.
5. Unescape `\'` trong string nếu có.

**Fallback ANTLR:** nếu brace-match fail → warning `grid_formulas_parse_failed`; không fail cả summary.

### 4.3. Không đưa `g.$a` vào list `js.functions`

Chỉ object data — không phải function declaration.

### 4.4. Liên hệ fields

Optional enrichment (P2): với mỗi expression, extract identifiers trong `[field]` (bỏ `$ty_gia`) → có thể ghi `"depends_on": ["so_luong", "gia_nt0"]` per key — **nice-to-have**, không bắt buộc v1.

---

## 5. Tests bắt buộc

### T1 — PVDetail-like fixture (mini)

Script chứa đúng `g.$a` như snippet PVDetail + `o.grid.request(o, 'Item', ...)` +:

```js
g.showForm('PVOrderFilter');
g.showForm('PVDetailImport');
```

Assert:

- `grid_formulas.expressions["tien_nt0"]` đúng chuỗi
- `grid_formulas.aggregates["t_so_luong"] == ["t_so_luong", "so_luong"]`
- `"Item" in js.request_actions`
- `show_forms` chứa `PVOrderFilter`, `PVDetailImport`
- `related_controllers` chứa `PVOrderFilter`, `PVOrderGrid`, `PVOrderMultiGrid`, `PVOrderLookup`, … và `PVDetailImport`
- `PVDetailImport` **không** bị bịa thêm `PVDetailImportGrid` (vì không endswith `Filter`)
- Dir-only fixture **không** có key `grid_formulas` / `show_forms` nếu không có call
### T2 — Regression SVTran / unit cũ

- Dir Tran: không break; `request_actions` vẫn có Customer…
- `pytest tests/js_engine tests/xml_controller_summary tests/find_entity_by_xml -q`

### T3 — (Optional) UNC PVDetail

```python
d = summary_xml(r"\\172.168.5.14\CustomerPro\FBO\KOYU-FBOR2\Program\App_Data\Controllers\Grid\PVDetail.xml", use_cache=False)
assert "tien_nt0" in d["grid_formulas"]["expressions"]
assert "Item" in d["js"]["request_actions"]
assert "PVOrderFilter" in d["show_forms"]
assert "PVDetailImport" in d["show_forms"]
assert "PVOrderGrid" in d["related_controllers"]
```
---

## 6. Cập nhật docs schema (nhẹ)

Sửa ngắn [`docs/doc_summary_xml/03_json_schema.md`](../doc_summary_xml/03_json_schema.md):

- Thêm `$defs.GridFormulas` + property optional `grid_formulas`
- Thêm optional `show_forms` / `related_controllers` (cùng nghĩa Kuzu showForm)
- Ghi chú: `grid_formulas` khi có `g.$a`; `show_forms` khi có `g.showForm`

---

## 7. Thứ tự làm

```
1) grid_formulas.py + wire analyze/formatter/models
2) Fix request_actions Grid (visitor + fallback_regex)
3) show_forms + related_controllers — reuse JsBlockParser + copy Filter expand từ graph_builder
4) Tests T1/T2 (+ T3 nếu UNC)
5) Cập nhật 03_json_schema.md
6) (Optional) formula_triggers / depends_on
```

---

## 8. Definition of Done

- [x] PVDetail (fixture hoặc UNC): có `grid_formulas.expressions` + `aggregates` đúng (đo thực tế trên UNC PVDetail.xml)
- [x] PVDetail: `request_actions` chứa Item, UOM, Site, Download
- [x] PVDetail: `show_forms` có `PVOrderFilter`, `PVDetailImport`; `related_controllers` có derived từ Filter
- [x] Dir không có `g.$a` / `showForm` → không phình JSON bằng object/list rỗng (tự động omit key)
- [x] Unit/bridge tests xanh (14 passed, 1 skipped UNC)
- [x] Changelog dưới đây

---

## 9. Anti-pattern (Gemini tránh)

- ❌ Coi mọi value `g.$a` là expression string — bỏ sót aggregate `['t_x','col']`
- ❌ Chỉ extract khi `folder_type==Grid` cứng — miss file Dir có `$a` (hiếm) hoặc path sai; **detect theo có object**
- ❌ Đưa cả `onChange` switch body vào JSON (quá dài) trừ P2 có kiểm soát
- ❌ Parse fail → `success: false` cả file — chỉ omit/`warnings`
- ❌ Tự viết regex `showForm` khác bản `JsBlockParser` (lệch Kuzu)
- ❌ Resolve path / gọi Kuzu trong summary — chỉ emit **tên** controller
- ❌ Expand suffix cho form **không** kết thúc `Filter` (vd. `PVDetailImport`)

---

## Changelog

| Ngày | Việc |
|---|---|
| 2026-08-21 | Tạo module `xml_controller_summary/grid_formulas.py` trích xuất `g.$a` (phân loại `expressions` vs `aggregates`) và `g.showForm` (tính `related_controllers` từ prefix Filter). |
| 2026-08-21 | Mở rộng regex `request_actions` trong `fallback_regex.py` hỗ trợ Grid (`o.grid.request(o, 'Item', ...)`, `g.request(g, 'Download', ...)`), thêm whitelist calls `o.grid.request`, `g.request`, `g.showForm`. |
| 2026-08-21 | Tích hợp vào `models.py`, `analyze.py`, `formatter.py` (tự động omit khi rỗng), cập nhật tài liệu JSON schema và hoàn thiện bộ test suite. |

