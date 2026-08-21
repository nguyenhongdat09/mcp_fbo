# 01 — Overview: Tool `summary_object`

## 1. Bối cảnh

Dự án **FastBusiness MCP** (`E:\PythonProject\mcp_fbo\`) hiện có 5 tools:

| Tool | Vai trò liên quan SQL |
|------|----------------------|
| `query_database` | Chạy SQL; `query_type=0` → `sp_helptext` / schema bảng |
| `query_radar` | Graph XML (không thay SQL body) |
| `read_local_file` | Đọc file `.sql` local |
| `get_xml_entities` | XML FBO |
| `search_qlyc` | Lịch sử UR |

Trong thực tế Agent FBO (Cursor) khi viết/sửa báo cáo:

1. Gọi `query_database(type=0, query='rs_rptInterestDetailedByLoanContract')` → nhận **full proc** (~300–500 dòng).
2. Đọc lại nhiều vòng khi debug → token tăng rất nhanh.
3. Graph dependency (`query_radar`) **không chứa** công thức nghiệp vụ (`so_du * ls / 100 / @days`, `@Status` ảnh hưởng `ngay_tu`…).

## 2. Mục tiêu

Thêm tool **`summary_object`** trả **JSON có cấu trúc**, đủ để Agent:

| Việc Agent hay làm | Summary | Snippet | Full |
|--------------------|---------|---------|------|
| Biết proc gọi ai, đụng bảng nào | ✅ | — | — |
| Biết tham số, temp, RS output | ✅ | — | — |
| Copy/sửa logic nghiệp vụ (lãi vay, pivot) | gợi ý vùng | ✅ | — |
| Sửa từng dòng trong proc | — | một phần | ✅ |

**Nguyên tắc tier:**

```
summary  →  snippet  →  full
(mặc định)   (theo keyword)   (hiếm, có giới hạn)
```

Agent rule (ghi trong tool description): **không** gọi `query_database type=0` khi chỉ cần định hướng — dùng `summary_object` trước.

## 3. Phạm vi v1

### Làm

- Parse **PROCEDURE**, **FUNCTION** (scalar + inline table), và **VIEW** (`sys.objects.type = 'V'` — summary nông: `tables_read`, columns; **không** đệ quy call graph).
- Trích xuất từ **body** (sau khi ghép `sp_helptext` hoặc từ `sys.sql_modules`):
  - Header: tên, schema, tham số (+ default nếu có)
  - `EXEC` / `EXECUTE` / call function
  - `FROM` / `JOIN` / `INTO` / `UPDATE` / `DELETE` / `MERGE` → tables
  - `CREATE TABLE #...` / `DECLARE @... TABLE` → temp tables
  - `DECLARE CURSOR`, `WHILE`, `sp_executesql`, `@q = '...'` → signals
  - `SELECT` cuối (gợi ý result set) — heuristic
  - Đọc `options WHERE name = '...'` → `options_keys`
- Phân loại object: `business` vs `infra`
- Call graph **nông** (configurable depth, max 30 objects, có `truncated_objects`)
- Optional: `called_by` (inbound) qua `sys.sql_expression_dependencies` hoặc `sys.dm_sql_referenced_entities`
- Lookup object theo **schema + name** (khác `query_database type=0` chỉ theo `name`)
- Cache thread-safe theo `(database, object_id, modify_date)` + TTL + LRU

### Không làm v1

- Parse perfect mọi dynamic SQL (chỉ **signal** + extract string literal đơn giản)
- Deploy / ALTER object
- Thay thế hoàn toàn `query_database type=0` cho **USER_TABLE** schema (vẫn dùng tool cũ)
- Đệ quy call graph sâu cho **VIEW** (view chỉ trả summary bảng nguồn, depth=0)
- Graph Kùzu build-time (có thể phase 2: sync summary vào FBOGraph)

## 4. Ràng buộc FastBusiness

### Infra patterns (depth = 0 mặc định)

```python
INFRA_PATTERNS = [
    r"^FastBusiness\$",   # FastBusiness$Balance$BContract
    r"^ff_",              # ff_GetStartDateOfCycle
    r"^fsd_",             # fsd_StringToTable
]
```

Các object match → `{ "name": "...", "kind": "infra" }` — **không** đệ quy parse con trừ khi `expand` chứa tên đó.

### Business patterns (depth 1–2 mặc định)

```python
BUSINESS_PATTERNS = [
    r"^zc_",
    r"^rs_rpt",
    r"^rs_",
    r"^zcs?",
]
```

### Temp / partition tables

- `#temp` → `temp_tables`
- `r00$`, `r01$`… → `tables_read` + flag `uses_partition: true`
- Không coi temp là node đệ quy

## 5. Vì sao ANTLR4

| Phương án | Ưu | Nhược |
|-----------|-----|-------|
| Regex thuần | Nhanh viết | Proc FBO lồng `BEGIN/END`, string, comment → dễ sai |
| `sqlparse` | Có sẵn Python | T-SQL đặc thù (`@var`, `#temp`, `GO`, `$` trong tên) kém |
| **ANTLR4 + T-SQL grammar** | Cây cú pháp, visitor rõ | Cần subset grammar, maintain grammar |

**Khuyến nghị v1:** Fork grammar T-SQL community (vd. [antlr/grammars-v4 sql/tsql](https://github.com/antlr/grammars-v4/tree/master/sql/tsql)) → **subset** cho proc body:

- Bỏ qua `GO`, batch separator
- Cho phép identifier có `$`
- Visitor custom, không cần support toàn bộ T-SQL

**Fallback:** Nếu parse fail → trả `parse_status: "partial"` + heuristic regex (calls, tables) + vẫn có `snippet`/`full` raw text.

## 6. Liên hệ cuộc trò chuyện gốc

Use case thực tế đã debug:

- Proc chuẩn: `rs_rptInterestDetailedByLoanContract`
- Proc mới: `zc_bcthlv` (pivot tháng, reuse pipeline lãi vay)
- Bug: `@Status = '1'` vs `'0'` — **chỉ đọc được từ body**, không từ call graph

→ Summary phải có `signals` + `param_effects` (heuristic) + snippet theo keyword `Status`, `tl_th`, `ctdmku`.

## 7. Thành công / KPI

- Response `mode=summary` cho proc ~400 dòng: **< 10 KB JSON** (vs 50–150 KB full text)
- Parse thành công ≥ 90% proc trong `App_Data` Filter exec (sample 50 proc)
- Test case FBISP242 pass (xem `06_implementation_checklist.md`)
- Không break 5 tools hiện có
