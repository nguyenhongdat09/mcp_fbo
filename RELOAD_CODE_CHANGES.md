# How to Reload Code Changes - FastBusiness MCP

## Vấn đề: Pull code mới nhưng vẫn chạy code cũ

### Nguyên nhân:

1. **Python modules bị cache** - Python không tự động reload modules
2. **.exe package cũ** - Nếu đang dùng .exe, cần rebuild
3. **MCP server chưa restart** - Server vẫn dùng code cũ trong memory

---

## Giải pháp

### Solution 1: Restart MCP Server (Python Development)

Nếu bạn đang dùng Python (không phải .exe):

#### Cursor:
1. Mở Command Palette: `Ctrl+Shift+P`
2. Gõ: `MCP: Restart Server`
3. Chọn server `fastbusiness-mcp`
4. Đợi server restart
5. Test lại

#### VS Code:
1. Mở Command Palette: `Ctrl+Shift+P`
2. Gõ: `Restart MCP Servers`
3. Hoặc reload window: `Developer: Reload Window`

---

### Solution 2: Rebuild .exe Package

Nếu bạn đang dùng .exe package:

**Vấn đề:** .exe đã được build từ code cũ, cần rebuild!

```bash
# 1. Pull code mới
cd E:\mcp_fbo
git pull origin claude/mcp-pull-fastbusiness-011CUkuccYZCQMezy1RoGUhj

# 2. Rebuild .exe
pyinstaller fastbusiness_mcp.spec --clean

# 3. Copy .exe mới vào package
copy dist\fastbusiness_mcp.exe FastBusiness-MCP-v1.0.0\

# 4. Restart Cursor MCP server
```

**Hoặc dùng script:**
```bash
cd E:\mcp_fbo
build_and_package.bat
```

---

### Solution 3: Clear Python Cache (Thorough)

Nếu restart không work:

```bash
cd E:\mcp_fbo

# 1. Stop MCP server (Restart Cursor)

# 2. Clear Python cache
del /s /q __pycache__
del /s /q *.pyc

# 3. Reinstall package
pip uninstall fastbusiness-mcp -y
pip install -e .

# 4. Restart MCP server
```

---

### Solution 4: Force Reload (Development Only)

Thêm code reload vào server (chỉ dev):

```python
# fastbusiness_mcp/server.py (top of file)
import importlib
import sys

# Force reload modules
if 'fastbusiness_mcp.tools.xml_handler_tool' in sys.modules:
    importlib.reload(sys.modules['fastbusiness_mcp.tools.xml_handler_tool'])
```

**Không khuyến khích cho production!**

---

## Cách kiểm tra code đã update chưa

### Check 1: Xem code version

Thêm print vào code để check:

```python
# fastbusiness_mcp/tools/xml_handler_tool.py (line 454)
def _add_client_script_to_field(...):
    """Add clientScript to field definition BEFORE closing </field> tag"""
    print("[DEBUG] Using NEW version - insert before closing tag")  # ← Thêm
    ...
```

Restart và xem logs có dòng debug không.

---

### Check 2: Xem function docstring

```python
# Old version
"""Add clientScript to field definition"""

# New version
"""Add clientScript to field definition BEFORE closing </field> tag"""
```

Trong logs, check docstring nào xuất hiện.

---

### Check 3: Test trực tiếp

Tạo test file nhỏ:

```python
# test_xml_handler.py
from fastbusiness_mcp.tools.xml_handler_tool import XMLHandlerTool

tool = XMLHandlerTool()

xml = """<field name="test">
  <header v="Test"/>
</field>"""

result, found = tool._add_client_script_to_field(xml, "test", "onchange=\"test()\"")

print(result)
# Should see clientScript BEFORE </field>
```

Run:
```bash
python test_xml_handler.py
```

---

## Recommended Workflow

### Development (Python):

```bash
1. git pull origin <branch>
2. Restart MCP server (Ctrl+Shift+P → MCP: Restart)
3. Test
```

### Production (.exe):

```bash
1. git pull origin <branch>
2. pyinstaller fastbusiness_mcp.spec --clean
3. Copy dist\fastbusiness_mcp.exe to package
4. Restart Cursor
5. Test
```

---

## Troubleshooting

### Problem: "Still using old code after restart"

**Cause:** Python cached .pyc files

**Fix:**
```bash
# Delete all cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Restart server
```

---

### Problem: ".exe still old even after rebuild"

**Cause:** Copied wrong .exe or old .exe still in use

**Fix:**
```bash
# 1. Stop Cursor completely
# 2. Delete old .exe
del FastBusiness-MCP-v1.0.0\fastbusiness_mcp.exe

# 3. Rebuild
pyinstaller fastbusiness_mcp.spec --clean

# 4. Copy new .exe
copy dist\fastbusiness_mcp.exe FastBusiness-MCP-v1.0.0\

# 5. Start Cursor
```

---

### Problem: "Can't find changes in git"

**Check commit:**
```bash
git log --oneline -5
# Should see: 3d3e4ec fix: Correct XML handler clientScript and function placement

git show 3d3e4ec
# Should see changes to xml_handler_tool.py
```

---

## Quick Checklist

Before testing:

- [ ] Pulled latest code from git
- [ ] If using .exe: Rebuilt package
- [ ] Restarted MCP server
- [ ] Cleared Python cache (if needed)
- [ ] Checked git log shows latest commit
- [ ] Tested with simple example

---

## Example: Complete Reload Process

### For Python Development:

```bash
# Terminal 1: Update code
cd E:\mcp_fbo
git pull origin claude/mcp-pull-fastbusiness-011CUkuccYZCQMezy1RoGUhj

# Cursor: Restart MCP
# Ctrl+Shift+P → "MCP: Restart Server" → Select fastbusiness-mcp

# Test
# Call: "Thêm xử lý nhập so_ct_hd gán so_seri_hd = '123455'"
# Check XML output
```

### For .exe Package:

```bash
# Terminal: Update & rebuild
cd E:\mcp_fbo
git pull origin claude/mcp-pull-fastbusiness-011CUkuccYZCQMezy1RoGUhj
pyinstaller fastbusiness_mcp.spec --clean
copy dist\fastbusiness_mcp.exe FastBusiness-MCP-v1.0.0\

# Cursor: Restart completely
# Close Cursor → Reopen → Wait for MCP to start

# Test
# Call: "Thêm xử lý nhập so_ct_hd gán so_seri_hd = '123455'"
# Check XML output
```

---

## Summary

| Method | When | Steps |
|--------|------|-------|
| **Restart Server** | Python dev | Ctrl+Shift+P → Restart MCP |
| **Rebuild .exe** | Using package | `pyinstaller` + copy |
| **Clear Cache** | Cache issues | Delete `__pycache__` |

**Most common:** Just restart MCP server! 🔄
