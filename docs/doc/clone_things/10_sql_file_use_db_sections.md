# 10 — SQL file sections: `USE` App rồi Sys (Gemini implement)

> **Vai trò:** BA + Tester — spec để Gemini fix append `.sql`.  
> **Bối cảnh:** Dual lookup app/sys đã có (`cloned[].db` / `skipped_exists[].db`). File `.sql` hiện **chưa** `USE <database>` → user F5 nhầm object sys (vd. `syscheckfields`) vào DB app.  
> **Phạm vi sửa:** [`clone_things/file_manager.py`](../../../clone_things/file_manager.py), gọi từ [`clone_things/service.py`](../../../clone_things/service.py).  
> **Tham chiếu dual-DB:** [`../doc_fix/FIX-clone_things-dual-app-sys.md`](../doc_fix/FIX-clone_things-dual-app-sys.md)

---

## 1. Đánh giá cách user đề xuất

**Hợp lý và nên làm** — đúng thói quen SSMS/Azure Data Studio: một script, F5 chạy tuần tự, `USE` đổi context DB.

Chốt BA (làm rõ hơn wording “use db_app / use db_sys”):

| Ý user | Chốt implement |
|--------|----------------|
| `USE db_app` / `USE db_sys` | Dùng **tên catalog thật** từ connection **project_target** (Web.config), ví dụ `USE [Newpearl_R2SP223_A]` và `USE [Newpearl_R2SP223_S]` — **không** literal `db_app` |
| App objects phía trên | Mọi block clone có `db=app` nằm **sau** `USE [app_db]` và **trước** `USE [sys_db]` |
| Sys objects phía dưới | Mọi block clone có `db=sys` nằm **sau** `USE [sys_db]` |
| File cũ chưa có marker | Lần ghi đầu / trước append: đảm bảo có đủ 2 marker (thiếu thì chèn) |

Layout chuẩn file sau khi ensure markers:

```sql
USE [Newpearl_R2SP223_A]
GO

-- ===== APP objects =====
-- clone_things: dbo.zc_xxx | ... | from source
CREATE PROCEDURE ...
GO

USE [Newpearl_R2SP223_S]
GO

-- ===== SYS objects =====
-- clone_things: dbo.syscheckfields | ... | from source
CREATE TABLE ...
GO
```

Optional comment `-- ===== APP/SYS =====` — khuyến nghị có cho dễ nhìn; không bắt buộc AC.

---

## 2. Lấy tên database

Từ `target_dbs` đã load trong service (`load_project_db_connections`):

```text
app_db_name = target_dbs["app"]["database"]   # vd Newpearl_R2SP223_A
sys_db_name = target_dbs["sys"]["database"]   # vd Newpearl_R2SP223_S
```

- Thiếu `app` connection → không tạo section app; warning.
- Thiếu `sys` connection → không tạo section sys; object `db=sys` → warning + vẫn append cuối file (hoặc skip) — **BA chốt:** append cuối + `warnings` nếu không có sys catalog name.
- Luôn bracket identifier: `USE [{name}]` (tên DB có thể có ký tự đặc biệt hiếm).

Detect marker trong file (case-insensitive, cho phép khoảng trắng / ngoặc):

```text
^\s*USE\s+\[?{re.escape(app_db_name)}\]?\s*;?\s*$
^\s*USE\s+\[?{re.escape(sys_db_name)}\]?\s*;?\s*$
```

Không nhận diện bằng chuỗi cố định `db_app` / `db_sys`.

---

## 3. Thuật toán `ensure_use_db_sections(path, app_db, sys_db)`

Gọi **một lần** sau khi resolve output file + đã biết `target_dbs` (trước vòng queue), hoặc lazy ngay trước lần `append_script_block` đầu tiên.

```
content = read(file)  # có thể rỗng / có sẵn script cũ không USE

1. Nếu chưa có USE app_db:
   - Prepend:
       USE [app_db]
       GO
       <blank line>
     + content cũ (đẩy xuống)
   - Ghi lại file

2. content = read lại
   Nếu chưa có USE sys_db (và sys_db biết được):
   - Append cuối (sau content hiện tại):
       <blank line nếu cần>
       USE [sys_db]
       GO
       <blank line>

3. Kết quả: luôn có vùng APP (sau USE app) và vùng SYS (sau USE sys) để insert
```

**File đã có sẵn script user** (không marker): bước 1 đẩy toàn bộ content cũ xuống dưới `USE app` — coi như thuộc vùng APP (an toàn hơn đẩy vào SYS).

**File đã có USE app nhưng chưa USE sys:** chỉ thêm USE sys ở cuối.

**File đã đủ 2 USE:** không đụng.

Sau mỗi `USE ...` **bắt buộc** có dòng `GO` (batch SSMS).

---

## 4. Thuật toán `append_script_block(..., db: "app"|"sys", app_db, sys_db)`

Thay vì chỉ append cuối file:

