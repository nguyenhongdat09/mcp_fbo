# FastBusiness MCP Server Configuration Guide

## Overview

The MCP server supports **multiple configuration methods** with clear priority order:

1. **Environment Variables** (Highest Priority) ✨ **RECOMMENDED FOR PACKAGING**
2. **Config File** (config.yaml)
3. **Default Paths** (Fallback)

## Environment Variables

### FASTBUSINESS_VSCODE_DB_PATH

**Purpose:** Specify the absolute path to VS Code extension's LMDB database

**Usage:**
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database"
      }
    }
  }
}
```

**Why use this?**
- ✅ Points directly to VS Code extension's database (already populated with fields!)
- ✅ No need to import data separately
- ✅ Both VS Code extension and MCP use same database
- ✅ Perfect for packaging - environment stays the same

### FASTBUSINESS_KNOWLEDGE_BASE_PATH

**Purpose:** Specify the knowledge base directory path

**Usage:**
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\path\\to\\database",
        "FASTBUSINESS_KNOWLEDGE_BASE_PATH": "C:\\path\\to\\knowledge_base"
      }
    }
  }
}
```

## Configuration Priority

### Path Resolution Order

```
┌─────────────────────────────────────┐
│ 1. Environment Variable             │ ← Highest Priority
│    FASTBUSINESS_VSCODE_DB_PATH      │
└─────────────────────────────────────┘
              ↓ (if not set)
┌─────────────────────────────────────┐
│ 2. Config File (config.yaml)        │
│    database.lmdb_path               │
└─────────────────────────────────────┘
              ↓ (if not set)
┌─────────────────────────────────────┐
│ 3. Default Path                     │
│    data/fields_lmdb                 │
└─────────────────────────────────────┘
```

### Example Logs

When server starts, you'll see:

**Using Environment Variable:**
```
INFO - ✓ Using LMDB path from environment variable: C:\Users\nguye\.vscode\extensions\...
INFO - 📂 Final LMDB database path: C:\Users\nguye\.vscode\extensions\...\src\Database
INFO - ✓ LMDB initialized at C:\Users\nguye\.vscode\extensions\...\src\Database (450 fields)
```

**Using Config File:**
```
INFO - ✓ Using LMDB path from config: data/fields_lmdb
INFO - ✓ Converted to absolute path: E:\mcp_fbo\data\fields_lmdb
INFO - 📂 Final LMDB database path: E:\mcp_fbo\data\fields_lmdb
```

## Configuration Methods

### Method 1: Environment Variables (Recommended for Production)

**Advantages:**
- ✅ No code changes needed for different environments
- ✅ Easy to package and deploy
- ✅ Can point to existing databases (VS Code extension)
- ✅ Secure - no hardcoded paths in code

**MCP Config (Cursor/VS Code):**
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database",
        "FASTBUSINESS_KNOWLEDGE_BASE_PATH": "E:\\mcp_fbo\\knowledge_base"
      }
    }
  }
}
```

### Method 2: Config File (config.yaml)

**Advantages:**
- ✅ Centralized configuration
- ✅ Easy to edit without touching MCP config
- ✅ Good for development

**Edit config.yaml:**
```yaml
database:
  lmdb_path: "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database"

paths:
  knowledge_base: "E:\\mcp_fbo\\knowledge_base"
```

**MCP Config:**
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\mcp_fbo"
    }
  }
}
```

### Method 3: Default Paths (Development Only)

Server uses relative paths from working directory:
- LMDB: `{cwd}/data/fields_lmdb`
- Knowledge Base: `{cwd}/knowledge_base`

## Common Scenarios

### Scenario 1: Using VS Code Extension Database

**Problem:** You already have a populated database in VS Code extension

**Solution:** Use environment variable to point to it

```json
{
  "env": {
    "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\YOUR_USER\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-X.X.XX\\src\\Database"
  }
}
```

### Scenario 2: Separate Database for MCP

**Problem:** You want MCP to have its own database

**Solution:** Use default path and import data

