# FastBusiness MCP Server - AI Coding Agent Instructions

**Project:** FastBusiness XML Controller Configuration & SQL Server Integration  
**Language:** XML, T-SQL, ES5 JavaScript  
**Version:** 1.0 - November 2024

---

## 🎯 Project Overview

FastBusiness is an enterprise accounting/ERP system. This repository contains:
- **XML Configurations** (`App_Data/Controllers/Dir/`, `App_Data/Controllers/GridView/`) - Form definitions, field layouts, event handlers
- **MCP Server** - Model Context Protocol server providing AI assistance for FastBusiness development
- **SQL Utilities** - Field generation, partition management

### Critical Constraints
1. **XML files MUST include partition references** - Use `$partition$current`, `$partition$previous`, `@@prime$partition$current` patterns
2. **ES5 JavaScript only** - No arrow functions, `const`, `let`, `async/await`, template literals, or spread operators
3. **SQL column access by INDEX only** - `result[0].Value` not `result[0].ma_kh`
4. **Always generate SQL after XML changes** - Database schema must match XML configuration

---

## 📁 File Type Detection & Workflows

### File Types in `App_Data/Controllers/`

| File Pattern | Type | Purpose | Key Characteristics |
|---|---|---|---|
| `Dir/` | **DIR** | Master/Detail form entry | Master table with nested detail grid, full CRUD |
| `GridView/` | **GRID_VIEW** | Read-only grid display | Sorting, filtering, no editing |
| `Filter/` | **FILTER** | Search/filter criteria | No detail table, read-only result |
| `*.ent` | **ENTITY** | Reusable template fragments | SQL, XML, or JavaScript blocks |

**Detection method:**
```xml
<!-- DIR: Has <dir> root and <commands> section -->
<dir table="m66$000000" code="stt_rec">
  <fields>...</fields>
  <views>...</views>
  <commands>...</commands>
</dir>

<!-- GRID_VIEW: <grid> root, display-only -->
<grid table="i66$000000">
  <columns>...</columns>
</grid>

<!-- FILTER: <filter> root -->
<filter table="c93$000000">
  <fields>...</fields>
</filter>
```

---

## 🔑 Essential Patterns

### 1. Partition Pattern (CRITICAL)

FastBusiness partitions data by date. **All tables use partition suffixes:**

```xml
<!-- Partition table reference pattern -->
<partition table="c66$000000" prime="m66$" inquiry="i66$" 
           field="ngay_ct" 
           expression="convert(char(6), {0}, 112)" 
           increase="dateadd(month, 1, {0})" />

<!-- In SQL/JavaScript: Replace $partition$current with actual partition -->
<!-- Example: m66$202411 = November 2024 partition -->

<!-- Dynamic references in SQL (DO NOT hardcode partition!) -->
insert into d66$$partition$current select * from @d66
update @@master set ngay_ct = @ngay_ct where stt_rec = @stt_rec
delete d66$$partition$previous where stt_rec = @stt_rec

<!-- $$ = double dollar = automatic partition replacement -->
<!-- @@master = prime master table variable -->
<!-- @@prime$partition$current = current partition reference -->
```

**VIOLATION RULES:**
- ❌ NEVER write `m66$202411` directly - Use `m66$$partition$current`
- ❌ NEVER write `d66$202411` - Use `d66$$partition$current`
- ❌ Hardcoded partitions break when month changes!

### 2. DataFormatString Auto-Detection

**CRITICAL:** Always detect and add correct dataFormatString based on field naming and context.

