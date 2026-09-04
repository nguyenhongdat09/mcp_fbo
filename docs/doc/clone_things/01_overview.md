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

1. Clone **toàn bộ script** object SQL thiếu ở project đích (lấy từ project nguồn) vào một file `.sql`.
2. Tự **phân loại** object (table / proc / func / view) qua catalog SQL Server.
3. Tự **mở rộng dependency** với proc/func (và seed từ XML) bằng summary hiện có.
4. **Target-first:** chỉ clone object **chưa có** ở DB target.
5. Báo rõ object **không có ở cả hai** project.
6. Trả JSON gọn cho Agent; đồng thời user **nhìn thấy** file `.sql` (mở editor).

## 3. Không làm gì (Out of scope — v1)

| Hạng mục | Ghi chú |
|----------|---------|
| `type != 0` (clone file XML / copy Controllers) | Để dành phase sau; param `type` vẫn có, default `0` |
| Deploy / EXECUTE script lên DB target | Chỉ **ghi file** — không chạy DDL trên target |
| Sửa / ALTER object đã có ở target | Object đã có → `skipped_exists`, không overwrite |
| Decrypt / đọc `.f` mã hóa | Giống summary_xml: không hỗ trợ |
| Clone data (INSERT rows) | Chỉ schema / definition |
| UI VS Code extension command | Parity UX NewSqlTemp ở phía MCP Python; không bắt buộc sửa extension |

## 4. In scope — v1

- MCP tool mới `clone_things`
- Input: `type`, `object`, `project_source`, `project_target`, `path_to_pasted`
- Config: `clone_things.sql_temp_folder`, `clone_things.open_editor_cmd`
- Seed từ tên SQL **hoặc** path XML (summary)
- Queue đệ quy dependency
- Append script + blank line separator
- Open file cho user
- JSON response đầy đủ (`cloned`, `skipped_exists`, `not_found_both`, …)

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