```bash
cd E:\mcp_fbo
python scripts/import_fields_to_lmdb.py --xml-dir "E:\FBO\SP2263\App_Data\Controllers"
```

### Scenario 3: Packaging for Distribution

**Problem:** Need to package MCP with database for others to use

**Solution:** Use relative paths with proper working directory

**Directory Structure:**
```
FastBusiness-MCP-Package/
├── fastbusiness_mcp/
├── data/
│   └── fields_lmdb/      ← Pre-populated database
├── knowledge_base/
├── config.yaml
└── run_mcp.bat
```

**MCP Config:**
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "C:\\FastBusiness-MCP-Package"  ← Package installation directory
    }
  }
}
```

### Scenario 4: Multiple Users / Shared Database

**Problem:** Team wants to share a central database

**Solution:** Use environment variable pointing to network location

```json
{
  "env": {
    "FASTBUSINESS_VSCODE_DB_PATH": "\\\\FileServer\\Shared\\FastBusiness\\Database",
    "FASTBUSINESS_KNOWLEDGE_BASE_PATH": "\\\\FileServer\\Shared\\FastBusiness\\KnowledgeBase"
  }
}
```

## Troubleshooting

### Check Active Configuration

When server starts, check logs for:
```
INFO - ✓ Using LMDB path from environment variable: <path>
INFO - 📂 Final LMDB database path: <absolute_path>
INFO - ✓ LMDB initialized at <path> (XXX fields)
```

### Database Empty

If you see:
```
WARNING - ⚠️ LMDB database created NEW at <path> - Database is EMPTY!
```

**Solutions:**
1. Point to VS Code extension database (Method 1)
2. Import data: `python scripts/import_fields_to_lmdb.py --xml-dir <path>`

### Wrong Database Path

If response shows wrong path:
```
❌ Field not found
📂 Database: C:\Users\nguye\data\fields_lmdb  ← Wrong path!
```

**Fix:** Set environment variable with correct path

### Path Not Found

If you see:
```
ERROR - Failed to initialize LMDB: <path> not found
```

**Fix:** Make sure the path exists or create it first

## Best Practices

### For Development
- Use **config.yaml** for quick iterations
- Keep database in project directory: `data/fields_lmdb`

### For Production / Packaging
- Use **environment variables** for flexibility
- Point to pre-populated databases
- Document required environment variables

### For Team Sharing
- Use **network paths** in environment variables
- Share config templates
- Document paths in team wiki

## Example Configurations

### Windows Development
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\Projects\\mcp_fbo"
    }
  }
}
```

### Windows Production (Using VS Code Extension DB)
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "python",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "C:\\Program Files\\FastBusiness-MCP",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "C:\\Users\\nguye\\.vscode\\extensions\\nguyen-hong-dat.fbo-autocomplete-0.0.40\\src\\Database"
      }
    }
  }
}
```

### Linux Development
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "python3",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "/home/user/projects/mcp_fbo"
    }
  }
}
```

### Linux Production
```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "python3",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "/opt/fastbusiness-mcp",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "/var/lib/fastbusiness/database",
        "FASTBUSINESS_KNOWLEDGE_BASE_PATH": "/opt/fastbusiness-mcp/knowledge_base"
      }
    }
  }
}
```

## Quick Reference

| Configuration | Environment Variable | Config File | Default |
|--------------|---------------------|-------------|---------|
| **LMDB Database** | `FASTBUSINESS_VSCODE_DB_PATH` | `database.lmdb_path` | `data/fields_lmdb` |
| **Knowledge Base** | `FASTBUSINESS_KNOWLEDGE_BASE_PATH` | `paths.knowledge_base` | `knowledge_base` |

## Summary

- ✨ **Use environment variables for production** - Most flexible
- 📝 **Use config.yaml for development** - Quick iterations
- 📂 **Always check logs** for actual paths used
- ✅ **Point to VS Code extension DB** to avoid importing data twice
- 📦 **Document env vars** when packaging for distribution