**Detection Logic:**
```
Context: Is it a <view> section (display)? Or <fields> section (input)?
Pattern Match: Check field name prefix/suffix

| Pattern | View Format | Input Format | Example |
|---------|-------------|--------------|---------|
| so_luong, _sl$ | @quantityViewFormat | @quantityInputFormat | so_luong, sl_xuat |
| ^tien, _tien$, ^t_ (NO _nt) | @baseCurrencyAmountViewFormat | @baseCurrencyAmountInputFormat | tien, t_tien |
| _nt$ | @foreignCurrencyAmountViewFormat | @foreignCurrencyAmountInputFormat | tien_nt |
| ^gia, don_gia (NO _nt) | @baseCurrencyPriceViewFormat | @baseCurrencyPriceInputFormat | gia, don_gia |
| gia.*_nt$ | @foreignCurrencyPriceViewFormat | @foreignCurrencyPriceInputFormat | gia_nt |
| ty_gia | @exchangeRateViewFormat | @exchangeRateInputFormat | ty_gia |
| ^ngay_, _date$ | @datetimeFormat | @datetimeFormat | ngay_ct, ngay_lct |
| ^ma_ | @upperCaseFormat | @upperCaseFormat | ma_kh, ma_vt |
```

**SPECIAL RULE:** User says "thêm tiền ngoại tệ"? → Add `_nt` suffix ALWAYS!

```xml
<!-- ✅ CORRECT -->
<field name="tien_nt" type="Decimal" dataFormatString="@foreignCurrencyAmountInputFormat">

<!-- ❌ WRONG - Missing _nt suffix -->
<field name="tien" type="Decimal" dataFormatString="@foreignCurrencyAmountInputFormat">
```

### 3. SQL Type Detection from Field Names

When generating SQL (after XML field creation), auto-detect column type:

```sql
| Field Pattern | SQL Type | Examples |
| ^ma_ | varchar(33) | ma_kh, ma_vt, ma_bp |
| ^ten_, ^mo_ta, ^ghi_chu, _text$ | nvarchar(256) | ten_kh, ghi_chu |
| ^ngay_, _date$ | smalldatetime | ngay_ct, ngay_lct |
| ^tien, _tien$, ^gia, _gia$ (NO _nt) | numeric(19,4) | tien, t_tien, gia |
| _nt$ | numeric(19,4) | tien_nt, gia_nt |
| ^so_luong, _luong$, _sl$ | numeric(19,4) | so_luong, sl_xuat |
| ^thang$, ^nam$, ^so_ngay, _count$ | int | thang, nam, so_ngay |
| ^check_, ^is_, ^status$ | tinyint | status, is_active |
| Default | nvarchar(256) | All others |
```

### 4. Event Handler JavaScript Patterns (ES5 ONLY!)

```javascript
/* ✅ CORRECT - ES5 JavaScript */
function active$Form$(f) {
  // Variables: ALWAYS use 'var', NEVER 'const'/'let'
  var maKH = f.getItemValue('ma_kh');
  var ngayLCT = f.getItemValue('ngay_lct');

  // Date: Use 'new Date()'
  f.setItemValue('ngay_lct', new Date());

  // Conditions
  if (f._action === 'New') {
    f.setItemValue('status', '0');
  }

  // String concatenation: 'a' + 'b' NOT template literals
  var msg = 'Mã khách: ' + maKH + ', Ngày: ' + ngayLCT;

  // Function callbacks: Use function(){}, NOT arrow =>
  setTimeout(function() {
    f.getItem('ma_kh').focus();
  }, 100);
}

function on$Form$ResponseComplete(sender, e) {
  var result = e.type.Result;

  // SQL Result Access: MUST use INDEX, NOT property names!
  // SQL: select ma_kh, ten_kh, dia_chi from dmkh
  var maKH = result[0].Value;    // Index 0
  var tenKH = result[1].Value;   // Index 1
  var diaChi = result[2].Value;  // Index 2

  f.setItemValue('ten_kh', tenKH);
}

/* ❌ WRONG - ES6 Features (NOT Supported!) */
// const x = 5;           // NO const!
// let y = 10;            // NO let!
// const fn = () => {};   // NO arrow functions!
// `string ${x}`;         // NO template literals!
// await someFunction();   // NO async/await!
// ...obj;                // NO spread operator!
```

### 5. Grid Detail Access Pattern

```javascript
// Grid is nested in parent form - MUST access parent form first!
function load$GridDetail$(g) {
  var f = g.get_element().parentForm;  // ← CRITICAL!

  // Now can reference parent fields with $ prefix
  var tyGia = f.getItemValue('ty_gia');

  // Use $ prefix in calculations to access parent fields
  g.$a = {
    tien: '[tien]:=[so_luong]*[gia]',
    gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]'  // $ = parent field
  };
}
```

