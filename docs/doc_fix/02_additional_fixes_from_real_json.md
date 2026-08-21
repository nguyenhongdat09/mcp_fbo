# Additional Fixes — `summary_object` (from real JSON runs)

> **Nguồn:** 2 JSON thực tế user cung cấp (2026-08-20)
> - `dbo.rs_rptInterestDetailedByLoanContract` (`line_count=328`, `parse_status=partial`)
> - `dbo.rs_rptStockSummaryByLotItem` (`line_count=186`, `parse_status=partial`)
>
> **Mục tiêu:** Agent không hiểu sai / không nhiễu vì các signal/tables bị thiếu hoặc nhiễm.

---
## P0 (must-fix): `has_dynamic_sql` sai trong heuristic mode

### Hiện tại (Actual)
- Proc lớn (`line_count > 150`) đang chạy nhánh heuristic (không walk AST đầy đủ).
- Trong JSON user:
  - Có `calls_direct` chứa `dbo.sp_executesql` (kind = `system`)
  - Nhưng `summary.signals.has_dynamic_sql = false`

### Nguyên nhân khả dĩ
- `signals.has_dynamic_sql` được set trong visitor `visitExecute_statement` khi có AST.
- Nhánh heuristic bỏ qua ANTLR traversal => không gọi `visitExecute_statement` => flag không bao giờ được bật.

### Expected
- Nếu trong `definition` có chuỗi `sp_executesql` (case-insensitive, word boundary) thì:
  - `signals.has_dynamic_sql = true`
  - Không ảnh hưởng phân loại `calls_direct` (sp_executesql vẫn `kind=system`)

### Fix spec cho Gemini
- **File:** `sql_object_summary/visitors/summary_visitor.py`
- **Chỗ sửa:** trong `finalize()` (hoặc sau heuristic fallback), thêm scan regex:
  - `re.search(r"\bsp_executesql\b", self.full_text, re.IGNORECASE)` => `self.signals.has_dynamic_sql = True`

### Test cần thêm
- Thêm/extend test để đảm bảo heuristic branch set đúng:
  - Tình huống: `line_count > 150`, `parse_status=partial`
  - Definition chứa `EXEC sp_executesql ...`
  - Assert: `summary.signals.has_dynamic_sql is True`

---
## P1 (fix noise): `tables_write` bị dính `"set"`

### Hiện tại (Actual)
- JSON user cho `dbo.rs_rptInterestDetailedByLoanContract`:
  - `tables_write: ["set"]`

### Expected
- `"set"` không được coi là table name.

### Fix spec cho Gemini
- **File:** `sql_object_summary/visitors/summary_visitor.py`
- **Cách làm (ưu tiên):**
  - Trong `_normalize_table_name()` hoặc nơi thêm vào `tables_write_set`, thêm filter loại bỏ SQL keywords / reserved words.
- **Tối thiểu cần filter:** `set` (lowercase)
- **Khuyến nghị mở rộng:** filter các từ hay nhiễu từ regex extraction như `select`, `where`, `group`, `order`, `from`, `join` (nếu thấy thêm nhiễu ở các proc khác).

### Test cần thêm
- Tạo test snapshot/fixture cho proc interest (hoặc test nhỏ mô phỏng) để assert:
  - `"set" not in summary.tables_write`

---
## P2 (nice-to-have nhưng nên làm): `tables_read` nhiễm kiểu dữ liệu như `"nvarchar"`

### Hiện tại (Actual)
- JSON user cho `dbo.rs_rptStockSummaryByLotItem`:
  - `tables_read` có `"nvarchar"` (đây là SQL data type, không phải table)

### Expected
- Không đưa SQL data types / keyword vào `tables_read`.

### Fix spec cho Gemini
- **File:** `sql_object_summary/visitors/summary_visitor.py`
- Thêm danh sách loại bỏ `DATA_TYPE_NOISE` (ví dụ tối thiểu):
  - `nvarchar`, `varchar`, `char`, `nchar`, `int`, `bigint`, `smallint`, `tinyint`,
  - `bit`, `decimal`, `numeric`, `float`, `real`, `money`, `smallmoney`,
  - `datetime`, `smalldatetime`, `date`, `time`
- Áp dụng trong `_normalize_table_name()` trước khi trả `clean_name`.

### Test cần thêm
- Assert: `"nvarchar" not in tables_read` với proc stock summary.

---
## Notes (để tránh hiểu nhầm)
- Các fix này chỉ nhắm vào heuristic extraction noise/signal:
  - Không bắt buộc thay đổi logic AST path.
- Không thay đổi contracts `calls_direct/calls_business`.

