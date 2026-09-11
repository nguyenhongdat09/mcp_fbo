# FIX — `compare_things`: làm sạch `refs` SQL (false positive + `refs_match_body_diff`)

> **File ĐỘC LẬP cho Gemini fix**  
> **Ngày:** 2026-09-11  
> **Phạm vi:** [`compare_things/sql_fingerprint.py`](../../../compare_things/sql_fingerprint.py) (`extract_sql_refs`, `extract_sql_signals`), tests [`tests/compare_things/`](../../../tests/compare_things/)  
> **Sau khi:** [`FIX-compare_things-signals-pk-message.md`](./FIX-compare_things-signals-pk-message.md) đã OK trên live — còn nhiễu refs.  
> **Repro live:** FAHASA `FBISP24` vs AIH `SP228`, object `FastBusiness$App$GetApprovalMailList` / `ff_PRAuthorize`.

---

## 0. Prompt Gemini (copy-paste)

```text
Fix compare_things theo docs/doc/doc_fix/FIX-compare_things-sql-refs-noise.md

P0:
1) extract_sql_refs: đừng đưa cột / keyword thành table — live đang có "dbo.datetime2" trong refs_table (MailList).
   - Strip string literal SQL ('...') trước khi regex (dynamic SET @q = 'insert into #tmp select ..., datetime2, ... from ').
   - UPDATE: chỉ lấy identifier NGAY SAU UPDATE, dừng trước SET (đừng nuốt cột datetime2).
   - Denylist tên cột / noise FBO phổ biến: datetime0, datetime2, user_id0, user_id2, user_id3, user_id4, status, stt_rec, ma_dvcs, ...
   - Temp #x và @var đã skip — giữ.
2) Heuristic startswith("v") → view quá rộng; ưu tiên known view list + pattern FBO (vdm*, vgn*, vso*, vsys*) thay vì mọi identifier bắt đầu bằng v.
3) refs_match_body_diff: CHỈ emit khi fingerprint/body khác VÀ tập refs (views+tables) hai phía bằng nhau.
   Hiện code gắn signal này mỗi khi CẢ HAI có vdmduyetuq* — sai khi bảng refs lệch (vd source có dmnttduyet, target không) hoặc khi object identical.

P1:
4) Tests: MailList-like snippet có UPDATE ... SET datetime2 / dynamic SQL chứa datetime2 → refs_table KHÔNG chứa datetime2.
5) Tests: cả hai vdmduyetuq, refs tables khác nhau → KHÔNG có refs_match_body_diff; refs giống + sha khác → CÓ.
6) pytest tests/compare_things/ pass.
```

---

## 1. [P0] False positive `dbo.datetime2` trong `refs_table`

### Repro (live sau fix signals)

```text
compare_things(
  kind="sql",
  project_source=\\...\FBISP24,
  project_target=\\...\SP228,
  object="dbo.FastBusiness$App$GetApprovalMailList",
  mode="summary"
)
```

`refs.source.tables` / `refs.target.tables` có **`dbo.datetime2`** — đây là **cột** (`UPDATE dmxn SET datetime2 = ...`, `#tmp.datetime2`, chuỗi dynamic `select u_status, datetime2, ...`), không phải bảng.

### Root cause (code hiện tại)

[`sql_fingerprint.py`](../../../compare_things/sql_fingerprint.py) — `extract_sql_refs`:

```python
matches = re.findall(
    r"\b(?:FROM|JOIN|INTO|UPDATE)\s+(?:\[?dbo\]?\.)?\[?([a-zA-Z0-9_#$]+)\]?",
    text,
    re.IGNORECASE,
)
...
if obj_name.startswith("v") and len(obj_name) > 2:
    views.add(...)
else:
    tables.add(...)
```

Vấn đề kết hợp:

1. Regex chạy trên **cả** definition kể cả **string literal** dynamic SQL (`SET @q = 'insert into #tmp select ..., datetime2, ... from ' + ...`).
2. / hoặc nhầm identifier sau `UPDATE` / gần `SET datetime2`.
3. Không có denylist cột hệ thống FBO (`datetime2`, `user_id0`, …).

### Fix bắt buộc

