# 03 — JSON Schema & Ví dụ (`summary_xml`)

## 1. Schema tổng (`read_option=3`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["success", "mode", "spec_version", "file", "controller", "js", "sql", "fields", "meta"],
  "properties": {
    "success": { "type": "boolean" },
    "mode": { "const": "summary" },
    "spec_version": { "type": "string", "const": "1.0" },
    "file": {
      "type": "string",
      "description": "Relative path Controllers nếu suy ra được, else basename / path ngắn"
    },
    "controller": { "$ref": "#/$defs/ControllerMeta" },
    "js": { "$ref": "#/$defs/JsSummary" },
    "sql": { "$ref": "#/$defs/SqlSummary" },
    "fields": {
      "type": "array",
      "items": { "$ref": "#/$defs/FieldSummary" }
    },
    "meta": { "$ref": "#/$defs/Meta" }
  }
}
```

> **`controller` luôn có mặt** trong JSON (thuộc `required`). Các field bên trong (`db_table`, `title_v`…) **được phép null** nếu không suy ra được — không được bỏ hẳn key `controller`.

## 2. `$defs.ControllerMeta`

Metadata nông từ root / attributes thường có trên controller (optional — thiếu thì `{}` hoặc null fields).

```json
{
  "folder_type": { "type": ["string", "null"], "description": "Dir|Grid|Filter|Report|Lookup|… suy từ path" },
  "db_table": { "type": ["string", "null"] },
  "code_field": { "type": ["string", "null"] },
  "title_v": { "type": ["string", "null"] },
  "title_e": { "type": ["string", "null"] },
  "id": { "type": ["string", "null"], "description": "Thuộc tính id root nếu có" }
}
```

**v1:** Suy `folder_type` từ path segment (`.../Controllers/Dir/...` → `Dir`). Các field khác: parse attribute trên root element nếu có; thiếu thì để `null`. Object `controller` **luôn** emit (có thể toàn null bên trong).

## 2b. Kỳ vọng theo `folder_type` (không phải lỗi)

| folder_type | JS thường | SQL thường | Ghi chú |
|-------------|-----------|------------|---------|
| Dir (*Tran) | `script` + đôi khi `Checking` | command + action | Golden SVTran |
| Grid | thường **empty** | `query` (+ ít command) | `js.parse_status: "empty"` = OK |
| Filter | thường **empty** | `query` | Ví dụ §7b |
| Report | thường **empty** | `query` | OK |
| Lookup | empty hoặc rất ít | ít / không | OK |

**Không** đánh `success: false` chỉ vì JS empty khi SQL/fields vẫn có dữ liệu.

## 3. `$defs.JsSummary`

```json
{
  "parse_status": { "enum": ["ok", "partial", "failed", "empty"] },
  "sources": {
    "type": "array",
    "items": { "type": "string" },
    "description": "vd: script, command:Checking"
  },
  "functions": {
    "type": "array",
    "items": { "type": "string" },
    "description": "Tên hàm khai báo function Name("
  },
  "calls": {
    "type": "array",
    "items": { "type": "string" },
    "description": "Chỉ whitelist v1 cứng — xem §3.1"
  },
  "request_actions": {
    "type": "array",
    "items": { "type": "string" },
    "description": "Arg1 của f.request / parentForm.request — map tới <action id>"
  },
  "line_count": { "type": "integer", "description": "Số dòng JS đã nối (sau strip encrypted)" }
}
```

### Quy tắc extract `request_actions`

Từ AST hoặc regex fallback:

```javascript
o.parentForm.request('DebitAccount', 'DebitAccount', ['tk'], o);
f.request("TaxAccount", ...);
```

→ lấy **string literal đối số đầu** (hoặc đối số trùng tên action FBO): `DebitAccount`, `TaxAccount`.

Dedup + sort alphabetically khi trả JSON.

### Quy tắc `functions`

Chỉ **khai báo** `function Name(` — không liệt kê mọi call site. Giữ `$` trong tên.

### §3.1. `js.calls` whitelist — CHỐT CỨNG v1

Chỉ ghi nhận các dạng sau (normalize tên ngắn):

| Pattern callee | Giá trị ghi vào `calls` |
|----------------|-------------------------|
| `*.request` / `request` | `f.request` hoặc `o.parentForm.request` (giữ prefix thực tế nếu bắt được, else `request`) |
| `*.executeExpression` | `f.executeExpression` |
| `$message.show` | `$message.show` |

**Không** đưa vào v1: `setItemValue`, `getItemValue`, `$func.hideWait`, hay call khác (tránh noise / JSON phình).

Phase 2 mới mở rộng whitelist nếu Agent cần.

## 4. `$defs.SqlSummary`

```json
{
  "parse_status": { "enum": ["ok", "partial", "failed", "empty"] },
  "blocks": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["kind", "line"],
      "properties": {
        "kind": { "enum": ["command", "action", "query"] },
        "event": { "type": ["string", "null"], "description": "command/@event" },
        "id": { "type": ["string", "null"], "description": "action/@id" },
        "line": { "type": "integer" },
        "lang": { "enum": ["sql", "js"], "description": "Sau sniff; hầu hết sql" }
      }
    }
  },
  "tables": { "type": "array", "items": { "type": "string" } },
  "procs": { "type": "array", "items": { "type": "string" } },
  "views": {
    "type": "array",
    "items": { "type": "string" },
    "description": "v1: heuristic tên bắt đầu v / chứa view; hoặc để [] nếu không chắc"
  },
  "signals": {
    "type": "array",
    "items": {
      "type": "string",
      "enum": [
        "dynamic_sql",
        "partition",
        "cursor",
        "encrypted_skipped",
        "fbo_ifdef",
        "checking_routed_to_sql"
      ]
    }
  },
  "line_count": { "type": "integer" }
}
```

### Quy tắc tables / procs

- Reuse visitor T-SQL: `FROM`/`JOIN`/`INTO`/`UPDATE`/`DELETE` → tables
- `EXEC`/`EXECUTE` → procs
- Giữ tên có `$` và `@@prime$partition$current` / `d81$$partition$current`
- Temp `#x` → có thể bỏ khỏi `tables` hoặc đưa `signals` — **v1: không đưa `#temp` vào `tables`** (giống tinh thần summary_object temp tách)
- Dedup case-insensitive, trả về form xuất hiện đầu tiên hoặc lower — **chốt: giữ nguyên casing lần gặp đầu**

