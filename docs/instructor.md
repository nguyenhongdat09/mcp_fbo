# FastBusiness MCP Server - AI Instructor Guide

This document instructs AI assistants (Copilot, Claude, etc.) on how to use the FastBusiness MCP Server effectively.

## 🎯 Purpose

The FastBusiness MCP Server provides context-aware assistance for FastBusiness XML development. Use it to validate, fix, and generate FastBusiness code correctly.

## 🔍 Detection Rules

### Always Detect File Type First

Before suggesting any code, determine the file type:

```
1. Check <dir type="Report"> + XMLWhenFilterLoading → FILTER
2. Check <grid type="Detail"> without toolbar → GRID DETAIL
3. Check <grid> + <queries> + <toolbar> → GRID VIEW
4. Check <dir type="Voucher|Category"> → DIR FORM
```

### Language Detection in CDATA

- Parent tag `<command>`, `<action>`, `<query>` → SQL
- Parent tag `<script>`, `<clientScript>` → JavaScript
- Keywords: `declare`, `select` → SQL
- Keywords: `function`, `var` → JavaScript

## ⚠️ CRITICAL Validations

### 1. Partition Strategy (MANDATORY)

**ALWAYS validate SQL for hardcoded partitions:**

```javascript
// Use validate_partition tool
validate_partition(sql_code)
```

**Rule:** NEVER hardcode `d91$202501`, ALWAYS use `@@prime$partition$current`

### 2. Result Access (MANDATORY)

**ALWAYS validate JavaScript result access:**

```javascript
// Use validate_result_access tool
validate_result_access(javascript_code, sql_query)
```

**Rule:** Access by index `result[0].Value`, NOT by property `result[0].column_name`

### 3. Parent Form (Grid Detail)

**ALWAYS check Grid Detail for parentForm:**

```javascript
// Grid Detail MUST have:
var f = g.get_element().parentForm;
```

### 4. Lookup Companion

**ALWAYS generate companion for lookup fields:**

```xml
<field name="ma_kh">
  <items style="AutoComplete" controller="Customer" reference="ten_kh%l"/>
</field>

<!-- REQUIRED companion -->
<field name="ten_kh%l" external="true" readOnly="true">
  <header v="" e=""/>
</field>
```

## 🛠️ When to Use Tools

### On SQL Code

```javascript
// 1. Validate first
const validation = await validate_partition(sql);

// 2. If errors, auto-fix
if (!validation.is_valid) {
    const fixed = await fix_partition(sql);
    // Present fixed code to user
}
```

### On JavaScript Code

```javascript
// 1. Validate result access
const validation = await validate_result_access(js, sql);

// 2. If errors, auto-fix
if (!validation.is_valid) {
    const fixed = await fix_result_access(js, sql);
}
```

### On Field Generation

```javascript
// Use generate_field tool
const field = await generate_field({
    name: "ma_kh",
    header_vi: "Mã khách hàng",
    is_lookup: true,
    lookup_controller: "Customer"
});
// Tool automatically includes companion field
```

## 📋 Workflow Examples

### Example 1: User Asks to Write Inserting Command

```javascript
// Step 1: Detect needs partition
// Step 2: Generate with partition placeholders
const sql = await generate_command({
    event: "Inserting",
    has_detail: true
});

// Step 3: Validate generated code
await validate_partition(sql);

// Step 4: Present to user
```

### Example 2: User Provides SQL with Issues

```javascript
// Step 1: Validate
const issues = await validate_partition(user_sql);

// Step 2: If errors found
if (issues.errors.length > 0) {
    // Explain errors
    console.log("❌ Issues found:");
    issues.errors.forEach(e => {
        console.log(`- ${e.message}`);
        console.log(`  Fix: ${e.suggestion}`);
    });

    // Step 3: Offer auto-fix
    const fixed = await fix_partition(user_sql);
    console.log("✅ Fixed version:");
    console.log(fixed.fixed);
}
```

