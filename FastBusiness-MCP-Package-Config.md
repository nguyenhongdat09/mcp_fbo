# FastBusiness MCP Package - Quick Config

## Cursor MCP Config

### Đường dẫn cần thay đổi:

1. **Đường dẫn .exe**: `C:\FastBusiness-MCP-v1.0.0\fastbusiness_mcp.exe`
2. **Thư mục package** (cwd): `C:\FastBusiness-MCP-v1.0.0`
3. **Database path**: `E:\mcp_fbo\data\fields_lmdb`

---

## Copy Config Này:

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "cwd": "C:\\FastBusiness-MCP-v1.0.0",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
      }
    }
  }
}
```

---

## Giải thích:

### 1. `command` - Đường dẫn .exe
```json
"command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe"
```
- **Phải là ABSOLUTE PATH** (đường dẫn tuyệt đối)
- Thay `C:\FastBusiness-MCP-v1.0.0` bằng thư mục bạn giải nén package
- Dùng `\\` (double backslash) trong JSON

### 2. `cwd` - Working Directory
```json
"cwd": "C:\\FastBusiness-MCP-v1.0.0"
```
- Thư mục chứa package (có folder `knowledge_base/`)
- Server sẽ tìm `knowledge_base` từ đây
- **QUAN TRỌNG:** Phải set đúng để tìm knowledge_base!

### 3. `env.FASTBUSINESS_VSCODE_DB_PATH` - Database Path
```json
"FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
```
- Đường dẫn tới LMDB database
- Có thể trỏ tới:
  - Database của dự án Python: `E:\mcp_fbo\data\fields_lmdb`
  - Hoặc database trong package: `C:\FastBusiness-MCP-v1.0.0\data\fields_lmdb`

---

## Các Path Sẽ Được Resolve:

Khi chạy với config trên:

```
Database path: E:\mcp_fbo\data\fields_lmdb
  ↑ Từ environment variable

Knowledge base path: C:\FastBusiness-MCP-v1.0.0\knowledge_base
  ↑ Từ cwd + "knowledge_base" (default)
```

---

## Check Logs Sau Khi Restart:

Bạn sẽ thấy:
```
INFO - [OK] Using LMDB path from environment variable: E:\mcp_fbo\data\fields_lmdb
INFO - [DB] Final LMDB database path: E:\mcp_fbo\data\fields_lmdb
INFO - [KB] Knowledge base path: C:\FastBusiness-MCP-v1.0.0\knowledge_base
INFO - [OK] LMDB initialized at E:\mcp_fbo\data\fields_lmdb (450 fields)
```

**Nếu thấy paths như trên → OK!** ✅

---

## So Sánh: Python vs .exe

### Python (Development):
```json
{
  "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
  "args": ["-m", "fastbusiness_mcp.server"],
  "cwd": "E:\\mcp_fbo",
  "env": {
    "PYTHONPATH": "E:\\mcp_fbo",  ← Cần PYTHONPATH
    "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
  }
}
```

### .exe (Production):
```json
{
  "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
  "cwd": "C:\\FastBusiness-MCP-v1.0.0",
  "env": {
    // Không cần PYTHONPATH!
    "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
  }
}
```

---

## Troubleshooting

### Lỗi: "Knowledge base not found"

**Nguyên nhân:** `cwd` sai hoặc thiếu folder `knowledge_base/`

**Fix:**
1. Kiểm tra folder `knowledge_base/` có trong package không
2. Set `cwd` = thư mục chứa `knowledge_base/`
3. Hoặc set env var:
   ```json
   "env": {
     "FASTBUSINESS_KNOWLEDGE_BASE_PATH": "C:\\FastBusiness-MCP-v1.0.0\\knowledge_base"
   }
   ```

### Lỗi: "Database empty"

**Nguyên nhân:** Database path trỏ tới folder rỗng

**Fix:** Import data:
```bash
python scripts/import_fields_to_lmdb.py ^
  --xml-dir "E:\FBO\SP2263\App_Data\Controllers" ^
  --db-path "E:\mcp_fbo\data\fields_lmdb"
```

### Lỗi: ".exe not found"

**Nguyên nhân:** Đường dẫn `command` sai

**Fix:** Dùng absolute path:
```json
"command": "C:\\Full\\Path\\To\\fastbusiness_mcp.exe"
```

---

## Template Để Điền:

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "__PATH_TO_EXE__",
      "cwd": "__PACKAGE_FOLDER__",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "__DATABASE_PATH__"
      }
    }
  }
}
```

**Thay thế:**
- `__PATH_TO_EXE__`: Ví dụ `C:\FastBusiness-MCP-v1.0.0\fastbusiness_mcp.exe`
- `__PACKAGE_FOLDER__`: Ví dụ `C:\FastBusiness-MCP-v1.0.0`
- `__DATABASE_PATH__`: Ví dụ `E:\mcp_fbo\data\fields_lmdb`

Nhớ dùng `\\` (double backslash) trong JSON!

---

## Done! 🎉

Sau khi config xong:
1. Save MCP config
2. Restart Cursor
3. Check logs
4. Test gọi tool `generate_field_from_lmdb`

Nếu thấy `[OK] LMDB initialized` với số fields > 0 → Thành công! ✅
