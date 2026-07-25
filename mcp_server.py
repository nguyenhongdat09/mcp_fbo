import sys
import os
import json
import threading
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Lỗi: Chưa cài đặt thư viện 'mcp'. Vui lòng chạy lệnh: pip install mcp")
    sys.exit(1)

mcp = FastMCP("FboCodeGraph")

sys.path.append(str(Path(__file__).parent.resolve()))
from xml_codegraph.utils.path_helper import ProjectPathHelper
from xml_codegraph.service.watcher import start_watcher

# Caching connections và watcher
_watched_projects = set()
_kuzu_stores = {}

def start_watcher_for_project(reference_file: str):
    """Khởi chạy file watcher trong background thread nếu project này chưa được giám sát."""
    try:
        helper = ProjectPathHelper(reference_file)
        project_root = str(helper.get_project_root().resolve())
        if project_root in _watched_projects:
            return
        
        _watched_projects.add(project_root)
        controllers_dir = helper.get_controllers_path()
        graph_dir = helper.get_graph_dir()
        db_path = graph_dir / "kuzu"

        # Callback cập nhật trực tiếp cache RAM nếu cần
        # Khi dùng Kuzu, watcher sẽ tự ghi thay đổi vào file Kuzu DB qua update_single_node
        def watcher_thread():
            sys.stderr.write(f"[FboCodeGraph MCP] Starting file watcher thread for {controllers_dir}\n")
            try:
                start_watcher(controllers_dir, graph_dir)
            except Exception as e:
                sys.stderr.write(f"[FboCodeGraph MCP] Watcher thread failed: {e}\n")

        t = threading.Thread(target=watcher_thread, daemon=True)
        t.start()
    except Exception as e:
        sys.stderr.write(f"[FboCodeGraph MCP] Error starting watcher: {e}\n")

def get_kuzu_store(reference_file: str):
    """Lấy hoặc khởi tạo kết nối Kùzu DB cho dự án."""
    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    db_path = graph_dir / "kuzu"
    db_key = str(db_path)
    
    if db_key not in _kuzu_stores:
        # Tự động bật watcher cho project
        start_watcher_for_project(reference_file)
        
        from xml_codegraph.storage.kuzu_index import KuzuIndexStore
        _kuzu_stores[db_key] = KuzuIndexStore(db_path, read_only=True)
        
    return _kuzu_stores[db_key]

@mcp.tool()
def query_radar(reference_file: str, cypher_query: str = "", mode: str = "query") -> str:
    """
    Query hoặc đọc schema live của đồ thị Kùzu Graph DB (Radar tool).
    Dành cho việc truy vấn nâng cao hoặc các trường hợp ad-hoc.
    Khuyến khích sử dụng search_nodes, get_related_nodes, query_node_details cho các câu hỏi FBO thông thường.

    mode:
    - query (mặc định): chạy cypher_query.
    - schema: trả schema live XmlFile/Rel, columns, edge_type, quy tắc và ví dụ.

    --- SCHEMA & QUY TẮC TRUY VẤN KÙZU ---
    1. Node Table:
       - XmlFile (khóa chính: node_id)
       - Các thuộc tính chính:
         * relative_path: Đường dẫn tương đối dùng dấu BACKSLASH kép (Ví dụ: 'Dir\\\\CPTran.xml' hoặc 'Grid\\\\CPTax.xml').
         * folder_type: Thư mục (Dir, Grid, Filter, Report, Lookup, Templates).
         * controller_type: Loại (dir, grid, filter, report, lookup, templates).
         * fields_names: Mảng tên các field (STRING[]).
         * js_text / sql_text: Văn bản thô code SQL hoặc JS.
         * needs_xml / paired_f_path: Đánh dấu file mã hóa .f cần nguồn XML.
    2. Relationship Table:
       - Chỉ có duy nhất một bảng quan hệ tên là: :Rel (Từ XmlFile sang XmlFile).
       - KHÔNG sử dụng label quan hệ kiểu Neo4j như MATCH ()-[:GRID_MASTER_DETAIL]->().
         HÃY dùng MATCH ()-[r:Rel]->() WHERE r.edge_type = 'GRID_MASTER_DETAIL'.
       - Các giá trị edge_type:
         * 'GRID_MASTER_DETAIL': Liên kết từ màn hình chính sang Grid chi tiết.
         * 'LOOKUP_REFERENCE': Liên kết Lookup sang controller tham chiếu.
         * 'COMPANION_FILE': Liên kết các file cùng tên (ví dụ: Dir\\CPTran -> Grid\\CPTran).
         * 'SHARED_INCLUDE': Liên kết include dùng chung (chiếm ~99% cạnh - PHẢI filter để tránh trôi token).
         * 'ENTITY_INCLUDE', 'PARAM_ENTITY_USE', 'RETRIEVE_DATA_SOURCE'.
    3. Tìm kiếm JS handler:
       - Dùng `js_text CONTAINS 'Tên_Handler'` thay vì fields_names.

    Ví dụ Cypher hợp lệ:
    MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)
    WHERE a.relative_path = 'Dir\\\\CPTran.xml' AND r.edge_type = 'GRID_MASTER_DETAIL'
    RETURN b.relative_path, b.needs_xml, b.source_extension
    LIMIT 20
    """
    from xml_codegraph.mcp_tools import mcp_query_radar

    return mcp_query_radar(cypher_query, reference_file, mode)