```
ensure_use_db_sections(...)  # idempotent

content = read(file)
find index of USE sys_db line (và GO ngay sau nếu có)

nếu db == "app":
    insert_point = vị trí ngay TRƯỚC dòng USE [sys_db]
    (nếu không có USE sys → insert trước EOF, hoặc sau vùng app)
    chèn block (blank + header + script + GO) tại insert_point

nếu db == "sys":
    insert_point = sau marker USE sys (+ GO), tức CUỐI vùng sys / EOF
    chèn block tại cuối file (sau mọi sys đã có)
```

Block format giữ như hiện tại (header `-- clone_things: ...`, script, `GO`).

`not_found_both` comment tổng hợp: đặt **cuối file** (sau vùng sys), không xen giữa USE.

---

## 5. Wiring `service.py`

Khi gọi append:

```python
append_script_block(
    output_file,
    script,
    object_name,
    object_type,
    db=fetch_db,                    # "app" | "sys"
    app_db_name=...,                # từ target_dbs["app"]["database"]
    sys_db_name=...,                # từ target_dbs["sys"]["database"] nếu có
)
```

Truyền tên DB **target** (nơi user sẽ F5 deploy), không phải source.

---

## 6. Ví dụ end-to-end

**Given:** `path_to_pasted = E:\SQL Temp\newpearl_r2sp223 (6).sql` đang có vài proc app, chưa `USE`.

**Clone thêm:** `zc_bkctnb` (app) + `syscheckfields` (sys).

**Expected file:**

```sql
USE [Newpearl_R2SP223_A]
GO

-- (nội dung cũ nếu có, coi là app)

-- clone_things: dbo.zc_bkctnb | ... | from source
CREATE PROCEDURE [dbo].[zc_bkctnb] ...
GO

USE [Newpearl_R2SP223_S]
GO

-- clone_things: dbo.syscheckfields | USER_TABLE | from source
CREATE TABLE [dbo].[syscheckfields] ...
GO
```

User mở SSMS, chọn bất kỳ DB, F5 → tạo đúng trên `_A` rồi `_S`.

---

## 7. Test cases (Gemini viết unit)

| ID | Given | Action | Expected |
|----|-------|--------|----------|
| TC-USE-01 | File rỗng | ensure + append app | Đầu file `USE [AppDb]` + `GO`; block app; có `USE [SysDb]` phía dưới |
| TC-USE-02 | File rỗng | append sys | Block sys **sau** `USE [SysDb]` |
| TC-USE-03 | Đã có USE app+sys + 1 app block | append sys | Sys block sau USE sys; không đụng app section |
| TC-USE-04 | Đã có USE app+sys + 1 sys block | append app | App block **trước** USE sys |
| TC-USE-05 | File có script không USE | ensure | Prepend USE app; content cũ nằm vùng app; thêm USE sys cuối |
| TC-USE-06 | Detect `USE Newpearl_R2SP223_A` không bracket | Không chèn trùng USE app |
| TC-USE-07 | `db=sys` nhưng thiếu sys connection name | warning; không crash |

---

## 8. Anti-patterns

- Literal `USE db_app` / `USE db_sys` trong file output
- Dùng database name của **source** trong `USE` (phải là **target**)
- Append sys object vào cuối khi chưa có `USE sys` nằm giữa (user F5 vẫn đứng ở app)
- Bỏ `GO` sau `USE`
- Sửa/`normalize` lại toàn bộ file mỗi lần (chỉ ensure marker + insert đúng vùng)

---

## 9. Prompt Gemini (copy-paste)

```text
Implement SQL file USE App/Sys sectioning for clone_things per:
docs/doc/clone_things/10_sql_file_use_db_sections.md

Repo: E:\PythonProject\mcp_fbo

Requirements:
1. Real catalog names from target_dbs parsed["database"] — e.g. USE [Newpearl_R2SP223_A] / USE [Newpearl_R2SP223_S], never literal db_app/db_sys.
2. ensure_use_db_sections(file, app_db, sys_db): missing USE app → prepend + GO; missing USE sys → append at end + GO.
3. append_script_block(..., db, app_db_name, sys_db_name): app blocks insert BEFORE USE sys; sys blocks AFTER USE sys.
4. Wire from service.py using fetch_db and target database names.
5. Unit tests TC-USE-01..06 in tests/clone_things/; keep existing tests green.
6. Do not change dual-lookup / noise / partition $000000 logic except passing db names into append.

Return: files changed + pytest result.
```

---

## 10. Acceptance

- [ ] File clone có cả object app + sys → mở SSMS F5 không tạo `syscheckfields` nhầm vào DB app
- [ ] `syscheckfields` luôn nằm dưới `USE [*_S]`
- [ ] Object app luôn nằm giữa `USE [*_A]` và `USE [*_S]`
- [ ] Gọi clone nhiều lần cùng `path_to_pasted` không nhân đôi dòng `USE`
- [ ] `pytest tests/clone_things/` xanh
