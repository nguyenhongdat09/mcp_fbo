# Build Troubleshooting Guide

## Common Build Issues và Fixes

### Issue 1: ImportError - attempted relative import with no known parent package

**Lỗi:**
```
ImportError: attempted relative import with no known parent package
[PYI-17952:ERROR] Failed to execute script 'server' due to unhandled exception!
```

**Nguyên nhân:**
- PyInstaller chạy `server.py` như script độc lập
- File `server.py` dùng relative imports (`.tools`, `.utils`)
- Relative imports không work khi chạy script trực tiếp

**Giải pháp:**
✅ Đã fix bằng cách tạo `run_server.py` làm entry point
- `run_server.py` dùng absolute imports
- Set up Python path correctly
- Import và run `fastbusiness_mcp.server.main()`

**Verify fix:**
```bash
# Build lại
pyinstaller --clean fastbusiness_mcp.spec

# Test
dist\fastbusiness_mcp.exe
```

---

### Issue 2: Module not found errors

**Lỗi:**
```
ModuleNotFoundError: No module named 'mcp'
ModuleNotFoundError: No module named 'yaml'
```

**Nguyên nhân:**
- PyInstaller không detect được một số dependencies
- Cần thêm vào `hiddenimports` trong spec file

**Giải pháp:**
Edit `fastbusiness_mcp.spec`, thêm vào `hiddenimports`:
```python
hiddenimports = [
    'mcp',
    'mcp.server',
    'yaml',
    'lmdb',
    # ... other imports
]
```

**Verify:**
```bash
pyinstaller --clean fastbusiness_mcp.spec
dist\fastbusiness_mcp.exe
```

---

### Issue 3: Data files not found

**Lỗi:**
```
FileNotFoundError: knowledge_base/api_reference/context_rules.yaml not found
```

**Nguyên nhân:**
- PyInstaller không include data files (YAML, LMDB)
- Cần thêm vào `datas` trong spec file

**Giải pháp:**
Edit `fastbusiness_mcp.spec`, check `datas`:
```python
datas = [
    ('knowledge_base', 'knowledge_base'),
    ('data', 'data'),
    ('config.yaml', '.'),
]
```

**Verify:**
- Build lại
- Check trong `dist/` có folders `knowledge_base`, `data` không

---

### Issue 4: UPX not found

**Lỗi:**
```
Error: UPX is not available
```

**Nguyên nhân:**
- Spec file có `upx=True` nhưng UPX chưa cài

**Giải pháp 1: Disable UPX (đơn giản)**
Edit `fastbusiness_mcp.spec`:
```python
exe = EXE(
    # ...
    upx=False,  # Change to False
    # ...
)
```

**Giải pháp 2: Install UPX (recommended - nén file nhỏ hơn)**
1. Download UPX: https://github.com/upx/upx/releases
2. Extract vào `C:\upx\`
3. Add `C:\upx\` vào PATH
4. Restart terminal
5. Build lại

---

### Issue 5: Build thành công nhưng .exe rất lớn

**Vấn đề:**
- File .exe > 200MB
- Quá lớn để distribute

**Giải pháp:**

**1. Enable UPX compression:**
```python
upx=True,
```

**2. Exclude unused modules:**
```python
excludes=[
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'IPython',
    'notebook',
    'PIL',
    'PyQt5',
    'wx',
],
```

**3. Use --onefile mode:** (already default in spec)

**4. Strip debug symbols:** (already enabled)
```python
strip=False,  # Change to True
```

**Expected size:** 50-100MB

---

### Issue 6: Antivirus blocks executable

**Vấn đề:**
- Windows Defender hoặc antivirus delete .exe
- False positive

**Giải pháp:**

**Temporary:**
1. Disable antivirus khi build
2. Build executable
3. Add exception cho file
4. Re-enable antivirus

**Permanent:**
1. Code signing certificate (nếu có)
2. Submit .exe lên VirusTotal để whitelist

**User-side:**
- Add exception trong antivirus
- Hướng dẫn có trong SETUP_GUIDE.md

---

### Issue 7: Build fails với "Permission denied"

**Lỗi:**
```
PermissionError: [WinError 5] Access denied
```

**Nguyên nhân:**
- Old .exe đang chạy
- Antivirus đang scan
- Không có quyền ghi vào folder

**Giải pháp:**

**1. Close running processes:**
```bash
taskkill /IM fastbusiness_mcp.exe /F
```

**2. Run Command Prompt as Administrator:**
- Right-click Command Prompt
- "Run as administrator"
- Chạy build lại

**3. Clean before build:**
```bash
rmdir /s /q dist
rmdir /s /q build
pyinstaller --clean fastbusiness_mcp.spec
```

---

### Issue 8: Import lỗi sau khi freeze

**Lỗi:**
```
ImportError: cannot import name 'xxx' from 'yyy'
```

**Nguyên nhân:**
- Circular imports
- Dynamic imports
- Namespace packages

**Debug:**

**1. Test imports trước khi build:**
```python
# test_imports.py
import fastbusiness_mcp.server
import fastbusiness_mcp.tools.generate_field_from_lmdb
import fastbusiness_mcp.knowledge_base.engine

