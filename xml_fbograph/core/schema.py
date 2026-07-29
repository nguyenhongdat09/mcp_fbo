from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class GraphNode:
    # Định danh duy nhất (thường là SHA-1 của relative_path hoặc định danh dạng Controller/Entity)
    node_id: str
    
    # Thông tin đường dẫn file nguồn
    file_path: str
    relative_path: str
    
    # Phân loại tự động (được trích xuất từ namespace XML và cấu trúc thư mục)
    folder_type: str        # e.g., "Dir", "Grid", "Filter", "Report", "Templates"
    folder_subtype: str     # e.g., "Upload" (Templates/Upload), "Excel", "Rpt"
    xml_root_tag: str       # e.g., "dir", "grid", "lookup", "import"
    xml_namespace: str      # e.g., "urn:schemas-fast-com:data-dir"
    controller_type: str    # e.g., "dir", "grid", "lookup", "import" (suy ra từ namespace)

    # Chi tiết thuộc tính định nghĩa từ root element XML
    table: Optional[str] = None
    code_field: Optional[str] = None
    title_v: Optional[str] = ""
    title_e: Optional[str] = ""
    
    # Dữ liệu phân tích bên trong file
    entities: List[Dict] = field(default_factory=list)        # SYSTEM/Internal entities khai báo
    param_entities: List[str] = field(default_factory=list)    # Parameter entities được dùng (%Invoice;)
    fields: List[Dict] = field(default_factory=list)           # Các field khai báo (tên, kiểu, line, snippet)
    sql_blocks: List[Dict] = field(default_factory=list)       # Các đoạn code SQL CDATA
    js_blocks: List[Dict] = field(default_factory=list)        # Các đoạn code JS CDATA
    grid_refs: List[Dict] = field(default_factory=list)        # Grid detail controllers (ví dụ: CPDetail)
    lookup_refs: List[Dict] = field(default_factory=list)      # Lookup/Autocomplete controllers (ví dụ: Customer)
    
    # Metadata bổ sung
    file_size: int = 0
    last_modified: float = 0.0
    summary: str = ""
    is_encrypted: bool = False  # True nếu file là bản mã hóa nhị phân (.f)
    source_extension: str = ".xml"      # ".xml" | ".f"
    paired_f_path: Optional[str] = None # "Grid\\CPTax.f" nếu node từ .f
    needs_xml: bool = False             # True khi chỉ có .f mã hóa, hệ thống cần (nhưng thiếu) .xml gốc để phân tích nội dung
    canonical_path: str = ""            # Đường dẫn canonical của logical controller (ví dụ: Grid\CPDetail.xml)
    alias_of: str = ""                  # Node ID của canonical node đại diện cho controller này


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str              # e.g., ENTITY_INCLUDE, PARAM_ENTITY_USE, SQL_TABLE_USE...
    meta: Dict = field(default_factory=dict)  # Chứa thông tin bổ sung: line number, context

@dataclass
class XmlGraph:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    
    # Chỉ mục phụ trợ tăng tốc độ tìm kiếm
    node_by_path: Dict[str, str] = field(default_factory=dict)  # relative_path -> node_id
    edges_from: Dict[str, List[GraphEdge]] = field(default_factory=dict) # source_id -> list of edges
    edges_to: Dict[str, List[GraphEdge]] = field(default_factory=dict)   # target_id -> list of edges

    def add_node(self, node: GraphNode):
        self.nodes[node.node_id] = node
        self.node_by_path[node.relative_path.replace("\\", "/").lower()] = node.node_id

    def add_edge(self, edge: GraphEdge):
        self.edges.append(edge)
        self.edges_from.setdefault(edge.source_id, []).append(edge)
        self.edges_to.setdefault(edge.target_id, []).append(edge)
