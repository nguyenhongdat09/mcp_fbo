# FIX — `clone_things`: object sys (`syscheckfields`) bị nhét vào section App

> **Mục đích:** Doc gửi **Gemini fix** — sau feature USE App/Sys (spec [`10_sql_file_use_db_sections.md`](../clone_things/10_sql_file_use_db_sections.md)), build+test live vẫn ghi object DB **sys** vào vùng **App**.  
> **Ngày:** 2026-09-04  
> **Phạm vi code:** [`clone_things/file_manager.py`](../../../clone_things/file_manager.py) (`append_script_block`, `ensure_use_db_sections`), [`clone_things/service.py`](../../../clone_things/service.py) (truyền `db=fetch_db`), tests [`tests/clone_things/test_sql_file_use_db_sections.py`](../../../tests/clone_things/test_sql_file_use_db_sections.py)  
> **Không** đụng chrome_debug / dist trừ khi user yêu cầu rebuild sau fix.

---

## 1. Bằng chứng live (user build + test)

**File:** `e:\SQL Temp\newpearl_r2sp223 (6).sql`

| Vị trí | Nội dung |
|--------|----------|
| Dòng 1 | `USE [Newpearl_R2SP223_A]` |
| ~304, ~636 | `-- clone_things: dbo.syscheckfields \| USER_TABLE \| from source` + `CREATE TABLE syscheckfields` (**2 lần**, đều **trước** USE sys) |
| Dòng 769–770 (EOF) | `USE [Newpearl_R2SP223_S]` + `GO` — **không có block clone nào sau marker này** |

Kết luận quan sát:

1. Marker section **có** (App đầu file, Sys cuối file).
2. Section **Sys trống** — không object nào được chèn sau `USE [Newpearl_R2SP223_S]`.
3. `syscheckfields` là bảng **chỉ có trên DB sys** (đã probe trước đó: SRC SYS có, APP không, TGT SYS không → phải `cloned` với `db=sys`) nhưng nằm **giữa** `USE [..._A]` và `USE [..._S]` = vùng App.

User F5 cả file → `CREATE TABLE syscheckfields` chạy trên **Newpearl_R2SP223_A** → sai.

---

## 2. Spec đã chốt (không đổi BA)

Theo [`10_sql_file_use_db_sections.md`](../clone_things/10_sql_file_use_db_sections.md) §4:

```text
db == "app"  → insert NGAY TRƯỚC dòng USE [sys_db]
db == "sys"  → insert SAU marker USE [sys_db] (+ dòng GO ngay sau nếu có),
               tức trong vùng SYS / trước comment not_found (nếu có)
```

Layout kỳ vọng:

```sql
USE [Newpearl_R2SP223_A]
GO
-- ... app objects ...

USE [Newpearl_R2SP223_S]
GO
-- clone_things: dbo.syscheckfields | USER_TABLE | from source
CREATE TABLE ...
GO
```

---

## 3. Root cause cần Gemini xác nhận + sửa

### 3.1. Quan sát code hiện tại (`file_manager.append_script_block`)

Nhánh `is_sys` (**không** tìm `USE [sys_db]`):

- Chỉ insert trước `-- not found in 2 project:` **hoặc** append **EOF**.
- Unit TC-USE-02/03 có thể **pass** nếu `USE [sys]` đang nằm sát EOF (append EOF = “sau USE”).
- **Không đủ** so với spec: phải **neo** insert point = sau dòng `USE [sys_db]` (+ `GO` kế tiếp), không phụ thuộc “USE đang ở cuối file”.

Nhánh `app`:

- Đúng hướng: tìm `USE [sys_db]` rồi insert **trước** marker.

### 3.2. Vì sao file live khớp “mọi thứ là app”?

File `(6).sql`: **mọi** block clone (kể cả 2 lần `syscheckfields`) nằm trước `USE [..._S]`, vùng sys trống.

Điều này xảy ra khi **một hoặc nhiều** điều sau đúng:

| # | Giả thuyết | Cách verify |
|---|------------|-------------|
| A | `append_script_block(..., db=...)` nhận `"app"` (default) thay vì `"sys"` — `fetch_db`/`s_db` sai, hoặc service/build **không truyền** `db=` | JSON response `cloned[]` của `syscheckfields` phải có `"db": "sys"`. Nếu `"app"` hoặc thiếu field → bug service/lookup. |
| B | `db="sys"` nhưng nhánh sys **không** neo sau `USE [sys]`; đồng thời `ensure_use_db_sections` **append** `USE [sys]` **sau** content đã ghi → marker Sys bị đẩy xuống EOF, object sys bị kẹt vùng App | Reproduce: append sys trước khi có marker / ensure lại sau append; xem thứ tự. |
| C | File cũ clone trước feature USE; `ensure` chỉ **prepend** USE app + **append** USE sys cuối → content cũ (gồm syscheckfields) bị coi là App; lần clone **mới** vẫn ghi thêm syscheckfields vào App vì (A) hoặc (B) | So sánh: clone vào file **mới rỗng** vs append vào `(6).sql`. |

**Probe dual-DB trước đó:** `syscheckfields` chỉ tồn tại source **sys** → `find_object_on_side` + `fetch_db = s_db` **phải** ra `"sys"`. Nếu live JSON vẫn `"db":"app"` → ưu tiên sửa **service/lookup/wiring**, không chỉ file_manager.

---

## 4. Việc Gemini phải làm

### 4.1. `append_script_block` — chèn đúng section (bắt buộc)

Sau `ensure_use_db_sections(...)`:

