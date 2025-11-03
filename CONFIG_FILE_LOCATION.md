# Config File Location - FastBusiness MCP Package

## Vị trí file config.yaml

### ✅ BÊN TRONG package folder

```
FastBusiness-MCP-v1.0.0/
├── fastbusiness_mcp.exe
├── config.yaml              ← ĐẶT Ở ĐÂY
├── knowledge_base/
│   └── api_reference/
└── data/
    └── fields_lmdb/
```

---

## Tại sao?

### 1. Server tìm config từ working directory (cwd)

```python
# server.py
def __init__(self, config_path: str = "config.yaml"):
    self.config = self._load_config(config_path)
```

Mặc định tìm `config.yaml` - đây là **relative path** từ `cwd`

### 2. MCP config set cwd = package folder

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
      "cwd": "C:\\FastBusiness-MCP-v1.0.0",  ← Working directory
      ...
    }
  }
}
```

→ Server chạy với `cwd` = `C:\FastBusiness-MCP-v1.0.0`

→ Tìm config tại: `C:\FastBusiness-MCP-v1.0.0\config.yaml`

---

## Config Priority (Thứ tự ưu tiên)

### Database Path:
```
1. Environment Variable: FASTBUSINESS_VSCODE_DB_PATH  ← HIGHEST
2. config.yaml: database.lmdb_path
3. Default: {cwd}/data/fields_lmdb
```

### Knowledge Base Path:
```
1. Environment Variable: FASTBUSINESS_KNOWLEDGE_BASE_PATH  ← HIGHEST
2. config.yaml: paths.knowledge_base
3. Default: {cwd}/knowledge_base
```

---

## Nên config như thế nào?

### Option 1: Dùng Environment Variables (RECOMMENDED)

**MCP Config:**
```json
{
  "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
  "cwd": "C:\\FastBusiness-MCP-v1.0.0",
  "env": {
    "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
  }
}
```

**config.yaml (trong package):**
```yaml
# Có thể để trống hoặc dùng default values
database:
  lmdb_path: "data/fields_lmdb"  # Sẽ bị override bởi env var

paths:
  knowledge_base: "knowledge_base"  # Relative path OK
```

**Kết quả:**
- Database: `E:\mcp_fbo\data\fields_lmdb` (từ env var)
- Knowledge base: `C:\FastBusiness-MCP-v1.0.0\knowledge_base` (từ config)

---

### Option 2: Dùng Config File (Manual)

**MCP Config:**
```json
{
  "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
  "cwd": "C:\\FastBusiness-MCP-v1.0.0"
  // Không có env vars
}
```

**config.yaml (trong package):**
```yaml
database:
  lmdb_path: "E:\\mcp_fbo\\data\\fields_lmdb"  # Absolute path

paths:
  knowledge_base: "knowledge_base"  # Relative path
```

**Kết quả:**
- Database: `E:\mcp_fbo\data\fields_lmdb` (từ config)
- Knowledge base: `C:\FastBusiness-MCP-v1.0.0\knowledge_base` (từ config)

---

### Option 3: Không cần config.yaml (Defaults)

**MCP Config:**
```json
{
  "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
  "cwd": "C:\\FastBusiness-MCP-v1.0.0",
  "env": {
    "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
  }
}
```

**Không có config.yaml**

**Kết quả:**
- Database: `E:\mcp_fbo\data\fields_lmdb` (từ env var)
- Knowledge base: `C:\FastBusiness-MCP-v1.0.0\knowledge_base` (default)

---

## Khi nào cần config.yaml?

### ✅ CẦN config.yaml khi:
1. Muốn set paths cố định trong package (không dùng env vars)
2. Muốn customize logging level
3. Muốn customize validation settings

### ❌ KHÔNG CẦN config.yaml khi:
1. Dùng environment variables cho tất cả paths
2. Defaults đã OK (knowledge_base trong package, database từ env var)

---

## Example config.yaml cho Package

### Minimal (Recommended):
```yaml
# config.yaml - Đặt trong FastBusiness-MCP-v1.0.0/

server:
  name: "fastbusiness-xml-context"
  version: "1.0.0"

# Paths - dùng relative hoặc để cho env var override
database:
  lmdb_path: "data/fields_lmdb"

paths:
  knowledge_base: "knowledge_base"

logging:
  level: "INFO"
```

### Full (với absolute paths):
```yaml
# config.yaml - Đặt trong FastBusiness-MCP-v1.0.0/

server:
  name: "fastbusiness-xml-context"
  version: "1.0.0"

# Paths - absolute paths
database:
  lmdb_path: "E:\\mcp_fbo\\data\\fields_lmdb"  # Absolute

paths:
  knowledge_base: "C:\\FastBusiness-MCP-v1.0.0\\knowledge_base"  # Absolute

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

validation:
  strict_mode: true
  auto_fix: false
```

---

## Troubleshooting

### Lỗi: "Failed to load config"

**Log:**
```
WARNING - Failed to load config: [Errno 2] No such file or directory: 'config.yaml', using defaults
```

**Nguyên nhân:**
- config.yaml không có trong package folder
- hoặc `cwd` sai

**Fix:**
1. Đặt config.yaml vào `FastBusiness-MCP-v1.0.0/`
2. Hoặc để server dùng defaults (vẫn chạy OK nếu có env vars)

### Config không được áp dụng

**Nguyên nhân:** Environment variable override config file

**Check priority:**
1. Env var có set không? → Override config
2. Config có path không? → Dùng path đó
3. Không có cả 2 → Dùng default

---

## Best Practice

### 🎯 Recommended Setup:

**1. Package structure:**
```
FastBusiness-MCP-v1.0.0/
├── fastbusiness_mcp.exe
├── config.yaml              ← Minimal config
├── knowledge_base/
└── data/fields_lmdb/
```

**2. config.yaml (minimal):**
```yaml
server:
  name: "fastbusiness-xml-context"
  version: "1.0.0"

paths:
  knowledge_base: "knowledge_base"

logging:
  level: "INFO"
```

**3. MCP config:**
```json
{
  "command": "C:\\FastBusiness-MCP-v1.0.0\\fastbusiness_mcp.exe",
  "cwd": "C:\\FastBusiness-MCP-v1.0.0",
  "env": {
    "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
  }
}
```

**Advantages:**
- ✅ Linh hoạt: Database path dùng env var
- ✅ Portable: Knowledge base trong package
- ✅ Simple: Config file minimal

---

## Summary

| Item | Recommended Location | Notes |
|------|---------------------|-------|
| **config.yaml** | `FastBusiness-MCP-v1.0.0/config.yaml` | Bên trong package |
| **knowledge_base** | `FastBusiness-MCP-v1.0.0/knowledge_base/` | Bên trong package |
| **database** | External path (env var) | Trỏ tới database hiện có |

**Key Points:**
1. config.yaml đặt **BÊN TRONG** package folder
2. Server tìm config từ `cwd` (set trong MCP config)
3. Environment variables override config file
4. Có thể không cần config.yaml nếu dùng env vars + defaults

Done! 🎉
