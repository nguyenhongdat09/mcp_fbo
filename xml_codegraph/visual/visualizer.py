import html
from typing import Set, List
from xml_codegraph.core.schema import XmlGraph, GraphNode
from xml_codegraph.rules.edges_rules import EdgeType

def sanitize_mermaid_id(node_id: str) -> str:
    """Loại bỏ ký tự đặc biệt để làm ID node Mermaid hợp lệ."""
    return "".join(c if c.isalnum() or c == '_' else '_' for c in node_id)

def generate_mermaid_graph(graph: XmlGraph, center_node_id: str, max_depth: int = 2) -> str:
    """
    Sinh mã Mermaid dạng biểu đồ xung quanh center_node_id.
    """
    if center_node_id not in graph.nodes:
        return "graph TD\n    empty_node[Không tìm thấy node tương ứng]"

    # BFS thu thập các node và edge trong phạm vi max_depth
    visited_nodes: Set[str] = set()
    collected_edges = []
    
    queue = [(center_node_id, 0)]
    visited_nodes.add(center_node_id)
    
    while queue:
        current_id, depth = queue.pop(0)
        if depth >= max_depth:
            continue
            
        # Thu thập các edge đi ra (dependencies)
        if current_id in graph.edges_from:
            for edge in graph.edges_from[current_id]:
                collected_edges.append(edge)
                target_id = edge.target_id
                if target_id not in visited_nodes:
                    visited_nodes.add(target_id)
                    # Chỉ tiếp tục đi sâu nếu target là một Node trong graph (file XML)
                    if target_id in graph.nodes:
                        queue.append((target_id, depth + 1))
                        
        # Thu thập các edge đi vào (dependents)
        if current_id in graph.edges_to:
            for edge in graph.edges_to[current_id]:
                collected_edges.append(edge)
                source_id = edge.source_id
                if source_id not in visited_nodes:
                    visited_nodes.add(source_id)
                    if source_id in graph.nodes:
                        queue.append((source_id, depth + 1))

    # Bắt đầu sinh mã Mermaid
    lines = []
    lines.append("graph TD")
    
    # Định nghĩa class style cho Mermaid
    lines.append("    %% Style Classes")
    lines.append("    classDef center fill:#ef4444,stroke:#ef4444,stroke-width:2px,color:#fff;")
    lines.append("    classDef xml fill:#3b82f6,stroke:#1d4ed8,stroke-width:1px,color:#fff;")
    lines.append("    classDef entity fill:#f97316,stroke:#c2410c,stroke-width:1px,color:#fff;")
    lines.append("    classDef table fill:#10b981,stroke:#047857,stroke-width:1px,color:#fff;")
    lines.append("    classDef proc fill:#8b5cf6,stroke:#6d28d9,stroke-width:1px,color:#fff;")
    lines.append("    classDef external fill:#6b7280,stroke:#374151,stroke-width:1px,color:#fff;")
    lines.append("")

    # Xác định class cho từng node trước khi vẽ
    node_classes = {}
    for node_id in visited_nodes:
        if node_id in graph.nodes:
            node_classes[node_id] = "center" if node_id == center_node_id else "xml"
        else:
            # Sẽ được ghi đè dựa trên edge
            node_classes[node_id] = "external"

    # Duyệt qua các edge để gán class chính xác hơn cho các node ngoài
    for edge in collected_edges:
        if edge.target_id not in graph.nodes:
            if edge.edge_type == EdgeType.SQL_TABLE_USE:
                node_classes[edge.target_id] = "table"
            elif edge.edge_type == EdgeType.SQL_PROC_CALL:
                node_classes[edge.target_id] = "proc"
            elif edge.edge_type in {EdgeType.ENTITY_INCLUDE, EdgeType.PARAM_ENTITY_USE}:
                node_classes[edge.target_id] = "entity"

    # Vẽ các Node với class inline (:::style)
    for node_id in visited_nodes:
        m_id = sanitize_mermaid_id(node_id)
        cls = node_classes.get(node_id, "external")
        
        if node_id in graph.nodes:
            node = graph.nodes[node_id]
            label = f"{node.relative_path} ({node.folder_type})"
        else:
            # Escape HTML ký tự đặc biệt (như & thành &amp;) để tránh lỗi cú pháp Mermaid
            label = html.escape(node_id).replace('"', '\\"')
            
        lines.append(f'    {m_id}["{label}"]:::{cls}')

    lines.append("")
    
    # Vẽ các Edge
    written_edges = set()
    for edge in collected_edges:
        edge_key = (edge.source_id, edge.target_id, edge.edge_type)
        if edge_key in written_edges:
            continue
        written_edges.add(edge_key)
        
        src_m = sanitize_mermaid_id(edge.source_id)
        tgt_m = sanitize_mermaid_id(edge.target_id)
        
        arrow_label = edge.edge_type.replace("EdgeType.", "")
        lines.append(f"    {src_m} -->|{arrow_label}| {tgt_m}")

    return "\n".join(lines)
