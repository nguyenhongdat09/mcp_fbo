# FIX — `clone_things` type=1: object encrypt ≠ not_found + BOM lạ trong `.sql`

> **Mục đích:** Doc gửi **Gemini fix** — 2 lỗi live sau test `zcnkscttbt.xml` / `zc_sctnt`.  
> **Ngày:** 2026-09-09  
> **Phạm vi:** [`clone_things/service.py`](../../../clone_things/service.py), [`clone_things/file_manager.py`](../../../clone_things/file_manager.py), JSON response type=1; optional reuse check encrypt từ `queryDatabase` / `summary_object`.  
> **Evidence:** live MCP + file [`scripts/_clone_things_live/case_proc_r1.sql`](../../../scripts/_clone_things_live/case_proc_r1.sql).  
> **Không** đụng chrome_debug.

---

## 1. Lỗi A — Object công ty **encrypted** bị hiểu sai

### 1.1. Hiện tượng live

Seed XML Filter `zcnkscttbt.xml` → proc `dbo.zc_sctnt` → `mode_recursion=1`.

Dep `dbo.FastBusiness$Partition$Execute`:

- Catalog **có** object (đã vào queue từ deps, không phải tên bịa).
- `fetch_object_script` / `summary_object(mode=full)` trả definition **rỗng** (module encrypted).
- JSON hiện tại: `warnings: ["fetch_failed: dbo.FastBusiness$Partition$Execute"]` — agent dễ tưởng lỗi mạng / thiếu object.
- User: nếu xếp vào `not_found_source` thì **sai** (object có trên DB, chỉ không đọc được body).

BA: `FastBusiness$*` **được phép** kéo (code công ty). Chỉ loại SQL Server system (`sp_` / `xp_` / `sys.` / `sp_executesql`). Encrypted công ty → báo **encrypt**, không báo not_found.

### 1.2. Chốt xử lý

Khi type=1 (và khuyến nghị type=0 tương tự nếu cùng path fetch):

```
exists trên source? 
  → không → not_found_source (giữ)
  → có → fetch script
       → có body → paste bình thường
       → body rỗng / fetch_failed:
            check IsEncrypted (xem §1.3)
              → encrypted = true  → đưa vào encrypt_proc (hoặc encrypted[]), KHÔNG not_found, KHÔNG giả fetch_failed mơ hồ
              → encrypted = false → giữ warnings fetch_failed / lý do khác (permission, timeout…)
```

**JSON type=1 — field mới (bắt buộc):**

| Field | Type | Mô tả |
|-------|------|--------|
| `encrypt_proc` | `string[]` | Tên object (thường proc/func/view) **tồn tại** nhưng definition encrypted / không đọc được do encrypt. Ví dụ `["dbo.FastBusiness$Partition$Execute"]` |

Optional (khuyến nghị): phần tử object thay vì chỉ string:

```json
"encrypt_proc": [
  {
    "name": "dbo.FastBusiness$Partition$Execute",
    "object_type": "SQL_STORED_PROCEDURE",
    "db": "app",
    "parent_proc": "dbo.zc_sctnt"
  }
]
```

Nếu giữ `string[]` cho đơn giản v1 — OK; vẫn nên gắn `parent_*` trong object form nếu đang có `parent_map` (agent biết encrypt nằm dưới proc nào).

- **Không** paste block ALTER giả cho object encrypt.
- `child_proc` trên cha **vẫn có thể liệt kê** tên encrypt (đã analyze deps) — đúng; agent nhìn `encrypt_proc` biết không sửa được body.
- Cập nhật `agent_message` khi có `encrypt_proc`: nhắc object mã hóa, không có trong file / không đọc được definition.

### 1.3. Cách detect encrypt (Gemini implement)

Ưu tiên **sys.objects / OBJECTPROPERTY** (user gợi ý `sysobjects` — chấp nhận tương đương hiện đại):

```sql
-- Theo object_id + schema (khuyến nghị)
SELECT CASE WHEN OBJECTPROPERTY(OBJECT_ID(N'dbo.FastBusiness$Partition$Execute'), 'IsEncrypted') = 1
            THEN 1 ELSE 0 END;

-- Hoặc (parity wording user / legacy):
SELECT 1
FROM sys.sysobjects
WHERE name = N'FastBusiness$Partition$Execute'
  AND OBJECTPROPERTY(id, 'IsEncrypted') = 1;

-- Bổ sung chắc chắn hơn với sql_modules:
SELECT 1
FROM sys.objects o
JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name = N'FastBusiness$Partition$Execute'
  AND SCHEMA_NAME(o.schema_id) = N'dbo'
  AND m.definition IS NULL
  AND OBJECTPROPERTY(o.object_id, 'IsEncrypted') = 1;
```

Chạy trên **đúng connection** `db` (app/sys) nơi `find_object_on_side` đã thấy object.

Reuse: `summary_object` / summary_bridge đã có warning `encrypted_or_empty_definition` khi definition rỗng — có thể propagate flag `encrypted: true` từ bridge thay vì chỉ `fetch_failed` rỗng. Gemini được phép:

1. Sửa `fetch_object_script` / gọi summary trả thêm `encrypted` flag, **hoặc**
2. Helper `is_object_encrypted(parsed_conn, schema, name) -> bool` trong `clone_things` khi script rỗng sau exists=True.

### 1.4. Phân biệt với `not_found_source`

| Tình huống | Field |
|------------|--------|
| Không có trong catalog source | `not_found_source` |
| Có + encrypted / definition null vì encrypt | **`encrypt_proc`** |
| Có + không encrypt nhưng fetch lỗi khác | `warnings` `fetch_failed: …` (kèm lý do nếu có) |
| System `sp_executesql` | exclude / noise — không cần encrypt_proc |

