# FastBusiness MCP Server - Chi Tiết Setup Guide

## 📋 Mục Lục
1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Verification](#verification)
5. [Usage Guide](#usage-guide)
6. [Advanced Setup](#advanced-setup)
7. [Troubleshooting](#troubleshooting)

---

## System Requirements

### Tối Thiểu
- **OS:** Windows 10 (64-bit)
- **RAM:** 4GB
- **Disk:** 100MB free space
- **Software:** Cursor IDE

### Khuyến Nghị
- **OS:** Windows 11
- **RAM:** 8GB+
- **Disk:** 500MB free space
- **Software:** Cursor IDE (latest version)

### Không Yêu Cầu
- ❌ Python (executable là standalone)
- ❌ Node.js
- ❌ Admin rights (trong hầu hết trường hợp)

---

## Installation

### Bước 1: Extract Package

1. **Download ZIP file:**
   - Nhận file `FastBusiness-MCP-vX.X.X.zip` từ nguồn cung cấp

2. **Extract file:**
   - Right-click ZIP → Extract All...
   - Chọn destination folder (ví dụ: `C:\`)
   - Click Extract

3. **Verify extraction:**
   ```
   C:\FastBusiness-MCP-v1.0.0\
   ├── fastbusiness_mcp.exe    ← File này phải có
   ├── README.md
   ├── SETUP_GUIDE.md
   └── examples\
   ```

4. **Unblock executable (nếu cần):**
   - Right-click `fastbusiness_mcp.exe`
   - Properties
   - Nếu có dòng "This file came from another computer...", check "Unblock"
   - Click Apply → OK

### Bước 2: Test Executable

1. **Open Command Prompt:**
   - Press `Win+R`
   - Type: `cmd`
   - Press Enter

2. **Navigate to folder:**
   ```
   cd C:\FastBusiness-MCP-v1.0.0
   ```

3. **Run executable:**
   ```
   fastbusiness_mcp.exe
   ```

4. **Expected output:**
   - MCP server starts
   - Shows stdio protocol messages
   - No error messages

5. **Stop server:**
   - Press `Ctrl+C`

**✅ Nếu không có error:** Executable hoạt động tốt, tiếp tục bước 3
**❌ Nếu có error:** Xem [Troubleshooting](#troubleshooting)

---

## Configuration

### Option 1: Quick Config (Khuyến nghị)

1. **Open Cursor Settings:**
   - Method 1: Press `Ctrl+,` (Settings) → Search "MCP" → Click "Edit in settings.json"
   - Method 2: Press `Ctrl+Shift+P` → Type "Preferences: Open User Settings (JSON)"

2. **Add MCP config:**
   ```json
   {
     "mcpServers": {
       "fastbusiness": {
         "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
         "args": []
       }
     }
   }
   ```

3. **Important notes:**
   - ⚠️ Thay `C:\\FastBusiness-MCP-v1.0.0\\` bằng đường dẫn thực tế
   - ⚠️ PHẢI dùng **double backslash** (`\\`) trong JSON
   - ⚠️ Không có dấu phẩy ở cuối (nếu là property cuối cùng)

4. **Save file:**
   - Press `Ctrl+S`
   - Close editor

### Option 2: Detailed Config (Có specify tools)

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "args": [],
      "tools": [
        "generate_field_from_lmdb",
        "search_lmdb_fields",
        "lmdb_database_stats",
        "generate_sql_for_fields",
        "detect_context_from_file",
        "get_api_help",
        "generate_code_from_pattern",
        "search_patterns",
        "get_critical_rules",
        "add_onchange_handler",
        "add_onfocus_handler",
        "add_form_lifecycle_handler"
      ]
    }
  }
}
```

**Lợi ích:**
- Specify chính xác tools nào được enable
- Có thể disable tools không dùng

### Option 3: With Environment Variables

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "args": [],
      "env": {
        "FASTBUSINESS_LOG_LEVEL": "INFO",
        "FASTBUSINESS_DB_PATH": "C:\\CustomPath\\database"
      }
    }
  }
}
```

**Environment variables:**
- `FASTBUSINESS_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`
- `FASTBUSINESS_DB_PATH`: Custom database path (optional)

### Common Path Mistakes

**❌ WRONG:**
```json
"command": "C:\FastBusiness-MCP\fastbusiness_mcp.exe"  // Single backslash
"command": "C:/FastBusiness-MCP/fastbusiness_mcp.exe"  // Forward slash
```

**✅ CORRECT:**
```json
"command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe"  // Double backslash
```

**With spaces in path:**
```json
"command": "C:\\Program Files\\FastBusiness-MCP\\fastbusiness_mcp.exe"  // OK with double backslash
```

---

## Verification

### Bước 1: Restart Cursor

1. **Close tất cả Cursor windows:**
   - Close all tabs
   - Close all windows
   - Check Task Manager: No `Cursor.exe` running

2. **Wait 5 seconds**

3. **Open Cursor again**

### Bước 2: Check MCP Server Status

**Method 1: Task Manager**
1. Open Task Manager (`Ctrl+Shift+Esc`)
2. Look for process: `fastbusiness_mcp.exe`
3. ✅ If found: MCP server is running
4. ❌ If not found: Check config and restart Cursor

**Method 2: Cursor Output Panel**
1. In Cursor: `View` → `Output`
2. Select "MCP" from dropdown
3. Look for messages like:
   ```
   [MCP] Starting server: fastbusiness
   [MCP] Server started successfully
   ```

### Bước 3: Test Tools

1. **Open any file in Cursor** (or create new file)

2. **Open Cursor chat** (or Composer)

3. **Ask AI:**
   ```
   List all available MCP tools
   ```

4. **Expected response:**
   AI should list 12 tools:
   - generate_field_from_lmdb
   - search_lmdb_fields
   - lmdb_database_stats
   - generate_sql_for_fields
   - detect_context_from_file
   - get_api_help
   - generate_code_from_pattern
   - search_patterns
   - get_critical_rules
   - add_onchange_handler
   - add_onfocus_handler
   - add_form_lifecycle_handler

5. **✅ If tools are listed:** Setup successful!
6. **❌ If no tools:** See [Troubleshooting](#troubleshooting)

---

## Usage Guide

### Tool 1: Generate Field

**Use case:** Thêm field vào XML file

**Example 1: Simple field**
```
You: Thêm field mã khách hàng
AI: [Opens generate_field_from_lmdb tool]
    Field name? → ma_kh
    → Generates XML field definition
```

**Example 2: Lookup field**
```
You: Thêm field mã khách hàng dạng lookup
AI: [Calls tool with lookup_type='autocomplete']
    → Generates lookup field XML
```

### Tool 2: Add onChange Handler

**Use case:** Thêm JavaScript onChange handler vào field

**Example:**
```
You: Thêm onchange cho ma_kh thì console.log(1)
AI: [Calls add_onchange_handler]
    → Adds <clientScript>onchange="..."</clientScript>
    → Generates onChange function in <script>
```

**Generated code:**
```javascript
function onChange$Voucher$ma_kh(sender) {
    var f = sender.parentForm;
    if (f._action === 'View') return;
    var value = f.getItemValue('ma_kh');
    console.log(1);
}
```

### Tool 3: Get API Help

**Use case:** Hỏi cách dùng API

**Example:**
```
You: Làm sao get giá trị field trong form?
AI: [Calls get_api_help for form API]
    → Shows f.getItemValue() documentation
```

### Tool 4: Detect Context

**Use case:** AI detect file type để dùng đúng API

**Example:**
```
You: File này là Dir hay Grid?
AI: [Calls detect_context_from_file]
    → Returns: Dir (Form)
    → Recommendations: Use f.xxx API
```

### Tool 5: Generate Code from Pattern

**Use case:** Generate code từ template có sẵn

**Example:**
```
You: Tạo code khởi tạo form mới
AI: [Calls generate_code_from_pattern]
    Pattern: form_init_new
    → Generates active$Form$ function
```

---

## Advanced Setup

### Multiple MCP Servers

Nếu bạn có nhiều MCP servers:

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe",
      "args": []
    },
    "other-server": {
      "command": "C:\\Other\\server.exe",
      "args": []
    }
  }
}
```

### Custom Working Directory

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe",
      "args": [],
      "cwd": "C:\\MyProject"
    }
  }
}
```

### Startup Script

Tạo batch file để start MCP server manually (for testing):

**run_mcp.bat:**
```batch
@echo off
echo Starting FastBusiness MCP Server...
echo Press Ctrl+C to stop
C:\FastBusiness-MCP\fastbusiness_mcp.exe
pause
```

---

## Troubleshooting

### Issue 1: Tools Không Hiện

**Symptoms:**
- AI không list tools
- Tools không available trong chat

**Diagnosis:**
1. Check Task Manager: `fastbusiness_mcp.exe` có chạy không?
2. Check Cursor Output panel: Có error messages không?

**Solutions:**

**Solution 1.1: Fix config path**
```json
// Check đường dẫn đúng chưa
"command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe"
// Phải dùng \\ không phải \
```

**Solution 1.2: Restart Cursor properly**
1. Close ALL Cursor windows
2. Check Task Manager: Kill Cursor.exe if still running
3. Wait 10 seconds
4. Open Cursor again

**Solution 1.3: Check executable**
```cmd
C:\FastBusiness-MCP\fastbusiness_mcp.exe
```
Phải chạy được, không error.

**Solution 1.4: Re-extract package**
- Có thể file corrupt khi extract
- Extract lại từ ZIP

### Issue 2: Permission Denied

**Symptoms:**
- Error: "Access denied"
- Server không start

**Solutions:**

**Solution 2.1: Run as Administrator**
1. Right-click Cursor.exe
2. "Run as administrator"

**Solution 2.2: Unblock executable**
1. Right-click `fastbusiness_mcp.exe`
2. Properties
3. Check "Unblock" (nếu có)
4. Apply

**Solution 2.3: Windows Defender exception**
1. Windows Security
2. Virus & threat protection
3. Manage settings
4. Exclusions → Add folder
5. Add `C:\FastBusiness-MCP\`

### Issue 3: Server Crashes

**Symptoms:**
- Server starts rồi tắt ngay
- Error messages trong Output panel

**Diagnosis:**
```cmd
# Run executable trực tiếp để xem error
C:\FastBusiness-MCP\fastbusiness_mcp.exe
```

**Common causes & solutions:**

**Cause 3.1: Missing dependencies**
- Hiếm gặp (executable là standalone)
- Solution: Re-download package

**Cause 3.2: Corrupt files**
- Solution: Re-extract ZIP

**Cause 3.3: Antivirus blocking**
- Solution: Add exception cho executable

### Issue 4: Slow Performance

**Symptoms:**
- Tools work nhưng chậm
- Delay khi call tools

**Causes:**
- Windows Defender scan mỗi lần run

**Solution:**
1. Add folder vào Windows Defender exclusions
2. Disable real-time protection (not recommended)
3. Use different antivirus with better performance

### Issue 5: Path Not Found

**Symptoms:**
- Error: "command not found"
- Error: "path does not exist"

**Solutions:**

**Solution 5.1: Check path syntax**
```json
// WRONG
"command": "C:\Path\file.exe"     // Single backslash
"command": "C:/Path/file.exe"      // Forward slash

