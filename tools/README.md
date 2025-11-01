# 🔧 Tools - LevelDB Export Utilities

## Vấn đề: Không cài được plyvel hoặc python-rocksdb

Nếu bạn đang dùng **Windows Python 3.13** và gặp lỗi khi cài:
- `pip install plyvel` → Build failed
- `pip install python-rocksdb` → Build failed

**Nguyên nhân**: Python 3.13 quá mới, chưa có pre-built wheels cho các packages này.

## Giải pháp: JSON Fallback Mode

MCP Server hỗ trợ chế độ **JSON fallback** - đọc dữ liệu từ file JSON thay vì LevelDB trực tiếp.

### 🎯 Quy trình

```
LevelDB (Python 3.11/Linux) → Export JSON → Copy JSON → Use in Python 3.13
```

## 📋 Bước 1: Export LevelDB → JSON

### Option A: Dùng Python 3.11 trên Windows

1. **Download và cài Python 3.11**:
   - https://www.python.org/downloads/release/python-3110/
   - Chọn "Windows installer (64-bit)"

2. **Tạo venv với Python 3.11**:
```powershell
# Giả sử Python 3.11 được cài tại C:\Python311
C:\Python311\python.exe -m venv venv311
venv311\Scripts\Activate.ps1
```

3. **Cài plyvel**:
```powershell
pip install plyvel-wheels
```

4. **Export databases**:
```powershell
python tools/export_leveldb_to_json.py --vscode
```

### Option B: Dùng WSL (Windows Subsystem for Linux)

1. **Cài WSL** (nếu chưa có):
```powershell
wsl --install
```

2. **Trong WSL, cài Python và plyvel**:
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip libleveldb-dev
pip3 install plyvel
```

3. **Copy code vào WSL**:
```bash
cd /mnt/e/mcp_fbo  # E: drive trong WSL
```

4. **Export databases**:
```bash
python3 tools/export_leveldb_to_json.py --vscode \
  --vscode-path "/mnt/c/Users/nguye/.vscode/extensions/nguyen-hong-dat.fbo-autocomplete-0.0.40/src/Database"
```

### Option C: Export từ máy Linux/Mac khác

1. Copy LevelDB database folders sang máy Linux/Mac
2. Chạy export script
3. Copy JSON files về Windows

## 📤 Export Script Usage

### Export tất cả databases từ VS Code extension:

```bash
python tools/export_leveldb_to_json.py --vscode
```

**Output**:
```
database/json_exports/
├── dir.json          # DIR database
├── filter.json       # FILTER database
├── gridview.json     # GRID_VIEW database
└── gridinput.json    # GRID_INPUT database
```

### Export single database:

```bash
python tools/export_leveldb_to_json.py \
  -s "C:\path\to\leveldb\Dir" \
  -o "database/json_exports/dir.json" \
  -t DIR
```

### Custom VS Code path:

```bash
python tools/export_leveldb_to_json.py --vscode \
  --vscode-path "C:\path\to\vscode\extension\Database"
```

### Custom output directory:

```bash
python tools/export_leveldb_to_json.py --vscode \
  --output-dir "E:\my_exports"
```

## 📋 Bước 2: Copy JSON files về Python 3.13 environment

1. **Copy folder `database/json_exports/`** sang máy Python 3.13

2. **Đặt vào đúng vị trí**:
```
E:\mcp_fbo\
└── database\
    └── json_exports\
        ├── dir.json
        ├── filter.json
        ├── gridview.json
        └── gridinput.json