@mcp.tool()
def search_nodes(query: str, reference_file: str, match_type: str = "all", folder_filter: str = None, limit: int = 20) -> str:
    """
    Tìm kiếm thông minh các Node, các định nghĩa field hoặc các khối code SQL/JS chứa từ khóa trong dự án.
    Tự động áp dụng từ điển đồng nghĩa (Synonyms) của FBO (ví dụ: 'giá bán' -> 'gia2', 'gia_nt2').
    
    query: Từ khóa hoặc field cần tìm (ví dụ: 'ma_kh', 'giá bán', 'dien_giai', 'TenVtFromDienGiai').
    reference_file: File XML bất kỳ trong dự án hiện tại để auto-detect dự án.
    match_type: Loại so khớp: 'all' (mặc định), 'field' (chỉ tìm định nghĩa field), 'code' (chỉ tìm trong sql/js blocks), 'file' (tìm theo tên file).
    folder_filter: Thư mục viết hoa cần lọc (ví dụ: 'Dir', 'Grid' hoặc 'Dir,Grid'). Nếu không chỉ định, mặc định tìm kiếm trên tất cả thư mục chính (Dir,Grid,Filter,Report,Lookup) để tránh Template nhiễu.
    limit: Số lượng kết quả tối đa trả về.
    """
    try:
        from xml_codegraph.query.engine import xml_graph_query
        if not folder_filter:
            folder_filter = "Dir,Grid,Filter,Report,Lookup"
        res = xml_graph_query("search", query, reference_file, match_type=match_type, folder_filter=folder_filter, limit=limit)
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi search_nodes: {str(e)}"

@mcp.tool()
def get_related_nodes(target: str, reference_file: str, mode: str = "navigate", include_shared: bool = False) -> str:
    """
    Truy vấn các file/node liên quan đến file target.
    
    target: Tên file hoặc đường dẫn tương đối (ví dụ: 'Dir/CPTran.xml', 'CPTax.xml').
    reference_file: File XML bất kỳ trong dự án hiện tại để auto-detect dự án.
    mode: 'navigate' (mặc định: các Grid con, Lookup, Companion, Master), 'dependencies' (các file include/entity/companion đi ra), 'dependents' (các file sử dụng target).
    include_shared: Nếu True, sẽ bao gồm các quan hệ SHARED_INCLUDE (include dùng chung, rất nhiều). Mặc định False để tránh ngập token.
    """
    try:
        from xml_codegraph.query.engine import xml_graph_query
        res = xml_graph_query(mode, target, reference_file)
        
        if not include_shared and isinstance(res, dict):
            for key in ("dependencies", "dependents", "results"):
                if key in res and isinstance(res[key], list):
                    res[key] = [item for item in res[key] if not (isinstance(item, dict) and item.get("type") == "SHARED_INCLUDE")]
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi get_related_nodes: {str(e)}"

@mcp.tool()
def query_node_details(target: str, reference_file: str, view: str = "context") -> str:
    """
    Truy vấn chi tiết thông tin cấu trúc bên trong của một file/controller.
    
    target: Tên file hoặc đường dẫn tương đối (ví dụ: 'Dir/CPTran.xml', 'CPTax.xml').
    reference_file: File XML bất kỳ trong dự án hiện tại để auto-detect dự án.
    view: 'context' (mặc định: trả về các fields, tables, master detail, companion info và needs_xml), 'blocks' (trả về các khối SQL và JS thô bên trong file).
    """
    try:
        from xml_codegraph.query.engine import xml_graph_query
        res = xml_graph_query(view, target, reference_file, compact=True)
        
        if isinstance(res, dict):
            if "needs_xml" not in res:
                res["needs_xml"] = []
            if "agent_hint" not in res:
                res["agent_hint"] = ""
            if "source_on_disk" not in res:
                res["source_on_disk"] = ""
                
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Lỗi query_node_details: {str(e)}"

@mcp.tool()
def read_local_file(file_path: str, reference_file: str) -> str:
    """
    Đọc trực tiếp nội dung XML file vật lý từ ổ cứng để đảm bảo dữ liệu mới nhất (Kính lúp tool).
    Hỗ trợ tự động giải mã font Tiếng Việt Windows-1258.
    
    file_path: Có thể là đường dẫn tương đối (ví dụ: 'Dir/CPTran.xml') hoặc tuyệt đối.
    """
    try:
        helper = ProjectPathHelper(reference_file)
        project_root = helper.get_project_root()
        
        # Phân tích đường dẫn
        p = Path(file_path)
        if not p.is_absolute():
            # Thử với controllers_path trước, sau đó project_root
            controllers_root = helper.get_controllers_path()
            p1 = controllers_root / file_path
            if p1.exists():
                p = p1
            else:
                p = project_root / file_path
                
        p = p.resolve()
        
        # Bảo mật: Không cho phép đọc file nằm ngoài thư mục dự án
        if not str(p).lower().startswith(str(project_root.resolve()).lower()):
            return f"Lỗi: Đường dẫn nằm ngoài thư mục dự án: {file_path}"
            
        if not p.exists():
            return f"Lỗi: File không tồn tại: {file_path}"
            
        # Sử dụng module parser chuẩn để decode windows-1258 chính xác tiếng Việt
        from xml_codegraph.parsers.xml_parser import read_file_content
        content = read_file_content(p)
        return content
    except Exception as e:
        return f"Lỗi đọc file: {str(e)}"

if __name__ == "__main__":
    mcp.run()
