# FastBusiness MCP Server - AI Coding Agent Instructions

**Project:** FastBusiness XML Controller Configuration & SQL Server Integration  
**Language:** XML, T-SQL, ES5 JavaScript  
**Version:** 2.0 - November 2024  
**Last Updated:** Based on INSTRUCTOR_GUIDE v3.0

---

## 🎯 Project Overview

FastBusiness is an enterprise accounting/ERP system with partition-based data architecture. This repository contains:
- **XML Controllers** (`App_Data/Controllers/`) - Dynamically-generated forms, grids, and filters
- **MCP Server** (`fastbusiness_mcp/`) - Provides AI context and code generation tools
- **Reference Documentation** (`docs/INSTRUCTOR_GUIDE.instructions.md`) - Complete pattern reference
- **Partition Strategy** - Data segmented by month with dynamic table routing

### Critical Constraints (NON-NEGOTIABLE)
1. **Partition References MANDATORY** - ALWAYS use `$partition$current`, `$partition$previous`, `@@prime$partition$current`  
   **❌ NEVER hardcode:** `m66$202411` (data loss when month rolls over)
2. **ES5 JavaScript ONLY** - No `const`, `let`, `await`, arrow functions, template literals, spread operators
3. **SQL Result Access by INDEX** - `result[0].Value` for column 1, `result[1].Value` for column 2, NOT `result[0].field_name`
4. **Always Ask About SQL** - After generating XML field, ALWAYS ask if user wants SQL generation
5. **Auto-Detect DataFormatString** - Field naming patterns determine display format automatically

---

## 📁 Architecture: Four File Types

FastBusiness has exactly **4 file type patterns**. Always detect first:

### Detection Algorithm (Priority Order)

```
1. Check <dir type="Report"> + XMLWhenFilterLoading ENTITY  → FILTER
2. Check <grid type="Detail"> without <toolbar>            → GRID DETAIL
3. Check <grid> + <queries> + <toolbar>                    → GRID VIEW
4. Check <dir type="Voucher|Category"> with <commands>     → DIR (Form)
```

### 1. FILTER (Search/Report Criteria)

**Purpose:** Read-only search form that runs SQL on "Processing" event  
**Signature:** `<dir type="Report" cache="true">`  
**Key Event:** `<command event="Processing">` - executes report query  
**No Detail Grid** - No master/detail  
**Example:** Customer search form, date range filter for reports

```xml
<dir type="Report" cache="true">
  <fields><!-- Simple input fields only --></fields>
  <command event="Processing">
    <!-- SQL: select data with @filters -->
    <!-- Returns: Result set displayed in read-only grid -->
  </command>
</dir>
```

### 2. DIR - Master/Detail Form (CRUD Entry)

**Purpose:** Create/Read/Update/Delete business documents  
**Signature:** `<dir type="Voucher">` or `<dir type="Category">`  
**Key Events:** `Inserting`, `Updating`, `Deleting`, `Loading`  
**Has Detail Grid** - Embedded `<field name="d91" ... grid>`  
**SQL Access:** Master table `m91$`, Detail table `d91$`, Inquiry table `i91$`  
**Lifecycle:** `init$Form()` → `active$Form()` → `close$Form()`  
**Example:** Sales Invoice form (header + line items), Customer master form

```xml
<dir table="m91$000000" code="stt_rec" type="Voucher">
  <partition table="c91$000000" prime="m91$" inquiry="i91$" field="ngay_ct"/>
  <fields>
    <!-- Master fields: ma_kh, ngay_lct, etc -->
    <!-- Detail field: <field name="d91" ... > (embedded grid) -->
  </fields>
  <commands>
    <command event="Inserting"><!-- SQL: insert with partition --></command>
    <command event="Updating"><!-- SQL: update with partition --></command>
  </commands>
</dir>
```

### 3. GRID DETAIL - Embedded Multi-Row Table