---

## 🚀 Complete Workflow: Add Field

### Step 1: Generate XML Field

```
User: "Thêm trường mã bộ phận"

→ Check file type: Use mcp_fastbusiness_detect_file_type
→ Generate field: Use mcp_fastbusiness_generate_field
  Field name: ma_bo_phan
  Type: String (AutoComplete lookup)
  DataFormatString: @upperCaseFormat (^ma_ pattern)
→ Add to <fields> section
→ Add to <view> item display
```

### Step 2: Always Ask About SQL

After XML field is added:
```
✅ Đã thêm field vào XML!

❓ Bạn có muốn tôi generate SQL để thêm field vào database không?
(Ví dụ: Thêm vào bảng d93)
```

### Step 3: Generate SQL Based on Field Name

```sql
-- Auto-detect from field name: ma_bo_phan → varchar(33)
exec fsd_addfields 'd93', 'ma_bo_phan', 'varchar(33)'

-- For lookup field, also create master table if needed
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'dmbo_phan')
BEGIN
  CREATE TABLE dmbo_phan (
    ma_bo_phan varchar(20) PRIMARY KEY,
    ten_bo_phan nvarchar(100),
    status varchar(1) DEFAULT '1'
  )
END
```

---

## 📋 Key Files to Reference

- **`docs/INSTRUCTOR_GUIDE.instructions.md`** - Complete reference for all patterns
- **`App_Data/Controllers/Dir/SI2Tran.xml`** - Example: Sales Invoice Order form (master-detail)
- **`App_Data/Controllers/GridView/`** - Example: Read-only grid display patterns
- **MCP Tools:** `mcp_fastbusiness_detect_file_type`, `mcp_fastbusiness_generate_field`, `mcp_fastbusiness_validate_partition`

---

## ⚠️ Common Mistakes to Avoid

| ❌ Mistake | ✅ Correct | Impact |
|---|---|---|
| Hardcoded `m66$202411` | Use `m66$$partition$current` | Data loss when month changes |
| Access SQL result: `result[0].ma_kh` | Use `result[0].Value` at correct index | Returns undefined |
| Use ES6 in JavaScript | Use ES5 only (function, var) | Code breaks in production |
| Forget `_nt` suffix for foreign currency | Always add `_nt` when needed | Wrong format applied |
| Grid detail accesses parent without `f.get_element().parentForm` | Get parent form first | Null reference error |
| Missing dataFormatString | Auto-detect from field name | Display format broken |

---

## 🔧 Essential MCP Commands

When working on FastBusiness files, use:

1. **`mcp_fastbusiness_detect_file_type`** - Identify DIR vs GRID_VIEW vs FILTER
2. **`mcp_fastbusiness_generate_field`** - Create XML field with correct attributes
3. **`mcp_fastbusiness_generate_script`** - Generate JavaScript template for events
4. **`mcp_fastbusiness_generate_command`** - Generate SQL command template
5. **`mcp_fastbusiness_validate_partition`** - Check for hardcoded partitions (CRITICAL!)
6. **`mcp_fastbusiness_validate_result_access`** - Check SQL result access patterns
7. **`mcp_fastbusiness_validate_xml_structure`** - Validate complete XML file

---

## 📞 When to Ask User for Clarification

- Field name or terminology unclear → Ask for Vietnamese/English labels
- Which table to add field to? → Ask `"Thêm vào bảng nào? (Ví dụ: d93, m91)"`
- SQL generation needed? → Always ask before generating
- Partition-specific logic needed? → Ask if field should handle month changes
- Event handler requirements? → Ask what should trigger the handler

---

## 🎓 Learning Path for New Changes

1. Read this file first (you are here!)
2. Check `docs/INSTRUCTOR_GUIDE.instructions.md` for detailed examples
3. Search similar fields in existing XML files (e.g., SI2Tran.xml)
4. Use MCP validation tools before committing
5. Always generate and test SQL changes in isolated partition first
