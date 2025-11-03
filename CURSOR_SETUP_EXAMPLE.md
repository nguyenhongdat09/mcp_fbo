# Cursor MCP Setup - Quick Example

## Your Current Working Config

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "fastbusiness_mcp.server"
      ],
      "cwd": "E:\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database",
        "PYTHONPATH": "E:\\mcp_fbo"
      }
    }
  }
}
```

## What This Does

✅ **Points to VS Code extension database** - No need to import data separately!

The key is this line:
```json
"FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database"
```

This tells the MCP server to use the **same database** that your VS Code extension already has populated.

## Path Breakdown

```
C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database
│                                 └──────────────────┬─────────────────┘
│                                                     │
│                                              VS Code Extension
│                                                     │
└── Your VS Code extensions folder                   │
                                                      └── Database subfolder
```

## How to Find Your VS Code Extension Database Path

### Method 1: Check VS Code Extensions Folder

1. Open VS Code
2. Press `Ctrl+Shift+P` → Type "Extensions: Open Extensions Folder"
3. Or manually go to: `C:\Users\YOUR_USERNAME\.vscode\extensions\`
4. Find folder starting with: `nguyen-hong-dat.fbo-autocomplete-`
5. Open that folder → Look for `src\Database` subfolder
6. Copy full path

### Method 2: Check Extension Settings

1. Open VS Code
2. Go to Extensions → Find "FBO Autocomplete"
3. Check extension details for database location
4. Or check extension's settings.json

### Method 3: Search for LMDB Files

1. Open File Explorer
2. Search in `C:\Users\YOUR_USERNAME\.vscode\` for `*.mdb` or `data.mdb`
3. Find the one in FBO extension folder
4. Copy folder path (not file path!)

## Example Paths

Your path will look like one of these:

### Windows
```
C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database
C:\Users\JohnDoe\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-1.0.0\Database
```

### If Using VS Code Insiders
```
C:\Users\nguye\.vscode-insiders\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database
```

### If Using Portable VS Code
```
E:\PortableApps\VSCode\data\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database
```

## Template to Fill In

Copy this template and **replace YOUR_USERNAME and version**:

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\YOUR_USERNAME\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-X.X.XX\\src\\Database"
      }
    }
  }
}
```

**Replace:**
- `YOUR_USERNAME` with your Windows username
- `X.X.XX` with actual extension version (e.g., `0.0.40`)

## Verification

After setting up, restart Cursor and check logs:

**✅ Success - Should see:**
```
INFO - ✓ Using LMDB path from environment variable: C:\Users\nguye\.vscode\...
INFO - ✓ LMDB initialized at C:\Users\nguye\.vscode\...\Database (450 fields)
```

**❌ Problem - If you see:**
```
WARNING - ⚠️ LMDB database created NEW at C:\Users\nguye\data\fields_lmdb - Database is EMPTY!
```
→ Environment variable not working, path is wrong

## Common Mistakes

### Mistake 1: Wrong Path Format
```json
❌ "FASTBUSINESS_VSCODE_DB_PATH": "C:/Users/nguye/.vscode/..."  // Wrong: forward slashes
✅ "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\..." // Correct: escaped backslashes
```

### Mistake 2: Pointing to File Instead of Folder
```json
❌ "FASTBUSINESS_VSCODE_DB_PATH": "C:\\...\\Database\\data.mdb"  // Wrong: points to file
✅ "FASTBUSINESS_VSCODE_DB_PATH": "C:\\...\\Database"            // Correct: points to folder
```

### Mistake 3: Extension Version Mismatch
```json
❌ "...\\fbo-autocomplete-0.0.40\\..."  // Wrong: old version
✅ "...\\fbo-autocomplete-0.0.50\\..."  // Correct: current installed version
```

Check actual folder name in `.vscode\extensions\`!

## Alternative: Use Standalone Database

If you **don't** want to use VS Code extension database, you can create a standalone database:

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
      }
    }
  }
}
```

Then import data:
```bash
cd E:\mcp_fbo
python scripts\import_fields_to_lmdb.py --xml-dir "E:\FBO\SP2263\App_Data\Controllers" --db-path "E:\mcp_fbo\data\fields_lmdb"
```

## Testing

After setup, test with this MCP call:

```json
{
  "tool": "lmdb_database_stats"
}
```

**Expected response:**
```
Database Statistics:
Database path: C:\Users\nguye\.vscode\extensions\...\Database

Statistics:
  DIR: 150 fields
  FILTER_VOUCHER: 80 fields
  ...
  Total: 450 fields
```

If you see `Total: 0 fields`, the path is wrong!

## Summary

1. ✅ Copy template above
2. ✅ Replace `YOUR_USERNAME` with your Windows username
3. ✅ Find extension version in `.vscode\extensions\`
4. ✅ Update version in path (e.g., `0.0.40` → `0.0.50`)
5. ✅ Save config
6. ✅ Restart Cursor
7. ✅ Check logs for "Using LMDB path from environment variable"
8. ✅ Test with `lmdb_database_stats` tool

Done! 🎉
