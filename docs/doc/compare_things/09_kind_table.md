# 09 — `kind=table` (schema ngữ nghĩa)

## 1. Mục tiêu

So **schema bảng** giữa 2 project DB — **không** so data rows, **không** phụ thuộc thứ tự cột vật lý.

### Ví dụ bắt buộc identical

| Source | Target |
|--------|--------|
| Cột `K int`, `L int` (ordinal K rồi L) | Cột `L int`, `K int` (ordinal L rồi K) |

→ **identical** (cùng tên + type (+ nullability/precision)).

### Chỉ different khi

| Tín hiệu | Chi tiết |
|----------|----------|
| Cột thiếu / thừa | Tên cột chỉ có một bên |
| Type lệch | Cùng tên khác type/null/length/precision/scale |
| PK lệch | Tập cột PK hoặc thứ tự **trong** PK constraint khác |
| Index lệch | Thiếu/thừa index hoặc định nghĩa key columns khác |
| Trigger lệch | Thiếu/thừa tên hoặc definition hash khác (nếu đọc được) |

## 2. Input

`kind=table`, `project_source`, `project_target`, `object` (list tên bảng), `db_type`, `max_objects`.

## 3. Pipeline — `table_schema.py`

Đọc catalog SQL Server (qua connection đã resolve), **không** so chuỗi `CREATE TABLE` raw:

1. `sys.columns` + `sys.types` → map `column_name.lower() → {type, max_length, precision, scale, is_nullable}`
2. PK: `sys.key_constraints` / `sys.index_columns` WHERE is_primary_key — list cột **theo key_ordinal** (thứ tự trong PK có ý nghĩa)
3. Indexes: non-PK indexes — tên, is_unique, is_unique_constraint, type_desc (clustered/nonclustered), list cột theo key_ordinal (+ included columns nếu lấy được)
4. Triggers: `sys.triggers` — tên; optional definition hash nếu readable / not encrypted
5. Fingerprint = canonical JSON/sorted structure hash:

```text
columns: sort by name
pk: list ordered by key_ordinal
indexes: sort by index name; within each, columns by key_ordinal
triggers: sort by name (+ hash)
```

**CẤM** đưa `column_id` / `ORDINAL_POSITION` vào fingerprint cột.

## 4. Diff → `schema_diff`

Xem sample [04](./04_json_response.md) §5.3.

`next_actions` map:

- cột thiếu target → `alter_add_column`
- type mismatch → `review_column_type`
- pk_diff → `review_pk`
- index → `review_index`
- trigger → `review_trigger`

## 5. Partition / `$` tables

Bảng partition kiểu `m41$` / `d91$`: so theo tên object catalog thực tế user truyền; không hardcode partition tháng. Ghi chú trong warning nếu tên có `$`.

## 6. CẤM

- Coi khác ordinal cột là different
- So row counts / data
- Auto CREATE/ALTER table
- So filegroup / extended properties (v1)
- FK / DEFAULT / CHECK chi tiết (ngoài scope v1 — ghi suggestions)
