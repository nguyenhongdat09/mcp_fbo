# GEMINI / Agent — (1) Bỏ Shell cho thao tác FBO

> **File độc lập** — **không** implement MCP tool mới.  
> Đây là **quy tắc agent + skill** (+ cách dùng tool MCP **đã có**).  
> Gửi Gemini / Cursor để cập nhật skill / `.cursorrules` / hướng dẫn agent — **không** viết code tool mới trong `mcp_fbo` cho mục (1).

---

## Kết luận một câu

**(1) Không tạo MCP tool mới.**  
Agent **cấm** dùng Shell Cursor cho list/copy/đọc FBO trên UNC.  
Dùng MCP sẵn: `compare_things` / `read_local_file` / `query_database` (+ `clone_things` type=0|1; sau này type=3 cho **copy** file).

---

## Vấn đề

Trên share UNC (`\\server\CustomerPro\FBO\...`), Shell Cursor (`Get-ChildItem`, `Copy-Item`, `Select-String`…) thường:

- Không có exit status / không trả output
- Agent “mù” → đoán sai hoặc bỏ dở

→ Thao tác FBO **không** đi qua Shell.

---

## Map việc → tool (không tool mới)

| Việc agent cần | Tool MCP | Ghi chú |
|----------------|----------|---------|
| Đọc XML/aspx/js/config/html | `read_local_file` | `reference_file` abs; `read_option` 1/2/3 |
| So thiếu/lệch file giữa 2 project | `compare_things` `kind=folder` hoặc `kind=file` | `include_glob` / `seed` hẹp — **không** hash cả `bin/` mặc định |
| SQL / schema / exec thử ngắn | `query_database` | Không `mode=full` dump proc dài → dùng `clone_things` type=1 |
| Lấy/sửa proc | `clone_things` type=1 | |
| Mang SQL thiếu | `clone_things` type=0 | |
| **Copy** file A→B (khi đã có type=3) | `clone_things` type=3 | Spec riêng: `GEMINI-clone_things-type3-file-clone.md`. Trước khi type=3 ship: **báo user copy tay**, vẫn **cấm** Shell |

---

## Quy tắc bắt buộc cho agent (đưa vào skill)

```
1. CẤM Shell cho: list bin/, copy DLL/aspx/js, đọc Web.config/Controllers trên UNC FBO.
2. Đọc file → read_local_file.
3. So 2 project thiếu file → compare_things (folder/file), không Get-ChildItem.
4. SQL → query_database (ngắn) hoặc clone_things type=0|1.
5. Copy file giữa 2 project:
   - Nếu MCP đã có clone_things type=3 → dùng type=3 (dry-run rồi execute).
   - Nếu chưa có type=3 → liệt kê path cho user copy tay; CẤM Shell Copy-Item.
6. Shell chỉ việc NGOÀI FBO (git local máy user, npm, …) khi path không phải UNC project FBO.
```

---

## Ví dụ đúng / sai

### Sai

```text
Shell: Get-ChildItem \\172.168.5.14\...\bin\*Mail*
Shell: Copy-Item HungThinh\bin\fsdMail.dll AIH\bin\
```

### Đúng

```text
compare_things(kind=folder, project_source=HungThinh, project_target=AIH,
  include_glob=*.dll, seed=Mail)     # hoặc seed/file hẹp

read_local_file(file_path=Main/Uploads/AjaxWeb.aspx, reference_file=...Dir/...)

# Sau khi type=3 ship:
clone_things(type=3, object=mail, project_source=..., project_target=..., execute=false)
```

---

## Phạm vi Gemini cho file này

| Làm | Không làm |
|-----|-----------|
| Cập nhật skill `fbo-clone-things` / rule agent: mục “CẤM Shell FBO” + bảng map tool | **Không** tạo MCP tool mới tên `no_shell` / `list_files` |
| Có thể thêm đoạn vào skill `fbo-send-mail-customize` (chỉ reminder cấm Shell — skill mail **không** phải spec MCP) | **Không** đổi `compare_things` / `read_local_file` API trừ khi BA yêu cầu riêng |
| Nhắc: copy file = đợi type=3 hoặc user tay | **Không** implement type=3 trong file này (xem file GEMINI type=3) |

### Đường dẫn skill / rules cần cập nhật (máy dự án)

Cập nhật **các bản đang dùng** (đồng bộ nội dung “CẤM Shell FBO”):

| Vị trí | Ghi chú |
|--------|---------|
| `C:\Users\Windows 10\.cursor\skills\fbo-clone-things\SKILL.md` | Skill Cursor (agent Cursor) |
| `C:\Users\Windows 10\.gemini\config\skills\fbo-clone-things\SKILL.md` | Skill Gemini trên máy này |
| `E:\PythonProject\mcp_fbo\.cursorrules` | Rules root repo MCP |

Doc cũ chỉ ghi `~/.cursor/skills/...` — **không đủ**; trên Windows path thực tế như bảng trên.  
Khi sửa skill: ưu tiên sửa bản Cursor; nếu dùng Gemini skill riêng thì **copy cùng nội dung** sang `.gemini\config\skills\...`.

---

## Quan hệ với type=3

| Ý | Tài liệu |
|---|----------|
| **(1) Bỏ Shell** — policy, không tool mới | **File này** |
| **(2) Copy file** — `clone_things` type=3 | `docs/doc/gemini/GEMINI-clone_things-type3-file-clone.md` |

(1) áp dụng **ngay** (kể cả trước khi type=3 ship).  
(2) cần Gemini **code MCP**.

---

## Prompt Gemini (skill / rules only)

```text
Cập nhật skill / hướng dẫn agent theo file:

E:\PythonProject\mcp_fbo\docs\doc\gemini\GEMINI-agent-no-shell-fbo.md

Yêu cầu:
1. KHÔNG implement MCP tool mới.
2. Thêm quy tắc: cấm Shell cho list/copy/đọc FBO trên UNC.
3. Map: read_local_file / compare_things / query_database / clone_things type=0|1.
4. Copy file: khi chưa có type=3 → user copy tay; khi có type=3 → dùng type=3.
5. Cập nhật skill tại (đồng bộ nội dung nếu cả hai tồn tại):
   - C:\Users\Windows 10\.cursor\skills\fbo-clone-things\SKILL.md
   - C:\Users\Windows 10\.gemini\config\skills\fbo-clone-things\SKILL.md
   và/hoặc E:\PythonProject\mcp_fbo\.cursorrules

Không sửa code mcp_fbo cho mục (1).
```
