# LMDB Database Setup Guide

## Problem: "Field not found" error

If you see this error when calling MCP tools:
```
❌ Database is EMPTY! Field "dept_id" not found in DIR
```

This means the LMDB field database hasn't been populated with field definitions yet.

## Root Cause

The MCP server uses a **relative path** for the database (`data/fields_lmdb`). When VS Code and Cursor run from different working directories, they create **separate databases**:

- VS Code working dir: `/path/A` → database at `/path/A/data/fields_lmdb` ✅
- Cursor working dir: `/path/B` → database at `/path/B/data/fields_lmdb` ❌ (empty)

## Solution 1: Import Field Definitions (Recommended)

Import your existing FastBusiness XML files into the database:

```bash
# Navigate to project root
cd /home/user/mcp_fbo

# Import from a single XML file
python scripts/import_fields_to_lmdb.py --xml-file path/to/your/file.xml

# Import from entire directory
python scripts/import_fields_to_lmdb.py --xml-dir path/to/your/xml/directory

# Example
python scripts/import_fields_to_lmdb.py --xml-dir e:/FBO/SP2263/App_Data/Controllers
```

## Solution 2: Use Absolute Database Path

Configure an **absolute path** in `config.yaml` so both VS Code and Cursor use the same database:

```yaml
database:
  path: "data/fields.db"
  lmdb_path: "/absolute/path/to/data/fields_lmdb"  # Use absolute path
```

Example:
```yaml
database:
  path: "data/fields.db"
  lmdb_path: "E:/projects/mcp_fbo/data/fields_lmdb"  # Windows absolute path
```

Or on Linux:
```yaml
database:
  path: "data/fields.db"
  lmdb_path: "/home/user/mcp_fbo/data/fields_lmdb"  # Linux absolute path
```

## Solution 3: Ensure Same Working Directory

Make sure both VS Code and Cursor launch the MCP server from the **same working directory**.

### In VS Code MCP Config:
```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "/absolute/path/to/mcp_fbo"
    }
  }
}
```

### In Cursor MCP Config:
```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "/absolute/path/to/mcp_fbo"
    }
  }
}
```

## Verification

After setup, verify the database contains fields:

```python
# Check database stats
from fastbusiness_mcp.lmdb_adapter import LMDBManager

lmdb = LMDBManager(db_path="data/fields_lmdb")
for context in ['DIR', 'FILTER_VOUCHER', 'FILTER_NORMAL', 'GRID_VIEW', 'GRID_INPUT']:
    count = lmdb.count_fields(context)
    print(f"{context}: {count} fields")
lmdb.close()
```

Expected output (after import):
```
DIR: 150 fields
FILTER_VOUCHER: 80 fields
FILTER_NORMAL: 45 fields
GRID_VIEW: 120 fields
GRID_INPUT: 95 fields
```

## Improvements in This Version

✅ **Better logging**: Shows database path and whether it's new or existing
✅ **Absolute path support**: Reads `lmdb_path` from config.yaml
✅ **Empty database detection**: Warns when database is empty with helpful instructions
✅ **Detailed error messages**: Shows database path and field count when errors occur

## Troubleshooting

### Database path shows wrong location
Check the MCP server logs for:
```
INFO - Using LMDB database path: /actual/path/used
```

### Database exists but fields not found
The database might be from old structure. Re-import:
```bash
rm -rf data/fields_lmdb
python scripts/import_fields_to_lmdb.py --xml-dir <your_xml_dir>
```

### VS Code works but Cursor doesn't
They're using different databases. Use Solution 2 (absolute path) to sync them.
