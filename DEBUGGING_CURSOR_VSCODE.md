# Debugging VS Code vs Cursor Database Path Issues

## Issue
VS Code and Cursor calling the same MCP tool with identical parameters but getting different results:
- **VS Code**: ✅ Field found successfully
- **Cursor**: ❌ "Field not found in DIR" error

## Root Cause
Working directory mismatch causing different database paths.

## How to Debug

### Step 1: Check Database Path in Response

From now on, **every MCP response** (both success and error) will show the database path:

**VS Code response:**
```
✅ Field generated from exact match
Field Name: dept_idt
...
📂 Database: E:/projects/mcp_fbo/data/fields_lmdb
```

**Cursor response:**
```
❌ Field "dept_id" not found in DIR
📊 Database has 0 fields in DIR
📂 Database: C:/Users/Name/.cursor/data/fields_lmdb
```

➡️ **If paths are different**, that's the problem!

### Step 2: Check MCP Server Logs

Look for the database initialization log:

**VS Code logs:**
```
INFO - Using LMDB database path: E:/projects/mcp_fbo/data/fields_lmdb
INFO - ✓ LMDB initialized at E:/projects/mcp_fbo/data/fields_lmdb (450 fields)
```

**Cursor logs:**
```
INFO - Using LMDB database path: C:/Users/Name/.cursor/data/fields_lmdb
WARNING - ⚠️ LMDB database created NEW at C:/Users/Name/.cursor/data/fields_lmdb - Database is EMPTY!
WARNING - ⚠️ Run: python scripts/import_fields_to_lmdb.py --xml-dir <your_xml_dir>
```

➡️ **If you see "Database is EMPTY"**, the database needs data!

### Step 3: Check Per-Request Logs

Every tool call now logs:
```
INFO - 🔍 Database: E:/projects/mcp_fbo/data/fields_lmdb (450 fields in DIR)
INFO - Calling tool.execute() with arguments: field_name=dept_id, context_type=DIR, lookup_type=autocomplete
```

➡️ **Check the field count**. If it's 0, database is empty.

## Solutions

### Solution A: Use Absolute Path (Recommended)

Edit `config.yaml`:
```yaml
database:
  lmdb_path: "E:/projects/mcp_fbo/data/fields_lmdb"  # Absolute path!
```

### Solution B: Set Working Directory

Edit MCP config in **both** VS Code and Cursor:

**claude_desktop_config.json / cursor_config.json:**
```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:/projects/mcp_fbo"  // Same path for both!
    }
  }
}
```

### Solution C: Import Data to Cursor's Database

If Cursor is using a different path and you want to keep it that way:

```bash
# Find Cursor's database path from logs (e.g., C:/Users/Name/.cursor/data/fields_lmdb)
cd E:/projects/mcp_fbo
python scripts/import_fields_to_lmdb.py \
  --xml-dir "E:/FBO/SP2263/App_Data/Controllers" \
  --db-path "C:/Users/Name/.cursor/data/fields_lmdb"
```

## Quick Verification

After applying any solution, call `lmdb_database_stats` tool to verify:

```json
{
  "tool": "lmdb_database_stats"
}
```

Expected response:
```
Database Statistics:

Database path: E:/projects/mcp_fbo/data/fields_lmdb

Statistics:
  DIR: 150 fields
  FILTER_VOUCHER: 80 fields
  FILTER_NORMAL: 45 fields
  GRID_VIEW: 120 fields
  GRID_INPUT: 95 fields
  Total: 490 fields
```

If all contexts show 0 fields, database is empty!

## Common Patterns

### Pattern 1: Fresh Install
```
Cursor log: "⚠️ LMDB database created NEW ... Database is EMPTY!"
```
➡️ Import data with `import_fields_to_lmdb.py`

### Pattern 2: Different Working Dirs
```
VS Code DB:  E:/projects/mcp_fbo/data/fields_lmdb (450 fields)
Cursor DB:   C:/Users/Name/Documents/mcp_fbo/data/fields_lmdb (0 fields)
```
➡️ Use absolute path in config.yaml

### Pattern 3: Portable App
```
VS Code DB:  D:/PortableApps/VSCode/data/fields_lmdb
Cursor DB:   E:/PortableApps/Cursor/data/fields_lmdb
```
➡️ Use absolute path pointing to one shared location

## Logs to Share When Reporting Issues

If you report a database issue, please include:

1. **Database path from response:**
   ```
   📂 Database: <path_here>
   ```

2. **Initialization log:**
   ```
   INFO - Using LMDB database path: <path_here>
   INFO - ✓ LMDB initialized at <path_here> (<count> fields)
   ```

3. **Per-request log:**
   ```
   INFO - 🔍 Database: <path_here> (<count> fields in <context>)
   ```

4. **Your MCP config `cwd` setting**

This will help diagnose the issue quickly!
