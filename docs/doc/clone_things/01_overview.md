# 01 — Overview: `clone_things`

## 1. Bối cảnh

Khi làm UR / migrate giữa hai dự án FastBusiness (ví dụ SP2263 → dự án khách), dev/agent thường cần mang theo:

- Stored procedure / function / view / table
- Cả chuỗi dependency (proc A gọi func B, đọc bảng C…)

Hiện đã có:

| Tool | Việc làm được | Việc chưa làm |
|------|---------------|---------------|
| `query_database` type=0 | Phân loại object, DDL table, summary/full proc | Không ghi file, không so 2 project |
| `read_local_file` option=3 | Liệt kê SQL tables/procs/views trong XML | Không clone |
| Extension `fboFile.NewSqlTemp` | Tạo `.sql` temp + mở tab | Không lấy object từ DB |

`clone_things` nối các mảnh trên thành một thao tác Agent-friendly.

## 2. Mục tiêu (Goals)

### type=0 — clone giữa 2 project

1. Clone **toàn bộ script** object SQL thiếu ở project đích (lấy từ project nguồn) vào một file `.sql`.
2. Tự **phân loại** object (table / proc / func / view) qua catalog SQL Server.
3. Tự **mở rộng dependency** với proc/func (và seed từ XML) bằng summary hiện có.
4. **Target-first:** chỉ clone object **chưa có** ở DB target.
5. Báo rõ object **không có ở cả hai** project.
6. Trả JSON gọn cho Agent; đồng thời user **nhìn thấy** file `.sql` (mở editor).

### type=1 — paste-for-edit (1 project)

1. Lấy definition proc/func/view (và table nếu cần) từ **một** `project_source` → paste vào `.sql`.
2. Đổi `CREATE PROC/FUNC/VIEW` → **`ALTER …`** để user F5 cập nhật object đã có.
3. JSON có `pasted[].line_start` / `line_end` + `agent_message` — agent sửa **trong file**, không dump full SQL ra chat.
4. Dedup trong file; **không** execute/deploy. Chi tiết: [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md).

## 3. Không làm gì (Out of scope)

| Hạng mục | Ghi chú |
|----------|---------|
| Clone file XML / copy Controllers (`type=2` dự phòng) | **Không** dùng `type=1` cho việc này — type=1 = paste-for-edit |
| Deploy / EXECUTE mặc định lên DB | type=0: theo config; type=1: **luôn tắt** |
| type=0: overwrite object đã có ở target | → `skipped_exists` |
| Decrypt / đọc `.f` mã hóa | Giống summary_xml: không hỗ trợ |
| Clone data (INSERT rows) | Chỉ schema / definition |
| UI VS Code extension command | Parity UX NewSqlTemp ở phía MCP Python |

## 4. In scope

- MCP tool `clone_things` với `type` ∈ `{0, 1}`
- Input: `type`, `object`, `project_source`, `project_target` (optional khi type=1), `path_to_pasted`
- Config: `clone_things.sql_temp_folder`, `clone_things.open_editor_cmd`
- **type=0:** seed SQL name hoặc XML; queue deps; `CREATE`; target-first; JSON `cloned` / …
- **type=1:** list tên SQL; `ALTER`; dedup file; line range; JSON `pasted` / …

## 5. Ví dụ end-to-end

### 5.1. Clone một proc

**Input**

```json
{
  "type": 0,
  "object": "zc_example_report",
  "project_source": "E:\\FBO\\SP2263",
  "project_target": "E:\\FBO\\CUSTOMER_A",
  "path_to_pasted": ""
}
```

**Giả định**

- Target không có `zc_example_report`
- Source có proc; summary thấy gọi `dbo.zc_helper` và đọc `dmkh`
- Target đã có `dmkh`, chưa có `zc_helper`
- `zc_helper` có ở source

**Kỳ vọng**

1. Tạo `E:\...\sql_temp\zc_example_report.sql` (theo config)
2. Append full definition `zc_example_report` rồi `zc_helper` (mỗi block cách 1 dòng trống)
3. `dmkh` → `skipped_exists`
4. Mở file trên Cursor/Code
5. JSON:

```json
{
  "success": true,
  "cloned": [
    {"name": "zc_example_report", "object_type": "PROCEDURE", "from": "source"},
    {"name": "zc_helper", "object_type": "FUNCTION", "from": "source"}
  ],
  "skipped_exists": [
    {"name": "dmkh", "object_type": "USER_TABLE", "where": "target"}
  ],
  "not_found_both": [],
  "path_to_pasted": "E:\\...\\zc_example_report.sql",
  "warnings": []
}
```

### 5.2. Object thiếu cả hai project

Source không có `funcGhost`, target cũng không →:

- Dòng trong `.sql`: `-- not found in 2 project: funcGhost`
- JSON: `"not_found_both": ["funcGhost"]`

### 5.3. Seed từ XML

`object` = `E:\FBO\SP2263\App_Data\Controllers\Dir\SVTran.xml`

→ summary_xml lấy `sql.tables`, `sql.procs`, `sql.views`, `controller.db_table` → đưa vào queue → cùng luật target-first.

### 5.4. type=1 — paste proc để chỉnh

```json
{
  "type": 1,
  "object": "dbo.zc_bkctnb",
  "project_source": "E:\\FBO\\SHOWA\\FBISP242\\App_Data\\Controllers\\Templates\\Upload\\SVTran.xml",
  "project_target": "",
  "path_to_pasted": "E:\\SQL Temp\\showa_fbisp242 (5).sql"
}
```

→ Append `ALTER PROCEDURE …` vào file; JSON `pasted` kèm `line_start`/`line_end`; user tự F5. Xem [11](./11_type1_paste_for_edit.md).

## 6. Actors

| Actor | Vai trò |
|-------|---------|
| AI Agent (Cursor) | Gọi tool, đọc JSON, có thể mở thêm tab nếu cần |
| Human user | Nhìn / chỉnh file `.sql` đã mở |
| Gemini implementer | Code theo checklist `08_*` |
| BA / Tester | Spec này + `07_test_cases.md` |

## 7. Định nghĩa thuật ngữ

| Thuật ngữ | Nghĩa |
|-----------|--------|
| **project_source** | Root hoặc path trong project FBO nguồn (có `Web.config` / `App_Data`) |
| **project_target** | Tương tự, project đích |
| **Target-first** | Kiểm tra tồn tại trên DB target trước khi lấy từ source |
| **Seed** | Danh sách object ban đầu đưa vào queue |
| **sql temp** | File `.sql` tạo mới khi `path_to_pasted` trống, trong `sql_temp_folder` |
| **Open for visibility** | Mở file bằng editor CLI / shell association — khác `open()` chỉ đọc bytes trong process |
| **paste-for-edit (type=1)** | Xuất definition ra `.sql` dạng ALTER để chỉnh; không clone sang project khác |
