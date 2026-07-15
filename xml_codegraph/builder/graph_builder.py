import os
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from xml_codegraph.core.schema import GraphNode, GraphEdge, XmlGraph
from xml_codegraph.rules.edges_rules import EdgeType
from xml_codegraph.parsers.xml_parser import XmlControllerParser, is_encrypted_file
from xml_codegraph.parsers.sql_parser import SqlBlockParser
from xml_codegraph.parsers.js_parser import JsBlockParser
from xml_codegraph.storage.kuzu_index import KuzuIndexStore
from xml_codegraph.utils.path_helper import get_graph_scan_roots, is_graph_scope_relative_path

def generate_node_id(relative_path: str) -> str:
    """Tạo ID duy nhất dựa trên đường dẫn tương đối (đã chuẩn hóa)."""
    normalized_path = relative_path.replace("\\", "/").lower()
    return hashlib.sha1(normalized_path.encode("utf-8")).hexdigest()

def detect_controller_type(folder_type: str, xml_root_tag: str, xml_namespace: str) -> str:
    """Tự động suy luận loại controller từ namespace hoặc tag chính."""
    if xml_namespace and "urn:schemas-fast-com:data-" in xml_namespace:
        return xml_namespace.split("data-")[-1].strip()
    if xml_root_tag:
        return xml_root_tag.strip()
    return "include"

def find_node_by_controller_name(graph: XmlGraph, controller_name: str) -> Optional[GraphNode]:
    """Tìm GraphNode có tên file khớp với controller_name (không phân biệt hoa thường)."""
    controller_lower = controller_name.lower().strip()
    
    # 1. Thử các đường dẫn tương đối trực tiếp trước
    for folder in ["grid", "dir", "filter", "lookup", "report", "form"]:
        candidate_rel = f"{folder}/{controller_lower}.xml"
        node_id = graph.node_by_path.get(candidate_rel)
        if node_id:
            return graph.nodes[node_id]
            
    # 2. Quét toàn bộ node, ưu tiên thư mục grid và dir trước
    candidates = []
    for node in graph.nodes.values():
        basename = Path(node.relative_path).stem.lower()
        if basename == controller_lower:
            candidates.append(node)
            
    if candidates:
        def sort_priority(n):
            f = n.folder_type.lower()
            if f == "grid":
                return 0
            if f == "dir":
                return 1
            return 2
        candidates.sort(key=sort_priority)
        return candidates[0]
            
    return None


