# Workflow: Add JavaScript Handlers to XML Fields

## ⚠️ CRITICAL: When to Use Snippet Tools

When user says **ANY** of these phrases:
- "Thêm xử lý khi nhập X" / "Add handler when entering X"
- "Khi nhập X thì Y" / "When X is entered then Y"
- "Thêm onChange cho X" / "Add onChange to X"
- "Thêm onFocus cho X" / "Add onFocus to X"
- "Khi focus X thì Y" / "When X is focused then Y"

→ **YOU MUST USE**: `add_clientscript_to_field` + `add_function_to_script` tools!

## ❌ What NOT to Do

**DO NOT** write XML manually like this:
```xml
<!-- WRONG! Don't do this! -->
<field name="so_ct_hd">
  <header>...</header>
  <clientScript>onchange="..."</clientScript>  <!-- You will get position wrong! -->
</field>
```

**DO NOT** use code assistant to generate clientScript XML!

**DO NOT** insert function outside CDATA!

## ✅ Correct Workflow (3 Steps)

### Step 0: Understand the Request

User: **"Thêm xử lý khi nhập so_ct_hd thì gán so_seri_hd = '123455'"**

Parse:
- Field: `so_ct_hd`
- Event: `onChange` (vì "khi nhập")
- Logic: `f.setItemValue("so_seri_hd", "123455")`
- File type: DIR (form) → Function: `onChange$Voucher$so_ct_hd`

---

### Step 1: Get Field XML

**Tool**: `get_field_info`

```json
{
  "field_name": "so_ct_hd",
  "file_path": "e:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml"
}
```

**Result**:
```xml
<field name="so_ct_hd" dataFormatString="@upperCaseFormat" align="right">
  <header v="Số hóa đơn" e="Invoice Number"></header>
  <items style="Mask"/>
</field>
```

**Save** this as `field_xml` for next step!

---

### Step 2: Add clientScript to Field

**Tool**: `add_clientscript_to_field`

```json
{
  "field_xml": "<field name=\"so_ct_hd\" dataFormatString=\"@upperCaseFormat\" align=\"right\">\n  <header v=\"Số hóa đơn\" e=\"Invoice Number\"></header>\n  <items style=\"Mask\"/>\n</field>",
  "handler_type": "onchange",
  "function_name": "onChange$Voucher$so_ct_hd"
}
```

**Result** from server:
```json
{
  "success": true,
  "original_field": "<field name=\"so_ct_hd\">...</field>",
  "modified_field": "<field name=\"so_ct_hd\" dataFormatString=\"@upperCaseFormat\" align=\"right\">\n  <header v=\"Số hóa đơn\" e=\"Invoice Number\"></header>\n  <items style=\"Mask\"/>\n  <clientScript><![CDATA[onchange=\"onChange$Voucher$so_ct_hd(this);\"]]></clientScript>\n</field>",
  "instructions": "Replace original_field with modified_field in your editor"
}
```

**Action**: Replace `original_field` with `modified_field` in file!

**Result in file**:
```xml
<field name="so_ct_hd" dataFormatString="@upperCaseFormat" align="right">
  <header v="Số hóa đơn" e="Invoice Number"></header>
  <items style="Mask"/>
  <clientScript><![CDATA[onchange="onChange$Voucher$so_ct_hd(this);"]]></clientScript>
</field>
```

✓ clientScript in **correct position** (before `</field>`)!

---

### Step 3: Add Function to Script Section

**Tool**: `add_function_to_script`

First, generate the function code:
```javascript
function onChange$Voucher$so_ct_hd(sender) {
    var f = sender.parentForm;

    // Skip in view mode
    if (f._action === 'View') {
        return;
    }

    // User's logic
    f.setItemValue("so_seri_hd", "123455");
}
```

Then call tool:
```json
{
  "function_code": "function onChange$Voucher$so_ct_hd(sender) {\n    var f = sender.parentForm;\n\n    // Skip in view mode\n    if (f._action === 'View') {\n        return;\n    }\n\n    // User's logic\n    f.setItemValue(\"so_seri_hd\", \"123455\");\n}"
}
```

**Result** from server:
```json
{
  "success": true,
  "function_snippet": "<![CDATA[\nfunction onChange$Voucher$so_ct_hd(sender) {\n    var f = sender.parentForm;\n\n    if (f._action === 'View') {\n        return;\n    }\n\n    f.setItemValue(\"so_seri_hd\", \"123455\");\n}\n]]>\n    </text>\n</script>",
  "search_pattern": "    </text>\\n</script>",
  "instructions": "Find search_pattern and replace with function_snippet"
}
```

