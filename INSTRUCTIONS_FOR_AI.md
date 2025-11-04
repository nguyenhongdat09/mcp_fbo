# CRITICAL INSTRUCTIONS FOR AI ASSISTANTS (Cursor, VS Code, etc.)

## 🚨 READ THIS FIRST when user asks to add JavaScript handlers!

This MCP server provides **PRECISE TOOLS** to add JavaScript handlers to FastBusiness XML files.

**NEVER write XML manually!** Always use the snippet tools to ensure 100% correct XML structure.

---

## When to Use Snippet Tools

User says **ANY** of these phrases:
- "Thêm xử lý khi nhập X" / "Add handler when entering X"
- "Khi nhập X thì Y" / "When X is entered then Y"
- "Thêm onChange cho X" / "Add onChange to X"
- "Thêm onFocus cho X" / "Add onFocus to X"
- "Khi focus X thì Y" / "When X is focused then Y"

→ **YOU MUST USE**: `add_clientscript_to_field` + `add_function_to_script` tools!

---

## Required 3-Step Workflow

### Example User Request:
**"Thêm xử lý khi nhập so_ct_hd gán so_seri_hd = '123455'"**

### Step 1: Get Field XML
```
Call: get_field_info
  field_name: 'so_ct_hd'
  file_path: 'e:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\AITran.xml'

Result: field_xml
```

### Step 2: Add clientScript to Field
```
Call: add_clientscript_to_field
  field_xml: (from Step 1)
  handler_type: 'onchange'
  function_name: 'onChange$Voucher$so_ct_hd'

Result: modified_field XML with clientScript
```

**Action**: Replace original field in file with modified_field

### Step 3: Add Function to Script Section
```
Generate function:
function onChange$Voucher$so_ct_hd(sender) {
    var f = sender.parentForm;
    if (f._action === 'View') return;
    f.setItemValue("so_seri_hd", "123455");
}

Call: add_function_to_script
  function_code: (the function above)

Result: function_snippet with CDATA wrapper
```

**Action**:
1. Find pattern `    </text>\n</script>` in file
2. Replace it with function_snippet

---

## Function Naming Rules

**DIR files (form)**:
- onChange: `onChange$Voucher$field_name`
- onFocus: `onFocus$Voucher$field_name`

**GRID files**:
- GridView: `onChange$Grid$field_name`
- GridDetail: `onChange$Voucher$GridName$field_name`

**FILTER files**:
- onChange: `onChange$Filter$field_name`

---

## Why These Tools Are CRITICAL

### ❌ Without Tools (Manual XML):
- clientScript might be in **wrong position**
- Function might be **outside CDATA**
- Function might be **after `</text>`**
- Multiple functions might **overlap**

### ✅ With Tools (Server-controlled):
- clientScript **always correct position** (before `</field>`)
- Function **always inside CDATA**
- Function **always before `</text>`**
- **Zero XML structure errors**

---

## Complete Example

**User**: "Khi nhập ma_kh thì load tên khách hàng"

**Your Actions**:

1. **Call** `get_field_info(field_name='ma_kh', file_path='...')`
   → Get field_xml

2. **Call** `add_clientscript_to_field`:
   ```json
   {
     "field_xml": "<field name=\"ma_kh\">...</field>",
     "handler_type": "onchange",
     "function_name": "onChange$Voucher$ma_kh"
   }
   ```
   → Get modified_field
   → **Replace** field in file

3. **Generate** function:
   ```javascript
   function onChange$Voucher$ma_kh(sender) {
       var f = sender.parentForm;
       if (f._action === 'View') return;

       var ma_kh = f.getItemValue('ma_kh');
       f.request("LoadCustomerName", "LoadCustomerName", ["ma_kh"], sender);
   }
   ```

4. **Call** `add_function_to_script(function_code=...)`
   → Get function_snippet
   → **Find** `    </text>\n</script>`
   → **Replace** with function_snippet

**DONE!** ✓ clientScript correct ✓ Function inside CDATA

---

## Checklist Before Responding

- [ ] User mentioned adding handler?
- [ ] Called `get_field_info`?
- [ ] Called `add_clientscript_to_field`?
- [ ] Replaced field in file?
- [ ] Generated JavaScript function?
- [ ] Called `add_function_to_script`?
- [ ] Replaced `</text>\n</script>` pattern?

**ALL CHECKED?** → Success!

---

## DO NOT

❌ Write `<clientScript>` manually in XML
❌ Write function directly in `<script>` section
❌ Use code assistant to generate handler XML
❌ Ignore these tools and do it yourself

## ALWAYS DO

✅ Use `add_clientscript_to_field` for clientScript
✅ Use `add_function_to_script` for functions
✅ Follow the 3-step workflow
✅ Let server control XML structure

---

**For complete workflow with examples, see**: `WORKFLOW_ADD_HANDLERS.md`