**Purpose:** Nested grid inside DIR form for line items  
**Signature:** `<grid type="Detail">` WITHOUT `<toolbar>` or `<queries>`  
**Key Events:** No LoadingQuery - data from parent form's detail field  
**Calculations:** `g.$a = { field_name: 'calculation_formula' }`  
**Access Parent:** **CRITICAL:** `var f = g.get_element().parentForm;`  
**Example:** Invoice line items in header form, PO lines in purchase order

```xml
<!-- Inside DIR's field definition -->
<field name="d91" external="true" rows="144">
  <items style="Grid" controller="SalesInvoiceDetail">
    <item value="ForeignKey">
      <text v="String: stt_rec, stt_rec"/>
    </item>
  </items>
</field>

<!-- Separate grid XML file -->
<grid type="Detail">
  <script>
    <text><![CDATA[
    function load$GridDetail$(g) {
      var f = g.get_element().parentForm;  // ← CRITICAL!
      g.$a = {
        tien: '[tien]:=[so_luong]*[gia]',
        tien_vnd: '[tien_vnd]:=[so_luong]*[gia]*[$ty_gia]'  // $ = parent
      };
    }
    ]]></text>
  </script>
</grid>
```

### 4. GRID VIEW - Read-Only Display Grid

**Purpose:** Master data display with search/filter/export (no editing)  
**Signature:** `<grid>` + `<queries>` + `<toolbar>`  
**Key Event:** `<query event="Loading">` - executes ListingQuery stored proc  
**Toolbar:** Standard buttons (Insert, Edit, Delete, Export, Print, etc)  
**Lifecycle:** `load$Grid()` → `scattering$Grid()` → `dispose$Grid()`  
**Example:** Customer list grid, Sales order browse, Transaction history

```xml
<grid table="i91$000000" type="Category">
  <partition table="c91$000000" prime="i91$" field="ngay_ct"/>
  <queries>
    <query event="Loading">
      <!-- Executes stored proc that returns paginated data -->
    </query>
    <query event="Finding">
      <!-- Executes search with filters -->
    </query>
  </queries>
  <toolbar>
    <!-- Standard CRUD buttons -->
  </toolbar>
</grid>
```

---

## � Field Type Detection & Workflow

### Quick Reference Table

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

### 2. DataFormatString Auto-Detection (Context-Aware!)

**CRITICAL PATTERN:** DataFormatString is CONTEXT-AWARE - different for `<fields>` (input) vs `<view>` (display)

**Example:** Field `so_luong`
- In `<fields>` section: `dataFormatString="@quantityInputFormat"` (allows decimal input)
- In `<view>` section: `dataFormatString="@quantityViewFormat"` (display only, read-only)

**Auto-Detection Rules:**

| Field Pattern | SQL Type | Input Context | View Context | Example |
|---|---|---|---|---|
| so_luong, _sl$ | numeric(19,4) | @quantityInputFormat | @quantityViewFormat | so_luong, sl_xuat |
| ^tien, _tien$, ^t_ (NO _nt) | numeric(19,4) | @baseCurrencyAmountInputFormat | @baseCurrencyAmountViewFormat | tien, t_tien |
| _nt$ | numeric(19,4) | @foreignCurrencyAmountInputFormat | @foreignCurrencyAmountViewFormat | tien_nt, gia_nt |
| ^gia, don_gia (NO _nt) | numeric(19,4) | @baseCurrencyPriceInputFormat | @baseCurrencyPriceViewFormat | gia, don_gia |
| gia.*_nt$ | numeric(19,4) | @foreignCurrencyPriceInputFormat | @foreignCurrencyPriceViewFormat | gia_nt |
| ty_gia | numeric(19,4) | @exchangeRateInputFormat | @exchangeRateViewFormat | ty_gia |
| ^ngay_, _date$ | smalldatetime | @datetimeFormat | @datetimeFormat | ngay_ct, ngay_lct |
| ^ma_ | varchar(33) | @upperCaseFormat | @upperCaseFormat | ma_kh, ma_vt |
| ^ten_, ghi_chu | nvarchar(256) | (none) | (none) | ten_kh, ghi_chu |

**⭐ SPECIAL RULE:** User says "thêm tiền ngoại tệ"?  
- **ALWAYS add `_nt` suffix** → Field name becomes `tien_nt` (not `tien`)
- **Auto-select format** based on context

