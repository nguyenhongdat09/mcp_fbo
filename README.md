# FastBusiness MCP Server

MCP server cho FastBusiness (kiến trúc `mcp.server.MCPServer` / FastMCP + Pydantic v2): **query SQL**, **đọc XML entity**, **Kùzu Graph DB (Radar)**, **đọc file vật lý**, và **tra cứu lịch sử yêu cầu (search_qlyc)**.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cấu hình MCP (Cursor/VS Code)

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\PythonProject\\mcp_fbo\\.venv\\Scripts\\python.exe",
      "args": ["-m", "fastbusiness_mcp.server"],
      "cwd": "E:\\PythonProject\\mcp_fbo"
    }
  }
}
```

## MCP Tools (5 tools)

| Tool | Mô tả |
|---|---|
| `query_database` | Chạy SQL & Phân tích Schema/Proc (tự động tra cứu DDL Table hoặc tóm tắt AST Proc/View/Function với ANTLR4) |
| `get_xml_entities` | Đọc entity XML (`content` / `path` / `list`) |
| `query_radar` | Truy vấn Kùzu Graph DB theo Template Cypher chuẩn |
| `read_local_file` | Đọc file controller FBO từ ổ cứng (`read_option=1`: raw, `2`: flat, `3`: summary_xml JSON gọn) |

| `search_qlyc` | Tra cứu lịch sử ticket / yêu cầu đã thực hiện |

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
