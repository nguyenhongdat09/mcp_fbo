# MCP Tool `summary_object` — Tài liệu triển khai (gửi Gemini)

> **Mục đích:** Thêm tool MCP phân tích proc/function SQL Server trên FastBusiness, trả JSON gọn thay vì full `object_definition` — tiết kiệm token cho AI Agent.
>
> **Hướng triển khai:** ANTLR4 (T-SQL grammar) + tái sử dụng module `queryDatabase` hiện có.
>
> **Repo:** `E:\PythonProject\mcp_fbo\`

---

## Danh sách tài liệu

| File | Nội dung |
|------|----------|
| [01_overview.md](./01_overview.md) | Bối cảnh, mục tiêu, phạm vi, không làm gì |
| [02_tool_api.md](./02_tool_api.md) | Input/output MCP tool, 3 tier (summary / snippet / full) |
| [03_json_schema.md](./03_json_schema.md) | JSON schema chi tiết + ví dụ thực tế FBO |
| [04_antlr4_parser.md](./04_antlr4_parser.md) | Kiến trúc ANTLR4, visitor, extract rules |
| [05_integration.md](./05_integration.md) | Bridge mỏng trong `queryDatabase`, MCP, cache, test |
| [06_implementation_checklist.md](./06_implementation_checklist.md) | Checklist từng bước cho Gemini |
| [07_architecture_layers.md](./07_architecture_layers.md) | **Kiến trúc 3 lớp** — `tsql_engine` / `sql_object_summary` / bridge |
| [08_review_changelog.md](./08_review_changelog.md) | Log các sửa sau review |
| [09_tsql_grammar.md](./09_tsql_grammar.md) | **Grammar `.g4` có sẵn** + generate ANTLR + entry rules |

---

## Tóm tắt 1 trang

### Vấn đề

Tool `query_database` với `query_type=0` gọi `sp_helptext` → trả **toàn bộ body** proc (300–800+ dòng). Agent FBO thường chỉ cần:

- Tham số, bảng đọc/ghi, temp table
- Proc/function được gọi (1 hop)
- Dấu hiệu: cursor, dynamic SQL, partition, pivot
- **Snippet** đoạn logic nghiệp vụ (tính lãi, bucket tháng…) — không cần full proc

### Giải pháp

Tool mới **`summary_object`**:

```
Agent → summary_object(object_name, mode=summary)  → JSON ~2–8 KB
Agent → summary_object(..., mode=snippet, keywords=[...])  → đoạn SQL cần đọc
Agent → summary_object(..., mode=full)  → fallback (giới hạn max_chars)
```

### Quy tắc cây gọi (đã thống nhất với Agent)

| Loại object | Depth mặc định |
|-------------|----------------|
| Proc nghiệp vụ (`zc_*`, `rs_rpt*`, `rs_*`) | mặc định **1**, tối đa **3** (`max_depth`) |
| Infra (`FastBusiness$%`, `ff_%`, `fsd_%`) | **0 cấp** — chỉ tên + `kind: "infra"` |
| **VIEW** (`sys.objects.type = V`) | **0 cấp** — chỉ `tables_read` + columns, không đệ quy call graph |
| Table / temp | Liệt kê phẳng, không đệ quy |

Bung thêm cấp chỉ khi `expand=[...]` hoặc `max_depth` tăng thủ công (tối đa 30 objects, vượt giới hạn lưu vào `truncated_objects`).

### Kiến trúc module (3 lớp — xem chi tiết `07_architecture_layers.md`)

```
mcp_fbo/
  tsql_engine/
    grammar/                   ← TSqlLexer.g4 + TSqlParser.g4 (CÓ SẴN)
    generated/                 ← sau generate.bat
    tools/download_grammar.py
    engine.py
  sql_object_summary/          # analyze definition (pure logic) → JSON
  queryDatabase/
    object_catalog/
    bridges/summary_bridge.py
  fastbusiness_mcp/
    mcp_app.py
```

**Dependency một chiều:** `mcp → queryDatabase → sql_object_summary → tsql_engine`

### Dependency mới

```txt
antlr4-python3-runtime>=4.13.0
```

(Grammar `.g4` **đã nằm sẵn** trong `tsql_engine/grammar/`. Chạy `tools/generate.bat` → `generated/`. Chi tiết: `09_tsql_grammar.md`.)

---

## Thứ tự đọc cho Gemini

1. `07_architecture_layers.md` — **đọc trước** (tách folder, quy tắc dependency)
2. `09_tsql_grammar.md` — **grammar `.g4` + generate** (bắt buộc trước khi code visitor)
3. `01_overview.md` — hiểu WHY
4. `02_tool_api.md` — contract MCP
5. `03_json_schema.md` — output cụ thể
6. `04_antlr4_parser.md` — HOW parse (`tsql_engine`)
7. `05_integration.md` — bridge trong `queryDatabase`
8. `06_implementation_checklist.md` — làm tuần tự

---

## Case test bắt buộc (FBISP242)

Sau khi implement, test với DB project FBISP242:

| Object | Kiểm tra |
|--------|----------|
| `rs_rptInterestDetailedByLoanContract` | params `@LoanFrom`, `@Status`; tables `dmku`, `ctdmku`, `options`; signals cursor; snippet chứa `tl_th`, `@days` |
| `zc_bcthlv` | pivot RS1/RS2; temp `#lai_thang`; gọi logic tương tự proc chuẩn |
| `FastBusiness$Balance$BContract` | `kind: infra`, **không** expand con mặc định |
| `ff_GetStartDateOfCycle` | `kind: infra`, depth 0 |

Connection resolve giống `query_database`: truyền `file_path` XML bất kỳ trong project FBO.

**Khác `query_database type=0`:** `summary_object` lookup theo **schema + name** (`dbo.zc_bcthlv` hoặc `object_name` + param `schema`); xem `02_tool_api.md` §2.1.