```xml
<!-- ✅ CORRECT -->
<field name="tien_nt" type="Decimal" dataFormatString="@foreignCurrencyAmountInputFormat">

<!-- ❌ WRONG - Missing _nt suffix -->
<field name="tien" type="Decimal" dataFormatString="@foreignCurrencyAmountInputFormat">
```

### 3. Partitioned Table Rule (CRITICAL for SQL Generation)

**⭐ CRITICAL RULE:** When generating SQL for field addition, check if table has `$` (partitioned):

| Situation | Rule | Example |
|---|---|---|
| Table in XML has `$` | Use `$` in fsd_addfields | `table="d81$000000"` → `exec fsd_addfields 'd81$', ...` |
| Table in XML has NO `$` | Don't add `$` | `table="dmvt"` → `exec fsd_addfields 'dmvt', ...` |

**Why?** FastBusiness tables with `$` are partitioned by month. The `$` must be preserved to ensure data routing works correctly.

```sql
-- ✅ CORRECT - Table has $ in XML, use $ in SQL
-- XML: <dir table="m81$000000" ...>
exec fsd_addfields 'd81$', 'ma_bo_phan', 'varchar(33)'
exec fsd_addfields 'd81$', 'ten_bo_phan%l', 'nvarchar(256)'

-- ✅ CORRECT - Table has NO $ in XML, don't use $ in SQL
-- XML: <dir table="dmvt" ...>
exec fsd_addfields 'dmvt', 'ma_bo_phan', 'varchar(33)'
```

### 4. SQL Type Detection from Field Names (For SQL Generation)

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
| Default | nvarchar(256) | All others |

**SQL Generation Example:**

**⭐ CRITICAL RULE:** If table has `$` (partitioned), use `$` in field command too!
- Table `d91$000000` → use `exec fsd_addfields 'd91$', ...`
- Table `dmvt` → use `exec fsd_addfields 'dmvt', ...`

```sql
-- Auto-detect from field names
-- For partitioned tables (with $ in name):
exec fsd_addfields 'd91$', 'ma_bo_phan', 'varchar(33)'     -- ^ma_ pattern
exec fsd_addfields 'd91$', 'tien_nt', 'numeric(19,4)'      -- _nt$ pattern
exec fsd_addfields 'd91$', 'so_luong', 'numeric(19,4)'     -- so_luong pattern
exec fsd_addfields 'd91$', 'ngay_lct', 'smalldatetime'    -- ngay_ pattern
exec fsd_addfields 'd91$', 'thang', 'int'                  -- ^thang$ pattern
exec fsd_addfields 'd91$', 'status', 'tinyint'            -- status pattern
```

### 5. Complete Workflow: "Add Field to Form" Request

**USER:** "Thêm trường mã bộ phận vào form đơn hàng"

**AI STEP 1: Detect File Type**
```
→ File: App_Data/Controllers/Dir/SI2Tran.xml
→ Check: <dir type="Voucher"> ✓
→ Type: DIR Form
```

**AI STEP 2: Generate XML Field**
```
→ Pattern: ^ma_ 
→ Auto-select type: String (lookup)
→ Auto-select format: @upperCaseFormat
→ Create companion field: ten_bo_phan%l (for display)

Generated:
<field name="ma_bo_phan" categoryIndex="4">
  <header v="Mã bộ phận" e="Department Code"/>
  <items style="AutoComplete" 
         controller="Department" 
         reference="ten_bo_phan%l" 
         key="status = '1'" 
         information="ma_bo_phan$dmbo_phan.ten_bo_phan%l"/>
  <clientScript><![CDATA[onchange="onChange$Voucher$Department(this);"]]></clientScript>
</field>

<field name="ten_bo_phan%l" readOnly="true" external="true" defaultValue="''">
  <header v="" e=""/>
</field>
```

**AI STEP 3: Add to View Layout**
```xml
<item value="1101000----: [ma_bo_phan].Label, [ma_bo_phan], [ten_bo_phan%l]"/>
```