// CORRECT
"command": "C:\\Path\\file.exe"    // Double backslash
```

**Solution 5.2: Check file exists**
```cmd
dir "C:\FastBusiness-MCP\fastbusiness_mcp.exe"
```
Phải show file.

**Solution 5.3: Spaces in path**
```json
// Path có spaces - OK với double backslash
"command": "C:\\Program Files\\FastBusiness-MCP\\fastbusiness_mcp.exe"
```

### Issue 6: Wrong Python Version Error

**Symptoms:**
- Error about Python version
- Import errors

**Cause:**
- Không nên xảy ra (executable là standalone)
- Có thể do PATH environment variable conflict

**Solution:**
1. Check không có `PYTHONPATH` trong environment variables
2. Remove any Python-related env vars from config:
```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe",
      "args": [],
      "env": {}  // Empty env
    }
  }
}
```

---

## Diagnostic Commands

### Test Executable

```cmd
# Navigate to folder
cd C:\FastBusiness-MCP

# Test run
fastbusiness_mcp.exe

# Check version (if supported)
fastbusiness_mcp.exe --version

# Check help (if supported)
fastbusiness_mcp.exe --help
```

### Check Cursor Config

```cmd
# Open settings.json location
echo %APPDATA%\Cursor\User\settings.json

# View file
notepad "%APPDATA%\Cursor\User\settings.json"
```

### Check Processes

```cmd
# List running MCP processes
tasklist | findstr "fastbusiness_mcp"

