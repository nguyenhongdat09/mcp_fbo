---
applyTo: '**/*.xml, **/*.ent'
---
# FastBusiness MCP Server - AI Instructor Guide v3.0

**Version:** 3.0 - Updated 2024-10-31
**Critical Updates:** SQL Generation Workflow, DataFormatString Detection, FastBusiness API Context

---

## 🎯 Purpose

This guide instructs AI assistants (Claude, Copilot, etc.) on how to work with FastBusiness XML development correctly.

**CRITICAL RULES:**
1. **Always ask about SQL generation** after generating XML fields
2. **Always use ES5 JavaScript** (no const, await, arrow functions)
3. **Always use correct FastBusiness API** (f.setItemValue, result[index].Value)
4. **Always auto-detect dataFormatString** based on field naming patterns

---

## 📋 Complete Field Generation Workflow

### Workflow: Add New Field

**Steps:**

#### Step 1: Generate XML Field
- Detect file type first
- Try `generate_field_from_db` first
- Fallback to `generate_field` if not in database
- Auto-detect dataFormatString (see rules below)

#### Step 2: **ALWAYS Ask About SQL** ⭐ NEW

After successfully generating XML field, **ALWAYS** ask user:

```
✅ Đã thêm field vào XML!

📋 Các field vừa thêm:
- ma_kh (Mã khách hàng / Customer Code)
- ten_kh (Tên khách hàng / Customer Name)
- ngay_lct (Ngày lập chứng từ / Document Date)

❓ Bạn có muốn tôi generate SQL để thêm field vào database không?
```

#### Step 3: If User Says "Yes"

Ask for table name:

```
📋 Thêm field vào bảng nào? (Ví dụ: d93, m91, i91)
```

#### Step 4: Auto-Detect Field Type & Generate SQL

Use these rules to detect SQL type:

| Pattern | SQL Type | Example |
|---------|----------|---------|
| `^ma_` | `varchar(33)` | ma_kh, ma_vt, ma_bp |
| `^ten_`, `^mo_ta`, `^ghi_chu`, `^dia_chi`, `_text$` | `nvarchar(256)` | ten_kh, ghi_chu |
| `^ngay_`, `_date$` | `smalldatetime` | ngay_ct, ngay_lct |
| `^tien`, `_tien$`, `^gia`, `_gia$`, `^t_` (NO `_nt`) | `numeric(19,4)` | tien, t_tien, gia |
| `_nt$` | `numeric(19,4)` | tien_nt, gia_nt, t_tien_nt |
| `^so_luong`, `_luong$`, `_sl$` | `numeric(19,4)` | so_luong, sl_xuat |
| `^thang$`, `^nam$`, `^so_ngay`, `_count$` | `int` | thang, nam, so_ngay |
| `^check_`, `^is_`, `^status$` | `tinyint` | status, is_active |
| **Default** | `nvarchar(256)` | Everything else |

**Generate SQL format:**

```sql
-- Thêm vào bảng d93
exec fsd_addfields 'd93', 'ma_kh', 'varchar(33)'
exec fsd_addfields 'd93', 'ten_kh', 'nvarchar(256)'
exec fsd_addfields 'd93', 'ngay_lct', 'smalldatetime'
exec fsd_addfields 'd93', 'tien_nt', 'numeric(19,4)'
exec fsd_addfields 'd93', 'so_luong', 'numeric(19,4)'
exec fsd_addfields 'd93', 'thang', 'int'
exec fsd_addfields 'd93', 'status', 'tinyint'
```

#### Step 5: Show Success Message

```
✅ SQL đã được generate!

📋 Copy đoạn SQL trên và chạy trong SQL Server Management Studio để thêm field vào database.

⚠️ Lưu ý: Chạy SQL trước khi deploy XML file lên server.
```

---

## 🎨 DataFormatString Auto-Detection Rules

**CRITICAL:** Always auto-detect and add `dataFormatString` when generating fields.

### Detection Logic

```javascript
// Context detection
var isViewContext = (fileType === "GRID_VIEW") || (section === "<view>");
var isInputContext = (fileType === "DIR") || (fileType === "FILTER") || (section === "<fields>");
```

### Format Rules

