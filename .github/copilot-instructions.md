# FastBusiness MCP Server - AI Field Generation Instructions

**Project:** FastBusiness XML Controller Configuration & SQL Server Integration
**Language:** XML, T-SQL, ES5 JavaScript
**Version:** 3.0 - LMDB Field Generation Only
**Last Updated:** November 2024

---

## 🎯 Project Overview

FastBusiness is an enterprise accounting/ERP system with partition-based data architecture. This MCP server provides:
- **LMDB Field Database** - Pre-parsed field definitions from existing XML files
- **Smart Field Generation** - Auto-detect context (DIR/FILTER/GRID) and lookup types
- **SQL Generation** - Auto-generate `fsd_addfields` commands for database schema updates

### Critical Constraints (NON-NEGOTIABLE)

1. **Partition References MANDATORY** - ALWAYS use `$partition$current`, `$partition$previous`, `@@prime$partition$current`
   **❌ NEVER hardcode:** `m66$202411` (data loss when month rolls over)
2. **Partitioned Table Rule** - Preserve `$` suffix in SQL: `d91$000000` → `exec fsd_addfields 'd91$', ...`
3. **Auto-Detect DataFormatString** - Field naming patterns determine display format automatically
4. **Always Ask About SQL** - After generating XML field, ALWAYS ask if user wants SQL generation

---

## 🔑 Field Type Auto-Detection

### 1. Context Type Detection (Automatic)

MCP server auto-detects file context from **folder path** (priority) or **XML content** (fallback):

**Folder Path Detection (Recommended):**
```
Path contains \Dir\    → DIR (Form with master/detail)
Path contains \Filter\ → FILTER_VOUCHER or FILTER_NORMAL
Path contains \Grid\   → GRID_VIEW or GRID_INPUT
```

**XML Content Detection (Fallback):**
```
Has <dir> tag    → DIR
Has <grid> tag   → GRID_VIEW or GRID_INPUT
Has <filter> tag → FILTER
```

### 2. Lookup Type Detection (From Vietnamese Requests)

```
"thêm trường X"                      → lookup_type='default' (no lookup)
"thêm trường X dạng lookup"          → lookup_type='autocomplete' (single select)
"thêm trường X lookup chọn nhiều"    → lookup_type='lookup' (multi-select)
```

### 3. DataFormatString Auto-Detection (Context-Aware)

**CRITICAL:** DataFormatString varies by context (`<fields>` vs `<view>`)

| Field Pattern | SQL Type | Input Format | View Format | Example |
|---|---|---|---|---|
| so_luong, _sl$ | numeric(19,4) | @quantityInputFormat | @quantityViewFormat | so_luong |
| ^tien, _tien$ (NO _nt) | numeric(19,4) | @baseCurrencyAmountInputFormat | @baseCurrencyAmountViewFormat | tien |
| _nt$ | numeric(19,4) | @foreignCurrencyAmountInputFormat | @foreignCurrencyAmountViewFormat | tien_nt |
| ^gia, don_gia (NO _nt) | numeric(19,4) | @baseCurrencyPriceInputFormat | @baseCurrencyPriceViewFormat | gia |
| gia.*_nt$ | numeric(19,4) | @foreignCurrencyPriceInputFormat | @foreignCurrencyPriceViewFormat | gia_nt |
| ty_gia | numeric(19,4) | @exchangeRateInputFormat | @exchangeRateViewFormat | ty_gia |
| ^ngay_, _date$ | smalldatetime | @datetimeFormat | @datetimeFormat | ngay_ct |
| ^ma_ | varchar(33) | @upperCaseFormat | @upperCaseFormat | ma_kh |
| ^ten_, ghi_chu | nvarchar(256) | (none) | (none) | ten_kh |

---

## 💾 SQL Generation Workflow

### Partitioned Table Rule (CRITICAL)

**⭐ CRITICAL RULE:** When generating SQL, check if table has `$` (partitioned):

| XML Table Name | SQL Command | Why |
|---|---|---|
| `table="d81$000000"` | `exec fsd_addfields 'd81$', ...` | Table is partitioned - preserve `$` |
| `table="m91$000000"` | `exec fsd_addfields 'm91$', ...` | Prime table is partitioned |
| `table="dmvt"` | `exec fsd_addfields 'dmvt', ...` | Non-partitioned - no `$` |
| `table="dmkh"` | `exec fsd_addfields 'dmkh', ...` | Master data table - no `$` |

**Why?** FastBusiness tables with `$` are partitioned by month. The `$` must be preserved to ensure data routing works correctly.

```sql
-- ✅ CORRECT - Table has $ in XML, use $ in SQL
-- XML: <dir table="m81$000000" ...>
exec fsd_addfields 'd81$', 'ma_bo_phan', 'varchar(33)'
exec fsd_addfields 'd81$', 'ten_bo_phan%l', 'nvarchar(256)'

-- ✅ CORRECT - Table has NO $ in XML, don't use $ in SQL
-- XML: <dir table="dmvt" ...>
exec fsd_addfields 'dmvt', 'ma_bo_phan', 'varchar(33)'

-- ❌ WRONG - Mismatch between XML and SQL
-- XML: table="d81$000000"
exec fsd_addfields 'd81', ...  -- Missing $! This will fail!
```

