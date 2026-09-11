# 04 — JSON Response Schema

## 1. Success response

Top-level object (tool trả về JSON string):

| Field | Type | Required | Mô tả |
|-------|------|----------|--------|
| `success` | `bool` | có | `true` khi hoàn tất pipeline (kể cả khi có not_found / open fail) |
| `spec_version` | `string` | có | `"1.0"` |
| `type` | `int` | có | Echo input type (`0` hoặc `1`) |
| `object` | `string` | có | Echo input object |
| `mode_seed` | `string` | có | `"sql_name"` \| `"xml"` |
| `project_source` | `string` | có | Absolute path đã normalize |
| `project_target` | `string` | có | Absolute path đã normalize |
| `path_to_pasted` | `string` | có | Absolute path file `.sql` đã ghi |
| `cloned` | `array` | có | Object lấy từ source và đã append |
| `skipped_exists` | `array` | có | Object đã có ở target (BA: luôn liệt kê, không im lặng) |
| `skipped_noise` | `array[string]` | có | Tên object hệ thống / catalog SQL Server (`tempdb`, `systypes`…) đã tự động lọc bỏ, không ghi vào `not_found_both` |
| `not_found_both` | `array` | có | Tên object không có ở target **và** source |
| `warnings` | `array[string]` | có | Cảnh báo không làm fail job |
| `meta` | `object` | khuyến nghị | Thống kê chạy |

### 1.1. Phần tử `cloned[]`

| Field | Type | Required | Mô tả |
|-------|------|----------|--------|
| `name` | `string` | có | Tên object (có thể kèm schema) |
| `object_type` | `string` | có | `USER_TABLE` \| `PROCEDURE` \| `FUNCTION` \| `VIEW` \| … |
| `from` | `string` | có | Luôn `"source"` trong v1 |
| `db` | `string` | có | Loại DB nguồn đã fetch (`"app"` \| `"sys"`) |
| `chars` | `int` | optional | Độ dài script đã ghi |
| `line_count` | `int` | optional | Số dòng script |

### 1.2. Phần tử `skipped_exists[]`

| Field | Type | Required | Mô tả |
|-------|------|----------|--------|
| `name` | `string` | có | Tên object |
| `object_type` | `string` | khuyến nghị | Nếu biết từ catalog target |
| `where` | `string` | có | Luôn `"target"` |
| `db` | `string` | có | Loại DB đích phát hiện tồn tại (`"app"` \| `"sys"`) |

### 1.3. `not_found_both`

- **Form bắt buộc:** `string[]` — danh sách tên, ví dụ `["funcA", "funcB"]`.
- Agent có thể format câu: `not found in 2 project: funcA, funcB`.
- File `.sql` cuối cùng có đúng một dòng comment tổng hợp (xem `03`).

### 1.4. `meta` (khuyến nghị)

```json
{
  "processed_count": 12,
  "queue_remaining": 0,
  "truncated_max_objects": false,
  "open_file_attempted": true,
  "open_file_ok": true,
  "db_lookup_order": ["app", "sys"],
  "elapsed_ms": 1840
}
```

## 2. Sample — happy path

```json
{
  "success": true,
  "spec_version": "1.0",
  "type": 0,
  "object": "zc_example_report",
  "mode_seed": "sql_name",
  "project_source": "E:\\FBO\\SP2263",
  "project_target": "E:\\FBO\\CUSTOMER_A",
  "path_to_pasted": "E:\\SqlTemp\\zc_example_report.sql",
  "cloned": [
    {
      "name": "dbo.zc_example_report",
      "object_type": "PROCEDURE",
      "from": "source",
      "db": "app",
      "chars": 12040,
      "line_count": 280
    },
    {
      "name": "dbo.zc_helper",
      "object_type": "FUNCTION",
      "from": "source",
      "db": "app",
      "chars": 2100,
      "line_count": 60
    }
  ],
  "skipped_exists": [
    {
      "name": "dbo.dmkh",
      "object_type": "USER_TABLE",
      "where": "target",
      "db": "app"
    }
  ],
  "skipped_noise": [],
  "not_found_both": [],
  "warnings": [],
  "meta": {
    "processed_count": 3,
    "queue_remaining": 0,
    "truncated_max_objects": false,
    "open_file_attempted": true,
    "open_file_ok": true,
    "db_lookup_order": ["app", "sys"],
    "elapsed_ms": 2100
  }
}
```

## 3. Sample — missing + open warning

