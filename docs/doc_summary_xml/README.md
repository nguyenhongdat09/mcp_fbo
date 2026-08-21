# MCP `summary_xml` — Tài liệu triển khai (gửi Gemini)

> **Mục đích:** Mở rộng tool MCP `read_local_file` để trả **JSON tóm tắt** controller XML FastBusiness (JS + SQL + fields) thay vì full flat XML — tiết kiệm token cho AI Agent.
>
> **Hướng triển khai:** Flat entity → tách block JS/SQL/fields → ANTLR4 (ECMAScript + tái sử dụng `tsql_engine`) → JSON gọn.
>
> **Repo:** `E:\PythonProject\mcp_fbo\`
>
> **Song song với:** [`docs/doc/`](../doc/) (`summary_object` cho proc/view SQL Server).

---

## Danh sách tài liệu

| File | Nội dung |
|------|----------|
| [01_overview.md](./01_overview.md) | Bối cảnh, mục tiêu, phạm vi, không làm gì |
| [02_tool_api.md](./02_tool_api.md) | Input/output `read_local_file` `read_option=3` |
| [03_json_schema.md](./03_json_schema.md) | JSON schema chi tiết + ví dụ SVTran |
| [04_extract_and_antlr.md](./04_extract_and_antlr.md) | Extract tag, JS ANTLR, SQL reuse, field map |
| [05_integration.md](./05_integration.md) | Bridge vào MCP, cache, test |
| [06_implementation_checklist.md](./06_implementation_checklist.md) | Checklist từng bước cho Gemini |
| [07_architecture_layers.md](./07_architecture_layers.md) | Kiến trúc lớp — `js_engine` / `xml_controller_summary` / bridge |

---

## Tóm tắt 1 trang

### Vấn đề

`read_local_file` với `read_option=2` (flat) trả **toàn bộ XML đã expand entity** (SVTran ~3.000+ dòng). Agent FBO thường chỉ cần:

- Có bao nhiêu hàm JS (`onChange$Voucher$*`, `init$Voucher$`…)
- Bảng / proc / view SQL trong command + action
- Danh sách field gọn: type bucket + lookup + onChange

### Giải pháp

Mở rộng **`read_local_file`** — **không** tạo tool MCP mới:

```
Agent → read_local_file(..., read_option=1)  → raw XML
Agent → read_local_file(..., read_option=2)  → flat XML
Agent → read_local_file(..., read_option=3)  → JSON summary_xml (~2–15 KB)
```

### Pipeline (đã xác nhận trên flat SVTran)

```
file_path
  → flat_xml (XmlEntityExpander)     # bỏ quan tâm ENTITY / Include
  → strip <encrypted> / <Encrypted>
  → extract:
       JS  = <script> CDATA + <command event="Checking"> CDATA
       SQL = command khác Checking + <action> + <query>
       Fields = <field> (type / lookup / clientScript)
  → ANTLR JS (js_engine) + ANTLR T-SQL (tsql_engine reuse)
  → JSON summary
```

### Kiến trúc module (tách biệt + nhúng nhẹ)

> Chi tiết bắt buộc: [`07_architecture_layers.md`](./07_architecture_layers.md) — **đọc trước khi code.**

```
mcp_fbo/
  js_engine/                     ← MỚI: ANTLR JS thuần (reuse sau này cho lint/Graph)
  tsql_engine/                   ← REUSE sẵn (nhúng parse(), không fork)
  xml_controller_summary/        ← MỚI: pure analyze_flat_xml(str) → JSON
  find_entity_by_xml/
    facade.flat_xml              ← REUSE I/O
    bridges/summary_xml_bridge   ← nhúng nhẹ: path → flat → analyze (~10 dòng)
  xml_fbograph/mcp_tools.py      ← chỉ switch read_option=3 → bridge
  fastbusiness_mcp/mcp_app.py    ← Literal[1,2,3] — không chứa logic summary
```

**Ba cấp API (caller chọn đúng tầng, không trộn):**

| Cần gì | Gọi |
|--------|-----|
| Parse JS/SQL thuần | `js_engine.parse` / `tsql_engine.parse` |
| Đã có flat string | `xml_controller_summary.analyze_flat_xml` |
| Có file path | `summary_xml(path)` bridge |

**Dependency một chiều:** `mcp → bridge → xml_controller_summary → {js_engine, tsql_engine}`  
**Cấm:** logic extract/ANTLR nằm trong MCP; copy visitor vào FBOGraph; `xml_controller_summary` tự `open`/flat.
---

## Thứ tự đọc cho Gemini

1. `07_architecture_layers.md` — **đọc trước** (tách folder, quy tắc dependency)
2. `04_extract_and_antlr.md` — extract rules + ANTLR JS + SQL reuse
3. `01_overview.md` — hiểu WHY
4. `02_tool_api.md` — contract MCP
5. `03_json_schema.md` — output cụ thể
6. `05_integration.md` — bridge vào `read_local_file`
7. `06_implementation_checklist.md` — làm tuần tự

---

## Case test bắt buộc (LIKSIN / FBISP23)

Sau khi implement, test với file:

`\\172.168.5.14\CustomerPro\HRM\LIKSIN\FBISP23\App_Data\Controllers\Dir\SVTran.xml`

| Kiểm tra | Kỳ vọng |
|----------|---------|
| `js.functions` chứa | `onChange$Voucher$Customer`, `init$Voucher$`, `active$Voucher$` |
| `js.sources` | `script`, `command:Checking` |
| `js.request_actions` chứa | `Customer`, `TaxAccount`, `DebitAccount`, `GetTaxRate` |
| `sql.tables` chứa | `dmtk`, `dmthue`, `options`, partition dạng `*$partition$*` hoặc `@@prime$partition$current` |
| `sql.blocks` có | `command:Loading`, `command:Scattering`, `action:TaxAccount` |
| `fields` có `ma_kh` | `type: char`, `lookup: Customer`, `onchange: onChange$Voucher$Customer` |
| `fields` có `ty_gia` | `type: number` |
| `fields` có `ngay_ct` | `type: date` |
| `read_option=1` và `2` | **không** đổi behavior |

CI có thể dùng **fixture mock** (đoạn XML rút gọn) — không bắt buộc UNC trong pipeline.
