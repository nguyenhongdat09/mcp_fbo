# 🪟 Hướng Dẫn Sử Dụng Trên Windows Python 3.13

## ⚠️ Vấn Đề

Bạn đang dùng **Windows Python 3.13** và gặp lỗi:
```
ERROR: Failed building wheel for plyvel
ERROR: Failed building wheel for python-rocksdb
```

**Nguyên nhân**: Python 3.13 quá mới, chưa có pre-built wheels. Build từ source cần C++ compiler và dependencies phức tạp.

## ✅ Giải Pháp: JSON Fallback Mode

MCP Server tự động dùng **JSON fallback mode** khi không cài được plyvel/rocksdb.

### Quy Trình Đơn Giản

```
Step 1: Export LevelDB → JSON (dùng Python 3.11 hoặc WSL)
Step 2: Copy JSON files về Python 3.13
Step 3: Run MCP server (tự động dùng JSON)
```

---

## 📋 STEP 1: Export LevelDB → JSON

Bạn có 2 options:

### Option A: Dùng Python 3.11 (Đơn giản nhất)

#### 1.1. Download Python 3.11
- Link: https://www.python.org/downloads/release/python-3110/
- Chọn "Windows installer (64-bit)"
- Cài đặt (checkbox "Add to PATH")

#### 1.2. Tạo venv với Python 3.11
```powershell
# Mở PowerShell
cd E:\mcp_fbo

# Tạo venv mới với Python 3.11
py -3.11 -m venv venv311

# Activate
venv311\Scripts\Activate.ps1
```

#### 1.3. Cài plyvel
```powershell
pip install plyvel-wheels
```

#### 1.4. Export databases
```powershell
# Pull code mới nhất trước
git pull origin claude/fastbusiness-mcp-server-011CUd52Yfab3eJKMkoyoxd5

# Export
python tools/export_leveldb_to_json.py --vscode
```

**Kết quả**:
```
Exporting from VS Code extension...
✅ DIR: 150 fields, 0.45 MB
✅ FILTER: 80 fields, 0.25 MB
✅ GRID_VIEW: 120 fields, 0.38 MB
✅ GRID_INPUT: 100 fields, 0.32 MB

Export completed successfully!
```

Files được tạo:
```
E:\mcp_fbo\database\json_exports\
├── dir.json
├── filter.json
├── gridview.json
└── gridinput.json
```

#### 1.5. Deactivate venv Python 3.11
```powershell
deactivate
```

### Option B: Dùng WSL

#### 1.1. Cài WSL (nếu chưa có)
```powershell
wsl --install
# Restart máy nếu cần
```

#### 1.2. Vào WSL và cài dependencies
```bash
# Trong WSL terminal
sudo apt-get update
sudo apt-get install python3 python3-pip libleveldb-dev
pip3 install plyvel
```

#### 1.3. Export từ WSL
```bash
cd /mnt/e/mcp_fbo

python3 tools/export_leveldb_to_json.py --vscode \
  --vscode-path "/mnt/c/Users/nguye/.vscode/extensions/nguyen-hong-dat.fbo-autocomplete-0.0.40/src/Database"
```

---

## 📋 STEP 2: Về Python 3.13 Environment

### 2.1. Pull code mới nhất
```powershell
cd E:\mcp_fbo
git pull origin claude/fastbusiness-mcp-server-011CUd52Yfab3eJKMkoyoxd5
```

### 2.2. Activate venv Python 3.13
```powershell
venv\Scripts\Activate.ps1
```

### 2.3. Kiểm tra JSON files
```powershell
ls database\json_exports\
```

Phải thấy:
```
dir.json
filter.json
gridview.json
gridinput.json
```

---

## 📋 STEP 3: Test Mọi Thứ Hoạt Động

### 3.1. Quick Test
```powershell
python quick_test.py
```

**Kết quả mong đợi**:
```
🔍 QUICK TEST - LevelDB Tool

Step 1: Checking database backend...
  ⚠️  No LevelDB backend installed
  ✅ Using JSON fallback mode

Step 2: Checking LevelDB Manager...
  ✅ LevelDB Manager ready (using json)

Step 3: Checking database paths...
  Looking for JSON export files...
  ✅ Found: database\json_exports\dir.json
  ✅ Found: database\json_exports\filter.json
  ✅ Found: database\json_exports\gridview.json
  ✅ Found: database\json_exports\gridinput.json

Step 4: Testing generate_field_from_db tool...
  ✅ Tool works! Generated field: so_luong
  Source: exact_match

============================================================
✅ ALL CHECKS PASSED - LevelDB tool is ready!
============================================================
```

### 3.2. Start MCP Server
```powershell
python -m fastbusiness_mcp.server
```