| Field Pattern | View Context | Input Context | Example Fields |
|---------------|--------------|---------------|----------------|
| `so_luong`, `_sl$` | `@quantityViewFormat` | `@quantityInputFormat` | so_luong, sl_xuat, sl_ton |
| `^tien`, `_tien$`, `^t_` (NO `_nt`) | `@baseCurrencyAmountViewFormat` | `@baseCurrencyAmountInputFormat` | tien, t_tien, tien_hang |
| `_nt$` (money) | `@foreignCurrencyAmountViewFormat` | `@foreignCurrencyAmountInputFormat` | tien_nt, t_tien_nt |
| `^gia`, `don_gia` (NO `_nt`) | `@baseCurrencyPriceViewFormat` | `@baseCurrencyPriceInputFormat` | gia, don_gia, gia_ban |
| `gia.*_nt$` | `@foreignCurrencyPriceViewFormat` | `@foreignCurrencyPriceInputFormat` | gia_nt, don_gia_nt |
| `ty_gia`, `exchange_rate` | `@exchangeRateViewFormat` | `@exchangeRateInputFormat` | ty_gia |
| `^ngay_`, `_date$` | `@datetimeFormat` | `@datetimeFormat` | ngay_ct, ngay_lct |
| `^ma_` | `@upperCaseFormat` | `@upperCaseFormat` | ma_kh, ma_vt, ma_bp |
| **Others** | `null` | `null` | ten_kh, ghi_chu |

### XML Generation Examples

#### DIR Form (Input Context)

```xml
<field name="so_luong" type="Decimal" dataFormatString="@quantityInputFormat">
  <header v="Số lượng" e="Quantity"/>
</field>

<field name="tien_nt" type="Decimal" dataFormatString="@foreignCurrencyAmountInputFormat">
  <header v="Tiền NT" e="Foreign Amount"/>
</field>

<field name="ngay_lct" type="DateTime" dataFormatString="@datetimeFormat">
  <header v="Ngày lập CT" e="Document Date"/>
</field>

<field name="ma_kh" dataFormatString="@upperCaseFormat">
  <header v="Mã khách hàng" e="Customer Code"/>
</field>
```

#### Grid View (View Context)

```xml
<field name="so_luong" dataFormatString="@quantityViewFormat" allowSorting="true">
  <header v="Số lượng" e="Quantity"/>
</field>

<field name="tien_nt" dataFormatString="@foreignCurrencyAmountViewFormat" allowSorting="true">
  <header v="Tiền NT" e="Foreign Amount"/>
</field>
```

### Special Case: Foreign Currency

**IMPORTANT:** When user says "thêm tiền ngoại tệ", ALWAYS add `_nt` suffix!

```
User: "thêm tiền ngoại tệ"
AI:
  Field name: tien_nt  ← MUST have _nt suffix
  Type: Decimal
  Format: @foreignCurrencyAmountInputFormat
```

❌ **WRONG:**
```
Field name: tien  ← Missing _nt!
```

---

## 🔧 FastBusiness JavaScript API Rules

**CRITICAL:** FastBusiness uses **ES5 JavaScript** (old version). **NEVER** use:
- ❌ `const`, `let` (use `var` only)
- ❌ `await`, `async`
- ❌ Arrow functions `() =>`
- ❌ Template literals `` `${x}` ``
- ❌ Spread operator `...`
- ❌ `Promise`

**ALWAYS use:**
- ✅ `var` for variables
- ✅ `function` keyword
- ✅ `'string' + variable` for concatenation
- ✅ Callbacks, not Promises

### Form API

#### ✅ CORRECT - Get/Set Values

```javascript
function active$Form$(f) {
  // Get value
  var maKH = f.getItemValue('ma_kh');
  var ngayLCT = f.getItemValue('ngay_lct');

  // Set value
  f.setItemValue('ma_vv', 'AA');
  f.setItemValue('status', 1);

  // Set date
  f.setItemValue('ngay_lct', new Date());

  // Focus field
  f.getItem('ma_kh').focus();

  // Check action
  if (f._action === 'New') {
    f.setItemValue('ngay_lct', new Date());
  }

  // Check if value empty
  if (maKH === '' || maKH === null) {
    alert('Vui lòng nhập mã khách hàng');
    return false;
  }
}
```

#### ❌ WRONG - Don't Do This

```javascript
// ❌ Direct field access
f.fields.ma_kh.value = 'x'; // WRONG!

// ❌ DOM access
document.getElementById('ma_kh').value = 'x'; // WRONG!

// ❌ Direct property
f.ma_kh = 'x'; // WRONG!

// ❌ ES6 syntax
const maKH = f.getItemValue('ma_kh'); // NO const!
```

### Grid Detail API (Embedded in Form)

#### ✅ CORRECT - Access Parent Form

```javascript
function load$GridVoucherDetail$(g) {
  // CRITICAL: MUST get parent form first!
  var f = g.get_element().parentForm;

  // Now can access parent fields
  var tyGia = f.getItemValue('ty_gia');
  var maVT = f.getItemValue('ma_vt');

  // Set calculations with parent field (use $ prefix)
  g.$a = {
    tien: '[tien]:=[so_luong]*[gia]',
    gia_vnd: '[gia_vnd]:=[gia_nt]*[$ty_gia]', // $ = parent field!
    tien_vnd: '[tien_vnd]:=[so_luong]*[gia_vnd]'
  };
}
```

