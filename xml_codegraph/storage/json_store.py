import json
from pathlib import Path
from typing import Dict, Any
from xml_codegraph.core.schema import GraphNode, GraphEdge, XmlGraph

class JsonGraphStore:
    def __init__(self, file_path: Path):
        self.file_path = Path(file_path).resolve()

    def save(self, graph: XmlGraph) -> None:
        """Lưu toàn bộ đồ thị Graph xuống file JSON."""
        # Chuyển đổi dữ liệu đối tượng sang dạng Dictionary có thể serialize
        data = {
            "nodes": {},
            "edges": []
        }
        
        for node_id, node in graph.nodes.items():
            data["nodes"][node_id] = {
                "node_id": node.node_id,
                "file_path": node.file_path,
                "relative_path": node.relative_path,
                "folder_type": node.folder_type,
                "folder_subtype": node.folder_subtype,
                "xml_root_tag": node.xml_root_tag,
                "xml_namespace": node.xml_namespace,
                "controller_type": node.controller_type,
                "table": node.table,
                "code_field": node.code_field,
                "title_v": getattr(node, 'title_v', ''),
                "title_e": getattr(node, 'title_e', ''),
                "entities": node.entities,
                "param_entities": node.param_entities,
                "fields": node.fields,
                "grid_refs": getattr(node, "grid_refs", []),
                "lookup_refs": getattr(node, "lookup_refs", []),
                "sql_blocks": node.sql_blocks,
                "js_blocks": node.js_blocks,
                "file_size": node.file_size,
                "last_modified": node.last_modified,
                "summary": node.summary
            }
            
        for edge in graph.edges:
            data["edges"].append({
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "edge_type": edge.edge_type,
                "meta": edge.meta
            })
            
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> XmlGraph:
        """Đọc và dựng lại đồ thị Graph từ file JSON."""
        graph = XmlGraph()
        if not self.file_path.exists():
            return graph
            
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        for node_id, node_data in data.get("nodes", {}).items():
            node = GraphNode(
                node_id=node_data["node_id"],
                file_path=node_data["file_path"],
                relative_path=node_data["relative_path"],
                folder_type=node_data["folder_type"],
                folder_subtype=node_data["folder_subtype"],
                xml_root_tag=node_data["xml_root_tag"],
                xml_namespace=node_data["xml_namespace"],
                controller_type=node_data["controller_type"],
                table=node_data.get("table"),
                code_field=node_data.get("code_field"),
                title_v=node_data.get("title_v", ""),
                title_e=node_data.get("title_e", ""),
                entities=node_data.get("entities", []),
                param_entities=node_data.get("param_entities", []),
                fields=node_data.get("fields", []),
                grid_refs=node_data.get("grid_refs", []),
                lookup_refs=node_data.get("lookup_refs", []),
                sql_blocks=node_data.get("sql_blocks", []),
                js_blocks=node_data.get("js_blocks", []),
                file_size=node_data.get("file_size", 0),
                last_modified=node_data.get("last_modified", 0.0),
                summary=node_data.get("summary", "")
            )
            graph.add_node(node)
            
        for edge_data in data.get("edges", []):
            edge = GraphEdge(
                source_id=edge_data["source_id"],
                target_id=edge_data["target_id"],
                edge_type=edge_data["edge_type"],
                meta=edge_data.get("meta", {})
            )
            graph.add_edge(edge)
            
        return graph
