# 🚀 Hướng dẫn Test Nhanh trên VS Code

## Bước 1: Cài đặt Dependencies (Đã xong ✅)

```bash
pip install pydantic lxml aiosqlite pyyaml
```

## Bước 2: Khởi tạo Database (Đã xong ✅)

```bash
python scripts/init_db.py
```

## Bước 3: Test trên VS Code

### Option 1: Dùng Debug Menu (RECOMMENDED)

1. Mở VS Code
2. Nhấn `F5` hoặc vào menu **Run > Start Debugging**
3. Chọn configuration:

   - **Test All MCP Tools** - Test tất cả (khuyến nghị)
   - **Test Partition Validator** - Test partition
   - **Test Result Access** - Test result access
   - **Test File Detector** - Test file detector
   - **Debug MCP Server** - Debug server

4. Xem kết quả trong Terminal

### Option 2: Chạy từ Terminal

```bash
# Test tất cả tools
python tests/manual/test_mcp_client.py

# Test từng tool
python tests/manual/test_partition.py
python tests/manual/test_result_access.py
python tests/manual/test_file_detector.py
```

## Kết quả Mong đợi

```
======================================================================
FastBusiness MCP Server - Comprehensive Tool Testing
======================================================================

📋 Test 1: Partition Validator
----------------------------------------------------------------------
SQL: select * from d91$202501 where stt_rec = @stt_rec
Valid: ❌ NO
  ❌ Hardcoded partition table 'd91$202501' detected
     💡 Replace with: @@prime$partition$current

🔧 Test 2: Partition Fixer
----------------------------------------------------------------------
✅ Fixed 1 hardcoded partition(s)
Original: select * from d91$202501 where stt_rec = @stt_rec
Fixed:    select * from @@prime$partition$current where stt_rec = @stt_rec

...

📊 Test Summary:
  ✅ Partition Validator - Working
  ✅ Partition Fixer - Working
  ✅ Result Access Validator - Working
  ✅ Result Access Fixer - Working
  ✅ File Type Detector - Working
  ✅ Field Generator - Working
  ✅ Command Generator - Working
```

## Các Tool Có Sẵn

### 1. Partition Validator ⚠️ CRITICAL
```python
# Test hardcoded partition
sql = "select * from d91$202501"
# Expected: ❌ Error - must use @@prime$partition$current
```

### 2. Result Access Validator ⚠️ CRITICAL
```python
# Test wrong result access
js = "var x = result[0].ma_kh"
# Expected: ❌ Error - must use result[0].Value
```

### 3. File Type Detector
```python
# Auto-detect XML file type
# Types: Filter, Dir, Grid View, Grid Detail
```

### 4. Code Generators
```python
# Generate fields, commands, scripts
```

### 5. Auto Fixers
```python
# Auto-fix partition and result access issues
```

## Debug trong VS Code

1. Đặt breakpoint trong code (click vào margin bên trái số dòng)
2. Chọn debug configuration
3. Nhấn F5
4. Code sẽ dừng tại breakpoint
5. Dùng Debug toolbar để:
   - Continue (F5)
   - Step Over (F10)
   - Step Into (F11)
   - Step Out (Shift+F11)

## Xem Log

Tất cả log sẽ hiển thị trong:
- **Terminal** tab (output của test)
- **Debug Console** (khi debug)

## Test với File XML Thực Tế

```python
from fastbusiness_mcp.analyzers.file_type_detector import FileTypeDetector
from fastbusiness_mcp.utils.file_utils import read_file

# Load your XML file
xml_content = read_file("/path/to/your/file.xml")

# Detect type
detector = FileTypeDetector()
context = detector.detect(xml_content)

print(f"Type: {context.file_type}")
print(f"Table: {context.table_name}")
```

## Chạy Unit Tests

```bash
# Chạy tất cả unit tests
pytest tests/unit/ -v

# Chạy với coverage
pytest tests/unit/ --cov=fastbusiness_mcp

# Chạy 1 file test
pytest tests/unit/test_validators/test_partition_validator.py -v
```

## Troubleshooting

### Lỗi: Module not found
```bash
pip install -e .
```

### Lỗi: Database not found
```bash
python scripts/init_db.py
```

### Không thấy Debug Menu
- Đảm bảo file `.vscode/launch.json` tồn tại
- Restart VS Code

## Next Steps

1. ✅ Test các tools cơ bản (Done)
2. Test với file XML thực tế của bạn
3. Tích hợp với Claude Desktop (xem README.md)
4. Scan project của bạn: `python scripts/scan_project.py /path/to/project`

---

**Tất cả tests đã pass! Server sẵn sàng sử dụng! 🎉**
