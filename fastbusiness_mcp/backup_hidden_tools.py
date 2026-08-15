# backup_hidden_tools.py
# File này lưu trữ các tools liên quan đến KuzuDB đã được ẩn đi. 
# Sau này nếu muốn bật lại, bạn có thể dựa vào nội dung này để đưa trở lại server.py.

"""
======================================================================
1. IMPORTS CẦN BẬT LẠI (thêm vào phần from xml_fbograph.mcp_tools)
======================================================================
    mcp_search_nodes,
    mcp_get_related_nodes,
    mcp_query_node_details,
"""

"""
======================================================================
2. KHỐI LIST TOOLS CẦN THÊM VÀO _on_list_tools (bên trong mảng tools)
======================================================================
                Tool(
                    name="search_nodes",
                    description=\"\"\"Tim kiem node/field/code trong du an FBO.
Synonym ASCII (uu tien, tranh loi encoding): truyen query KHONG DAU.
Vi du: 'giay bao no' -> CPTran; 'phieu chi' -> CDTran; 'dien giai' -> dien_giai; 'gia ban' -> gia2/gia_nt2; 'ten hang hoa' -> ten_vt.
Van chap nhan co dau (tu dong fold), nhung agent nen dung khong dau.\"\"\",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Keyword ASCII uu tien: 'giay bao no', 'phieu chi', 'dien giai', 'ma_kh', 'CPTran'",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.\\nVí dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml\\nhoặc UNC: \\\\\\\\server\\\\CustomerPro\\\\FBO\\\\...\\\\App_Data\\\\Controllers\\\\Dir\\\\SVTran.xml\\nCẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.\\nThiếu hoặc relative sẽ bị reject; không dùng để build Kuzu.",
                            },
                            "match_type": {
                                "type": "string",
                                "description": "Match type: 'all' (default), 'field', 'code', 'file'",
                            },
                            "folder_filter": {
                                "type": "string",
                                "description": "Folders to search, comma separated (e.g. 'Dir,Grid'). Defaults to Dir,Grid,Filter,Report,Lookup",
                            },
                            "limit": {
                                "type": "number",
                                "description": "Maximum results (default: 20)",
                            },
                        },
                        "required": ["query", "reference_file"],
                    },
                ),
                Tool(
                    name="get_related_nodes",
                    description=\"\"\"Truy vấn các file/node liên quan đến file target.\"\"\",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "Target file relative path or basename (e.g., 'Dir/CPTran.xml', 'CPTax.xml')",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.\\nVí dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml\\nhoặc UNC: \\\\\\\\server\\\\CustomerPro\\\\FBO\\\\...\\\\App_Data\\\\Controllers\\\\Dir\\\\SVTran.xml\\nCẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.\\nThiếu hoặc relative sẽ bị reject; không dùng để build Kuzu.",
                            },
                            "mode": {
                                "type": "string",
                                "description": "Mode: 'navigate' (default), 'dependencies', 'dependents'",
                            },
                            "include_shared": {
                                "type": "boolean",
                                "description": "Include SHARED_INCLUDE relationships (default: false)",
                            },
                        },
                        "required": ["target", "reference_file"],
                    },
                ),
                Tool(
                    name="query_node_details",
                    description=\"\"\"Truy vấn chi tiết thông tin cấu trúc bên trong của một file/controller.
CHÚ Ý QUAN TRỌNG: Nếu file XML cần truy vấn không tồn tại, KHÔNG ĐƯỢC tự ý tạo mới hay sinh file này. Hãy thông báo ngay cho người dùng và chờ chỉ thị.\"\"\",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "Target file relative path or basename (e.g., 'Dir/CPTran.xml', 'CPTax.xml')",
                            },
                            "reference_file": {
                                "type": "string",
                                "description": "BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.\\nVí dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml\\nhoặc UNC: \\\\\\\\server\\\\CustomerPro\\\\FBO\\\\...\\\\App_Data\\\\Controllers\\\\Dir\\\\SVTran.xml\\nCẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.\\nThiếu hoặc relative sẽ bị reject; không dùng để build Kuzu.",
                            },
                            "view": {
                                "type": "string",
                                "description": "View type: 'context' (default) or 'blocks'",
                            },
                        },
                        "required": ["target", "reference_file"],
                    },
                ),
"""

"""
======================================================================
3. KHỐI LOGIC CẦN THÊM VÀO _on_call_tool (bên trong if/elif name == ...)
======================================================================
            elif name == "search_nodes":
                query = arguments["query"]
                reference_file = arguments["reference_file"]
                match_type = arguments.get("match_type", "all")
                folder_filter = arguments.get("folder_filter")
                limit = int(arguments.get("limit", 20))
                res = mcp_search_nodes(query, reference_file, match_type, folder_filter, limit)
                return CallToolResult(content=[TextContent(type="text", text=res)])

            elif name == "get_related_nodes":
                target = arguments["target"]
                reference_file = arguments["reference_file"]
                mode = arguments.get("mode", "navigate")
                include_shared = arguments.get("include_shared", False)
                res = mcp_get_related_nodes(target, reference_file, mode, include_shared)
                return CallToolResult(content=[TextContent(type="text", text=res)])

            elif name == "query_node_details":
                target = arguments["target"]
                reference_file = arguments["reference_file"]
                view = arguments.get("view", "context")
                res = mcp_query_node_details(target, reference_file, view)
                return CallToolResult(content=[TextContent(type="text", text=res)])
"""
