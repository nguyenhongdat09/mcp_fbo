# FastBusiness MCP Server - Build Instructions

## Quick Start: Onedir Build (Recommended)

### Cách 1: Dùng file .bat (Đơn giản nhất) ⭐

```bash
# Chạy file .bat
build_onedir.bat
```

**Kết quả**:
```
FastBusiness-MCP-Package/
  fastbusiness_mcp.exe      <- Chạy file này
  _internal/                <- Chứa DLL và dependencies
    python39.dll
    VCRUNTIME140.dll
    ...
  knowledge_base/           <- YAML knowledge base
  data/                     <- LMDB database
  config.yaml
```

### Cách 2: Chạy command thủ công

```bash
# Clean old build
rmdir /s /q build dist

# Build onedir
pyinstaller run_server.py ^
  --name fastbusiness_mcp ^
  --onedir ^
  --console ^
  --add-data "knowledge_base;knowledge_base" ^
  --add-data "data;data" ^
  --add-data "config.yaml;." ^
  --hidden-import mcp ^
  --hidden-import yaml ^
  --hidden-import lmdb ^
  --clean
```

---

## Onefile Build (Single .exe)

Nếu muốn 1 file .exe duy nhất:

```bash
# Build với spec file
pyinstaller fastbusiness_mcp.spec --clean
```

**Lưu ý**:
- ✅ Onefile tiện (1 file)
- ❌ Dễ lỗi VCRUNTIME140.dll
- ❌ Chậm hơn (phải extract)

→ **Recommend dùng Onedir** cho production!

---

## So Sánh Onefile vs Onedir

| Feature | Onefile (.exe) | Onedir (folder) |
|---------|----------------|-----------------|
| **File count** | 1 file | 1 folder (~200 files) |
| **Size** | ~20-30 MB | ~80-100 MB |
| **Startup time** | Chậm (extract DLLs) | Nhanh |
| **Stability** | Dễ lỗi DLL | Rất stable |
| **Deploy** | Copy 1 file | Copy cả folder |
| **Recommend** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## Deployment Instructions

### Onedir Deployment:

**Bước 1**: Build package
```bash
build_onedir.bat
```

**Bước 2**: Copy folder sang máy target
```
FastBusiness-MCP-Package/  -> Copy toàn bộ folder này
```

**Bước 3**: Cấu hình MCP trong Cursor/VS Code

Cursor: `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`

VS Code: `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "C:\\FastBusiness-MCP-Package\\fastbusiness_mcp.exe",
      "cwd": "C:\\FastBusiness-MCP-Package",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
      }
    }
  }
}
```

**Bước 4**: Restart Cursor/VS Code

**Bước 5**: Test
```
Cursor AI: "List available tools"
→ Should see fastbusiness MCP tools
```

---

## Troubleshooting

### Build lỗi "PyInstaller not found"
```bash
pip install pyinstaller
```

### Build lỗi "Module not found"
```bash
pip install -r requirements.txt
```

### .exe lỗi "VCRUNTIME140.dll"
→ Dùng **onedir build** (file .bat)
→ Hoặc cài Visual C++ Runtime: https://aka.ms/vs/17/release/vc_redist.x64.exe

### .exe chạy nhưng không có output
→ Check console output
→ Check config.yaml paths
→ Check LMDB database exists

---

## Build Options Reference

### Onedir (Recommended)
```bash
build_onedir.bat
```
→ Output: `FastBusiness-MCP-Package/`

### Onefile (Single .exe)
```bash
pyinstaller fastbusiness_mcp.spec --clean
```
→ Output: `dist/fastbusiness_mcp.exe`

### Development Mode (No build)
```bash
python run_server.py
```
→ Use trong development, không deploy

---

## Files Structure

### Source Files (Development)
```
mcp_fbo/
  run_server.py             <- Entry point
  fastbusiness_mcp/         <- Source code
  knowledge_base/           <- YAML knowledge base
  data/fields_lmdb/         <- LMDB database
  config.yaml               <- Configuration
  build_onedir.bat          <- Build script
  fastbusiness_mcp.spec     <- PyInstaller spec (onefile)
```

### Build Output (Onedir)
```
FastBusiness-MCP-Package/
  fastbusiness_mcp.exe      <- Run this
  _internal/                <- Dependencies
  knowledge_base/
  data/
  config.yaml
```

### Build Output (Onefile)
```
dist/
  fastbusiness_mcp.exe      <- Single file
```

---

## Testing After Build

### Test 1: Run executable
```bash
cd FastBusiness-MCP-Package
fastbusiness_mcp.exe
```
→ Should show MCP server starting

### Test 2: Check database
```bash
# Set env var
set FASTBUSINESS_VSCODE_DB_PATH=E:\mcp_fbo\data\fields_lmdb

# Run
fastbusiness_mcp.exe
```
→ Should load LMDB database

### Test 3: Test in Cursor
1. Configure MCP settings
2. Restart Cursor
3. Ask AI: "List available MCP tools"
4. Should see fastbusiness tools

---

## Notes

- **Always use onedir for production** (more stable)
- **Onefile is OK for personal use** (if works on your machine)
- **Clean build** before rebuild: `rmdir /s /q build dist`
- **Test on clean Windows VM** before deploying
- **Antivirus may block** - add exception if needed

---

## Quick Commands

```bash
# Build onedir (recommended)
build_onedir.bat

# Build onefile
pyinstaller fastbusiness_mcp.spec --clean

# Clean build
rmdir /s /q build dist

# Test .exe
dist\fastbusiness_mcp\fastbusiness_mcp.exe

# Development mode
python run_server.py
```

---

## Support

If build fails:
1. Check Python version: `python --version` (need 3.8+)
2. Check PyInstaller: `pyinstaller --version`
3. Install dependencies: `pip install -r requirements.txt`
4. Clean and rebuild: `rmdir /s /q build dist` then rebuild

If .exe fails on other PC:
1. Use onedir build (not onefile)
2. Install Visual C++ Runtime on target PC
3. Check antivirus settings
4. See FIX_VCRUNTIME_ERROR.md for details
