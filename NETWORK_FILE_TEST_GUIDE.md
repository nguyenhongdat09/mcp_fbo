# 🌐 Hướng dẫn Test File XML từ Network Share

## File cần test
```
\\172.168.5.14\CustomerPro\FBI\TMSG\FBISP242\App_Data\Controllers\Dir\SATran.xml
```

## Cách 1: Chạy trực tiếp trên VS Code (KHUYẾN NGHỊ)

### Bước 1: Mở VS Code trên máy Windows có kết nối mạng

Đảm bảo máy của bạn có thể truy cập được đường dẫn mạng:
```
\\172.168.5.14\CustomerPro\FBI\TMSG\FBISP242\App_Data\Controllers\Dir\
```

### Bước 2: Chạy Debug Configuration

1. Nhấn `F5` hoặc vào menu **Run > Start Debugging**
2. Chọn **"Test Network XML File"**
3. Xem kết quả trong Terminal

### Bước 3: Đọc kết quả

Script sẽ thực hiện 7 bước phân tích:

```
================================================================================
FastBusiness XML File Analyzer
================================================================================

🔍 Step 1: Reading file...
--------------------------------------------------------------------------------
✅ Successfully read with utf-8
File size: 123,456 characters
Lines: 3,456

🔍 Step 2: Validating XML structure...
--------------------------------------------------------------------------------
Structure: ✅ Valid
Message: XML structure is valid

🔍 Step 3: Extracting ENTITY declarations...
--------------------------------------------------------------------------------
Found 15 ENTITY declarations

Entity mappings:
  1. &XMLWhenFilterLoading; → SQLWhenFilterLoading.xml
  2. &XMLWhenFilterValidating; → SQLWhenFilterValidating.xml
  ... and 13 more

🔍 Step 4: Parsing XML...
--------------------------------------------------------------------------------
✅ Successfully parsed XML!
Root tag: <dir>
Attributes: {'table': 'm91$000000', 'type': 'Voucher'}

Elements found:
  - Fields: 45
  - Commands: 12
  - Actions: 8

🔍 Step 5: Detecting file type...
--------------------------------------------------------------------------------
File type: dir
Table: m91$000000
Has partition: True
Partition field: thang
Events: Inserting, Updating, Deleting, Loading

🔍 Step 6: Extracting CDATA blocks...
--------------------------------------------------------------------------------
Found 12 CDATA blocks

Validating CDATA content...

  ⚠️  CDATA Block 3 (line 145, <command>):
     ❌ Hardcoded partition table 'd91$202501' detected at line 3
        💡 Replace with: @@prime$partition$current

Validation Summary:
  - Partition issues: 2
  - Result access issues: 1
  ⚠️  Some issues found - review above

================================================================================
📊 SUMMARY
================================================================================

File Information:
  ✅ Path: \\172.168.5.14\...\SATran.xml
  ✅ Size: 123,456 characters
  ✅ Lines: 3,456
  ✅ Encoding: Detected automatically

Structure:
  ✅ Valid XML: True
  ✅ ENTITY declarations: 15
  ✅ Parsed successfully: Yes

Content:
  ✅ File type: dir
  ✅ Fields: 45
  ✅ Commands: 12
  ✅ CDATA blocks: 12

Validation:
  ⚠️  Partition issues: 2
  ✅ Result access issues: 0

⚠️  File parsed successfully but has some validation warnings
================================================================================
```

## Cách 2: Chạy từ Terminal/Command Prompt

### Option A: Test file mặc định
```bash
python tests/manual/test_network_file.py
```

### Option B: Test file khác
```bash
python tests/manual/test_network_file.py "\\172.168.5.14\CustomerPro\FBI\TMSG\FBISP242\App_Data\Controllers\Dir\MyFile.xml"
```

### Option C: Test file local (đã copy về máy)
```bash
python tests/manual/test_network_file.py "C:\Temp\SATran.xml"
```

## Cách 3: Nếu không truy cập được Network Share

### Bước 1: Copy file về máy local
```
Copy: \\172.168.5.14\CustomerPro\FBI\TMSG\FBISP242\App_Data\Controllers\Dir\SATran.xml
To:   C:\Temp\SATran.xml
```

### Bước 2: Sửa đường dẫn trong test script

Mở file `tests/manual/test_network_file.py` và sửa dòng 230:

```python
# Từ:
default_path = r"\\172.168.5.14\CustomerPro\FBI\TMSG\FBISP242\App_Data\Controllers\Dir\SATran.xml"

# Thành:
default_path = r"C:\Temp\SATran.xml"
```

### Bước 3: Chạy test
```bash
python tests/manual/test_network_file.py
```

## Ý nghĩa các bước phân tích

### Step 1: Reading file
- Thử đọc file với nhiều encoding khác nhau (utf-8, utf-16, latin-1, etc.)
- Hiển thị kích thước và số dòng

### Step 2: Validating XML structure
- Kiểm tra XML có hợp lệ không
- Kiểm tra có thẻ đóng/mở đúng không

