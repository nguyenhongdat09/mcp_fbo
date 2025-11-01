# 📁 JSON Exports Directory

Thư mục này chứa JSON exports của LevelDB databases.

## 🚀 Quick Start - Test Ngay

Nếu bạn muốn **test ngay** mà chưa có database, dùng sample file:

```powershell
cd database\json_exports
copy dir.json.sample dir.json
copy dir.json.sample filter.json
copy dir.json.sample gridview.json
copy dir.json.sample gridinput.json
```

Sau đó test:
```powershell
cd ..\..
python quick_test.py
```

✅ Tool sẽ hoạt động với sample data!

---

## 📤 Export Thật Từ LevelDB

Khi sẵn sàng dùng data thật, bạn có 2 options:

### Option 1: Node.js Export (KHUYẾN NGHỊ - DỄ NHẤT)

```powershell
# 1. Cài Node.js từ nodejs.org
# 2. Install package
cd tools
npm install

# 3. Export
cd ..
node tools/export_leveldb_nodejs.js
```

✅ Không cần Python 3.11, không cần build tools!

**Xem chi tiết**: `tools/NODEJS_EXPORT.md`

### Option 2: Python Export (Nếu Có Python 3.11 hoặc WSL)

```powershell
# Python 3.11
py -3.11 -m venv venv311
venv311\Scripts\Activate.ps1
pip install plyvel-wheels
python tools/export_leveldb_to_json.py --vscode
```

**Xem chi tiết**: `tools/README.md`

---

## 📋 Files Trong Thư Mục Này

| File | Mô tả | Size ước tính |
|------|-------|---------------|
| `dir.json` | DIR database export | ~500KB |
| `filter.json` | FILTER database export | ~300KB |
| `gridview.json` | GRID_VIEW database export | ~400KB |
| `gridinput.json` | GRID_INPUT database export | ~350KB |
| `dir.json.sample` | Sample file để test | ~5KB |
| `README.md` | File này | - |

---

## 🔄 Khi Nào Cần Export Lại?

Export lại khi:
- ✅ LevelDB database được update (thêm/sửa fields)
- ✅ VS Code extension được update
- ✅ Cần sync data mới nhất

**Không cần** export lại khi:
- ❌ Chỉ dùng để test
- ❌ Database không thay đổi

---

## 🗂️ JSON File Format

Mỗi JSON file có format:

```json
{
  "metadata": {
    "source": "leveldb",
    "db_type": "DIR",
    "exported_at": "2024-11-01T10:30:00",
    "total_fields": 150
  },
  "fields": {
    "so_luong": {
      "type": "Decimal",
      "align": "right",
      "dataFormatString": "@quantityInputFormat",
      "header_vi": "Số lượng",
      "header_en": "Quantity"
    },
    ...
  }
}
```

---

## 💡 Tips

### 1. Commit vào Git?

**Nên commit** nếu:
- Files < 10MB
- Team members khác cũng dùng Windows Python 3.13
- Database ít thay đổi

**Không nên** nếu:
- Files > 10MB
- Database thường xuyên update

### 2. Compress Files

Nếu files lớn, có thể zip:
```powershell
Compress-Archive -Path *.json -DestinationPath exports.zip
```

### 3. Validate JSON

Check JSON có valid không:
```powershell
node -e "JSON.parse(require('fs').readFileSync('dir.json', 'utf8')); console.log('Valid JSON')"
```

---

## 🔍 Troubleshooting

### Error: JSON export not found

**Nguyên nhân**: Chưa export hoặc files bị xóa

**Giải pháp**:
1. Check files tồn tại: `ls *.json`
2. Nếu không có, dùng sample: `copy dir.json.sample dir.json`
3. Hoặc export lại từ LevelDB

### Error: Invalid JSON format

**Nguyên nhân**: File JSON bị corrupt hoặc edit sai

**Giải pháp**:
1. Validate JSON: https://jsonlint.com/
2. Hoặc export lại từ LevelDB
3. Hoặc restore từ backup

### Warning: Using sample data

**Nguyên nhân**: Đang dùng file sample

**Ảnh hưởng**:
- Tool vẫn chạy được
- Nhưng chỉ có 10 fields mẫu thay vì 150+ fields thật

**Giải pháp**: Export data thật bằng Node.js hoặc Python

---

## ✅ Next Steps

1. ✅ Export JSON files (Node.js hoặc Python)
2. ✅ Verify files: `ls database\json_exports\`
3. ✅ Test: `python quick_test.py`
4. ✅ Run server: `python -m fastbusiness_mcp.server`

Good luck! 🚀
