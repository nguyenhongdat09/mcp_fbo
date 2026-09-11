# MCP `compare_things` — Tài liệu triển khai (gửi Gemini)

> **Mục đích:** MCP tool `compare_things` — so sánh đa loại giữa 2 project FastBusiness (và so 2 file / 2 folder trên đĩa) → JSON **agent-actionable** (giống / lệch / thiếu + khoảng dòng + gợi ý bước tiếp). Không clone, không ALTER, không deploy.

> **Vai trò tài liệu:** BA (requirements + contract) + Architecture + Tester (acceptance). **Phase này không implement code** — Gemini đọc bộ doc rồi code.

> **Repo:** `E:\PythonProject\mcp_fbo\`

> **Reuse bắt buộc:** `clone_things.db_ops` (resolve Web.config app/sys, `is_object_encrypted`), stdlib `difflib` / `hashlib` / `pathlib`. CẤM `query_database` mode=full dump definition ra chat/JSON mặc định.

> **Khác `clone_things`:** `clone_things` = mang thiếu / paste ALTER. `compare_things` = **chỉ ra lệch** để agent quyết bước tiếp.

---

## Danh sách tài liệu

| File | Nội dung |
|------|----------|
| [01_overview.md](./01_overview.md) | Bối cảnh, mục tiêu, kind matrix, vs clone_things, out of scope |
| [02_tool_api.md](./02_tool_api.md) | MCP params, validation, error_code theo kind |
| [03_architecture.md](./03_architecture.md) | Package `compare_things/` tách file, trách nhiệm module |
| [04_json_response.md](./04_json_response.md) | Schema JSON agent-actionable + samples + next_actions |
| [05_kind_file.md](./05_kind_file.md) | `kind=file` — 2 abs path, CRLF, hunks dòng |
| [06_kind_folder.md](./06_kind_folder.md) | `kind=folder` — UNC/bin, missing, meta size/ctime/mtime |
| [07_kind_sql.md](./07_kind_sql.md) | `kind=sql` — proc/func/view, seed, fingerprint, hunks, signals |
| [08_kind_xml.md](./08_kind_xml.md) | `kind=xml` — relative path 2 project → file engine |
| [09_kind_table.md](./09_kind_table.md) | `kind=table` — schema ngữ nghĩa (bỏ qua thứ tự cột) |
| [10_reuse_existing.md](./10_reuse_existing.md) | Map module hiện có, anti-patterns |
| [11_test_cases.md](./11_test_cases.md) | BA/QA test matrix + expected |
| [12_implementation_checklist.md](./12_implementation_checklist.md) | Phase P0→P3 + Prompt Gemini copy-paste |

---

## Thứ tự đọc (Gemini)

1. `01_overview` → nắm scope
2. `03_architecture` → scaffold đúng cây file (cấm 1 file khổng lồ)
3. `02_tool_api` + `04_json_response` → contract MCP
4. `05`→`09` theo phase implement
5. `10_reuse` trước khi đụng DB
6. `11_test_cases` + `12_checklist` khi code / DoD

---

## Prompt ngắn (dán Gemini)

```text
Implement MCP tool compare_things theo TOÀN BỘ docs/doc/compare_things/.
Package compare_things/ tách file đúng 03_architecture.md.
Wire fastbusiness_mcp/mcp_app.py. Tests tests/compare_things/.
JSON agent-actionable: hunks có line_start/line_end cho file/sql; next_actions; không dump full body mặc định.
kind=table: cột đảo thứ tự cùng type = identical.
kind=folder: so meta (size/ctime/mtime), missing files; compare_content default false.
Reuse clone_things.db_ops; skip encrypted. Không auto clone/ALTER/deploy.
Làm theo 12_implementation_checklist.md phase P0 → P0b → P1 → P2 → P3.
```

Chi tiết prompt: [12_implementation_checklist.md](./12_implementation_checklist.md).
