# 01 — Overview: `compare_things`

## 1. Bối cảnh

Khi port / review giữa hai dự án FastBusiness (ví dụ AIH SP228 ↔ FAHASA FBISP24), agent cần biết:

- Proc/view/func **thiếu** hay **khác definition** (kèm **dòng nào–dòng nào**)
- Bảng **schema** lệch cột/type/PK/index/trigger (không phụ thuộc thứ tự cột)
- XML controller cùng relative path khác nội dung
- Thư mục `bin` trên UNC: file nào thiếu, DLL nào khác size/ngày

Đã có:

| Tool | Làm được | Chưa làm |
|------|----------|----------|
| `clone_things` | Mang thiếu / paste ALTER | Không so “đã có nhưng khác” chi tiết cho agent quyết |
| `query_database` | Đọc 1 object 1 project | Không so 2 project một call |
| `read_local_file` | Đọc 1 file | Không diff 2 path / 2 folder |

`compare_things` = **một call → JSON lệch/thiếu đủ để agent chọn bước tiếp** (`clone_things`, sửa tay, bỏ qua…).

## 2. Mục tiêu (Goals)

1. So **đa kind** trong một tool MCP: `sql` | `table` | `xml` | `file` | `folder`.
2. Trả JSON **agent-actionable**:
   - `summary` nhìn nhanh
   - `compared[]` chi tiết từng object/file
   - **Hunks có `line_start` / `line_end`** cho file/xml/proc (sau normalize)
   - `signals`, `schema_diff`, `meta_diff` tùy kind
   - `message` + `next_actions[]` gợi ý bước tiếp
3. Mặc định **không dump full** body proc/XML/DLL (`mode` kiểm soát độ dài).
4. File/XML: mặc định **bỏ qua khác CRLF/LF** (`ignore_line_endings=true`).
5. Table: so **ngữ nghĩa schema** — đảo thứ tự cột cùng type = identical.
6. Folder (vd `bin` UNC): inventory + meta; không hash hết DLL mặc định.
7. Skip object **encrypted**; báo `encrypted_skip`.
8. Package code tách file dưới `compare_things/` — dễ mở rộng.

## 3. Kind matrix

| `kind` | Nguồn | Ví dụ |
|--------|--------|--------|
| `sql` | Proc / func / view trên SQL Server (2 project Web.config) | `GetApprovalRole`, `vdmduyetuq` |
| `table` | Schema catalog (cột/type/PK/index/trigger) | `dmuqduyet` |
| `xml` | File cùng relative path dưới 2 project | `Dir/PUDelegationApproval.xml` |
| `file` | 2 absolute path file | hai `.sql` / `.xml` trên disk |
| `folder` | 2 absolute/UNC directory | `\\...\SP228\bin` vs `\\...\FBISP24\bin` |

View nằm trong `kind=sql` (không có `kind=view` riêng).

## 4. Phân biệt `clone_things`

| | `compare_things` | `clone_things` |
|--|------------------|----------------|
| Mục đích | Chỉ ra giống/lệch/thiếu | Mang thiếu / paste ALTER |
| Ghi file `.sql` | Không | Có (type=0/1) |
| Deploy DB | Không | type=0 theo config; type=1 không |
| Khi nào gọi trước | So 2 project / 2 bin / review lệch | Đã biết cần mang hoặc sửa definition |

**Habit agent (ghi sau khi code — `.cursorrules`):** cần biết lệch giữa 2 project → `compare_things` trước; rồi mới `clone_things` nếu thiếu hoặc cần paste sửa.

## 5. In scope / Out of scope

### In scope v1

- MCP tool `compare_things` + package `compare_things/`
- 5 kind trên + modes `summary` | `hunks` | `body`
- UNC path Windows cho folder/file
- Seed keyword scan (`kind=sql`)
- Tests dưới `tests/compare_things/`

### Out of scope v1

| Hạng mục | Ghi chú |
|----------|---------|
| So data rows bảng | Chỉ schema |
| Auto ALTER / deploy / copy file sang folder kia | Agent/user quyết |
| Quét toàn Controllers tree không chỉ định object (xml bulk recursive) | `kind=xml` theo list relative path |
| UI VS Code `code --diff` | Tool trả JSON |
| Tool tên `compare_files` riêng | Logic ∈ `kind=file` |
| Hash bắt buộc mọi DLL trong `bin` | Chỉ khi `compare_content=true` + dưới `hash_max_bytes` |
| FK / check / default constraint chi tiết | Có thể phase sau; v1: cột+type+PK+index+trigger |
| Decrypt object / file mã hóa | `encrypted_skip` / báo lỗi đọc |

## 6. Ví dụ end-to-end (tóm tắt)

### 6.1. Hai file chỉ khác CRLF

→ `identical_content=true`, `only_line_ending_diff=true`, `next_actions: ["ignore_line_ending_only"]`.

### 6.2. Hai thư mục bin UNC

`folder_a` = `\\172.168.5.14\CustomerPro\FBO\AIH\SP228\bin`  
`folder_b` = `\\172.168.5.14\CustomerPro\FBI\FAHASAKHANHHOA\FBISP24\bin`

→ `missing_on_b` / `missing_on_a` + `different_meta` (size/created/modified) + message rõ.

### 6.3. SQL seed FAHASA vs AIH

`kind=sql`, `seed=dmuqduyet,vdmduyetuq` → proc Authorize/MailList/Role `different` nếu target còn đọc `dmduyet`, kèm **hunk line ranges** + `signals`.

### 6.4. Table cột đảo thứ tự

Source `K int, L int` vs target `L int, K int` → **identical**.

Chi tiết JSON: [04_json_response.md](./04_json_response.md). Flow từng kind: `05`–`09`.