```json
{
  "success": true,
  "spec_version": "1.0",
  "type": 0,
  "object": "zc_root",
  "mode_seed": "sql_name",
  "project_source": "E:\\FBO\\SP2263",
  "project_target": "E:\\FBO\\CUSTOMER_A",
  "path_to_pasted": "E:\\SqlTemp\\zc_root.sql",
  "cloned": [
    {
      "name": "dbo.zc_root",
      "object_type": "PROCEDURE",
      "from": "source",
      "db": "app"
    }
  ],
  "skipped_exists": [],
  "skipped_noise": ["dbo.tempdb"],
  "not_found_both": ["dbo.funcGhost", "dbo.procGhost"],
  "warnings": [
    "open_file_failed: [WinError 2] cursor not found; startfile also failed: ..."
  ],
  "meta": {
    "processed_count": 3,
    "open_file_attempted": true,
    "open_file_ok": false,
    "db_lookup_order": ["app", "sys"]
  }
}
```

## 4. Sample — XML seed

```json
{
  "success": true,
  "spec_version": "1.0",
  "type": 0,
  "object": "E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml",
  "mode_seed": "xml",
  "project_source": "E:\\FBO\\SP2263",
  "project_target": "E:\\FBO\\CUSTOMER_A",
  "path_to_pasted": "E:\\SqlTemp\\svtran.sql",
  "cloned": [],
  "skipped_exists": [
    {"name": "dbo.dmkh", "object_type": "USER_TABLE", "where": "target", "db": "app"},
    {"name": "dbo.dmtk", "object_type": "USER_TABLE", "where": "target", "db": "app"},
    {"name": "dbo.userinfo2", "object_type": "USER_TABLE", "where": "target", "db": "sys"}
  ],
  "skipped_noise": ["dbo.tempdb", "dbo.systypes"],
  "not_found_both": [],
  "warnings": [],
  "meta": {
    "processed_count": 15,
    "mode_seed_count": 15,
    "db_lookup_order": ["app", "sys"]
  }
}
```

## 5. Error response (fail-fast)

Khi validation / resolve connection / sql_temp_folder fail **trước** khi clone:

```json
{
  "success": false,
  "spec_version": "1.0",
  "error_code": "sql_temp_folder_not_configured",
  "message": "Chưa cấu hình clone_things.sql_temp_folder hoặc thư mục không tồn tại.",
  "path_to_pasted": null,
  "cloned": [],
  "skipped_exists": [],
  "skipped_noise": [],
  "not_found_both": [],
  "warnings": []
}
```

Hoặc thống nhất format string `[ERROR] clone_things ...` giống tool khác — **ưu tiên JSON** cho tool mới để Agent parse ổn định. Nếu bắt buộc string wrapper:

```
[ERROR] clone_things
{"success": false, "error_code": "...", ...}
```

## 6. Quy tắc Agent đọc kết quả (type=0)

1. Luôn đọc `path_to_pasted` — file đã mở / cần mở.
2. `cloned` = object cần review trước khi deploy.
3. `skipped_exists` = không thiếu ở target; không paste lại.
4. `not_found_both` = cần tìm thủ công / dự án thứ 3 / tên sai.
5. `warnings` không được bỏ qua nếu liên quan truncate / open fail.

## 7. Response type=1 (paste-for-edit)

Schema đầy đủ + sample: **[11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md) §8**.

Tóm tắt field bắt buộc:

| Field | Type | Mô tả |
|-------|------|--------|
| `type` | `1` | |
| `mode` | `"paste_for_edit"` | |
| `pasted[]` | array | `name`, `object_type`, `db`, **`line_start`**, **`line_end`**, `script_style` |
| `skipped_already_in_file[]` | array | Object đã có CREATE/ALTER trong file |
| `not_found_source` | `string[]` | Không có trên source |
| `agent_message` | `string` | Hướng dẫn agent sửa trong file theo line range |
| `meta.execute_clone` | `false` | Force |

Agent đọc type=1:

1. Mở `path_to_pasted`, sửa trong `pasted[].line_start`–`line_end`.
2. Không dump full SQL ra chat; không gọi lại paste cùng object nếu đã skip/pasted.
3. User tự F5.

## 8. Không được trả

- Full SQL script trong JSON (tránh phình token) — script chỉ nằm trong file.
- Password / connection string.
- Toàn bộ summary AST lồng nhau per object (chỉ tên + type trong arrays).