**Action**:
1. Find this pattern in file: `    </text>\n</script>` (with 4 spaces before `</text>`)
2. Replace it with `function_snippet`

**Before**:
```xml
  <script>
    <text><![CDATA[
    // Existing code...
    ]]>
    </text>
  </script>
```

**After**:
```xml
  <script>
    <text><![CDATA[
    // Existing code...

function onChange$Voucher$so_ct_hd(sender) {
    var f = sender.parentForm;

    if (f._action === 'View') {
        return;
    }

    f.setItemValue("so_seri_hd", "123455");
}
]]>
    </text>
  </script>
```

✓ Function **INSIDE CDATA**!
✓ Function **BEFORE `</text>`**!

---

## Function Naming Convention

### DIR Files (Form)
```
onChange: onChange$Voucher$field_name
onFocus: onFocus$Voucher$field_name

Example:
onChange$Voucher$ma_kh
onFocus$Voucher$so_ct
```

### GRID Files (Grid)

**GridView** (has `allowSorting` or `allowFilter`):
```
onChange: onChange$Grid$field_name

Example:
onChange$Grid$ma_kh
```

**GridDetail** (no `allowSorting`/`allowFilter`):
```
onChange: onChange$Voucher$GridName$field_name

Example:
onChange$Voucher$GridAPDetail$so_luong
```

### FILTER Files
```
onChange: onChange$Filter$field_name

Example:
onChange$Filter$ma_kh
```

---

## Complete Examples

### Example 1: DIR File - onChange

**User**: "Khi nhập ma_kh thì load tên khách hàng"

**Steps**:
1. `get_field_info(field_name='ma_kh', file_path='...')`
2. `add_clientscript_to_field(field_xml=..., handler_type='onchange', function_name='onChange$Voucher$ma_kh')`
3. Replace field in file
4. Generate function:
```javascript
function onChange$Voucher$ma_kh(sender) {
    var f = sender.parentForm;
    if (f._action === 'View') return;

    var ma_kh = f.getItemValue('ma_kh');
    f.request("LoadCustomerName", "LoadCustomerName", ["ma_kh"], sender);
}
```
5. `add_function_to_script(function_code=...)`
6. Find `    </text>\n</script>` and replace

**Done!**

---

### Example 2: GRID File - onChange

**User**: "Khi nhập so_luong trong grid thì tính tien = so_luong * gia"

**Steps**:
1. Detect file type: GRID (GridDetail)
2. `get_field_info(field_name='so_luong', file_path='...')`
3. `add_clientscript_to_field(field_xml=..., handler_type='onchange', function_name='onChange$Voucher$GridAPDetail$so_luong')`
4. Replace field in file
5. Generate function:
```javascript
function onChange$Voucher$GridAPDetail$so_luong(sender) {
    var g = sender.grid;
    var f = g.get_element().parentForm;  // CRITICAL: Get parent form

    var row = g._activeRow;
    var sl = g._getItemValue(row, g._getColumnOrder('so_luong'));
    var gia = g._getItemValue(row, g._getColumnOrder('gia'));

    g._setItemValue(row, g._getColumnOrder('tien'), sl * gia);
}
```
6. `add_function_to_script(function_code=...)`
7. Find `    </text>\n</script>` and replace

**Done!**

---

## Why These Tools Are Critical

### Without Tools (Manual XML):
❌ clientScript might be **after opening tag** instead of **before closing tag**
❌ Function might be **outside CDATA** instead of **inside CDATA**
❌ Function might be **after `</text>`** instead of **before `</text>`**
❌ Multiple functions might **overlap** or **duplicate**

### With Tools (Server-controlled):
✅ Server generates **100% correct XML structure**
✅ clientScript **always in correct position**
✅ Function **always inside CDATA**
✅ Function **always before `</text>`**
✅ **Zero XML structure errors**

---

## Checklist

Before responding to user's handler request, verify:

- [ ] User mentioned adding handler? (onChange/onFocus/khi nhập/khi focus)
- [ ] Called `get_field_info` to get field_xml?
- [ ] Called `add_clientscript_to_field` to add clientScript?
- [ ] Replaced field in file with modified_field?
- [ ] Generated JavaScript function code?
- [ ] Called `add_function_to_script` to wrap function in CDATA?
- [ ] Found `    </text>\n</script>` pattern in file?
- [ ] Replaced pattern with function_snippet?

**ALL CHECKED?** → You successfully added handler with 100% correct XML structure!