### SQL Type Detection from Field Names

When generating SQL after XML field creation, auto-detect SQL column type:

| Field Pattern | SQL Type | Examples |
|---|---|---|
| ^ma_ | varchar(33) | ma_kh, ma_vt, ma_bp |
| ^ten_, mo_ta, ghi_chu | nvarchar(256) | ten_kh, ghi_chu |
| ^ngay_, _date$ | smalldatetime | ngay_ct, ngay_lct |
| ^tien, _tien$, ^t_ (NO _nt) | numeric(19,4) | tien, t_tien, gia |
| _nt$ | numeric(19,4) | tien_nt, gia_nt |
| ^so_luong, _luong$, _sl$ | numeric(19,4) | so_luong, sl_xuat |
| ^thang$, ^nam$, ^so_ngay, _count$ | int | thang, nam, so_ngay |
| ^check_, ^is_, ^status$ | tinyint | status, is_active |
| %l$ | nvarchar(256) | ten_kh%l (lookup display) |
| Default | nvarchar(256) | All others |

### Complete SQL Generation Example

```sql
-- Auto-detect from field names
-- For partitioned tables (with $ in name):
exec fsd_addfields 'd91$', 'ma_bo_phan', 'varchar(33)'     -- ^ma_ pattern
exec fsd_addfields 'd91$', 'ten_bo_phan%l', 'nvarchar(256)' -- lookup display
exec fsd_addfields 'd91$', 'tien_nt', 'numeric(19,4)'      -- _nt$ pattern
exec fsd_addfields 'd91$', 'so_luong', 'numeric(19,4)'     -- so_luong pattern
exec fsd_addfields 'd91$', 'ngay_lct', 'smalldatetime'     -- ngay_ pattern
exec fsd_addfields 'd91$', 'thang', 'int'                  -- ^thang$ pattern
exec fsd_addfields 'd91$', 'status', 'tinyint'             -- status pattern

-- For non-partitioned tables (no $ in name):
exec fsd_addfields 'dmvt', 'ma_bo_phan', 'varchar(33)'
exec fsd_addfields 'dmvt', 'ten_bo_phan', 'nvarchar(256)'
```

---

## 🚀 Complete Workflow: Add Field to Form

### Step 1: Use MCP Tool to Generate XML Field

```
User: "Thêm trường mã bộ phận dạng lookup"

→ Tool: generate_field_from_lmdb
  Parameters:
    - field_name: 'ma_bo_phan'
    - lookup_type: 'autocomplete'
    - file_path: 'e:\FBO\SP2263\App_Data\Controllers\Dir\SI2Tran.xml'

→ MCP auto-detects:
  - Context: DIR (from \Dir\ in path)
  - Format: @upperCaseFormat (from ^ma_ pattern)
  - Lookup suffix: 't' (AutoComplete style)

→ MCP generates XML:
  <field name="ma_bo_phant" categoryIndex="4">
    <header v="Mã bộ phận" e="Department Code"/>
    <items style="AutoComplete"
           controller="Department"
           reference="ten_bo_phan%l"
           key="status = '1'"
           information="ma_bo_phan$dmbo_phan.ten_bo_phan%l"/>
  </field>

  <field name="ten_bo_phan%l" readOnly="true" external="true">
    <header v="" e=""/>
  </field>
```

### Step 2: ✅ ALWAYS ASK USER ABOUT SQL (MANDATORY!)

```
✅ Đã thêm field vào XML!

📋 Các field vừa thêm:
- ma_bo_phant (Mã bộ phận / Department Code)
- ten_bo_phan%l (Tên bộ phận / Department Name - lookup)

❓ Bạn có muốn tôi generate SQL để thêm field vào database không?
(Ví dụ: Thêm vào bảng d66$, m66$, hoặc i66$?)
```

### Step 3: Generate SQL (If User Confirms)

```
User: "Có, thêm vào d91$ và m91$"

→ Tool: generate_sql_for_fields
  Parameters:
    - field_names: ['ma_bo_phant', 'ten_bo_phan%l']
    - tables: ['d91$', 'm91$']

→ MCP generates SQL:

-- Thêm vào detail table d91$ (partitioned - có $)
exec fsd_addfields 'd91$', 'ma_bo_phan', 'varchar(33)'
exec fsd_addfields 'd91$', 'ten_bo_phan%l', 'nvarchar(256)'

-- Thêm vào master table m91$ (partitioned - có $)
exec fsd_addfields 'm91$', 'ma_bo_phan', 'varchar(33)'
exec fsd_addfields 'm91$', 'ten_bo_phan%l', 'nvarchar(256)'

-- Tạo bảng master dmbo_phan (nếu chưa có)
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'dmbo_phan')
BEGIN
  CREATE TABLE dmbo_phan (
    ma_bo_phan varchar(33) PRIMARY KEY,
    ten_bo_phan nvarchar(256),
    status varchar(1) DEFAULT '1'
  )
END

✅ SQL đã được generate!
📋 Copy và chạy trong SQL Server Management Studio
⚠️ Chạy SQL trước khi deploy XML file lên server!
```