1. **Preprocess:** loại hoặc blank-out nội dung trong `'...'` / `N'...'` (xử lý escape `''`) trước khi findall.
2. **UPDATE:** match `UPDATE\s+(table)` rồi **không** lấy token sau `SET` làm object. Ví dụ chỉ:

   `UPDATE\s+(?:\[?dbo\]?\.)?\[?(?P<name>[a-zA-Z0-9_#$]+)\]?(?:\s+SET\b|\s+|$)`

3. **Denylist** (lower): ít nhất  
   `datetime0`, `datetime2`, `user_id0`, `user_id2`, `user_id3`, `user_id4`, `status`, `stt_rec`, `stt_rec0`, `ma_dvcs`, `u_status`, `kieu_duyet`, `parallel_yn`, `deny_mail_yn`, `xtype`, `reset`  
   + SQL keywords còn sót: `set`, `values`, `where`, `and`, `or`, `on`, `as`, `with`.
4. Giữ skip `#temp` / `@var`.

### Test

Snippet giống MailList:

```sql
UPDATE dmxn SET datetime2 = @datetime2 WHERE stt_rec = @id
SET @q = 'insert into #tmp select u_status, datetime2, ma_dvcs from ' + @t
FROM vdmduyetuq a JOIN dmquyen b ON ...
```

→ `tables` chứa `dmxn`, `dmquyen`; **không** chứa `datetime2`.  
→ `views` chứa `vdmduyetuq`.

---

## 2. [P0] Heuristic `startswith("v")` → view

### Vấn đề

Mọi identifier bắt đầu `v` bị xếp `refs_view` (kể cả tên lạ / nhầm). Ngược lại bảng không `v` đều vào `tables`.

### Fix

- **Views:** known list (`vdmduyetuq`, `vgndmduyetuq`, `vsodmduyetuq`, `vsysuserinfo`, `vsysuser`, …) **hoặc** prefix FBO rõ: `vdm`, `vgn`, `vso`, `vsys`, `v#` không dùng.
- **Tables:** phần còn lại sau denylist; known tables (`dmduyet`, `dmuqduyet`, `dmquyen`, …) vẫn force vào tables bằng word-boundary (đã có).
- Không dùng `startswith("v")` chung.

---

## 3. [P0] `refs_match_body_diff` gắn sai điều kiện

### Code hiện tại

```python
if src_has_view_uq and tgt_has_view_uq:
    signals.append("refs_match_body_diff")
```

### Live

`App$GetApprovalMailList`: cả hai có `vdmduyetuq` + `dmuqduyet`, signal có `refs_match_body_diff`, nhưng `refs_table` source có thêm `dmnttduyet` còn target không → **refs không match**.

`ff_PRAuthorize`: refs views/tables **giống**, body khác `@Amount` precision → signal này **đúng** — giữ behavior này.

### Fix

Chỉ emit `refs_match_body_diff` khi:

1. `fingerprint` / `sha_norm` source ≠ target (body khác), **và**
2. `set(views_src)==set(views_tgt)` và `set(tables_src)==set(tables_tgt)` (sau khi đã làm sạch extract).

Nếu chỉ cùng `vdmduyetuq` nhưng tables lệch → **không** gắn `refs_match_body_diff`; có thể gắn `refs_partial_overlap` (P1 optional).

Không emit signal này khi `status=identical`.

Gọi `extract_sql_signals` nên nhận sẵn refs đã extract (hoặc so sha) — tránh chỉ nhìn “có substring uq”.

---

## 4. Việc không làm

- Đổi contract summary / bật preview mặc định  
- Sửa PK / message file (đã xong FIX trước)  
- Đổi semantics source/target  

---

## 5. Tiêu chí xong

1. MailList FAH↔AIH: `refs_table` **không** còn `datetime2`.  
2. `ff_PRAuthorize` different + refs giống → vẫn có `refs_match_body_diff`.  
3. MailList refs tables lệch → **không** có `refs_match_body_diff`.  
4. `pytest tests/compare_things/` pass.

---

## 6. File chạm

- [`compare_things/sql_fingerprint.py`](../../../compare_things/sql_fingerprint.py) — `extract_sql_refs`, `extract_sql_signals`  
- Tests mới/sửa dưới `tests/compare_things/`