```

## 📋 Bước 3: Sử dụng JSON fallback trong MCP Server

### Không cần cấu hình gì!

Khi chạy `python -m fastbusiness_mcp.server`, server sẽ:

1. ✅ Thử import `plyvel` → Fail
2. ✅ Thử import `rocksdb` → Fail
3. ✅ Tự động chuyển sang **JSON fallback mode**
4. ✅ Đọc từ `database/json_exports/*.json`

**Log sẽ hiện**:
```
WARNING: Neither plyvel nor rocksdb is installed. Using JSON fallback mode.
INFO: Using json as database backend
INFO: Using JSON export files as data source
INFO: Connected to DIR JSON export at database/json_exports/dir.json
INFO: Connected to FILTER JSON export at database/json_exports/filter.json
...
```

### Optional: Custom JSON path

Nếu JSON files ở chỗ khác, set environment variable:

```powershell
$env:FASTBUSINESS_JSON_DB_PATH = "E:\my_exports"
python -m fastbusiness_mcp.server
```

## 🧪 Test JSON fallback

### Quick test:

```powershell
python quick_test.py
```

**Kết quả mong đợi**:
```
Step 1: Checking database backend...
  ✅ Using JSON fallback mode

Step 2: Checking LevelDB Manager...
  ✅ LevelDB Manager ready (using json)

Step 3: Checking database paths...
  ✅ Found: database\json_exports\dir.json

Step 4: Testing generate_field_from_db tool...
  ✅ Tool works! Generated field: so_luong
  Source: exact_match
```

## 📊 JSON File Format

File JSON được export có format:

```json
{
  "metadata": {
    "source": "leveldb",
    "db_type": "DIR",
    "exported_at": "2024-11-01T10:30:00",
    "total_fields": 150,
    "source_path": "C:\\path\\to\\leveldb\\Dir",
    "exported_by": "export_leveldb_to_json.py"
  },
  "fields": {
    "so_luong": {
      "type": "Decimal",
      "align": "right",
      "dataFormatString": "@quantityInputFormat",
      "header_vi": "Số lượng",
      "header_en": "Quantity"
    },
    "ma_khat": {
      "type": "String",
      "align": "left",
      "items": {
        "style": "AutoComplete",
        "controller": "DmVatTu",
        "key": "ma_vtat",
        "reference": "ten_kh%l"
      },
      "header_vi": "Mã khách hàng",
      "header_en": "Customer Code"
    },
    ...
  }
}
```

## ⚠️ Lưu ý

### Performance
- JSON fallback **chậm hơn** plyvel/rocksdb một chút
- Tất cả data load vào memory khi khởi động
- OK cho database < 100MB

### Update data
- Khi database thay đổi, cần export lại JSON
- Không thể write vào JSON (read-only)

### Production
- **Khuyến nghị** dùng plyvel hoặc rocksdb cho production
- JSON fallback chỉ dùng cho development/testing trên Windows Python 3.13

## 🚀 Best Practice

### Cho Windows Python 3.13:
1. Development: Dùng JSON fallback
2. Production: Deploy trên Linux server (có plyvel)

### Cho team:
1. Một người export JSON từ LevelDB (dùng Python 3.11/WSL)
2. Commit JSON files vào Git (nếu nhỏ < 10MB)
3. Mọi người pull về và dùng JSON fallback

## ❓ Troubleshooting

### Lỗi: "JSON export not found"

**Nguyên nhân**: File JSON chưa được export

**Giải pháp**:
1. Check xem file có tồn tại không: `ls database\json_exports\`
2. Nếu không có, export lại bằng script
3. Check path đúng không

### Lỗi: "Error decoding JSON"

**Nguyên nhân**: File JSON bị corrupt hoặc format sai

**Giải pháp**:
1. Xóa file JSON cũ
2. Export lại từ LevelDB
3. Kiểm tra file encoding (phải UTF-8)

### Lỗi: Export script fail "plyvel not installed"

**Nguyên nhân**: Đang chạy trên Python 3.13 hoặc không có plyvel

**Giải pháp**:
1. Dùng Python 3.11: `C:\Python311\python.exe tools/export_leveldb_to_json.py --vscode`
2. Hoặc dùng WSL
3. Hoặc nhờ người khác export

## 📞 Support

Nếu gặp vấn đề:
1. Check log messages khi start server
2. Run `python quick_test.py` để diagnose
3. Check JSON files có tồn tại không
4. Verify JSON format (open bằng text editor)