1. Resolve `sys_match` = dòng `USE [sys_db_name]` (regex case-insensitive, bracket optional — giữ như ensure).
2. Tính `sys_body_start` = vị trí **sau** dòng USE đó; nếu dòng kế là `GO` thì sau dòng GO đó.
3. **`db == "sys"`** (so sánh `.lower()`):
   - Nếu có `sys_match`: insert block vào vùng sys = trước `-- not found in 2 project:` nếu comment nằm **sau** `sys_body_start`, else **EOF** (vẫn sau USE sys).
   - Nếu **không** có `sys_db_name` / không tạo được marker: giữ hành vi TC-USE-07 (append cuối + warning phía service).
4. **`db == "app"`** (và mọi giá trị khác `"sys"`):
   - Insert **ngay trước** `sys_match` nếu có; không thì trước not_found / EOF như hiện tại.
5. **Cấm** nhánh sys dùng chung logic “insert trước USE sys”.

Gợi ý pseudo:

```text
ensure_use_db_sections(...)
content = read()
sys_match = find USE sys line
sys_body_start = after USE [+ GO]
nf_match = find not_found (optional)

if db == sys:
    if sys_match:
        # insert at end of sys region: before nf if nf > sys_body_start else EOF
        insert_at = nf_match.start if nf_match and nf_match.start >= sys_body_start else len(content)
        # but never insert_at < sys_body_start
    else:
        append EOF
else:  # app
    insert_at = sys_match.start if sys_match else (nf or EOF)
```

### 4.2. `service.py` — wiring + assert mềm

- Giữ `db=fetch_db` với `fetch_db = s_db or "app"`.
- Khi `s_db == "sys"`: **bắt buộc** `append_script_block(..., db="sys", sys_db_name=target_sys_db)`.
- Nếu `fetch_db == "sys"` mà `target_sys_db` rỗng → đã có warning `sys_db_name_missing_for_append` (giữ).
- Optional (khuyến nghị): trong `cloned[]` log thêm `app_db`/`sys_db` target names đã dùng để user đối chiếu file.

### 4.3. Không tự “cứu” file `(6).sql` cũ trừ khi dễ

BA: fix cho lần clone **mới**. File đã bẩn có thể:

- User tạo file temp mới / xóa 2 block `syscheckfields` khỏi vùng App rồi clone lại, **hoặc**
- Optional helper: nếu Gemini muốn, khi append `db=sys` mà trong vùng **app** đã có header `-- clone_things: dbo.syscheckfields` trùng tên → không bắt buộc migrate; ưu tiên insert đúng vị trí cho block mới.

---

## 5. Acceptance criteria

| ID | Given | Then |
|----|--------|------|
| AC-1 | File rỗng + append `db=sys` + app/sys names NEWPEARL | `USE [..._A]` … `USE [..._S]` … **rồi** block `syscheckfields` |
| AC-2 | File đã có app block + 2 USE + append `db=sys` | `syscheckfields` **sau** `USE [..._S]`; app block **trước** USE sys |
| AC-3 | File đã có sys block + append `db=app` | app block **trước** `USE [..._S]`; sys block không đổi thứ tự tương đối |
| AC-4 | Live clone object chỉ có trên source sys (vd. `syscheckfields`) | JSON `cloned[].db == "sys"` **và** file: block sau `USE [target_sys_db]` |
| AC-5 | Repro path user: append vào file mới (không dùng `(6).sql` bẩn) với cùng project NEWPEARL target | Section Sys **không trống** nếu có ≥1 object `db=sys` |

---

## 6. Unit tests (bổ sung / siết)

File hiện có: `tests/clone_things/test_sql_file_use_db_sections.py` (TC-USE-01…07).

Thêm / sửa:

1. **TC-USE-08 (repro live shape):** content giống file user — `USE A`, vài app block, `syscheckfields` **sai chỗ** (trước USE S), `USE S` ở EOF không có body → `append_script_block(..., db="sys", ...)` → block **mới** phải xuất hiện **sau** `USE [..._S]` (không thêm vào trước marker).
2. **TC-USE-09:** `USE A` + app + `USE S` + **đã có** 1 sys block → append sys thứ 2 → cả hai sys sau USE S; không xen app.
3. **TC-USE-10 (service):** mock `find_object_on_side` source trả `db=sys` cho `syscheckfields` → assert file order `USE A` < app? < `USE S` < `syscheckfields` và `cloned[0]["db"]=="sys"`.

Chạy: `pytest tests/clone_things/test_sql_file_use_db_sections.py -q`

---

## 7. Cách user verify sau fix (không cần Gemini làm)

1. Rebuild MCP / chạy code mới.
2. Dùng **file `.sql` mới** (hoặc xóa sạch `(6)`), cùng `project_target` NEWPEARL `R2SP223`.
3. Clone seed có kéo `syscheckfields` (hoặc object=`syscheckfields`).
4. Mở file: `syscheckfields` phải **dưới** `USE [Newpearl_R2SP223_S]`.
5. JSON: `"db": "sys"` trên object đó.

---

## 8. Tham chiếu

- Spec USE sections: [`../clone_things/10_sql_file_use_db_sections.md`](../clone_things/10_sql_file_use_db_sections.md)
- Dual app/sys lookup: [`FIX-clone_things-dual-app-sys.md`](./FIX-clone_things-dual-app-sys.md)
- Code: `clone_things/file_manager.py` → `append_script_block` / `ensure_use_db_sections`
- Code: `clone_things/service.py` → `fetch_db = s_db or "app"` + gọi append