class GraphBuilder:
    def __init__(self, controllers_root: Path, cache_path: Optional[Path] = None):
        self.controllers_root = Path(controllers_root).resolve()
        self.xml_parser = XmlControllerParser(self.controllers_root)
        self.sql_parser = SqlBlockParser()
        self.js_parser = JsBlockParser()
        
        # Nap cache do thi cu de chay so sanh incremental (tu Kuzu)
        self.old_graph = None
        if cache_path and cache_path.exists():
            try:
                self.old_graph = KuzuIndexStore(cache_path).load_graph()
            except Exception:
                pass

    def build(self) -> XmlGraph:
        """Duyệt Dir, Grid, Filter, Report và Templates/Upload để xây dựng Graph."""
        graph = XmlGraph()
        
        file_extensions = {".xml", ".ent", ".txt", ".f"}
        raw_files: List[Path] = []
        scan_roots = get_graph_scan_roots(self.controllers_root)
        if not scan_roots:
            print(f"[CodeGraph] No scan roots under: {self.controllers_root}")
            return graph

        for scan_root in scan_roots:
            for root, _, files in os.walk(scan_root):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in file_extensions:
                        raw_files.append(file_path)

        # Lọc bỏ file .f nếu đã có file .xml cùng tên
        xml_stems = set()
        for f in raw_files:
            if f.suffix.lower() == ".xml":
                xml_stems.add((f.parent, f.stem.lower()))

        all_files = []
        for f in raw_files:
            if f.suffix.lower() == ".f":
                if (f.parent, f.stem.lower()) in xml_stems:
                    continue  # Bỏ qua file .f khi có source .xml
            all_files.append(f)

        # Hàng đợi các file cần parse mới/update
        files_to_parse: List[Path] = []
        
        # Duyệt nhanh để lọc ra các file không đổi (Incremental Cache)
        for file_path in all_files:
            rel_path = os.path.relpath(file_path, self.controllers_root)
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
            
            cached_node = None
            if self.old_graph:
                cached_id = self.old_graph.node_by_path.get(rel_path.replace("\\", "/").lower())
                if cached_id:
                    node = self.old_graph.nodes.get(cached_id)
                    if node and node.last_modified == mtime and node.file_size == size:
                        cached_node = node
            
            if cached_node and is_graph_scope_relative_path(rel_path):
                # File không đổi -> dùng lại dữ liệu cũ từ cache
                graph.add_node(cached_node)
            else:
                # File mới hoặc đã thay đổi -> cần parse lại
                files_to_parse.append(file_path)

        # Hàm trợ giúp xử lý parse đơn lẻ để đẩy vào luồng song song
        def parse_single_file(path: Path) -> Optional[GraphNode]:
            try:
                is_f_file = path.suffix.lower() == ".f"
                if is_f_file:
                    relative_path = os.path.relpath(path, self.controllers_root)
                    relative_xml_path = str(Path(relative_path).with_suffix(".xml"))
                    node_id = generate_node_id(relative_xml_path)
                    
                    rel_parts = Path(relative_path).parts
                    folder_type = rel_parts[0]
                    folder_subtype = rel_parts[1] if len(rel_parts) > 2 else ""
                    
                    return GraphNode(
                        node_id=node_id,
                        file_path=str(path),
                        relative_path=relative_xml_path,
                        folder_type=folder_type,
                        folder_subtype=folder_subtype,
                        xml_root_tag="",
                        xml_namespace="",
                        controller_type=folder_type.lower(),
                        table=None,
                        code_field=None,
                        title_v="",
                        title_e="",
                        entities=[],
                        param_entities=[],
                        fields=[],
                        grid_refs=[],
                        lookup_refs=[],
                        sql_blocks=[],
                        js_blocks=[],
                        file_size=os.path.getsize(path),
                        last_modified=os.path.getmtime(path),
                        is_encrypted=True,
                        source_extension=".f",
                        paired_f_path=relative_path,
                        needs_xml=True
                    )

                # Kiểm tra encrypted trước khi parse XML cho file không phải .f
                try:
                    raw_bytes = path.read_bytes()
                    encrypted = is_encrypted_file(raw_bytes)
                except Exception:
                    raw_bytes = b""
                    encrypted = False

                data = self.xml_parser.parse(path)
                relative_path = data["relative_path"]
                node_id = generate_node_id(relative_path)
                
                controller_type = detect_controller_type(
                    data["folder_type"], 
                    data["xml_root_tag"], 
                    data["xml_namespace"]
                )
                
                return GraphNode(
                    node_id=node_id,
                    file_path=data["file_path"],
                    relative_path=relative_path,
                    folder_type=data["folder_type"],
                    folder_subtype=data["folder_subtype"],
                    xml_root_tag=data["xml_root_tag"],
                    xml_namespace=data["xml_namespace"],
                    controller_type=controller_type,
                    table=data["table"],
                    code_field=data["code_field"],
                    title_v=data.get("title_v", ""),
                    title_e=data.get("title_e", ""),
                    entities=data["entities"],
                    param_entities=data["param_entities"],
                    fields=data["fields"],
                    grid_refs=data.get("grid_refs", []),
                    lookup_refs=data.get("lookup_refs", []),
                    sql_blocks=data["sql_blocks"],
                    js_blocks=data["js_blocks"],
                    file_size=data["file_size"],
                    last_modified=os.path.getmtime(path),
                    is_encrypted=encrypted,
                    source_extension=".xml",
                    paired_f_path=None,
                    needs_xml=False
                )
            except Exception as e:
                print(f"[CodeGraph] Skip build error: {path}. Detail: {e}")
                return None

        # Parse song song su dung ThreadPoolExecutor
        if files_to_parse:
            print(f"[CodeGraph] Parsing {len(files_to_parse)} new/changed files...")
            max_workers = min(32, (os.cpu_count() or 4) * 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = executor.map(parse_single_file, files_to_parse)
                for node in results:
                    if node:
                        graph.add_node(node)

        # Bước 2: Thiết lập mối liên kết (Edges)
        # Quét lần thứ 2 để map ID của các thực thể phụ thuộc
        for source_id, node in graph.nodes.items():
            # 2.1 Mối quan hệ SYSTEM Entity Include
            # Ví dụ: <!ENTITY XMLWhenVoucherInit SYSTEM "..\Include\XML\WhenVoucherInit.xml">
            for ent in node.entities:
                target_rel_path = ent["relative_path"].replace("\\", "/").lower()
                target_id = graph.node_by_path.get(target_rel_path)
                
                if target_id:
                    # Tạo cạnh Entity Include
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=target_id,
                        edge_type=EdgeType.ENTITY_INCLUDE,
                        meta={"entity_name": ent["name"]}
                    )
                    graph.add_edge(edge)
                else:
                    # Nếu target không tồn tại (có thể là file ngoài thư mục Controllers)
                    pass

            # 2.2 Mối quan hệ Parameter Entity Use
            # Ví dụ: %Invoice; (kế thừa các quy tắc từ Invoice.ent)
            for p_ent_name in node.param_entities:
                # Tìm xem entity name này có được khai báo SYSTEM ở đâu trong file này không
                matched_ent_path = None
                for ent in node.entities:
                    if ent["name"] == p_ent_name:
                        matched_ent_path = ent["relative_path"].replace("\\", "/").lower()
                        break
                
                if matched_ent_path:
                    target_id = graph.node_by_path.get(matched_ent_path)
                    if target_id:
                        edge = GraphEdge(
                            source_id=source_id,
                            target_id=target_id,
                            edge_type=EdgeType.PARAM_ENTITY_USE,
                            meta={"param_entity": p_ent_name}
                        )
                        graph.add_edge(edge)

            # 2.3 Phân tích các khối SQL CDATA bên trong XML
            for sql_block in node.sql_blocks:
                parsed_sql = self.sql_parser.parse(sql_block["content"])
                
                # Cạnh liên kết với DB Table (SQL_TABLE_USE)
                for table in parsed_sql["tables"]:
                    # Tạo quan hệ tượng trưng từ controller đến tên bảng
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=table, # target_id là tên bảng (dạng chuỗi)
                        edge_type=EdgeType.SQL_TABLE_USE,
                        meta={"line": sql_block["line"]}
                    )
                    graph.add_edge(edge)

                # Cạnh liên kết với Stored Procedure (SQL_PROC_CALL)
                for proc in parsed_sql["stored_procedures"]:
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=proc, # target_id là tên proc (dạng chuỗi)
                        edge_type=EdgeType.SQL_PROC_CALL,
                        meta={"line": sql_block["line"]}
                    )
                    graph.add_edge(edge)

            # 2.4 Phân tích các khối JS CDATA bên trong XML
            for js_block in node.js_blocks:
                parsed_js = self.js_parser.parse(js_block["content"])
                
                # Quét các client fields được JS tương tác
                for field in parsed_js["client_fields"]:
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=field, # liên kết với trường cụ thể
                        edge_type=EdgeType.JS_FUNC_CALL,
                        meta={"line": js_block["line"], "js_action": "field_access"}
                    )
                    graph.add_edge(edge)

                # 2.5 Phân tích các cuộc gọi g.showForm
                show_form_calls = parsed_js.get("show_form_calls", [])
                for target_form in show_form_calls:
                    target_node = find_node_by_controller_name(graph, target_form)
                    if target_node:
                        edge = GraphEdge(
                            source_id=source_id,
                            target_id=target_node.node_id,
                            edge_type=EdgeType.RETRIEVE_DATA_SOURCE,
                            meta={"line": js_block["line"], "form": target_form}
                        )
                        graph.add_edge(edge)
                    
                    # Cắt chuỗi lấy từ "Filter" trở về trước
                    if target_form.endswith("Filter"):
                        prefix = target_form[:-6]
                        suffixes = [
                            ("Grid", "Grid"),
                            ("MultiGrid", "Grid"),
                            ("Form", "Form"),
                            ("MultiForm", "Form"),
                            ("Lookup", "Lookup")
                        ]
                        for suffix, folder_name in suffixes:
                            candidate_name = f"{prefix}{suffix}"
                            candidate_node = find_node_by_controller_name(graph, candidate_name)
                            if candidate_node:
                                edge = GraphEdge(
                                    source_id=source_id,
                                    target_id=candidate_node.node_id,
                                    edge_type=EdgeType.RETRIEVE_DATA_SOURCE,
                                    meta={"line": js_block["line"], "relation": f"derived_{suffix}", "source_form": target_form}
                                )
                                graph.add_edge(edge)

            # 2.6 Mối quan hệ Master -> Detail Grid
            for grid_ref in getattr(node, "grid_refs", []):
                detail_controller = grid_ref["controller"]
                target_node = find_node_by_controller_name(graph, detail_controller)
                if target_node:
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=target_node.node_id,
                        edge_type=EdgeType.GRID_MASTER_DETAIL,
                        meta={"field_name": grid_ref["field_name"], "foreign_key": grid_ref.get("foreign_key")}
                    )
                    graph.add_edge(edge)
                else:
                    print(f"[CodeGraph Builder Warning] Missing controller '{detail_controller}' for Grid '{grid_ref['field_name']}' in '{node.relative_path}'")

            # 2.7 Mối quan hệ LOOKUP_REFERENCE
            for lookup_ref in getattr(node, "lookup_refs", []):
                lookup_controller = lookup_ref["controller"]
                target_node = find_node_by_controller_name(graph, lookup_controller)
                if target_node:
                    edge = GraphEdge(
                        source_id=source_id,
                        target_id=target_node.node_id,
                        edge_type=EdgeType.LOOKUP_REFERENCE,
                        meta={"field_name": lookup_ref["field_name"]}
                    )
                    graph.add_edge(edge)

        # 2.7b Detect GRID_MASTER_DETAIL from JS pattern: f.getItem("dXX") / f.getItem("rXX")
        # This is how FBO references detail Grids from Dir controller JS code.
        # Example: f.getItem("d11") in CPTran.xml -> CPDetail, f.getItem("r30") -> GLTax
        import re as _re
        _GET_ITEM_PATTERN = _re.compile(
            r'(?:f|form|parentForm)\.getItem\s*\(\s*["\']([dr]\d+)["\']\s*\)',
            _re.IGNORECASE
        )
        DIR_TYPES = ('dir', 'Dir')
        GRID_TYPES = ('grid', 'Grid')
        for source_id, node in graph.nodes.items():
            if node.controller_type not in DIR_TYPES:
                continue
            for js_block in getattr(node, 'js_blocks', []):
                content = js_block.get('content', '')
                found_items = set(_GET_ITEM_PATTERN.findall(content))
                for item_id in found_items:
                    target_node = None
                    for tnode in graph.nodes.values():
                        if tnode.controller_type in GRID_TYPES and tnode.code_field == item_id:
                            target_node = tnode
                            break
                    if target_node and target_node.node_id != source_id:
                        existing_targets = {
                            (e.target_id, e.edge_type)
                            for e in graph.edges_from.get(source_id, [])
                        }
                        key = (target_node.node_id, EdgeType.GRID_MASTER_DETAIL)
                        if key not in existing_targets:
                            graph.add_edge(GraphEdge(
                                source_id=source_id,
                                target_id=target_node.node_id,
                                edge_type=EdgeType.GRID_MASTER_DETAIL,
                                meta={'field_name': item_id, 'detected_from': 'js_getItem'}
                            ))

        # 2.8 Ph\u00e2n t\u00edch m\u1ed1i quan h\u1ec7 d\u00f9ng chung (SHARED_INCLUDE)
        # N\u1ebfu hai Controller c\u00f9ng include m\u1ed9t file th\u1ef1c th\u1ec3 (v\u00ed d\u1ee5: CheckLockedDate.txt)
        # Ch\u00fang ta s\u1ebd t\u1ef1 \u0111\u1ed9ng nh\u00f3m ch\u00fang l\u1ea1i \u0111\u1ec3 d\u1ec5 ph\u1ee5c v\u1ee5 vi\u1ec7c ph\u00e2n t\u00edch \u1ea3nh h\u01b0\u1edfng ch\u00e9o
        shared_includes: Dict[str, List[str]] = {} # include_node_id -> list of controller_node_ids

        for edge in graph.edges:
            if edge.edge_type == EdgeType.ENTITY_INCLUDE:
                shared_includes.setdefault(edge.target_id, []).append(edge.source_id)

        for include_id, controllers in shared_includes.items():
            if len(controllers) > 1:
                # Có trên 2 controller cùng dùng chung file này
                for c1 in controllers:
                    for c2 in controllers:
                        if c1 != c2:
                            edge = GraphEdge(
                                source_id=c1,
                                target_id=c2,
                                edge_type=EdgeType.SHARED_INCLUDE,
                                meta={"shared_resource_id": include_id}
                            )
                            graph.add_edge(edge)

        # 2.9 Phân tích mối quan hệ Companion Files (các file cùng tên ở các folder khác nhau)
        basename_groups: Dict[str, List[str]] = {} # basename -> list of node_ids
        for node_id, node in graph.nodes.items():
            basename = Path(node.relative_path).name.lower()
            if "." in basename:
                basename = basename.split(".")[0]
            basename_groups.setdefault(basename, []).append(node_id)
            
        for basename, node_ids in basename_groups.items():
            if len(node_ids) > 1:
                for i in range(len(node_ids)):
                    for j in range(i + 1, len(node_ids)):
                        id1 = node_ids[i]
                        id2 = node_ids[j]
                        # Thêm cạnh hai chiều
                        edge1 = GraphEdge(
                            source_id=id1,
                            target_id=id2,
                            edge_type=EdgeType.COMPANION_FILE,
                            meta={"basename": basename}
                        )
                        edge2 = GraphEdge(
                            source_id=id2,
                            target_id=id1,
                            edge_type=EdgeType.COMPANION_FILE,
                            meta={"basename": basename}
                        )
                        graph.add_edge(edge1)
                        graph.add_edge(edge2)

        return graph