### `views` v1 — chốt

- Mọi identifier bảng/view từ FROM/JOIN/… đều vào **`tables`** trước.
- **`views` ⊆ `tables`:** chỉ là classification hint (heuristic tên `^v[0-9a-z_]+` / `^zv`). Tên view **vẫn nằm trong `tables`**; `views` là danh sách con (có thể trùng tên với phần tử trong `tables`).
- Không chắc → `views: []` — **không** xóa khỏi `tables`.
- Không fail nếu heuristic nhầm.

## 5. `$defs.FieldSummary`

```json
{
  "type": "object",
  "required": ["name", "type"],
  "properties": {
    "name": { "type": "string" },
    "type": { "enum": ["char", "number", "checkbox", "date"] },
    "lookup": {
      "type": "string",
      "description": "items/@controller nếu có"
    },
    "onchange": {
      "type": "string",
      "description": "Tên hàm từ clientScript onchange=..."
    },
    "hidden": { "type": "boolean" },
    "allowNulls": { "type": ["boolean", "null"] }
  },
  "additionalProperties": false
}
```

**Token discipline:** Chỉ thêm `lookup` / `onchange` / `hidden` / `allowNulls` khi có giá trị hữu ích. Không dump `header`, `key`, `information`, `width`.

### Map type → bucket

| XML `type` / hint | Bucket |
|-------------------|--------|
| `DateTime`, `*Date*` | `date` |
| `Decimal`, `Int16`, `Int32`, `Int64`, `Byte`, `Double`, `Single`, `Numeric` | `number` |
| `CheckBox`, `Boolean` | `checkbox` |
| `items style="CheckBox"` (kể cả thiếu type) | `checkbox` |
| còn lại / thiếu type | `char` |