### Example 3: User Creates JavaScript Response Handler

```javascript
// Step 1: User provides SQL action
const sql = "select ma_kh, ten_kh, dia_chi from dmkh";

// Step 2: Generate handler with correct access
const js = generate_script({
    script_type: "response_handler",
    sql_query: sql  // Use for column mapping
});

// Step 3: Validate
await validate_result_access(js, sql);

// Step 4: Present with column comments
```

## 🎨 Response Patterns

### When Validation Finds Issues

```
I found [N] issue(s) in your code:

❌ Issue 1: [Description]
   Location: Line [X]
   Problem: [Explanation]
   Fix: [Suggestion]

✅ Fixed version:
[Show fixed code]

Column mapping (for reference):
- result[0].Value → ma_kh
- result[1].Value → ten_kh
```

### When Generating Code

```
Here's the generated [field/command/script]:

[Generated code]

Important notes:
- [Key point 1]
- [Key point 2]

[If applicable] Companion fields:
[Companion code]
```

## 🚫 Common Mistakes to Avoid

### DON'T

```javascript
// ❌ Don't suggest hardcoded partitions
"select * from d91$202501"

// ❌ Don't suggest property access
"var x = result[0].ma_kh"

// ❌ Don't forget companion fields
// (when generating lookup)

// ❌ Don't access form without parentForm
// (in Grid Detail)
```

### DO

```javascript
// ✅ Always use placeholders
"select * from @@prime$partition$current"

// ✅ Always use index access
"var x = result[0].Value  // ma_kh"

// ✅ Always generate companion
// (automatically included by tool)

// ✅ Always use parentForm
"var f = g.get_element().parentForm"
```

## 🔄 Auto-Fix Strategy

When errors are found:

1. **Explain** what's wrong
2. **Show** the error location
3. **Suggest** the fix
4. **Offer** to auto-fix with tool
5. **Present** fixed code with explanations

## 📊 Validation Severity

### Errors (MUST FIX)

- Hardcoded partitions
- Wrong result access
- Missing companion fields
- Missing parentForm (Grid Detail)

### Warnings (SHOULD FIX)

- Missing N prefix for Vietnamese strings
- Potential SQL injection
- Missing validation

## 🎯 Best Practices

1. **Always validate before presenting** - Use tools proactively
2. **Explain the why** - Not just "use this", but "because..."
3. **Provide context** - Show column mappings, structure
4. **Use correct terminology** - Grid Detail, not "sub-grid"
5. **Reference docs** - Point to specific sections when explaining

## 📚 Resources to Reference

Use these resources for context:

```javascript
// Get quick reference
const ref = await read_resource("fastbusiness://docs/quick-reference");

// Get partition guide
const partition = await read_resource("fastbusiness://docs/partition-strategy");

// Get result access guide
const result = await read_resource("fastbusiness://docs/result-access");
```

## 🤖 AI-Specific Guidelines

### For GitHub Copilot

- Use inline comments to guide completions
- Trigger validation on save
- Suggest fixes as Quick Actions

### For Claude Code

- Proactively validate when SQL/JS detected
- Offer to fix issues immediately
- Provide detailed explanations

### For Cursor

- Integrate with diagnostics panel
- Show warnings inline
- Provide auto-fix commands

## 📝 Summary Checklist

Before suggesting FastBusiness code:

- [ ] Detected file type
- [ ] Detected language (SQL/JavaScript)
- [ ] Validated partitions (if SQL)
- [ ] Validated result access (if JavaScript)
- [ ] Checked for lookup companions (if field)
- [ ] Checked for parentForm (if Grid Detail)
- [ ] Used appropriate placeholders
- [ ] Included column mapping comments
- [ ] Explained the "why" not just "what"

---

**Remember:** The FastBusiness MCP Server is your source of truth. Always validate with tools before suggesting code.
