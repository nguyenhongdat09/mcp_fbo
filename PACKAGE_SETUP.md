# FastBusiness MCP v1.0.0 - Setup Guide

## Cấu trúc Package

```
FastBusiness-MCP-v1.0.0/
├── fastbusiness_mcp.exe      ← Executable
├── config.yaml               ← Configuration (nếu có)
├── knowledge_base/           ← Knowledge base files
│   └── api_reference/
├── data/
│   └── fields_lmdb/         ← LMDB database (empty, cần import)
└── run_mcp.bat              ← Optional launcher script
```

## MCP Configuration cho .exe

### Option 1: Dùng cwd (RECOMMENDED)

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "cwd": "C:\\FastBusiness-MCP-v1.0.0",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
      }
    }
  }
}
```

**Giải thích:**
- `command`: Đường dẫn TUYỆT ĐỐI tới .exe
- `cwd`: Thư mục package (để tìm knowledge_base/)
- `env.FASTBUSINESS_VSCODE_DB_PATH`: Đường dẫn database (tuyệt đối)

**Knowledge base sẽ tự động tìm tại:** `C:\FastBusiness-MCP-v1.0.0\knowledge_base`

---

### Option 2: Dùng Environment Variables (Linh hoạt hơn)

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "cwd": "C:\\FastBusiness-MCP-v1.0.0",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb",
        "FASTBUSINESS_KNOWLEDGE_BASE_PATH": "C:\\FastBusiness-MCP-v1.0.0\\knowledge_base"
      }
    }
  }
}
```

**Giải thích:**
- Tương tự Option 1
- Thêm `FASTBUSINESS_KNOWLEDGE_BASE_PATH` để chỉ rõ path knowledge base

---

### Option 3: Database trong Package (Standalone)

Nếu muốn database nằm trong package (không dùng external DB):

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "cwd": "C:\\FastBusiness-MCP-v1.0.0",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\FastBusiness-MCP-v1.0.0\\data\\fields_lmdb"
      }
    }
  }
}
```

**Cần import data trước:**
```bash
cd C:\FastBusiness-MCP-v1.0.0
python scripts/import_fields_to_lmdb.py ^
  --xml-dir "E:\FBO\SP2263\App_Data\Controllers" ^
  --db-path "C:\FastBusiness-MCP-v1.0.0\data\fields_lmdb"
```

---

## Path Resolution Logic

### Database Path
```
Priority:
1. Environment Variable: FASTBUSINESS_VSCODE_DB_PATH
2. config.yaml: database.lmdb_path
3. Default: {cwd}/data/fields_lmdb
```

### Knowledge Base Path
```
Priority:
1. Environment Variable: FASTBUSINESS_KNOWLEDGE_BASE_PATH
2. config.yaml: paths.knowledge_base
3. Default: {cwd}/knowledge_base
```

**{cwd} = Working directory từ MCP config**

---

## Verification

### 1. Check Logs

Sau khi restart Cursor, check logs:

```
INFO - [OK] Using LMDB path from environment variable: E:\mcp_fbo\data\fields_lmdb
INFO - [DB] Final LMDB database path: E:\mcp_fbo\data\fields_lmdb
INFO - [KB] Knowledge base path: C:\FastBusiness-MCP-v1.0.0\knowledge_base
INFO - [OK] LMDB initialized at ... (XXX fields)
```

### 2. Test Tool Call

Call `lmdb_database_stats`:

```
[STATS] LMDB Field Database Statistics

Database path: E:\mcp_fbo\data\fields_lmdb

Statistics:
  DIR: 150 fields
  FILTER_VOUCHER: 80 fields
  ...
```

---

## Troubleshooting

### Problem: "Knowledge base not found"

**Check logs for:**
```
[KB] Knowledge base path: C:\some\wrong\path\knowledge_base
```

**Fix:**
1. Set `cwd` đúng trong MCP config
2. Hoặc set `FASTBUSINESS_KNOWLEDGE_BASE_PATH` env var

### Problem: "Database empty"

**Check logs for:**
```
[WARNING] LMDB database created NEW at ... - Database is EMPTY!
```

**Fix:**
Import data vào database:
```bash
python scripts/import_fields_to_lmdb.py ^
  --xml-dir "E:\FBO\SP2263\App_Data\Controllers" ^
  --db-path "E:\mcp_fbo\data\fields_lmdb"
```

### Problem: ".exe not starting"

**Check:**
1. Đường dẫn .exe có đúng không?
2. Có permission để chạy .exe?
3. Python runtime dependencies đã được bundle?

---

## Example Configs

### Development (dùng Python)
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

### Production (dùng .exe)
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "cwd": "C:\\FastBusiness-MCP-v1.0.0",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
      }
    }
  }
}
```

### Portable (database trong package)
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "D:\\Portable\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "cwd": "D:\\Portable\\FastBusiness-MCP-v1.0.0",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "D:\\Portable\\FastBusiness-MCP-v1.0.0\\data\\fields_lmdb"
      }
    }
  }
}
```

---

## Quick Start Template

**Copy và thay đổi paths:**

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "PATH_TO_EXE\\fastbusiness_mcp.exe",
      "cwd": "PATH_TO_PACKAGE_FOLDER",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "PATH_TO_DATABASE"
      }
    }
  }
}
```

**Thay thế:**
- `PATH_TO_EXE`: Đường dẫn tuyệt đối tới .exe
- `PATH_TO_PACKAGE_FOLDER`: Thư mục chứa package (có knowledge_base/)
- `PATH_TO_DATABASE`: Đường dẫn database LMDB

---

## Notes

1. **LUÔN dùng đường dẫn tuyệt đối (absolute paths)**
2. **Set `cwd` = thư mục package** để tìm knowledge_base
3. **Database path nên là tuyệt đối** (qua env var)
4. **Không cần `PYTHONPATH`** khi chạy .exe
5. **Check logs** để verify paths đúng

---

## Summary

✅ **command**: Absolute path tới .exe
✅ **cwd**: Package folder (có knowledge_base/)
✅ **env.FASTBUSINESS_VSCODE_DB_PATH**: Database path (absolute)
✅ **env.FASTBUSINESS_KNOWLEDGE_BASE_PATH**: (Optional) Knowledge base path

Done! 🚀