### Extract `onchange`

Từ:

```xml
<clientScript><![CDATA[onchange="onChange$Voucher$Customer(this);"]]></clientScript>
```

Regex gợi ý:

```python
r"onchange\s*=\s*[\"']\s*([a-zA-Z0-9_$]+)\s*\("
```

→ `onChange$Voucher$Customer`

## 6. `$defs.Meta`

```json
{
  "flat_chars": { "type": "integer" },
  "estimated_tokens_saved": { "type": "integer" },
  "skipped_encrypted_blocks": { "type": "integer" },
  "warnings": { "type": "array", "items": { "type": "string" } },
  "parse_ms": { "type": "integer" }
}
```

`estimated_tokens_saved ≈ max(0, (flat_chars - len(json_chars)) // 4)`

## 7. Ví dụ rút gọn (golden SVTran)

```json
{
  "success": true,
  "mode": "summary",
  "spec_version": "1.0",
  "file": "Dir\\SVTran.xml",
  "controller": {
    "folder_type": "Dir",
    "db_table": null,
    "title_v": null
  },
  "js": {
    "parse_status": "ok",
    "sources": ["script", "command:Checking"],
    "functions": [
      "active$Voucher$",
      "init$Voucher$",
      "onChange$Voucher$Customer",
      "onChange$Voucher$DebitAccount",
      "onChange$Voucher$TaxAccount",
      "onChange$Voucher$TaxCode",
      "onChange$Voucher$Transaction"
    ],
    "calls": [
      "$message.show",
      "f.executeExpression",
      "f.request",
      "o.parentForm.request"
    ],
    "request_actions": [
      "Customer",
      "DebitAccount",
      "GetTaxRate",
      "TaxAccount",
      "Term",
      "Transaction"
    ],
    "line_count": 420
  },
  "sql": {
    "parse_status": "partial",
    "blocks": [
      { "kind": "command", "event": "Loading", "id": null, "line": 855, "lang": "sql" },
      { "kind": "command", "event": "Scattering", "id": null, "line": 944, "lang": "sql" },
      { "kind": "action", "event": null, "id": "TaxAccount", "line": 3288, "lang": "sql" },
      { "kind": "action", "event": null, "id": "Customer", "line": 3250, "lang": "sql" }
    ],
    "tables": [
      "d81$$partition$current",
      "dmct",
      "dmdvcs",
      "dmmagd",
      "dmthue",
      "dmtk",
      "hddt00$$partition$current",
      "options",
      "v20dmctnk",
      "zcdmloaidt",
      "zvdmloaidt"
    ],
    "procs": ["sp_executesql"],
    "views": ["zvdmloaidt", "v20dmctnk"],
    "signals": ["dynamic_sql", "partition", "encrypted_skipped", "fbo_ifdef"],
    "line_count": 1800
  },
  "fields": [
    {
      "name": "ma_kh",
      "type": "char",
      "lookup": "Customer",
      "onchange": "onChange$Voucher$Customer",
      "allowNulls": false
    },
    {
      "name": "tk",
      "type": "char",
      "lookup": "Account",
      "onchange": "onChange$Voucher$DebitAccount",
      "allowNulls": false
    },
    {
      "name": "ty_gia",
      "type": "number"
    },
    {
      "name": "ngay_ct",
      "type": "date",
      "allowNulls": false
    },
    {
      "name": "stt_rec",
      "type": "char",
      "hidden": true
    }
  ],
  "meta": {
    "flat_chars": 210000,
    "estimated_tokens_saved": 48000,
    "skipped_encrypted_blocks": 3,
    "warnings": ["sql_partial_due_to_fbo_ifdef"],
    "parse_ms": 350
  }
}
```

> Số liệu `line_count` / `flat_chars` trong ví dụ là **minh họa**. Test assert theo **tập tên** (functions, tables chứa `dmtk`, field `ma_kh.lookup == Customer`), không assert số tuyệt đối cứng.  
> `views` ở trên ⊆ `tables` (vd. `zvdmloaidt`, `v20dmctnk` có mặt ở cả hai).