#### ❌ WRONG - Grid Detail Mistakes

```javascript
// ❌ Access parent field directly from grid
var tyGia = g.getItemValue('ty_gia'); // Grid doesn't have this field!

// ❌ Forget to get parent form
g.$a = {
  gia_vnd: '[gia_vnd]:=[gia_nt]*[ty_gia]' // Missing $ prefix!
};

// ❌ Missing parentForm
var f = g.parentForm; // Must use g.get_element().parentForm
```

### SQL Result Access API

#### ✅ CORRECT - Access by Index

```javascript
function on$Form$ResponseComplete(sender, e) {
  if (e.type.Context === 'GetCustomer') {
    var result = e.type.Result;

    // SQL Query: select ma_kh, ten_kh, dia_chi from dmkh
    // CRITICAL: Access by INDEX, not property name!
    var maKH = result[0].Value;   // Index 0 = ma_kh
    var tenKH = result[1].Value;  // Index 1 = ten_kh
    var diaChi = result[2].Value; // Index 2 = dia_chi

    // Set to form
    f.setItemValue('ten_kh', tenKH);
    f.setItemValue('dia_chi', diaChi);
  }
}
```

**Column Mapping Comments:**

Always add comments to explain column mapping:

```javascript
// SQL: select ma_kh, ten_kh, dia_chi, dien_thoai from dmkh
var maKH = result[0].Value;    // ma_kh
var tenKH = result[1].Value;   // ten_kh
var diaChi = result[2].Value;  // dia_chi
var dienThoai = result[3].Value; // dien_thoai
```

#### ❌ WRONG - Property Access

```javascript
// ❌ Access by property name (DOESN'T WORK!)
var maKH = result[0].ma_kh; // UNDEFINED!
var tenKH = result[0]['ten_kh']; // UNDEFINED!

// ❌ Using object destructuring (ES6)
var {ma_kh, ten_kh} = result[0]; // ES6 not supported!
```

### Grid View API (Standalone)

#### ✅ CORRECT

```javascript
function load$CustomerGrid$(g) {
  // Get active row
  var row = g._activeRow;

  // Get column order
  var colMaKH = g._getColumnOrder('ma_kh');
  var colTenKH = g._getColumnOrder('ten_kh');

  // Get value
  var maKH = g._getItemValue(row, colMaKH);
  var tenKH = g._getItemValue(row, colTenKH);
}
```

---

## 🎯 Complete Workflow Examples

### Example 1: Add Field with SQL

```
User: "Thêm tiền ngoại tệ vào form"

AI:
Step 1: Detect file type
[detect_file_type] → Result: DIR

Step 2: Generate field
[generate_field_from_db or generate_field]
Field name: tien_nt  ← Auto add _nt suffix!
Type: Decimal
Format: @foreignCurrencyAmountInputFormat

<field name="tien_nt" type="Decimal" dataFormatString="@foreignCurrencyAmountInputFormat">
  <header v="Tiền ngoại tệ" e="Foreign Currency Amount"/>
</field>

✅ Đã thêm field vào XML!

📋 Các field vừa thêm:
- tien_nt (Tiền ngoại tệ / Foreign Currency Amount)

❓ Bạn có muốn tôi generate SQL để thêm field vào database không?

User: "có, thêm vào d93"

AI:
-- Thêm vào bảng d93
exec fsd_addfields 'd93', 'tien_nt', 'numeric(19,4)'

✅ SQL đã được generate!
📋 Copy đoạn SQL trên và chạy trong SQL Server Management Studio.
```

### Example 2: Add Event Handler

```
User: "Thêm xử lý nhập ngày lập chứng từ khi tạo mới"

AI:
Step 1: Find field location
[Quick search for 'ngay_lct' field]

Step 2: Generate handler code (ES5 JavaScript!)

<script>
<text><![CDATA[
function active$Form$(f) {
  // Auto-fill ngày lập chứng từ when creating new
  if (f._action === 'New') {
    f.setItemValue('ngay_lct', new Date());
  }
}
]]></text>
</script>

✅ Code đã được thêm!

⚠️ Lưu ý:
- Sử dụng var, không dùng const/let
- Sử dụng f.setItemValue() để set giá trị
- Code JavaScript phiên bản cũ (ES5)
```

### Example 3: Grid Detail with Parent Field