---

## 2. Lỗi B — Ký tự lạ (UTF-8 BOM) trong file `.sql`

### 2.1. Evidence

File: `scripts/_clone_things_live/case_proc_r1.sql` dòng 4–5 (sau `USE`/`GO`):

```text
USE [VLOTUS_SP228_A]
GO

﻿          ← ký tự vô hình / “?” tùy editor
```

Hex:

```text
USE [VLOTUS_SP228_A]\nGO\n\n\xef\xbb\xbf\n\n-- clone_things type=1: ...
```

`\xef\xbb\xbf` = **UTF-8 BOM** (`U+FEFF`).

### 2.2. Root cause (đã reproduce trên Python runtime máy user)

```python
>>> "\ufeff".strip()
"\ufeff"          # KHÔNG bị xóa — truthy!
>>> bool("\ufeff".strip())
True
```

Luồng:

1. `path_to_pasted` file đã tồn tại với BOM (vd. PowerShell `Set-Content -Encoding utf8`, Notepad, hoặc tool khác ghi BOM).
2. [`ensure_use_db_sections`](../../../clone_things/file_manager.py):

```python
content = p.read_text(encoding="utf-8")   # giữ \ufeff
if content.strip():                       # True vì BOM không strip!
    content = app_header + "\n\n" + content.lstrip("\n")
    # → USE ... GO\n\n + \ufeff   ← BOM nằm giữa header và script
```

3. Agent/user thấy dòng “trống” / ký tự lạ giữa `GO` và `-- clone_things`.

### 2.3. Fix bắt buộc (file_manager)

Trong `ensure_use_db_sections`, `append_script_block`, `append_not_found_summary`, `object_already_in_sql_file` (mọi chỗ đọc `.sql`):

1. Đọc bằng `encoding="utf-8-sig"` **hoặc** sau read: `content = content.lstrip("\ufeff")` / `content.replace("\ufeff", "")`.
2. Trước khi coi “file có nội dung”: dùng helper `def _sql_file_body(content: str) -> str` strip BOM + whitespace để quyết định prepend USE.
3. Ghi file: `encoding="utf-8"` **không** BOM (mặc định Python `open(..., "w", encoding="utf-8")` đã OK — giữ vậy).
4. `resolve_output_file` / `create_sql_temp_file`: khi tạo file mới, không ghi BOM.

Unit test:

- File đầu vào chỉ chứa BOM (bytes `EF BB BF`) hoặc BOM + `\n` → sau `ensure_use` + append **không** còn `\ufeff` / `\xef\xbb\xbf` trong file.
- Không xuất hiện BOM giữa `GO` và block `-- clone_things`.

---

## 3. Acceptance

| ID | Given | Then |
|----|--------|------|
| AC-ENC-01 | Exists + IsEncrypted=1 + definition null | Có trong `encrypt_proc`; **không** trong `not_found_source` |
| AC-ENC-02 | Cha paste được; child encrypt | Cha có tên child trong `child_proc`; child trong `encrypt_proc`; không block ALTER giả của child |
| AC-ENC-03 | Thật sự không tồn tại | Chỉ `not_found_source` |
| AC-BOM-01 | `path_to_pasted` precreate UTF-8 BOM | Sau clone, file không còn `\xef\xbb\xbf` / `\ufeff` |
| AC-BOM-02 | Regression append nhiều block | Không `GOUSE`; không BOM giữa các section |

---

## 4. Test gợi ý

```text
tests/clone_things/test_encrypted_and_bom.py
  test_encrypt_proc_when_is_encrypted
  test_not_found_when_missing
  test_strip_utf8_bom_on_ensure_and_append
```

Live re-test (sau fix): cùng XML VLOTUS `zcnkscttbt.xml`, `mode_recursion=1` → `FastBusiness$Partition$Execute` ∈ `encrypt_proc`; mở `.sql` không còn dòng BOM sau `GO`.

---

## 5. Prompt Gemini (copy-paste)

```text
Bạn là implementer FastBusiness MCP (repo E:\PythonProject\mcp_fbo).

Fix theo docs/doc/doc_fix/FIX-clone_things-encrypted-and-sql-bom.md:

1) Encrypted objects (vd FastBusiness$Partition$Execute):
   - Khi exists=True nhưng definition/fetch rỗng → check OBJECTPROPERTY(..., 'IsEncrypted')=1
     (hoặc sys.sql_modules.definition IS NULL + IsEncrypted).
   - Đưa vào JSON field encrypt_proc (không not_found_source; đừng chỉ fetch_failed mơ hồ).
   - Không paste ALTER giả. child_proc trên cha vẫn được liệt kê tên.
   - FastBusiness$* vẫn được phép kéo; chỉ exclude system SQL Server (sp_/xp_/sys./sp_executesql).

2) UTF-8 BOM trong .sql:
   - Root cause: "\ufeff".strip() truthy trên runtime → ensure_use prepend USE giữ BOM giữa GO và script.
   - Đọc utf-8-sig hoặc lstrip BOM mọi chỗ file_manager; test file pre-BOM không còn EF BB BF.

Viết unit tests. Không regress type=0/1 khác. Không sửa docs trừ khi cần link ngắn.
```

---

## 6. Tham chiếu

- Live output recursion=1: `fetch_failed: dbo.FastBusiness$Partition$Execute`, `not_found_source: dbo.sp_executesql`
- Spec type=1: [`../clone_things/12_type1_xml_mode_get_recursion.md`](../clone_things/12_type1_xml_mode_get_recursion.md), [`../clone_things/13_type1_parent_child_relations.md`](../clone_things/13_type1_parent_child_relations.md)
- summary_bridge warning: `encrypted_or_empty_definition`
