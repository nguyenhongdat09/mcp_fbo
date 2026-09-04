# MCP `clone_things` — Tài liệu triển khai (gửi Gemini)

> **Mục đích:** Thêm MCP tool `clone_things` để clone object SQL (table / stored procedure / function / view) từ **project nguồn** sang **project đích**, ghi script vào file `.sql`, mở file cho user thấy, và trả JSON tóm tắt cho Agent.
>
> **Vai trò tài liệu:** BA (requirements + contract) + Tester (acceptance / test matrix). **Không** implement code trong phase doc này.
>
> **Repo:** `E:\PythonProject\mcp_fbo\`
>
> **Reuse bắt buộc:** `query_database` (type=0, mode summary/full), `read_local_file` / `summary_xml` (read_option=3), `find_connect_by_path`.

---

## Danh sách tài liệu

| File | Nội dung |
|------|----------|
| [01_overview.md](./01_overview.md) | Bối cảnh, mục tiêu, phạm vi, ví dụ end-to-end |
| [02_tool_api.md](./02_tool_api.md) | MCP input params, validation, error shape |
| [03_resolution_and_flow.md](./03_resolution_and_flow.md) | Target-first, seed XML/SQL, queue loop, append, open file |
| [04_json_response.md](./04_json_response.md) | JSON schema response + samples |
| [05_config_and_sql_temp.md](./05_config_and_sql_temp.md) | `config.yaml`, NewSqlTemp parity, mở editor bằng Python |
| [06_reuse_existing.md](./06_reuse_existing.md) | Map sang module hiện có — cấm reinvent |
| [07_test_cases.md](./07_test_cases.md) | BA/QA test matrix + expected |
| [08_implementation_checklist.md](./08_implementation_checklist.md) | Phase implement + anti-patterns + Prompt Gemini |
| [09_suggestions.md](./09_suggestions.md) | Gợi ý mở rộng (không bắt buộc v1) |

---

## Tóm tắt 1 trang

### Vấn đề

Agent / dev thường cần mang object SQL từ dự án A sang dự án B khi làm UR:

- Phải tự `query_database` từng object trên 2 DB
- Phải tự lần dependency (proc gọi proc/func/table)
- Phải tự paste vào `.sql` — dễ sót, khó theo dõi object nào thiếu ở cả 2 project

### Giải pháp

Tool MCP mới:

```
Agent → clone_things(
  type=0,
  object=<sql_name | xml_path>,
  project_source=<abs path>,
  project_target=<abs path>,
  path_to_pasted=<abs .sql | "">
) → JSON { cloned, skipped_exists, not_found_both, path_to_pasted, warnings }
```

### Quy tắc lõi (không được lệch)

1. **Target-first:** object đã có ở DB target → **không** lấy từ source; ghi vào `skipped_exists` (v1: không quét deps của object đã có).
2. Chỉ khi **không có ở target** mới lấy definition/DDL từ source → append vào `.sql`.
3. Không có ở **cả hai** → ghi `not_found_both` (và **một** dòng comment tổng hợp cuối `.sql`).
4. Proc/func → phân tích dependency (summary) → enqueue → lặp đến hết queue / limit.
5. `object` là XML → seed danh sách SQL qua `summary_xml`, rồi cùng vòng target-first.
6. `path_to_pasted` trống → tạo `.sql` temp theo `clone_things.sql_temp_folder` (parity NewSqlTemp) → **mở file** (CLI / `os.startfile`), không tạo ngầm.
7. Append: dòng trống + **`GO`** giữa các batch CREATE (SSMS-valid).

### Pipeline

```
resolve output .sql
  → seed queue (SQL name | XML summary)
  → while queue:
        exists target? → skipped_exists (no deps scan)
        else exists source? → fetch full → append (blank + GO) → analyze deps → enqueue
        else → accumulate not_found_both
  → one summary comment for not_found_both
  → open .sql for user
  → return JSON
```

---

## Quyết định BA đã chốt

| # | Quyết định |
|---|------------|
| 1 | Object đã có target → `skipped_exists` trong JSON (không im lặng); không quét deps con |
| 2 | Mở file: Python `Popen` `cursor`/`code` (PATH + LocalAppData default), fallback `os.startfile`; fail → `warnings` |
| 3 | `type` mặc định `0` (SQL). Clone file XML thuần = out of scope v1 |
| 4 | Exclude infra mặc định: `FastBusiness$`, `ff_`, `fsd_` |
| 5 | Exists qua `sys.objects` — **cấm** `fetch_one` cho bảng |
| 6 | Separator block v1: blank line + `GO` |
| 7 | Visited key normalize `dbo.name` lowercase |

---

## Thứ tự đọc cho Gemini

1. [01_overview.md](./01_overview.md) — WHY + scope
2. [02_tool_api.md](./02_tool_api.md) — contract input
3. [03_resolution_and_flow.md](./03_resolution_and_flow.md) — algorithm
4. [04_json_response.md](./04_json_response.md) — contract output
5. [05_config_and_sql_temp.md](./05_config_and_sql_temp.md) — config + open file
6. [06_reuse_existing.md](./06_reuse_existing.md) — reuse map
7. [07_test_cases.md](./07_test_cases.md) — AC / tests
8. [08_implementation_checklist.md](./08_implementation_checklist.md) — làm tuần tự
9. [09_suggestions.md](./09_suggestions.md) — optional sau v1

---

## Acceptance tóm tắt (v1)

- [ ] Tool `clone_things` đăng ký MCP, params đúng contract
- [ ] Target-first + recursive deps + not_found_both
- [ ] Append có 1 dòng trống **và `GO`** giữa các block CREATE
- [ ] `path_to_pasted` trống → tạo file trong `sql_temp_folder` + mở editor
- [ ] JSON có đủ `cloned`, `skipped_exists`, `not_found_both`, `path_to_pasted`, `warnings`
- [ ] Exists dùng `sys.objects` (không `fetch_one` cho table); table DDL ghép từ `val`
- [ ] Reuse `query_database` / `summary_xml` / connection resolver — không tự viết SQL catalog khi đã có type=0