### Step 3: Extracting ENTITY declarations
- Tìm tất cả ENTITY declarations trong DOCTYPE
- Hiển thị danh sách entities (quan trọng cho việc debug)

### Step 4: Parsing XML
- Parse XML với multi-strategy parser (có thể handle nhiều entities)
- Đếm số lượng fields, commands, actions

### Step 5: Detecting file type
- Phát hiện loại file (Filter, DIR, Grid View, Grid Detail)
- Xác định table, partition field, events

### Step 6: Validating CDATA blocks
- Tìm tất cả CDATA blocks (chứa SQL và JavaScript)
- **CRITICAL**: Validate partition usage (phát hiện hardcoded partition)
- **CRITICAL**: Validate result access (phát hiện sai pattern)

### Step 7: Summary
- Tổng hợp tất cả thông tin
- Đánh giá file có valid không
- Liệt kê các vấn đề cần fix

## Xử lý Lỗi

### Lỗi: File not found
```
❌ Failed to read file: File not found: \\172.168.5.14\...
```

**Giải pháp:**
1. Kiểm tra đường dẫn mạng có đúng không
2. Kiểm tra máy có kết nối được với 172.168.5.14 không
3. Thử ping: `ping 172.168.5.14`
4. Thử truy cập thủ công trong File Explorer
5. Copy file về local và test

### Lỗi: Permission denied
```
❌ Failed to read file: Permission denied: \\172.168.5.14\...
```

**Giải pháp:**
1. Kiểm tra quyền truy cập network share
2. Đăng nhập với user có quyền đọc
3. Copy file về local và test

### Lỗi: Could not read file with any encoding
```
❌ Could not read file with any encoding
```

**Giải pháp:**
1. File có thể bị corrupt
2. Thử mở bằng text editor khác (Notepad++, VS Code)
3. Kiểm tra file có phải binary không

### Lỗi: Failed to parse XML
```
❌ Failed to parse XML with all strategies
   Please check the XML file for syntax errors
```

**Giải pháp:**
1. Mở file bằng XML editor để kiểm tra syntax
2. Kiểm tra có thẻ đóng/mở thiếu không
3. Kiểm tra có ký tự đặc biệt không hợp lệ không

## Các Issues Thường Gặp

### 🔴 CRITICAL: Hardcoded Partition
```
❌ Hardcoded partition table 'd91$202501' detected
💡 Replace with: @@prime$partition$current
```

**Nghĩa là:**
- File có dùng bảng partition cố định (d91$202501)
- Cần đổi thành `@@prime$partition$current` để dynamic

**Cách fix:**
1. Tìm đoạn SQL chứa `d91$202501`
2. Thay bằng `@@prime$partition$current`
3. Hoặc dùng MCP tool `fix_partition_usage` để auto-fix

### 🔴 CRITICAL: Result Access Pattern
```
❌ Direct property access 'result[0].ma_kh' detected
💡 Use result[index].Value instead
```

**Nghĩa là:**
- JavaScript code truy cập result sai cách
- Phải dùng `.Value` thay vì `.property_name`

**Cách fix:**
1. Tìm đoạn code có `result[0].ma_kh`
2. Đổi thành `result[0].Value` (nếu chỉ có 1 field trong SELECT)
3. Hoặc dùng MCP tool `fix_result_access` để auto-fix

### ⚠️  WARNING: Parent Form Access
```
❌ Direct parent access 'g.parentForm' detected
💡 Use g.get_element().parentForm instead
```

**Nghĩa là:**
- Grid Detail code truy cập parent form không đúng cách

**Cách fix:**
1. Đổi `g.parentForm` thành `g.get_element().parentForm`

## Output Files

Script không tạo file output. Tất cả kết quả hiển thị trong Terminal.

Nếu muốn save kết quả:
```bash
python tests/manual/test_network_file.py > test_result.txt 2>&1
```

## Next Steps Sau Khi Test

### Nếu file VALID (không có lỗi)
```
✅ File is valid and ready to use!
```
👉 File OK, có thể dùng ngay

### Nếu file có WARNINGS
```
⚠️  File parsed successfully but has some validation warnings
```
👉 File parse được nhưng có issues cần fix:
1. Xem danh sách issues trong output
2. Dùng MCP tools để auto-fix:
   - `fix_partition_usage` - Fix hardcoded partitions
   - `fix_result_access` - Fix result access patterns
3. Hoặc fix thủ công theo suggestions

### Nếu file INVALID
```
❌ File has parsing errors that need to be fixed
```
👉 File không parse được:
1. Kiểm tra XML syntax
2. Kiểm tra encoding
3. Kiểm tra ENTITY declarations

## Tích hợp với Claude Desktop

Sau khi test file, bạn có thể dùng MCP server để:
1. Auto-detect file type
2. Auto-fix partition issues
3. Auto-fix result access issues
4. Generate new fields
5. Generate commands
6. Validate code

Xem `README.md` để biết cách config Claude Desktop.

---

**🎯 Mục tiêu:** Đảm bảo file XML parse được và không có critical issues trước khi deploy!