## 7b. Ví dụ Filter (JS empty — expected)

```json
{
  "success": true,
  "mode": "summary",
  "spec_version": "1.0",
  "file": "Filter\\SVInvoiceFilter.xml",
  "controller": {
    "folder_type": "Filter",
    "db_table": null,
    "title_v": null
  },
  "js": {
    "parse_status": "empty",
    "sources": [],
    "functions": [],
    "calls": [],
    "request_actions": [],
    "line_count": 0
  },
  "sql": {
    "parse_status": "ok",
    "blocks": [
      { "kind": "query", "event": null, "id": null, "line": 120, "lang": "sql" }
    ],
    "tables": ["m81$", "dmkh"],
    "procs": [],
    "views": [],
    "signals": ["partition"],
    "line_count": 80
  },
  "fields": [
    { "name": "ngay_ct1", "type": "date" },
    { "name": "ma_kh", "type": "char", "lookup": "Customer" }
  ],
  "meta": {
    "flat_chars": 12000,
    "estimated_tokens_saved": 2500,
    "skipped_encrypted_blocks": 0,
    "warnings": [],
    "parse_ms": 40
  }
}
```

> `js.parse_status: "empty"` trên Filter/Grid/Report **không** phải lỗi — Agent vẫn dùng `sql` + `fields`.

## 8. `success: false`

Khi flat rỗng / file `.f` encrypted / không extract được gì:

```json
{
  "success": false,
  "mode": "summary",
  "spec_version": "1.0",
  "file": "Dir\\Broken.f",
  "controller": {
    "folder_type": "Dir",
    "db_table": null,
    "title_v": null
  },
  "js": { "parse_status": "empty", "sources": [], "functions": [], "calls": [], "request_actions": [], "line_count": 0 },
  "sql": { "parse_status": "empty", "blocks": [], "tables": [], "procs": [], "views": [], "signals": [], "line_count": 0 },
  "fields": [],
  "meta": {
    "flat_chars": 0,
    "estimated_tokens_saved": 0,
    "skipped_encrypted_blocks": 0,
    "warnings": ["encrypted_file_not_supported"],
    "parse_ms": 1
  }
}
```

Warning codes thường gặp: `empty_flat_xml`, `encrypted_file_not_supported`, `flat_failed`.

---

## 9. Cấu trúc mở rộng cho Grid & Form liên quan (`grid_formulas`, `show_forms`, `related_controllers`)

Khi controller (thường là Grid) có định nghĩa `g.$a = { ... }` hoặc gọi `g.showForm('...')`, JSON summary sẽ bổ sung các trường sau (tự động omit nếu không có):

```json
{
  "grid_formulas": {
    "expressions": {
      "gia0_tg": "[gia0]:=[gia_nt0]*[$ty_gia]",
      "tien_nt0": "[tien_nt0]:=[so_luong]*[gia_nt0]"
    },
    "aggregates": {
      "t_so_luong": ["t_so_luong", "so_luong"],
      "t_tien_nt0": ["t_tien_nt0", "tien_nt0"]
    }
  },
  "show_forms": [
    "PVDetailImport",
    "PVOrderFilter"
  ],
  "related_controllers": [
    "PVDetailImport",
    "PVOrderFilter",
    "PVOrderForm",
    "PVOrderGrid",
    "PVOrderLookup",
    "PVOrderMultiForm",
    "PVOrderMultiGrid"
  ]
}
```

- **`grid_formulas.expressions`**: Công thức tính toán giữa các cột cùng dòng trên Grid (String chứa `[col]:=...`).
- **`grid_formulas.aggregates`**: Công thức cộng dồn cột grid lên trường master (Mảng 2 phần tử `["master_field", "grid_col"]`).
- **`show_forms`**: Danh sách tên form gọi trực tiếp qua `g.showForm(...)`.
- **`related_controllers`**: Danh sách `show_forms` kèm các controller mở rộng từ `*Filter` (`Grid`, `MultiGrid`, `Form`, `MultiForm`, `Lookup`).

