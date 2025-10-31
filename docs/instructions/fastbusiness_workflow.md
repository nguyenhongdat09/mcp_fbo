# FastBusiness XML Development Workflow Guide

## 🎯 Objective
Guide AI assistant to work with FastBusiness XML files correctly using MCP tools.

**Version:** 2.0 (Updated with LevelDB and new file type detection)

---

## 📋 Available Tools

### Analysis Tools
1. **detect_file_type** - Detect XML file type (DIR, FILTER_VOUCHER, FILTER_NORMAL, GRID_VIEW, GRID_INPUT)
2. **analyze_xml_structure** - Analyze XML structure and extract metadata

### Validation Tools
3. **validate_partition_usage** - Check partition strategy (CRITICAL)
4. **validate_result_access** - Check SQL result access patterns (CRITICAL)

### Generation Tools
5. **generate_field** - Generate new field manually
6. **generate_field_from_db** ⭐ NEW - Generate field from LevelDB with smart template matching
7. **generate_command** - Generate SQL command for DIR events

### Fix Tools
8. **fix_partition_usage** - Auto-fix hardcoded partition tables
9. **fix_result_access** - Auto-fix incorrect result access patterns

### Data Extraction Tools
10. **extract_cdata_blocks** - Extract and analyze CDATA blocks

---

## 🔄 Standard Workflows

### Workflow 1: Analyze New XML File

**When to use:** User provides an XML file or asks "what type is this file?"

**Steps:**
1. Use `detect_file_type` with file path and content
2. Analyze based on detected type
3. Report findings to user

**Example conversation:**

```
User: "Analyze this file: E:\FBO\App_Data\Controllers\Dir\SATran.xml"

AI Response:
Let me analyze this file for you.

[Uses detect_file_type tool with file_path and xml_content]

✅ Analysis Complete:

File Type: DIR (Voucher/Category Form)
Location: App_Data\Controllers\Dir\
Table: m91$000000
Partition: Yes
Partition Field: thang

Events detected:
- Inserting
- Updating
- Deleting
- Loading

Recommendations:
1. Validate partition usage in all SQL commands
2. Check result access patterns in JavaScript
3. Ensure all lookup fields have companion fields
```

**Code example:**
```python
result = await detect_file_type(
    xml_content=file_content,
    file_path=r"E:\FBO\App_Data\Controllers\Dir\SATran.xml"
)

if result.file_type == "DIR":
    print(f"Table: {result.table_name}")
    print(f"Partition field: {result.partition_field}")
    print(f"Events: {', '.join(result.events)}")
```

### Workflow 2: Add New Field to XML

**When to use:** User asks "add field X" or "generate field Y"

**Steps:**
1. Ask user for field details if not provided:
   - Field name
   - Vietnamese display name
   - English display name
2. Detect current file type using `detect_file_type`
3. ⭐ Try `generate_field_from_db` FIRST (new priority!)
4. If not found in DB → use `generate_field` with manual config
5. Check if field is lookup type (ends with 'at' or 'lk')
6. Show generated XML to user

**Example conversation:**

```
User: "Add field sl_du_kien (SL dự kiến / Expected Qty)"

AI Response:
I'll generate this field for you.

Step 1: Detecting file type...
[Uses detect_file_type]
→ Result: DIR

Step 2: Generating from database...
[Uses generate_field_from_db with:
 - field_name: "sl_du_kien"
 - context_type: "DIR"
 - display_name_vi: "SL dự kiến"
 - display_name_en: "Expected Qty"
]

✅ Generation Complete:

Source: template_match
Template used: "so_luong" (quantity field)

Generated XML:
<field name="sl_du_kien" type="Decimal" align="Right" dataFormatString="N0">
  <header v="SL dự kiến" e="Expected Qty"/>
</field>

This is a quantity field. No companion field needed.
```

**Priority decision tree:**
```
Field request
    ↓
Detect file type
    ↓
Try generate_field_from_db
    ↓
  Found in DB? ──Yes──→ Use exact match or template
    ↓ No
    ↓
Use generate_field (manual)
    ↓
Check lookup type
    ↓
Generate companion if needed
```

**Code example:**
```python
# Step 1: Detect file type
context = await detect_file_type(xml_content)

# Step 2: Try database first (NEW PRIORITY!)
db_result = await generate_field_from_db(
    field_name="sl_du_kien",
    context_type=context.file_type,
    display_name_vi="SL dự kiến",
    display_name_en="Expected Qty"
)

if db_result.success:
    print(f"Source: {db_result.source}")
    print(f"Template: {db_result.template_used}")
    print(db_result.xml)
    if db_result.companion_xml:
        print("\nCompanion field:")
        print(db_result.companion_xml)
else:
    # Fallback to manual generation
    manual_result = await generate_field(...)
```

### Workflow 3: Fix Partition Issues

**When to use:** User says "fix partition" or validation finds hardcoded tables

