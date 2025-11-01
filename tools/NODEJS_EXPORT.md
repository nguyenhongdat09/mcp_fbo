# 🟢 Export LevelDB Bằng Node.js (DỄ NHẤT!)

## ✅ Tại Sao Dùng Node.js?

| Feature | Python (plyvel) | **Node.js (level)** |
|---------|-----------------|---------------------|
| Cài đặt trên Windows | ❌ Failed build | ✅ **npm install** |
| Cần C++ compiler | ✅ Cần | ❌ **Không cần** |
| Cần build tools | ✅ Cần | ❌ **Không cần** |
| Python 3.13 | ❌ Không work | ✅ **Không liên quan** |
| Thời gian setup | 😓 1-2 giờ | 😊 **2 phút** |

**Kết luận**: Node.js export là giải pháp **NHANH NHẤT và DỄ NHẤT** cho Windows!

---

## 📋 Bước 1: Cài Node.js (Nếu Chưa Có)

### Kiểm tra đã có Node.js chưa:

```powershell
node --version
```

Nếu hiện version (vd: `v20.10.0`) → ✅ Đã có, skip bước này

### Nếu chưa có:

1. **Download Node.js**:
   - Link: https://nodejs.org/
   - Chọn "LTS" version (khuyến nghị)
   - Download "Windows Installer (.msi)"

2. **Cài đặt**:
   - Chạy file .msi vừa download
   - Next → Next → Install
   - **Quan trọng**: Checkbox "Automatically install necessary tools" → **KHÔNG CẦN** tick (Node.js tự build sẵn)

3. **Verify**:
```powershell
node --version
npm --version
```

Cả 2 đều phải hiện version → ✅ OK

---

## 📋 Bước 2: Cài Package `level`

```powershell
cd E:\mcp_fbo\tools
npm install
```

Hoặc cài global:
```powershell
npm install -g level
```

**Chỉ mất 10-30 giây!** Không có lỗi, không cần build.

---

## 📋 Bước 3: Export LevelDB → JSON

### Default (VS Code extension path):

```powershell
cd E:\mcp_fbo
node tools/export_leveldb_nodejs.js
```

### Custom path:

```powershell
$env:FASTBUSINESS_VSCODE_DB_PATH = "C:\path\to\your\database"
node tools/export_leveldb_nodejs.js
```

---

## 📊 Kết Quả Mong Đợi

```
============================================================
LEVELDB TO JSON EXPORTER (Node.js)
============================================================

VS Code extension path: C:\Users\nguye\.vscode\...
Output directory: database/json_exports

============================================================
Exporting DIR database
============================================================
Source: C:\Users\nguye\.vscode\...\Database\Dir
Output: database/json_exports/dir.json

Opening database...
Reading fields...
  ✅ Read 150 fields

Writing JSON file...
  ✅ Exported to database/json_exports/dir.json
  File size: 472,581 bytes (0.45 MB)

============================================================
Exporting FILTER database
============================================================
...

============================================================
EXPORT SUMMARY
============================================================
✅ DIR: 150 fields, 0.45 MB
✅ FILTER: 80 fields, 0.25 MB
✅ GRID_VIEW: 120 fields, 0.38 MB
✅ GRID_INPUT: 100 fields, 0.32 MB

Total: 4/4 databases exported
Total fields: 450
Total size: 1.40 MB

✅ Export completed successfully!

Next steps:
  1. JSON files are ready at: E:\mcp_fbo\database\json_exports
  2. These files can be used with MCP server in JSON fallback mode
  3. Run: python -m fastbusiness_mcp.server
  4. Server will automatically detect and use JSON files
```

---

## 📋 Bước 4: Test JSON Files

```powershell
# Về Python environment
cd E:\mcp_fbo
venv\Scripts\Activate.ps1

# Test
python quick_test.py
```

**Kết quả**:
```
✅ Using JSON fallback mode
✅ LevelDB Manager ready (using json)
✅ Found: database\json_exports\dir.json
✅ Tool works!
```

---

## 🎯 Script Options

### Thay đổi VS Code path:

```powershell
$env:FASTBUSINESS_VSCODE_DB_PATH = "D:\MyExtensions\fbo-autocomplete\Database"
node tools/export_leveldb_nodejs.js
```

### Thay đổi output directory:

```powershell
$env:FASTBUSINESS_JSON_DB_PATH = "E:\exports"
node tools/export_leveldb_nodejs.js
```

### Export single database:

Sửa file `export_leveldb_nodejs.js`, comment out databases không cần:

```javascript
const databases = [
    { dir: 'Dir', file: 'dir.json', type: 'DIR' },
    // { dir: 'Filter', file: 'filter.json', type: 'FILTER' },
    // { dir: 'GridView', file: 'gridview.json', type: 'GRID_VIEW' },
    // { dir: 'GridInput', file: 'gridinput.json', type: 'GRID_INPUT' },
];
```

---

## ❓ Troubleshooting

### Lỗi: "level" package not installed

```powershell
cd E:\mcp_fbo\tools
npm install level
```

### Lỗi: Database not found

Check path:
```powershell
ls "C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database"
```

Phải thấy folders: `Dir`, `Filter`, `GridView`, `GridInput`

Nếu không đúng, set custom path:
```powershell
$env:FASTBUSINESS_VSCODE_DB_PATH = "YOUR_ACTUAL_PATH"
```

### Lỗi: Permission denied

Chạy PowerShell as Administrator:
```powershell
# Right-click PowerShell → Run as Administrator
cd E:\mcp_fbo
node tools/export_leveldb_nodejs.js
```

---

## 🚀 So Sánh Với Python Method

| Step | Python Method | Node.js Method |
|------|---------------|----------------|
| 1. Install tools | Download Python 3.11<br>Install Visual Studio<br>Build plyvel (failed!) | Download Node.js<br>npm install ✅ |
| 2. Export | ❌ Không chạy được | node export.js ✅ |
| 3. Time | 😓 2 hours (và failed) | 😊 **5 minutes** |

---

## ✅ Summary

**Cho Windows users**:
1. ✅ Cài Node.js (5 phút)
2. ✅ `npm install` (30 giây)
3. ✅ `node tools/export_leveldb_nodejs.js` (30 giây)
4. ✅ DONE!

**Đơn giản hơn Python rất nhiều!**

---

## 💡 Pro Tips

### 1. Cài Node.js bằng winget (nhanh hơn):

```powershell
winget install OpenJS.NodeJS.LTS
```

### 2. Sử dụng nvm (Node Version Manager):

```powershell
# Cài nvm-windows
winget install CoreyButler.NVMforWindows

# Cài Node.js qua nvm
nvm install lts
nvm use lts
```

### 3. Export thành script tái sử dụng:

Tạo file `export.bat`:
```batch
@echo off
cd /d E:\mcp_fbo
node tools/export_leveldb_nodejs.js
pause
```

Double-click `export.bat` để chạy!

---

## 📞 Need Help?

Nếu vẫn gặp vấn đề:
1. Check Node.js version: `node --version` (cần >= 14.0.0)
2. Check npm version: `npm --version`
3. Try global install: `npm install -g level`
4. Check database path exists
5. Run as Administrator

Good luck! 🎉
