"""Feature flags bật/tắt từng MCP tool khi build exe.

True  -> tool được đăng ký lên server (hiện trên IDE)
False -> bỏ qua, tool không tồn tại trong list_tools

Key = đúng `name` của tool trong mcp_app.py.

Lưu ý:
- `tool_help` ngoài flag này còn cần file entitlement `config_jev.xml`/
  `config_jev.yaml` (có apiKey) mới hiện — flag=False thì tắt hẳn kể cả
  khi có entitlement.
- File này đóng gói vào exe lúc build — sửa flag xong phải build lại.
"""

TOOLS_ENABLED = {
    "query_database": True,
    "get_xml_entities": True,
    "query_radar": True,
    "read_local_file": True,
    "search_qlyc": True,
    "clone_things": True,
    "compare_things": True,
    "search_files": True,
    "tool_help": True,
}
