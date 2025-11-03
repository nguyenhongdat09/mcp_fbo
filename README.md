# FastBusiness MCP Server

MCP (Model Context Protocol) server cho FastBusiness XML development.

## Cài đặt

```bash
# Install dependencies
pip install -r requirements.txt

# Import field definitions vào LMDB database
python scripts/import_fields_to_lmdb.py --xml-dir "E:\FBO\SP2263\App_Data\Controllers"
```

## Cấu hình MCP

### Cursor/VS Code MCP Config

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\mcp_fbo",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\data\\fields_lmdb"
      }
    }
  }
}
```

### Environment Variables

- `FASTBUSINESS_VSCODE_DB_PATH`: Đường dẫn tới LMDB database
- `FASTBUSINESS_KNOWLEDGE_BASE_PATH`: Đường dẫn tới knowledge base

## Các Tool Chính

### 1. generate_field_from_lmdb
Generate field XML từ database

### 2. generate_sql_for_fields
Generate SQL commands để add fields vào database

### 3. add_onchange_handler
Thêm onChange handler vào field

### 4. add_onfocus_handler
Thêm onFocus handler vào field

### 5. add_form_lifecycle_handler
Thêm form lifecycle handlers (active$Form$, etc.)

### 6. detect_context_from_file
Detect file type và context (Dir/Grid/Filter)

### 7. get_api_help
Get API reference (Form API, Grid API)

### 8. get_critical_rules
Get critical rules cho context hiện tại

## Critical Rules

### Partition
```sql
-- Sai
select * from d91$202501

-- Đúng
select * from @@prime$partition$current
```

### Result Access
```javascript
// Sai
var x = result[0].column_name;

// Đúng
var x = result[0].Value;
```

### Grid Detail Parent Access
```javascript
var f = g.get_element().parentForm;
```

## License

MIT License
