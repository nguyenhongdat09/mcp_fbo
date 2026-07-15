# FastBusiness MCP Server

MCP server cho FastBusiness: **query SQL** (resolve connection từ path) và **đọc XML entity**.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cấu hình MCP (Cursor/VS Code)

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\mcp_fbo"
    }
  }
}
```

## MCP Tools

| Tool | Mô tả |
|---|---|
| `query_database` | Chạy SQL — resolve connection từ `file_path` |
| `get_xml_entities` | Đọc entity XML (`content` / `path`) |

## Modules

```
find_connect_by_path/   # Resolve Web.config → connection string
queryDatabase/          # Connect + execute SQL
find_entity_by_xml/     # Đọc entity từ XML (lxml)
```

## Build executable

```bash
build_onedir.bat
```

Output: `dist/fastbusiness_mcp/fastbusiness_mcp.exe`