⭐ **CRITICAL RULE: Lookup Fields in View Layout**

**If field has `reference="ten_bo_phan%l"`:**
- The input field (`ma_bo_phan`) and display field (`ten_bo_phan%l`) MUST be in the **SAME item**
- They go together: `[ma_bo_phan].Label, [ma_bo_phan], [ten_bo_phan%l]`
- **NEVER** separate them into different items!

```xml
<!-- ✅ CORRECT - Both fields in same item -->
<item value="1101000----: [ma_bo_phan].Label, [ma_bo_phan], [ten_bo_phan%l]"/>

<!-- ❌ WRONG - Separated into different items -->
<item value="110000000: [ma_bo_phan].Label, [ma_bo_phan]"/>
<item value="1100000000: [ten_bo_phan%l], [dien_giai]"/>
```

**Why?** FastBusiness automatically manages the display field (`%l` suffix) as a companion to the input field. They must stay together in the view layout.

**AI STEP 4: ✅ ASK USER ABOUT SQL** (MANDATORY!)
```
✅ Đã thêm field vào XML!

📋 Các field vừa thêm:
- ma_bo_phan (Mã bộ phận / Department Code)
- ten_bo_phan%l (Tên bộ phận / Department Name - lookup)

❓ Bạn có muốn tôi generate SQL để thêm field vào database không?
(Ví dụ: Thêm vào bảng d66$, m66, hoặc i66?)
```

**AI STEP 5: Generate SQL (If User Confirms)**
```
User: "Có, thêm vào d66$"

→ Detect: ^ma_ pattern
→ SQL Type: varchar(33)
→ Generate:

-- Thêm vào bảng d66$
-- Lưu ý nếu bảng có chữ $ thì thêm vô còn không thì thôi ví dụ d66$000000 thì 
exec fsd_addfields 'd66$', 'ma_bo_phan', 'varchar(33)'
Còn nếu chỉ thấy bảng dmvt thì thôi không cần thêm $ ví dụ
exec fsd_addfields 'dmvt', 'ma_bo_phan', 'varchar(33)'
exec fsd_addfields 'd66$', 'ma_bo_phan', 'varchar(33)'
exec fsd_addfields 'd66$', 'ten_bo_phan%l', 'nvarchar(256)'

-- Tạo bảng master (nếu chưa có)
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'dmbo_phan')
BEGIN
  CREATE TABLE dmbo_phan (
    ma_bo_phan varchar(20) PRIMARY KEY,
    ten_bo_phan nvarchar(100),
    status varchar(1) DEFAULT '1'
  )
END

✅ SQL đã được generate!
📋 Copy và chạy trong SQL Server Management Studio
⚠️ Chạy SQL trước khi deploy XML file lên server!
```

---

## 🔑 Essential Patterns

### 1. Partition Pattern (CRITICAL)

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

### 2. Lookup Field Pattern (CRITICAL for View Layout)

**Purpose:** AutoComplete lookup fields create automatic companion display fields  
**Pattern:** Input field + Read-only display field + View layout placement  
**CRITICAL RULE:** Input and display fields MUST appear in SAME view item, never separated!

**Complete Example - Department Code Lookup:**

```xml
<!-- Step 1: Define input field with reference attribute -->
<field name="ma_bp" categoryIndex="4">
  <header v="Mã bộ phận" e="Department Code"/>
  <items style="AutoComplete" 
         controller="Department" 
         reference="ten_bp%l"
         key="status = '1'" 
         information="ma_bp$dmbp.ten_bp%l"/>
  <clientScript><![CDATA[onchange="onChange$Voucher$Department(this);"]]></clientScript>
</field>

<!-- Step 2: Define companion display field (REQUIRED) -->
<!-- CRITICAL: Must have %l suffix, readOnly="true", external="true" -->
<field name="ten_bp%l" readOnly="true" external="true" defaultValue="''">
  <header v="" e=""/>
</field>

<!-- Step 3: Add BOTH to view layout in SAME item -->
<!-- ✅ CORRECT - Both fields in same item, consecutive -->
<item value="1101000----: [ma_bp].Label, [ma_bp], [ten_bp%l]"/>

<!-- ❌ WRONG - Fields separated into different items (breaks lookup display!) -->
<!-- DO NOT DO THIS: -->
<!-- <item value="110000000: [ma_bp].Label, [ma_bp]"/> -->
<!-- <item value="1100000000: [ten_bp%l], [dien_giai]"/> -->
```

