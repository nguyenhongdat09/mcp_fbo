# 07 — `kind=sql` (proc / func / view)

## 1. Mục tiêu

So definition **proc / function / view** giữa DB project source và target (resolve Web.config app/sys).

Không chỉ fingerprint khác — khi `different` phải có **hunks line ranges** + `signals` + `next_actions` để agent quyết `clone_things` hay sửa.

## 2. Input

| Param | Ghi chú |
|-------|---------|
| `project_source`, `project_target` | Abs, resolve dual connection |
| `object` | List tên; hoặc rỗng nếu có `seed` |
| `seed` | Keywords `,`-separated — scan candidate |
| `db_type` | `app` \| `sys` \| `both` |
| `schema` | Default `dbo` khi tên không có prefix — **chỉ sql/table** |
| `ignore_line_endings` | default true |
| `ignore_whitespace` | default false |
| `context_lines` | default 3 — truyền vào difflib khi build hunks |
| `mode`, `max_objects`, `max_diff_lines` | |

## 3. Pipeline

### 3.1. Resolve object list

1. Resolve connections qua `db_access` → `clone_things.db_ops`.
2. Nếu `object` không rỗng: parse names; áp `schema` default.
3. Nếu `object` rỗng + `seed`: chạy **seed scan** §3.3 → candidate list.
4. Deduplicate (case-insensitive name); cắt `max_objects`.

### 3.2. Per object

1. Exists source / target theo `db_type` (§6).
2. Encrypted → `encrypted_skip`.
3. Missing một bên → status + next_actions.
4. Cả hai readable:
   - Lấy definition (reuse clone_things fetch — không dump full vào JSON)
   - Normalize như file (BOM, CRLF, whitespace)
   - Fingerprint = hash text normalized
   - Khác → `difflib` với `context_lines` → hunks `source_*` / `target_*` + signals

Signals tối thiểu v1: match `\bvdmduyetuq\b` / `\bdmduyet\b` và generic `\b{seed_keyword}\b` → `source_refs_*` / `target_refs_*`; điền `signals_in_hunk` khi preview chứa pattern.

### 3.3. Seed scan — SQL mẫu (chốt)

**Phạm vi scan:** chạy trên **source** theo `db_type` (app / sys / both).  
**Không** bắt buộc union target để tạo list (tránh nhầm object chỉ có ở target).  
Sau khi có list từ source: so từng tên với target (missing/different như bình thường).

Với mỗi keyword `k` trong seed (trim, bỏ rỗng), query:

```sql
-- Candidates: proc / func / view có definition chứa keyword (không encrypted filter ở đây)
SELECT TOP (@per_keyword_cap)
    OBJECT_SCHEMA_NAME(m.object_id) AS [schema_name],
    o.name AS [object_name],
    o.type AS [object_type]  -- P, FN, IF, TF, V, ...
FROM sys.sql_modules AS m
INNER JOIN sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%' + @k + '%'
  AND o.type IN ('P', 'FN', 'IF', 'TF', 'V')
ORDER BY o.name;
```

Gợi ý: `@per_keyword_cap = max(10, max_objects // max(1, so_keywords))` rồi merge/dedupe rồi cắt `max_objects` tổng.

Encrypted modules: `definition` NULL — không match LIKE; đúng vì anyway `encrypted_skip` nếu user chỉ định tên.

**CẤM:** `SELECT definition` full dump mọi row ra log/JSON. Scan chỉ lấy schema+name+type.

Optional bổ sung (P1): cũng LIKE trên `o.name` nếu muốn bắt tên object chứa keyword — không bắt buộc v1.

## 4. Object type

Map `P`→`proc`, `FN`/`IF`/`TF`→`func`, `V`→`view`.  
Table → dùng `kind=table`, không seed vào sql.

## 5. Output

Xem [04](./04_json_response.md) §5.2 + §5.6.

Acceptance: FAHASA vs AIH, seed `dmuqduyet,vdmduyetuq` → Authorize/MailList/Role `different` nếu target còn `dmduyet`, kèm hunks + signals.

## 6. `db_type=both` — conflict (chốt + ví dụ)

Khi `db_type=both`, với **mỗi** object name cần so:

1. Tìm trên **app** source, **sys** source, **app** target, **sys** target (exists + optional fingerprint nếu readable).
2. Chọn phía source để lấy body / exists:
   - Có trên **app** → dùng app (`db_type_found_source=app`)
   - Không app, có **sys** → dùng sys
3. Tương tự phía target → `db_type_found_target`.

### Conflict là gì?

**Conflict** khi **cùng `schema.name` tồn tại trên cả app và sys** của **cùng một phía** (source hoặc target).

| Tình huống | Xử lý v1 |
|------------|----------|
| Source app có `dbo.Foo`, source sys cũng có `dbo.Foo` | Dùng **app**; `warnings` += `db_conflict_source: dbo.Foo exists on app and sys; using app` |
| Chỉ sys có | Dùng sys; không conflict warning |
| Target conflict tương tự | Dùng app target; warning `db_conflict_target: ...` |
| So sánh: source lấy app body, target lấy sys body (vì target chỉ có sys) | Hợp lệ; `db_type_found_source`/`_target` khác nhau — **không** gọi là conflict; agent thấy field này |

**Không** gọi conflict khi fingerprint app≠sys — v1 không so app vs sys nội bộ một project; chỉ warn tồn tại kép rồi chọn app.

Ví dụ JSON snippet:

```json
{
  "name": "dbo.Foo",
  "db_type_found_source": "app",
  "db_type_found_target": "sys",
  "status": "different",
  "warnings": ["db_conflict_source: dbo.Foo exists on app and sys; using app"]
}
```

(`warnings` có thể ở item hoặc đẩy lên envelope — **chốt: envelope `warnings[]` + optional `compared[].note`**)

## 7. CẤM

- Full definition trong JSON mặc định
- `query_database` mode=full dump
- Auto ALTER / clone
- Seed scan đọc full module text vào response
- Coi table như sql kind