# Kill process (if needed)
taskkill /IM fastbusiness_mcp.exe /F
```

---

## Logs & Debugging

### Enable Debug Logging

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe",
      "args": [],
      "env": {
        "FASTBUSINESS_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

### View Logs

1. **Cursor Output Panel:**
   - View → Output
   - Select "MCP" from dropdown

2. **System Logs:**
   - Check `%TEMP%` folder for log files

3. **Manual logging:**
   ```cmd
   # Redirect output to file
   fastbusiness_mcp.exe > output.log 2>&1
   ```

---

## FAQ

### Q: Có cần cài Python không?

**A:** KHÔNG. Executable là standalone, đã bao gồm Python runtime.

### Q: Có thể move folder sang chỗ khác không?

**A:** Có. Move folder, rồi update path trong Cursor config.

### Q: File size lớn quá?

**A:** Normal. Executable chứa Python runtime và dependencies (~50-100MB).

### Q: Có thể dùng trên Mac/Linux không?

**A:** Không. Package này build cho Windows. Cần build riêng cho Mac/Linux.

### Q: Có thể update mà không mất config không?

**A:** Có. Config trong Cursor settings.json tách biệt. Chỉ cần update executable.

### Q: Antivirus báo virus?

**A:** False positive. Executable là hợp lệ. Add exception trong antivirus.

### Q: Có thể customize tools không?

**A:** Không (với executable). Để customize cần source code.

### Q: Có thể share cho người khác không?

**A:** Có. Copy folder hoặc share ZIP file. Recipient setup như hướng dẫn này.

---

## Next Steps

Sau khi setup thành công:

1. **Learn tools:** Đọc README.md để hiểu từng tool
2. **Practice:** Thử từng tool trong Cursor
3. **Integrate:** Tích hợp vào workflow hàng ngày
4. **Feedback:** Report bugs hoặc suggest features

---

## Support

Nếu gặp issue không có trong guide này:

1. Check [Troubleshooting](#troubleshooting) section
2. Check executable logs
3. Contact support: [your-email@example.com]

---

**Setup successful? Happy coding! 🎉**