**Log sẽ hiện**:
```
WARNING: Neither plyvel nor rocksdb is installed. Using JSON fallback mode.
INFO: Using json as database backend
INFO: Using JSON export files as data source
INFO: Connected to DIR JSON export at database\json_exports\dir.json
INFO: Connected to FILTER JSON export at database\json_exports\filter.json
INFO: Connected to GRID_VIEW JSON export at database\json_exports\gridview.json
INFO: Connected to GRID_INPUT JSON export at database\json_exports\gridinput.json
INFO: FastBusiness MCP Server initialized
```

---

## 🎯 Sử Dụng Tool Trong MCP

Sau khi server chạy, trong Claude/Cline prompt:

```
Dùng tool generate_field_from_db tạo trường "so_luong" cho DIR context
```

Hoặc:

```
Tạo các trường sau từ database:
- ma_vtat (mã vật tư) cho FILTER_NORMAL
- ngay_ct (ngày chứng từ) cho DIR
- tien_nt (tiền ngoại tệ) cho GRID_VIEW
```

Tool sẽ lấy data từ JSON files (thay vì LevelDB).

---

## 📊 So Sánh Performance

| Backend | Speed | Installation | Recommended For |
|---------|-------|--------------|-----------------|
| plyvel | ⚡⚡⚡ Rất nhanh | ❌ Khó (Windows 3.13) | Production Linux |
| rocksdb | ⚡⚡⚡ Rất nhanh | ❌ Khó (Windows 3.13) | Production |
| **JSON** | ⚡⚡ Nhanh | ✅ Cực dễ | **Windows Python 3.13** |

**JSON fallback**:
- ✅ Không cần build tools
- ✅ Không cần C++ compiler
- ✅ Works với mọi Python version
- ✅ Simple JSON files
- ⚠️ Chậm hơn một chút (nhưng OK cho dev)
- ⚠️ Load toàn bộ data vào memory

---

## ❓ FAQ

### Q: Tôi phải export lại JSON mỗi khi database thay đổi?

**A**: Đúng vậy. Khi LevelDB database update (thêm/sửa fields), bạn cần:
1. Export lại bằng script
2. Copy JSON files mới về

### Q: JSON files có thể commit vào Git không?

**A**:
- ✅ **Nên commit** nếu < 10MB và ít thay đổi
- ❌ **Không nên** nếu > 10MB hoặc thường xuyên update
- Tạo `.gitignore` entry: `database/json_exports/*.json`

### Q: Performance có đủ tốt cho production không?

**A**:
- ✅ OK cho development/testing
- ⚠️ OK cho production nếu database nhỏ (< 50MB)
- ❌ Không khuyến nghị cho production với database lớn
- **Best practice**: Deploy production trên Linux server với plyvel

### Q: Tôi có thể edit JSON files trực tiếp không?

**A**: ✅ CÓ! JSON files có thể edit bằng text editor.

Format:
```json
{
  "metadata": {...},
  "fields": {
    "so_luong": {
      "type": "Decimal",
      "header_vi": "Số lượng",
      ...
    }
  }
}
```

Nhưng cẩn thận với JSON syntax!

### Q: Làm sao biết server đang dùng backend nào?

**A**: Check log khi start server:
```
INFO: Using json as database backend          ← JSON mode
INFO: Using plyvel as database backend        ← plyvel mode
INFO: Using rocksdb as database backend       ← RocksDB mode
```

Hoặc chạy:
```powershell
python -c "from fastbusiness_mcp.leveldb_adapter.leveldb_manager import DB_BACKEND; print(f'Backend: {DB_BACKEND}')"
```

---

## 🚀 Summary - Quy Trình Hoàn Chỉnh

```
┌─────────────────────────────────────────────┐
│ Python 3.11 / WSL                           │
│                                             │
│ 1. pip install plyvel-wheels                │
│ 2. python tools/export_leveldb_to_json.py  │
│    → database/json_exports/*.json           │
└─────────────────────────────────────────────┘
                    │
                    │ Copy JSON files
                    ▼
┌─────────────────────────────────────────────┐
│ Windows Python 3.13                         │
│                                             │
│ 1. git pull (để có code mới)               │
│ 2. Copy JSON files vào database/json_exports│
│ 3. python quick_test.py (verify)           │
│ 4. python -m fastbusiness_mcp.server        │
│    → Tự động dùng JSON fallback ✅          │
└─────────────────────────────────────────────┘
```

---

## 📞 Cần Giúp Đỡ?

1. **Check logs**: Xem messages khi start server
2. **Run quick_test.py**: Diagnose vấn đề
3. **Verify JSON files**: Open bằng text editor, check format
4. **Read tools/README.md**: Hướng dẫn chi tiết hơn

Good luck! 🎉
