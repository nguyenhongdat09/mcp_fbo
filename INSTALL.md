# 📦 Hướng Dẫn Cài Đặt FastBusiness MCP Server

## 📋 Yêu Cầu Hệ Thống

- **Python**: >= 3.10
- **pip**: Latest version
- **Git**: For cloning repository

## 🚀 Các Bước Cài Đặt

### Bước 1: Clone Repository (nếu chưa có)

```bash
git clone <repository-url>
cd mcp_fbo
```

### Bước 2: Tạo Virtual Environment (Khuyến nghị)

#### Trên Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

#### Trên Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Bước 3: Cài Đặt Dependencies

#### Option A: Cài đặt Production (Khuyến nghị cho user thường)
```bash
pip install -r requirements.txt
```

Hoặc cài từng package riêng lẻ:
```bash
pip install mcp>=0.9.0
pip install lxml>=5.0.0
pip install pydantic>=2.0.0
pip install aiosqlite>=0.19.0
pip install plyvel>=1.5.0
pip install pyyaml>=6.0.0
```

#### Option B: Cài đặt Full (Bao gồm Dev Tools)
```bash
pip install -r requirements-dev.txt
```

#### Option C: Cài đặt từ pyproject.toml
```bash
pip install -e .
```

Hoặc với dev dependencies:
```bash
pip install -e ".[dev]"
```

### Bước 4: Verify Installation

```bash
python -c "import mcp; import lxml; import pydantic; import plyvel; print('✅ All packages installed successfully!')"
```

## 🔧 Cài Đặt LevelDB Support

**LƯU Ý**: Server hỗ trợ 2 backends: **plyvel** (LevelDB native) hoặc **python-rocksdb** (RocksDB - tương thích với LevelDB). Chỉ cần cài 1 trong 2.

### Windows

**Option A: RocksDB (KHUYẾN NGHỊ cho Windows Python 3.13)**
```bash
pip install python-rocksdb
```
✅ Hoạt động tốt trên Windows Python 3.13
✅ Không cần build tools
✅ Đọc được LevelDB databases

**Option B: plyvel (cho Python 3.11 hoặc thấp hơn)**
```bash
pip install plyvel-wheels
```

**Option C: Build từ source (Chỉ nếu Option A & B không work)**
1. Cài Visual Studio Build Tools:
   - Download: https://visualstudio.microsoft.com/downloads/
   - Chọn "Desktop development with C++"

2. Cài LevelDB:
   ```bash
   pip install plyvel --no-binary :all:
   ```

### Linux (Ubuntu/Debian)

**Option A: plyvel (Khuyến nghị)**
```bash
# Cài LevelDB development files
sudo apt-get update
sudo apt-get install libleveldb-dev

# Cài plyvel
pip install plyvel
```

**Option B: RocksDB**
```bash
pip install python-rocksdb
```

### macOS

**Option A: plyvel (Khuyến nghị)**
```bash
# Cài LevelDB qua Homebrew
brew install leveldb

# Cài plyvel
pip install plyvel
```

**Option B: RocksDB**
```bash
pip install python-rocksdb
```

## 🗄️ Setup Database

### Option 1: Sử dụng VS Code Extension Database (Đã có sẵn)

Nếu bạn đã cài VS Code extension `fbo-autocomplete`, database đã có tại:
```
C:\Users\nguye\.vscode\extensions\nguyen-hong-dat.fbo-autocomplete-0.0.40\src\Database
```

Server sẽ tự động detect và sử dụng.

### Option 2: Custom Database Path

Set environment variable:

**Windows (PowerShell):**
```powershell
$env:FASTBUSINESS_VSCODE_DB_PATH = "C:\Path\To\Your\Database"
```

**Windows (CMD):**
```cmd
set FASTBUSINESS_VSCODE_DB_PATH=C:\Path\To\Your\Database
```

**Linux/macOS:**
```bash
export FASTBUSINESS_VSCODE_DB_PATH="/path/to/your/database"
```

### Option 3: Local Database

Copy LevelDB files vào:
```
fastbusiness_mcp/database/
├── Dir/
├── Filter/
├── GridView/
└── GridInput/
```

## ✅ Test Installation

### Test 1: Import Modules
```bash
python -c "from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector; print('✅ Imports OK')"
```

### Test 2: Test LevelDB Connection
```bash
python -c "from fastbusiness_mcp.leveldb_adapter import LevelDBManager; print('✅ LevelDB OK')"
```

### Test 3: Run Manual Tests (Optional)
```bash
# Test file type detection
python tests/manual/test_file_type_detector.py

# Test MCP client
python tests/manual/test_mcp_client.py
```

## 🐛 Troubleshooting

### Lỗi: `ModuleNotFoundError: No module named 'plyvel'`

**Giải pháp:**
```bash
pip install plyvel
```

Nếu vẫn lỗi, thử:
```bash
pip install plyvel-wheels
```

### Lỗi: `error: Microsoft Visual C++ 14.0 or greater is required`

**Giải pháp (Windows):**
1. Cài Visual Studio Build Tools
2. Hoặc dùng pre-built wheel:
   ```bash
   pip install plyvel-wheels
   ```

### Lỗi: `libleveldb.so.1: cannot open shared object file`

**Giải pháp (Linux):**
```bash
sudo apt-get install libleveldb1d libleveldb-dev
```

### Lỗi: Database not found

**Giải pháp:**
1. Check VS Code extension đã cài chưa
2. Hoặc set custom path với `FASTBUSINESS_VSCODE_DB_PATH`
3. Hoặc copy LevelDB files vào `fastbusiness_mcp/database/`

## 📚 Next Steps

Sau khi cài đặt xong:

1. ✅ Đọc [README.md](README.md) để hiểu cách sử dụng
2. ✅ Đọc [QUICKSTART_TEST.md](QUICKSTART_TEST.md) để test các tính năng
3. ✅ Configure Claude Desktop (nếu dùng với Claude)

## 🔗 Links Hữu Ích

- **VS Code Extension**: `nguyen-hong-dat.fbo-autocomplete`
- **MCP Docs**: https://modelcontextprotocol.io
- **LevelDB**: https://github.com/google/leveldb
- **plyvel**: https://plyvel.readthedocs.io

---

## 💡 Tips

### Upgrade Dependencies
```bash
pip install --upgrade -r requirements.txt
```

### Freeze Current Environment
```bash
pip freeze > requirements-frozen.txt
```

### Uninstall All
```bash
pip uninstall -r requirements.txt -y
```

---

**Cần hỗ trợ?** Tạo issue tại repository hoặc liên hệ team!
