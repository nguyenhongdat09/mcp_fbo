# 08 — `kind=xml`

## 1. Mục tiêu

So file XML (thường controller) **cùng relative path** giữa 2 project FastBusiness → tái dụng engine `file_compare` / line hunks.

## 2. Input

| Param | Ghi chú |
|-------|---------|
| `project_source`, `project_target` | Abs project root **hoặc** path file trong project (giống clone_things) |
| `object` | Relative path(s) tính từ **Controllers/**: `Dir/Foo.xml`, `Grid/Bar.xml`, `Filter/Baz.xml` — list `,` / `;` |
| `ignore_line_endings`, `ignore_whitespace`, `mode`, `max_diff_lines`, `context_lines` | Như `kind=file` — truyền xuống shared diff |

Không dùng `schema` cho xml.

## 3. Resolve Controllers root (bắt buộc chốt)

### 3.1. Reuse helper hiện có — CẤM tự invent scan mơ hồ

Thứ tự resolve cho **mỗi** `project_source` / `project_target`:

1. **Project root** = `find_connect_by_path.path_resolver.get_project_root_from_path(project_*)`  
   (cắt tại `App_Data` hoặc đi lên tới có `Web.config` — cùng clone_things).
2. **Controllers dir** = `xml_fbograph.utils.path_helper.resolve_controllers_dir(project_root)`  
   Logic đã có: walk lên tìm `App_Data/Controllers`, hoặc `{root}/App_Data/Controllers` nếu là dir.

Nếu bước 1 hoặc 2 fail → `error_code=invalid_project_source` / `invalid_project_target` (hoặc `controllers_not_found`) + message rõ.

### 3.2. Ghép absolute path từng relative

```text
relative_norm = object.strip().lstrip("/\\").replace("\\", "/")
# CẤM: ".." trong bất kỳ segment → error_code=invalid_object (path traversal)

# Nếu relative đã bắt đầu bằng App_Data/Controllers/ → cắt prefix đó còn phần sau Controllers/
# Nếu relative đã bắt đầu bằng Controllers/ → cắt Controllers/

abs = ControllersDir / relative_norm   # Path join, giữ case filesystem
```

Ví dụ:

| `object` | Controllers | Abs |
|----------|-------------|-----|
| `Dir/PUDelegationApproval.xml` | `E:\FBO\AIH\SP228\App_Data\Controllers` | `...\Controllers\Dir\PUDelegationApproval.xml` |
| `App_Data/Controllers/Dir/X.xml` | (cùng) | `...\Controllers\Dir\X.xml` (sau normalize) |

### 3.3. Nhiều thư mục Controllers?

FBO chuẩn: **một** `App_Data/Controllers` per project web.  
`resolve_controllers_dir` trả **một** path (walk lên gần nhất / join chuẩn).

- **Không** merge nhiều Controllers trees trong v1.
- Nếu structure lệch (Controllers ngoài App_Data): helper có thể trả `None` → lỗi rõ, không đoán folder khác.
- Application phụ / multi-app: agent phải truyền `project_*` đúng root app cần so (không so cả solution).

### 3.4. Pseudo-code

```python
from find_connect_by_path.path_resolver import get_project_root_from_path
from xml_fbograph.utils.path_helper import resolve_controllers_dir

def resolve_xml_abs(project_path: str, relative: str) -> Path:
    root = get_project_root_from_path(project_path)
    if not root:
        raise CompareError("invalid_project_source", ...)
    controllers = resolve_controllers_dir(root)
    if not controllers:
        raise CompareError("controllers_not_found", ...)
    rel = normalize_relative(relative)  # no ..
    return Path(controllers) / rel
```

## 4. Pipeline

1. Parse list relative từ `object` (bắt buộc không rỗng).
2. Với mỗi relative: `path_source = resolve_xml_abs(project_source, rel)`, `path_target = resolve_xml_abs(project_target, rel)`.
3. Missing một bên → `missing_on_target` / `missing_on_source`; `next_actions` gợi ý copy XML thủ công (tool **không** copy).
4. Cả hai có → gọi **cùng hàm** diff với `file_compare` (truyền `context_lines`, `ignore_line_endings`, `mode`, …), gắn `relative_path`, `path_source`, `path_target`.
5. `.f` / không đọc được text → `status=error` hoặc skip với message; **không decrypt**.

## 5. Output

Như file + fields trong [04](./04_json_response.md) §5.5. Hunks dùng `a_`/`b_` (a=source path, b=target path).

## 6. Edge cases

| Case | Kỳ vọng |
|------|---------|
| Controllers không tồn tại | fail project với `controllers_not_found` |
| Relative có `..` | `invalid_object` |
| File chỉ có ở source | `missing_on_target` |
| Chỉ khác CRLF | như file: `only_line_ending_diff` |

## 7. CẤM

- Recursive quét cả Controllers khi `object` rỗng
- Tự viết walk tìm Controllers khác với helper đã có (trừ khi helper thiếu — khi đó mở rộng helper, không fork logic)
- Flat/resolve entity DTD đầy đủ — **v1 so raw file text**; phase 2 có thể so flat
- Dùng `schema` param cho xml