---

## 🔧 Available MCP Tools

### 1. generate_field_from_lmdb

**Purpose:** Generate XML field from LMDB database with auto-detection

**Parameters:**
- `field_name` (required): Field name without suffix (e.g., 'ma_kh', 'so_luong')
- `file_path` (recommended): Current file path for auto-detecting context
- `xml_content` (fallback): Current XML content if file_path not available
- `context_type` (optional): Manual override: DIR, FILTER_VOUCHER, GRID_VIEW, etc.
- `lookup_type` (optional): 'default', 'autocomplete', or 'lookup'

**Example:**
```
User: "Thêm trường mã khách hàng dạng lookup"
→ field_name='ma_kh', lookup_type='autocomplete', file_path='...\Dir\AITran.xml'
```

### 2. search_lmdb_fields

**Purpose:** Search for existing fields in database by pattern

**Parameters:**
- `pattern` (required): Search pattern (substring match)
- `context_type` (required): DIR, FILTER_VOUCHER, etc.
- `limit` (optional): Maximum results (default: 20)

**Example:**
```
search_lmdb_fields(pattern='ma_kh', context_type='DIR', limit=10)
```

### 3. lmdb_database_stats

**Purpose:** Get statistics about the LMDB field database

**Example:**
```
lmdb_database_stats()
→ Shows field count by context type
```

### 4. generate_sql_for_fields (NEW)

**Purpose:** Generate `fsd_addfields` SQL commands for database schema updates

**Parameters:**
- `field_names` (required): List of field names to add
- `tables` (required): List of table names (e.g., ['d91$', 'm91$'])
- `file_path` (optional): XML file path to extract table names automatically
- `xml_content` (optional): XML content to extract table names

**Auto-Detects:**
- SQL type from field name pattern
- Partitioned table (preserve `$` suffix)
- Master table creation for lookup fields

**Example:**
```
generate_sql_for_fields(
  field_names=['ma_bo_phan', 'ten_bo_phan%l'],
  tables=['d91$', 'm91$']
)
```

---

## ⚠️ Common Mistakes to Avoid

| ❌ Mistake | ✅ Correct | Impact |
|---|---|---|
| Hardcoded `m66$202411` | Use `m66$$partition$current` | Data loss when month changes |
| `exec fsd_addfields 'd91', ...` when XML has `d91$` | `exec fsd_addfields 'd91$', ...` | Table not found error |
| `exec fsd_addfields 'dmvt$', ...` when XML has `dmvt` | `exec fsd_addfields 'dmvt', ...` | Table not found error |
| Forget to ask user about SQL generation | Always ask after XML field is added | User forgets to update database |
| Wrong SQL type for field | Use auto-detection patterns | Data type mismatch errors |

---

## 📞 When to Ask User for Clarification

- Field name or terminology unclear → Ask for Vietnamese/English labels
- Which table to add field to? → Ask `"Thêm vào bảng nào? (Ví dụ: d93$, m91$, i91$)"`
- SQL generation needed? → **Always ask before generating**
- Multiple tables? → Ask which tables need the field (master, detail, inquiry)
- Lookup field needs master table? → Ask if master data table exists

---

## 📋 Key Files to Reference

- **`LMDB_FIELD_DATABASE.md`** - LMDB field database documentation
- **`scripts/import_fields_to_lmdb.py`** - Import fields from XML to LMDB
- **`fastbusiness_mcp/lmdb_adapter/xml_parser.py`** - XML parsing with regex only
- **`fastbusiness_mcp/tools/generate_field_from_lmdb.py`** - LMDB field generation tool

---

## 🎓 Quick Reference

### Field Naming Patterns → SQL Types

```
ma_*       → varchar(33)
ten_*      → nvarchar(256)
ngay_*     → smalldatetime
tien*      → numeric(19,4)
*_nt       → numeric(19,4)
so_luong   → numeric(19,4)
thang/nam  → int
status     → tinyint
*%l        → nvarchar(256)
```

### Table Name → fsd_addfields

```
d91$000000 → exec fsd_addfields 'd91$', ...
m91$000000 → exec fsd_addfields 'm91$', ...
dmvt       → exec fsd_addfields 'dmvt', ...
dmkh       → exec fsd_addfields 'dmkh', ...
```

### Workflow Summary

```
1. User requests field
   ↓
2. generate_field_from_lmdb (auto-detect context + lookup type)
   ↓
3. Ask user about SQL generation
   ↓
4. generate_sql_for_fields (auto-detect SQL types + preserve $)
   ↓
5. User runs SQL in SSMS
   ↓
6. Deploy XML to server
```

---

**Last Updated:** November 2024
**MCP Version:** 3.0 (LMDB Field Generation Only)
