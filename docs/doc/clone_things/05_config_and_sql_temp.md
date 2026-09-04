# 05 — Config & SQL Temp & Open Editor

## 1. `config.yaml`

Thêm block (implement phase — doc mô tả contract):

```yaml
# Clone SQL objects giữa 2 project (MCP tool clone_things)
clone_things:
  # Absolute path thư mục tạo file .sql khi path_to_pasted rỗng
  # Parity với VS Code setting: fbo-autocomplete.sqlTempFolder
  sql_temp_folder: ""

  # Cách mở file sau khi ghi: auto | cursor | code | os | none
  # auto = thử cursor → code → os.startfile
  open_editor_cmd: "auto"

  # Giới hạn an toàn
  max_objects: 50

  # false = chỉ ghi file, không mở UI (hữu ích CI)
  open_file: true
```

Loader: reuse cơ chế đọc `config.yaml` hiện có của MCP (không hardcode path tuyệt đối trong code).

## 2. Parity với extension `fboFile.NewSqlTemp`

Tham chiếu:

- Command: `fboFile.NewSqlTemp` — [`e:\CustomizeExtension\fbo-autocomplete\src\TreeFile\ContextMenu.js`](e:\CustomizeExtension\fbo-autocomplete\src\TreeFile\ContextMenu.js)
- Helper: `createSqlTempFile` — [`e:\CustomizeExtension\fbo-autocomplete\src\Utils\sqlTempFile.js`](e:\CustomizeExtension\fbo-autocomplete\src\Utils\sqlTempFile.js)
- Setting: `fbo-autocomplete.sqlTempFolder`

### 2.1. Hành vi khớp bắt buộc

| Hạng mục | Extension | MCP `clone_things` |
|----------|-----------|---------------------|
| Folder trống | Error message cấu hình Settings | `error_code=sql_temp_folder_not_configured` |
| Folder không tồn tại | Error | Cùng lỗi |
| Tên file | normalize + `(2)`, `(3)`… | Giống thuật toán JS |
| Mở file | `openTextDocument` + `showTextDocument` | CLI / `os.startfile` (xem §4) |
| Không tạo ngầm | User thấy file | User thấy file (hoặc warning nếu open fail) |

### 2.2. Thuật toán đặt tên (port từ JS)

```
# Parity NewSqlTemp: tên = group/project label (2 segment cuối project root), KHÔNG stem XML/object
base = project_source_label   # vd. VLOTUS/SP228 → vlotus_sp228
if base endswith .sql: strip
base = lower(base)
base = replace spaces and hyphens with _
base = strip leading/trailing _
if empty: base = "temp"
filename = base + ".sql"
while exists: base + " (" + counter + ").sql", counter++
```

Ví dụ: `project_source=...\VLOTUS\SP228\...\zcbkctnb.xml` → `vlotus_sp228.sql` (hoặc `vlotus_sp228 (4).sql` nếu đã có 1–3).

## 3. Quan hệ `sql_temp_folder` và `project_target`

**BA chốt v1:**

- `sql_temp_folder` là **absolute path** độc lập (giống extension), **không** tự ghép dưới `project_target`.
- `project_target` chỉ dùng resolve **DB connection** đích + ngữ cảnh clone.
- User muốn file nằm trong project đích → truyền `path_to_pasted` trỏ sẵn vào `...\Scripts\xxx.sql`, hoặc cấu hình `sql_temp_folder` trỏ vào folder trong project đó.

## 4. Mở file bằng Python (BA chốt — trả lời “Python có mở file được không?”)

### 4.1. Hai nghĩa của “mở file”

| API | Ý nghĩa | Đủ cho UX? |
|-----|---------|------------|
| `open(path, "a", encoding="utf-8")` | Đọc/ghi nội dung trong process MCP | **Không** — user không thấy tab |
| Mở bằng editor / shell association | Hiển thị file trên UI | **Có** — bắt buộc v1 |

### 4.2. Thuật toán `open_file_for_user(path)`

```
if config.open_file is false OR open_editor_cmd == "none":
    return ok_skipped

cmd = config.open_editor_cmd  # auto|cursor|code|os

def resolve_editor_exe(kind):  # kind = cursor|code
    # 1) which/PATH
    # 2) Windows default install paths nếu PATH thiếu:
    #    %LOCALAPPDATA%\Programs\cursor\resources\app\bin\cursor.cmd
    #    %LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd
    ...

def try_cli(exe, file_path):
    # NON-BLOCKING — cấm subprocess.run(..., check=True) block MCP
    subprocess.Popen([exe, file_path], shell=False, ...)  # hoặc Popen với .cmd
    return True  # spawned; lỗi FileNotFoundError → False

if cmd == "cursor":
    ok = try_cli(resolve_editor_exe("cursor"), path)
elif cmd == "code":
    ok = try_cli(resolve_editor_exe("code"), path)
elif cmd == "os":
    ok = False  # fall through to startfile
elif cmd == "auto":
    ok = try_cli(resolve_editor_exe("cursor"), path) or try_cli(resolve_editor_exe("code"), path)
else:
    ok = False

if not ok:
    try:
        os.startfile(path)  # Windows — có thể mở SSMS nếu association .sql
        ok = True
    except Exception as e:
        warnings.append(f"open_file_failed: {e}")
        return fail_soft

return ok
```

### 4.3. Lưu ý Windows / Cursor

- Nhiều máy **không** thêm `cursor` vào PATH khi cài → phải resolve path mặc định (§4.2) trước khi báo fail.
- Dùng `subprocess.Popen` (async); **không** `run(..., check=True)` làm block MCP request.
- `os.startfile` có thể mở SSMS (nặng) tùy file association — chấp nhận nếu CLI thiếu; ưu tiên Cursor/Code trước.
- **Không** phụ thuộc VS Code Extension Host API từ process MCP.

### 4.4. Khi open fail

- Clone + ghi file vẫn `success: true`.
- `warnings` có `open_file_failed: ...`.
- `meta.open_file_ok = false`.
- Agent có thể nhắc user mở thủ công `path_to_pasted`.

## 5. Encoding & newline

- File UTF-8 (no BOM trừ khi file sẵn có BOM — khi append giữ nguyên encoding detect đơn giản).
- Newline: ưu tiên `\n` hoặc giữ style file hiện có nếu detect được `\r\n`.

## 6. Nội dung header session (optional)

Khi tạo file mới, dòng đầu có thể:

```sql
-- clone_things session
-- source: E:\FBO\SP2263
-- target: E:\FBO\CUSTOMER_A
-- seed: zc_example_report
-- generated: 2026-09-04T08:55:00
```

Sau đó các block object. Không bắt buộc AC nếu implementer muốn tối giản — khuyến nghị có để user hiểu nguồn.
