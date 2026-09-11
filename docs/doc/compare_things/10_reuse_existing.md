# 10 — Reuse existing / Anti-patterns

## 1. Map sang code hiện có

| Nhu cầu | Dùng gì | Không làm |
|---------|---------|-----------|
| Resolve Controllers / project root (xml) | `find_connect_by_path.path_resolver.get_project_root_from_path` + `xml_fbograph.utils.path_helper.resolve_controllers_dir` | Tự walk invent Controllers |
| Seed scan sql | `sys.sql_modules` LIKE theo 07 §3.3 | SELECT full definition mọi candidate |
| Object encrypted? | `is_object_encrypted` | Đoán bằng tên |
| Lấy definition proc/func/view | Cùng hướng fetch definition như `clone_things` type0/type1 | Agent `query_database` mode=full dump vào JSON compare |
| Text diff | stdlib `difflib` | Thêm PyPI `diff-match-patch` (không cần v1) |
| Hash / path | `hashlib`, `pathlib`, `os.scandir` | Shell `fc` / `diff.exe` bắt buộc |
| JSON MCP | `formatter.py` như `clone_things.formatter` | Print debug |

Wrapper: `compare_things/db_access.py` import từ clone_things — **một chỗ** để sau này đổi API clone không sửa 5 file.

## 2. Quan hệ với `clone_things`

- `compare_things` **không** gọi `clone_things()` nội bộ để side-effect ghi file.
- JSON chỉ **gợi ý** `next_actions` chứa tên hành động agent sẽ gọi tool khác.
- Không share state file sql temp.

## 3. Anti-patterns (CẤM)

1. Một file `service.py` 2000 dòng chứa mọi kind.
2. Tool MCP tên `compare_files` song song — logic file ∈ `kind=file`.
3. `status=different` không có hunks/schema_diff/meta_diff.
4. Dump full proc/XML body vào response mặc định.
5. So bảng bằng string `CREATE TABLE` (false different vì thứ tự cột).
6. Hash toàn bộ `bin` mặc định trên UNC.
7. Auto ALTER / copy DLL / deploy.
8. Ignore encrypted rồi crash khi đọc definition.
9. Relative project path mơ hồ không document.
10. Import vòng: `clone_things` import `compare_things`.

## 4. Config

v1: không bắt buộc block mới trong `config.yaml`. Optional sau:

```yaml
compare_things:
  max_file_bytes: 10485760
  default_max_objects_folder: 200
```

Nếu chưa có config: hard-default trong code đúng API doc `02`.

## 5. Logging

Dùng logger giống package khác; không log full definition; có thể log counts + object names.
