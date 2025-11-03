# FastBusiness MCP Server

**Version:** 1.0.0
**Platform:** Windows 10/11
**Requirements:** Cursor IDE

---

## 🚀 Quick Start

### Bước 1: Extract Package

1. Extract folder này vào vị trí bạn muốn (ví dụ: `C:\FastBusiness-MCP\`)
2. Đảm bảo file `fastbusiness_mcp.exe` có trong folder

### Bước 2: Configure Cursor

1. Mở Cursor IDE
2. Press `Ctrl+Shift+P` (Command Palette)
3. Type: `Preferences: Open User Settings (JSON)`
4. Thêm config sau:

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe",
      "args": []
    }
  }
}
```

**⚠️ LƯU Ý:**
- Thay `C:\\FastBusiness-MCP\\` bằng đường dẫn thực tế của bạn
- Phải dùng **double backslash** (`\\`) trong JSON
- Đường dẫn không nên có khoảng trắng

### Bước 3: Restart Cursor

1. Close tất cả Cursor windows
2. Mở lại Cursor
3. Wait 5-10 giây để MCP server khởi động

### Bước 4: Verify

1. Mở Cursor chat (hoặc file bất kỳ)
2. Type: "List available MCP tools"
3. AI sẽ liệt kê các tools có sẵn

---

## 📋 Available Tools

MCP Server cung cấp 12 tools:

### 1. Field Generation Tools
- `generate_field_from_lmdb` - Generate field từ database
- `search_lmdb_fields` - Search fields trong database
- `lmdb_database_stats` - Xem thống kê database
- `generate_sql_for_fields` - Generate SQL commands

### 2. Code Assistant Tools
- `detect_context_from_file` - Detect file context (Dir/Grid/Filter)
- `get_api_help` - Xem API reference (f.xxx, g.xxx)
- `generate_code_from_pattern` - Generate code từ patterns
- `search_patterns` - Search code patterns
- `get_critical_rules` - Xem critical rules

### 3. XML Handler Tools
- `add_onchange_handler` - Thêm onChange handler
- `add_onfocus_handler` - Thêm onFocus handler
- `add_form_lifecycle_handler` - Thêm lifecycle handler (active$Form$, etc.)

---

## 💡 Usage Examples

### Example 1: Generate Field
```
You: Thêm field mã khách hàng dạng lookup
AI: [Calls generate_field_from_lmdb]
    → Generates XML field definition
```

### Example 2: Add onChange Handler
```
You: Thêm onchange cho ma_kh thì console.log(1)
AI: [Calls add_onchange_handler]
    → Adds onChange handler to XML
```

### Example 3: Get API Help
```
You: Làm sao get giá trị field trong form?
AI: [Calls get_api_help for form API]
    → Shows f.getItemValue() usage
```

---

## ⚙️ Advanced Configuration

### Specify Tools (Optional)

Nếu bạn muốn chỉ enable một số tools:

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe",
      "args": [],
      "tools": [
        "generate_field_from_lmdb",
        "add_onchange_handler",
        "get_api_help"
      ]
    }
  }
}
```

### Environment Variables (Optional)

```json
{
  "mcpServers": {
    "fastbusiness": {
      "command": "C:\\FastBusiness-MCP\\fastbusiness_mcp.exe",
      "args": [],
      "env": {
        "FASTBUSINESS_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## 🔧 Troubleshooting

### Problem: Tools không hiện trong Cursor

**Giải pháp:**
1. Check đường dẫn trong config có đúng không
2. Restart Cursor **hoàn toàn** (close tất cả windows)
3. Check Task Manager có process `fastbusiness_mcp.exe` đang chạy không
4. Xem Cursor logs: `Help` → `Show Logs` → Search "MCP"

### Problem: Permission Denied

**Giải pháp:**
1. Run Cursor as Administrator
2. Hoặc add exception cho `fastbusiness_mcp.exe` trong Windows Defender
3. Check file `fastbusiness_mcp.exe` không bị block:
   - Right-click file → Properties → Unblock (nếu có)

### Problem: Path Not Found

**Giải pháp:**
1. Đảm bảo dùng **double backslash** `\\` trong JSON
2. Check file tồn tại: Open Command Prompt, chạy:
   ```
   C:\FastBusiness-MCP\fastbusiness_mcp.exe --help
   ```
3. Nếu path có khoảng trắng, dùng quotes:
   ```json
   "command": "C:\\Program Files\\FastBusiness-MCP\\fastbusiness_mcp.exe"
   ```

### Problem: MCP Server Crashes

**Giải pháp:**
1. Test executable trực tiếp:
   ```
   C:\FastBusiness-MCP\fastbusiness_mcp.exe
   ```
2. Check error messages
3. Re-extract ZIP file (có thể file bị corrupt)
4. Contact support với error logs

### Problem: Tools Work But Slow

**Nguyên nhân:** Windows Defender đang scan .exe mỗi lần chạy

**Giải pháp:**
1. Add `fastbusiness_mcp.exe` vào Windows Defender exclusions
2. Steps:
   - Windows Security → Virus & threat protection
   - Manage settings → Exclusions
   - Add folder: `C:\FastBusiness-MCP\`

---

## 📖 Documentation

Chi tiết về từng tool và cách sử dụng:

1. **SETUP_GUIDE.md** - Hướng dẫn cài đặt chi tiết
2. **YAML_KNOWLEDGE_BASE_GUIDE.md** - Hiểu về YAML knowledge base
3. **XML_HANDLER_TOOLS_SUMMARY.md** - Chi tiết về XML handler tools

---

## 🔄 Update

### Cách update lên version mới:

1. Download version mới (ZIP file)
2. Close Cursor
3. Backup folder hiện tại (optional)
4. Extract ZIP mới, đè lên folder cũ
5. Restart Cursor

**LƯU Ý:** Config trong Cursor không cần thay đổi

---

## 🗑️ Uninstall

1. Close Cursor
2. Delete folder `C:\FastBusiness-MCP\`
3. Remove config từ Cursor settings.json:
   - Open settings.json
   - Xóa section `"fastbusiness": {...}`
4. Restart Cursor

---

## ℹ️ System Requirements

- **OS:** Windows 10 (64-bit) or Windows 11
- **RAM:** Minimum 4GB (8GB recommended)
- **Disk:** ~100MB free space
- **Software:** Cursor IDE (latest version)
- **Python:** **NOT REQUIRED** (executable is standalone)

---

## 🆘 Support

Nếu gặp vấn đề:

1. Check Troubleshooting section above
2. Check documentation files
3. Contact: [your-email@example.com]

---

## 📝 License

[Your License Information]

---

## 🙏 Credits

FastBusiness MCP Server
Developed by [Your Name/Company]
Version 1.0.0 - 2024

Powered by:
- Model Context Protocol (MCP)
- LMDB Database
- YAML Knowledge Base

---

**Thank you for using FastBusiness MCP Server! 🎉**