```
User: "Trong grid detail, tính tiền VND = số lượng * giá NT * tỷ giá (tỷ giá ở form cha)"

AI:
<script>
<text><![CDATA[
function load$GridVoucherDetail$(g) {
  // CRITICAL: Get parent form first
  var f = g.get_element().parentForm;

  // Set calculation formulas
  g.$a = {
    // Basic calculation
    tien_nt: '[tien_nt]:=[so_luong]*[gia_nt]',

    // Using parent field ($ prefix!)
    tien_vnd: '[tien_vnd]:=[so_luong]*[gia_nt]*[$ty_gia]'
  };
}
]]></text>
</script>

✅ Code đã được thêm!

📋 Giải thích:
- var f = g.get_element().parentForm → Lấy form cha
- [$ty_gia] → $ nghĩa là field ở form cha
- Công thức: tien_vnd = so_luong * gia_nt * ty_gia (từ form cha)
```

---

## 🚫 Common Mistakes - MUST AVOID

### Mistake 1: Not Asking About SQL

❌ **Wrong:**
```
User: "thêm mã khách hàng"
AI: [generates XML field only]
    [doesn't ask about SQL]
```

✅ **Correct:**
```
User: "thêm mã khách hàng"
AI: [generates XML field]
    ✅ Đã thêm field vào XML!
    ❓ Bạn có muốn tôi generate SQL để thêm vào database không?
```

### Mistake 2: Missing _nt Suffix

❌ **Wrong:**
```
User: "thêm tiền ngoại tệ"
AI: Field name: tien  ← Missing _nt!
```

✅ **Correct:**
```
User: "thêm tiền ngoại tệ"
AI: Field name: tien_nt  ← Has _nt suffix
    Format: @foreignCurrencyAmountInputFormat
```

### Mistake 3: Using ES6 JavaScript

❌ **Wrong:**
```javascript
const maKH = f.getItemValue('ma_kh'); // NO const!
const tenKH = f.getItemValue('ten_kh');

f.setItemValue('info', `${maKH} - ${tenKH}`); // NO template literals!
```

✅ **Correct:**
```javascript
var maKH = f.getItemValue('ma_kh'); // Use var
var tenKH = f.getItemValue('ten_kh');

f.setItemValue('info', maKH + ' - ' + tenKH); // String concatenation
```

### Mistake 4: Wrong Result Access

❌ **Wrong:**
```javascript
// SQL: select ma_kh, ten_kh from dmkh
var maKH = result[0].ma_kh; // UNDEFINED!
```

✅ **Correct:**
```javascript
// SQL: select ma_kh, ten_kh from dmkh
var maKH = result[0].Value;  // Index 0
var tenKH = result[1].Value; // Index 1
```

### Mistake 5: Missing Parent Form in Grid Detail

❌ **Wrong:**
```javascript
function load$GridDetail$(g) {
  var tyGia = g.getItemValue('ty_gia'); // Grid doesn't have this!
}
```

✅ **Correct:**
```javascript
function load$GridDetail$(g) {
  var f = g.get_element().parentForm; // Get parent first!
  var tyGia = f.getItemValue('ty_gia'); // Now can access
}
```

---

## 📊 Field Type Detection Reference

### Quick Reference Table

| Field Name Pattern | SQL Type | XML Type | Format |
|--------------------|----------|----------|--------|
| ma_kh | varchar(33) | String | @upperCaseFormat |
| ten_kh | nvarchar(256) | String | - |
| ngay_ct | smalldatetime | DateTime | @datetimeFormat |
| so_luong | numeric(19,4) | Decimal | @quantityInputFormat |
| tien | numeric(19,4) | Decimal | @baseCurrencyAmountInputFormat |
| tien_nt | numeric(19,4) | Decimal | @foreignCurrencyAmountInputFormat |
| gia | numeric(19,4) | Decimal | @baseCurrencyPriceInputFormat |
| gia_nt | numeric(19,4) | Decimal | @foreignCurrencyPriceInputFormat |
| ty_gia | numeric(19,4) | Decimal | @exchangeRateInputFormat |
| thang | int | Int32 | - |
| status | tinyint | Int16 | - |

---

## ✅ Success Checklist

Before completing any field generation task:

- [ ] Generated XML field with correct type
- [ ] Auto-detected and added dataFormatString
- [ ] **Asked user about SQL generation** ⭐
- [ ] If SQL: auto-detected field type and generated exec fsd_addfields
- [ ] Generated companion field if lookup type
- [ ] Used ES5 JavaScript (no const, await, arrow functions)
- [ ] Used correct API (f.setItemValue, result[index].Value)
- [ ] Added parent form access if Grid Detail
- [ ] Added column mapping comments if ResponseComplete

---

**Version History:**
- v3.0 (2024-10-31): Added SQL workflow, dataFormatString detection, FastBusiness API rules
- v2.0 (2024-10-31): Added LevelDB integration
- v1.0 (2024-10-30): Initial version

**This guide ensures AI generates correct, production-ready FastBusiness code.**