print("All imports OK!")
```

**2. Check hiddenimports:**
- Thêm missing module vào hiddenimports

**3. Add debug print:**
Edit `run_server.py`:
```python
import sys
print("Python path:", sys.path)
print("Frozen:", getattr(sys, 'frozen', False))

from fastbusiness_mcp.server import main
main()
```

---

### Issue 9: YAML files không load được

**Lỗi:**
```
FileNotFoundError: knowledge_base/api_reference/context_rules.yaml
```

**Nguyên nhân:**
- PyInstaller extract files vào temp folder khác
- Code đang tìm relative path sai

**Giải pháp:**

**1. Check datas trong spec:**
```python
datas = [
    ('knowledge_base', 'knowledge_base'),  # Source, Destination
]
```

**2. Sửa code load YAML:**
```python
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Running as compiled
    base_path = Path(sys._MEIPASS)  # Temp extract folder
else:
    # Running as script
    base_path = Path(__file__).parent

yaml_path = base_path / 'knowledge_base' / 'api_reference' / 'context_rules.yaml'
```

---

### Issue 10: Console window flashes và tắt ngay

**Vấn đề:**
- Double-click .exe
- Console window xuất hiện rồi tắt ngay
- Không thấy error message

**Giải pháp:**

**1. Chạy từ Command Prompt:**
```bash
cd dist
fastbusiness_mcp.exe
```
→ Sẽ thấy error message trước khi tắt

**2. Thêm pause vào code:**
Edit `run_server.py`:
```python
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
```

**3. Build lại:**
```bash
pyinstaller --clean fastbusiness_mcp.spec
```

---

## Build Best Practices

### 1. Clean build mỗi lần

```bash
pyinstaller --clean fastbusiness_mcp.spec
```

Không dùng cached builds → tránh lỗi cũ

### 2. Test ngay sau build

```bash
# Build
pyinstaller --clean fastbusiness_mcp.spec

# Test immediately
dist\fastbusiness_mcp.exe
```

### 3. Test trên clean machine

- VM Windows mới
- Không có Python
- Fresh install

### 4. Version control spec file

- Commit spec file vào git
- Track changes
- Rollback nếu cần

### 5. Document changes

Nếu sửa spec file, ghi chú:
```python
# 2024-11-03: Added xyz module to hiddenimports
# Reason: Import error when running frozen exe
hiddenimports = [
    'xyz',  # Fix for import error
    # ...
]
```

---

## Quick Reference

### Build commands

```bash
# Standard build
pyinstaller fastbusiness_mcp.spec

# Clean build (recommended)
pyinstaller --clean fastbusiness_mcp.spec

# Debug build (shows import errors)
pyinstaller --log-level DEBUG fastbusiness_mcp.spec

# One-time build without spec
pyinstaller --onefile ^
    --name fastbusiness_mcp ^
    --add-data "knowledge_base;knowledge_base" ^
    run_server.py
```

### Test commands

```bash
# Test executable
dist\fastbusiness_mcp.exe

# Test với input (MCP protocol)
echo {"jsonrpc":"2.0","method":"tools/list","id":1} | dist\fastbusiness_mcp.exe

# Kill process
taskkill /IM fastbusiness_mcp.exe /F

# Check if running
tasklist | findstr "fastbusiness_mcp"
```

### File locations

```
build/              # Temp build files (can delete)
dist/               # Output folder
  fastbusiness_mcp.exe    # Final executable
  knowledge_base/   # Extracted data files (trong temp khi chạy)
  data/             # Extracted data files
```

---

## Debugging Tips

### 1. Enable debug logging

Edit `run_server.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Check what's included in exe

```bash
# List files in archive
pyi-archive_viewer dist\fastbusiness_mcp.exe
```

### 3. Extract exe để xem

```bash
# Extract to folder
pyinstaller --onedir fastbusiness_mcp.spec

# Check dist/fastbusiness_mcp/ folder
dir dist\fastbusiness_mcp
```

### 4. Test imports manually

```python
# test_imports.py
import sys
print(sys.path)

import fastbusiness_mcp
print(fastbusiness_mcp.__file__)

from fastbusiness_mcp.server import main
print("Import OK!")
```

---

## Getting Help

Nếu vẫn gặp issues:

1. ✅ Check error message carefully
2. ✅ Search trong document này
3. ✅ Check PyInstaller docs: https://pyinstaller.org/
4. ✅ Check spec file config
5. ✅ Try clean build
6. ✅ Test on different machine

---

## Success Checklist

Build thành công khi:

- [ ] `pyinstaller` command chạy không error
- [ ] File `dist/fastbusiness_mcp.exe` được tạo
- [ ] Executable size ~50-100MB
- [ ] Run `dist\fastbusiness_mcp.exe` không error
- [ ] MCP server starts và show stdio messages
- [ ] Test trong Cursor: Tools available
- [ ] Test trên clean machine (no Python): Works

---

**Last updated:** 2024-11-03
**Version:** 1.0