**Why SAME Item is Critical:**
FastBusiness automatically manages companion display fields (`%l` suffix). When you create a field with `reference="ten_bp%l"`:
- The lookup input field (`ma_bp`) accepts the code/ID
- The display field (`ten_bp%l`) automatically shows the description
- They MUST stay together in view layout for the display to work
- If separated, the display field is ignored and only the code is shown

**JavaScript Handler Pattern for Lookup Fields:**

```javascript
/* ✅ CORRECT - ES5 only */
function onChange$Voucher$Department(obj) {
  var f = obj.form;  // Get parent form
  var maBp = f.getItemValue('ma_bp');
  
  // Load department details (example)
  if (maBp) {
    var req = new XMLHttpRequest();
    req.open('GET', '/AppHandler/Query.ashx?cmd=LoadDept&ma_bp=' + maBp);
    req.onload = function() {
      var result = JSON.parse(req.responseText);
      // Result column access: MUST use INDEX
      var tenBp = result[0].Value;      // Column 1
      var diaChi = result[1].Value;     // Column 2
      f.setItemValue('ten_bp%l', tenBp);
      f.setItemValue('dia_chi', diaChi);
    };
    req.send();
  }
}
```

---

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

### Step 1b: Add ONLY Direct-Related Fields ⭐ CRITICAL

**RULE:** When user requests field `ma_bp`, add ONLY:
- ✅ The requested field: `ma_bp`
- ✅ Direct-related companions: `ten_bp%l` (lookup display from `reference="ten_bp%l"`)
- ❌ NOT other fields: `dien_giai`, `ma_gd`, etc.

**Example - CORRECT:**
```xml
<!-- User: "Thêm trường ma_bp" -->
<!-- Only add ma_bp and its companion display field -->
<item value="1101000----: [ma_bp].Label, [ma_bp], [ten_bp%l]"/>
```

**Example - WRONG:**
```xml
<!-- ❌ WRONG - Added unrelated field dien_giai -->
<item value="1101000----: [ma_bp].Label, [ma_bp], [ten_bp%l]"/>
<item value="1100000000: [dien_giai].Label, [dien_giai]"/>  <!-- NOT REQUESTED! -->

<!-- ❌ WRONG - Added unrelated field ma_gd -->
<item value="1101000----: [ma_bp].Label, [ma_bp], [ten_bp%l]"/>
<item value="1101000000: [ma_gd].Label, [ma_gd], [ten_gd%l]"/>  <!-- NOT REQUESTED! -->
```

**What counts as "direct-related":**
- Display fields with `%l` suffix (auto-companion from `reference="field%l"`)
- Currency pairs: `_nt` fields (tien_nt paired with tien)
- Units/descriptions in lookup info attribute only

**What does NOT count:**
- Independent fields elsewhere in form
- Fields not mentioned in user's request
- Previously displayed fields in different view rows

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
-- ⭐ CRITICAL: Check if table has $ (partitioned)
-- If table="d93$000000" → use d93$ 
-- If table="dmvt" → use dmvt

-- Example for d93$ (partitioned table):
exec fsd_addfields 'd93$', 'ma_bo_phan', 'varchar(33)'

-- Example for dmvt (non-partitioned table):
exec fsd_addfields 'dmvt', 'ma_bo_phan', 'varchar(33)'

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
| Lookup field display in separate item | **MUST** go in same item as input | Lookup display not shown |
| `[ma_bp]` and `[ten_bp%l]` in different items | `[ma_bp], [ten_bp%l]` in SAME item | Display field ignored |
| Add unrelated fields (e.g., add `dien_giai` when user asks only for `ma_bp`) | Add ONLY requested field + direct companions (`%l` display) | Creates extra unwanted fields in view layout |

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