def build_and_save_graph(controllers_dir: Path, output_dir: Path) -> XmlGraph:
    """Build graph va luu vao Kuzu (khong con dung graph.json/SQLite)."""
    controllers_dir = Path(controllers_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = output_dir / "kuzu"
    # Dung Kuzu lam incremental cache (thay cho graph.json)
    builder = GraphBuilder(controllers_dir, cache_path=db_path)
    graph = builder.build()

    kuzu_store = KuzuIndexStore(db_path)
    kuzu_store.sync_graph(graph)

    return graph


def incremental_update_file(file_path: Path, controllers_root: Path, db_path: Path) -> Optional[GraphNode]:
    """
    Cap nhat incremental: chi re-parse file vua thay doi, ghi vao Kuzu,
    tra ve GraphNode moi de caller cap nhat in-memory graph.
    """
    import os
    controllers_root = Path(controllers_root).resolve()
    db_path = Path(db_path).resolve()
    file_path = Path(file_path).resolve()

    try:
        rel_path = os.path.relpath(file_path, controllers_root)
    except ValueError:
        return None

    if not is_graph_scope_relative_path(rel_path):
        return None

    xml_parser = XmlControllerParser(controllers_root)
    sql_parser = SqlBlockParser()
    js_parser  = JsBlockParser()

    try:
        try:
            raw_bytes = file_path.read_bytes()
            encrypted = is_encrypted_file(raw_bytes)
        except Exception:
            encrypted = False

        data = xml_parser.parse(file_path)
        node_id = generate_node_id(data["relative_path"])
        controller_type = detect_controller_type(
            data["folder_type"], data["xml_root_tag"], data["xml_namespace"]
        )
        node = GraphNode(
            node_id         = node_id,
            file_path       = data["file_path"],
            relative_path   = data["relative_path"],
            folder_type     = data["folder_type"],
            folder_subtype  = data["folder_subtype"],
            xml_root_tag    = data["xml_root_tag"],
            xml_namespace   = data["xml_namespace"],
            controller_type = controller_type,
            table           = data["table"],
            code_field      = data["code_field"],
            title_v         = data.get("title_v", ""),
            title_e         = data.get("title_e", ""),
            entities        = data["entities"],
            param_entities  = data["param_entities"],
            fields          = data["fields"],
            grid_refs       = data.get("grid_refs", []),
            lookup_refs     = data.get("lookup_refs", []),
            sql_blocks      = data["sql_blocks"],
            js_blocks       = data["js_blocks"],
            file_size       = data["file_size"],
            last_modified   = os.path.getmtime(file_path),
            is_encrypted    = encrypted,
        )

        # Tao edges chi cho node nay (khong co full graph nen chi lam SQL/JS/entity edges)
        edges: List[GraphEdge] = []
        for sql_block in node.sql_blocks:
            parsed = sql_parser.parse(sql_block["content"])
            for tbl in parsed.get("tables", []):
                edges.append(GraphEdge(node_id, tbl, EdgeType.SQL_TABLE_USE, {"line": sql_block["line"]}))
            for proc in parsed.get("stored_procedures", []):
                edges.append(GraphEdge(node_id, proc, EdgeType.SQL_PROC_CALL, {"line": sql_block["line"]}))

        kuzu_store = KuzuIndexStore(db_path)
        kuzu_store.update_single_node(node, edges)
        return node

    except Exception as e:
        print(f"[CodeGraph] incremental_update_file error for {file_path}: {e}")
        return None