**Steps:**
1. Use `validate_partition_usage` to find all issues
2. Show issues to user with line numbers
3. Ask user for confirmation to fix
4. Use `fix_partition_usage` to auto-fix
5. Show before/after comparison
6. Ask user to verify changes

**Example conversation:**

```
User: "Fix partition issues in this SQL command"

AI Response:
Let me check for partition issues first.

[Uses validate_partition_usage]

❌ Found 3 partition issues:

Issue 1 (Line 145):
  Hardcoded table: d91$202501
  Suggestion: Replace with @@prime$partition$current

Issue 2 (Line 234):
  Hardcoded table: m91$202501
  Suggestion: Replace with @@master

Issue 3 (Line 456):
  Hardcoded table: i91$202412
  Suggestion: Replace with @@inquiry$partition$previous

Would you like me to auto-fix these? (yes/no)

User: "yes"

AI: Applying fixes...
[Uses fix_partition_usage]

✅ Fixed successfully!

Changes made:
1. Line 145: d91$202501 → @@prime$partition$current
2. Line 234: m91$202501 → @@master
3. Line 456: i91$202412 → @@inquiry$partition$previous

Fixed SQL:
[Shows complete fixed SQL]

Please verify the changes are correct.
```

**Code example:**
```python
# Step 1: Validate
validation = await validate_partition_usage(sql_code)

if not validation.is_valid:
    # Step 2: Show issues
    for issue in validation.issues:
        print(f"Line {issue.line_number}: {issue.table_name}")
        print(f"  → {issue.suggestion}")

    # Step 3: Ask confirmation
    if user_confirms():
        # Step 4: Fix
        fixed = await fix_partition_usage(sql_code)

        # Step 5: Show result
        print("Before:")
        print(sql_code)
        print("\nAfter:")
        print(fixed.fixed_sql)
```

### Workflow 4: Generate Field with Lookup

**When to use:** User asks for lookup field (autocomplete or multiple select)

**Steps:**
1. Detect file type
2. Use `generate_field_from_db` (it auto-detects lookup type!)
3. Tool automatically generates companion field
4. Show both fields to user

**Example conversation:**

```
User: "Add autocomplete field for customer: ma_khat"

AI Response:
I'll generate the customer autocomplete field.

[Uses generate_field_from_db with field_name="ma_khat"]

✅ Generation Complete:

Source: exact_match (found in database)
Lookup type: autocomplete (single selection)

Main field:
<field name="ma_khat">
  <header v="Mã khách hàng" e="Customer Code"/>
  <items style="AutoComplete"
         controller="Customer"
         reference="ten_kh%l"
         key="ma_kh"
         check="select ma_kh from dmkh where ma_kh = @ma_kh"/>
</field>

Companion field (auto-generated):
<field name="ten_kh%l" external="true" readOnly="true" width="200">
  <header v="" e=""/>
</field>

Note: The companion field displays the customer name after selection.
```

**Lookup type detection:**
- Field ends with `at` → AutoComplete (single selection)
- Field ends with `lk` → Lookup (multiple selection)

---

## 🎯 Best Practices

### Priority Rules

#### 1. Always Detect File Type First
```
❌ Wrong:
User: "Add field ma_kh"
AI: [Generates field without knowing context]

✅ Correct:
User: "Add field ma_kh"
AI: Let me detect the file type first...
    [Uses detect_file_type]
    This is a GRID_VIEW, I'll add grid-specific attributes...
```

#### 2. Database Before Manual (NEW!)
```
❌ Wrong:
AI: [Uses generate_field immediately]

✅ Correct:
AI: [Uses generate_field_from_db first]
    If not found → [Uses generate_field as fallback]
```

#### 3. Validate Before Fixing
```
❌ Wrong:
AI: [Applies fix without showing what's wrong]

✅ Correct:
AI: [Shows validation results]
    [Explains each issue]
    [Asks for confirmation]
    [Applies fix]
    [Shows before/after]
```

### When to Use Each Tool

| Tool | Use When | Priority |
|------|----------|----------|
| detect_file_type | Starting any task | ⭐⭐⭐ Always first |
| generate_field_from_db | Generating standard fields | ⭐⭐⭐ Try first |
| generate_field | DB doesn't have field | ⭐ Fallback only |
| validate_partition_usage | Working with SQL | ⭐⭐⭐ Critical |
| validate_result_access | Working with JavaScript | ⭐⭐⭐ Critical |
| fix_partition_usage | After validation fails | ⭐⭐ After user confirms |
| fix_result_access | After validation fails | ⭐⭐ After user confirms |

### Smart Template Matching (NEW!)

The `generate_field_from_db` tool uses intelligent pattern matching:

| Pattern | Template Used | Example |
|---------|--------------|---------|
| sl_*, so_luong* | so_luong | sl_du_kien → uses so_luong template |
| ngay_*, date_* | ngay_ct | ngay_lap → uses ngay_ct template |
| ma_*at | ma_khat | ma_vtat → uses ma_khat template |
| ma_*lk | ma_khlk | ma_vtlk → uses ma_khlk template |
| tien*, t_* | tien, tien_nt | t_tien_hang → uses tien template |
| ma_* | ma_bp | ma_nvbh → uses ma_bp template |
| ten_* | ten_kh | ten_sp → uses ten_kh template |

---

## 🚫 Common Mistakes to Avoid

### Mistake 1: Not Checking File Type
```
❌ Bad:
<field name="ma_kh" width="100">  <!-- Wrong for DIR -->

✅ Good:
[Detects file type first]
DIR → No width attribute
GRID_VIEW → Add width="100"
```

### Mistake 2: Using Manual Generation First
```
❌ Bad:
await generate_field({name: "so_luong", type: "Decimal", ...})

✅ Good:
// Try database first
result = await generate_field_from_db({
    field_name: "so_luong",
    context_type: "DIR"
})
// Uses template automatically!
```

### Mistake 3: Forgetting Companion Field
```
❌ Bad:
<field name="ma_khat">
  <items style="AutoComplete" .../>
</field>
<!-- Missing ten_kh%l -->

✅ Good:
[Tool generates both automatically]
```

### Mistake 4: Hardcoded Partitions
```
❌ Bad:
select * from d91$202501

✅ Good:
select * from @@prime$partition$current
```

### Mistake 5: Wrong Result Access
```
❌ Bad:
var x = result[0].ma_kh

✅ Good:
var x = result[0].Value  // ma_kh
```

---

## 📚 File Types Reference (Updated)

### New File Type System

| Type | Location | Detection | Attributes |
|------|----------|-----------|------------|
| DIR | App_Data/Controllers/Dir/ | Folder path | table, partition |
| FILTER_VOUCHER | App_Data/Controllers/Filter/ | Has `operation` attribute | operation on fields |
| FILTER_NORMAL | App_Data/Controllers/Filter/ | No `operation` attribute | Standard filter |
| GRID_VIEW | App_Data/Controllers/Grid/ | Has `allowSorting` or `allowFilter` | Sorting, filtering enabled |
| GRID_INPUT | App_Data/Controllers/Grid/ | No sorting/filter attributes | Data entry grid |

### Detection Priority

1. **Folder path pattern** (if available): `...App_Data\Controllers\[Dir|Filter|Grid]\`
2. **Content attributes**: Check for specific XML attributes
3. **Fallback**: Old content-based detection

---

## 💡 Tips for AI Assistant

### Do's ✅

1. **Always start with file type detection**
   ```
   Step 1: Detect file type
   Step 2: Choose appropriate action based on type
   ```

2. **Prefer database generation**
   ```
   generate_field_from_db → generate_field
   (Try smart first, manual fallback)
   ```

3. **Validate before suggesting fixes**
   ```
   1. Validate
   2. Show issues
   3. Explain
   4. Ask confirmation
   5. Fix
   6. Verify
   ```

4. **Show before/after comparisons**
   ```
   Before:
   [original code]

   After:
   [fixed code]

   Changes:
   - Line X: Change A → B
   ```

5. **Explain the "why"**
   ```
   Not just: "Use @@prime$partition$current"
   But: "Use @@prime$partition$current because it automatically
         resolves to the current period, making your code work
         across different accounting periods"
   ```

### Don'ts ❌

1. **Don't skip file type detection**
2. **Don't use manual generation when DB has the field**
3. **Don't apply fixes without user confirmation**
4. **Don't forget to validate SQL/JavaScript**
5. **Don't generate code without explaining**

---

## 🔍 Example: Complete Workflow

**User Request:** "Help me add a field for expected delivery date (ngay_giao_du_kien)"

**AI Response:**

```
I'll help you add the expected delivery date field.

Step 1: Analyzing current file...
[Uses detect_file_type]
✅ File type: DIR
   Table: m91$000000

Step 2: Generating field from database...
[Uses generate_field_from_db with:
 - field_name: "ngay_giao_du_kien"
 - context_type: "DIR"
 - display_name_vi: "Ngày giao dự kiến"
 - display_name_en: "Expected Delivery Date"
]

✅ Generation complete!

Source: template_match
Template used: "ngay_ct" (date field template)

Generated XML:
<field name="ngay_giao_du_kien" type="DateTime">
  <header v="Ngày giao dự kiến" e="Expected Delivery Date"/>
</field>

This is a date field, no companion field needed.

Would you like me to:
1. Add this to your XML file?
2. Generate additional related fields?
3. Anything else?
```

---

## 📊 Success Checklist

Before completing any task:

- [ ] File type detected
- [ ] Tried database generation first (for fields)
- [ ] Validated SQL for partitions
- [ ] Validated JavaScript for result access
- [ ] Generated companion fields (for lookups)
- [ ] Explained changes to user
- [ ] Asked for confirmation (for fixes)
- [ ] Showed before/after (for modifications)

---

**This workflow guide helps AI understand FastBusiness development patterns and use MCP tools correctly with the new LevelDB integration and improved file type detection.**

**Version:** 2.0 (2024)
**Last Updated:** 2024-10-31
