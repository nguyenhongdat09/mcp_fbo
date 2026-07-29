import os
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import time

from xml_fbograph.core.schema import GraphNode, GraphEdge, XmlGraph
from xml_fbograph.rules.edges_rules import EdgeType
from xml_fbograph.parsers.xml_parser import XmlControllerParser, is_encrypted_file
from xml_fbograph.parsers.sql_parser import SqlBlockParser
from xml_fbograph.parsers.js_parser import JsBlockParser
from xml_fbograph.storage.kuzu_index import KuzuIndexStore
from xml_fbograph.utils.path_helper import get_graph_scan_roots, is_graph_scope_relative_path, get_extract_shared_include_yn

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

def normalize_controller_name(stem: str) -> str:
    """Chuẩn hóa stem của file (tên không kèm extension) loại bỏ các backup/copy/date suffix."""
    import re
    name = stem.strip()
    # Loại bỏ suffix dạng " - Copy", " - backup", " - old", " (1)", etc.
    name = re.compile(r'\s*-\s*(copy|backup|old|temp|bk|new|copy\s*\(\d+\)|\(\d+\)).*$', re.IGNORECASE).sub('', name)
    # Loại bỏ "_(bk|backup|old|temp|new|copy).*$"
    name = re.compile(r'_(bk|backup|old|temp|new|copy).*$', re.IGNORECASE).sub('', name)
    # Loại bỏ các khoảng trắng kèm ngoặc đơn số ở cuối, ví dụ " (1)" hoặc " (2)"
    name = re.compile(r'\s*\(\d+\)$').sub('', name)
    return name

def find_node_by_controller_name(graph: XmlGraph, controller_name: str) -> Optional[GraphNode]:
    """Tìm Canonical GraphNode khớp với controller_name (không phân biệt hoa thường)."""
    controller_lower = controller_name.lower().strip()
    
    # 1. Thử các đường dẫn tương đối trực tiếp trước, lấy đúng canonical node
    for folder in ["grid", "dir", "filter", "lookup", "report", "form"]:
        candidate_rel = f"{folder}/{controller_lower}.xml"
        node_id = graph.node_by_path.get(candidate_rel)
        if node_id:
            node = graph.nodes[node_id]
            if getattr(node, "alias_of", None) and node.alias_of in graph.nodes:
                return graph.nodes[node.alias_of]
            return node
            
    # 2. Quét toàn bộ node, ưu tiên Canonical Nodes của grid và dir
    candidates = []
    for node in graph.nodes.values():
        alias_of = getattr(node, "alias_of", None)
        # Chỉ xét Canonical Nodes
        if alias_of and alias_of != node.node_id:
            continue
        
        stem = Path(node.relative_path).stem
        norm_name = normalize_controller_name(stem).lower()
        if norm_name == controller_lower:
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
            
    # 3. Fallback: Nếu không tìm thấy trong Canonical Nodes, quét toàn bộ
    for node in graph.nodes.values():
        stem = Path(node.relative_path).stem
        norm_name = normalize_controller_name(stem).lower()
        if norm_name == controller_lower:
            alias_of = getattr(node, "alias_of", None)
            if alias_of and alias_of in graph.nodes:
                return graph.nodes[alias_of]
            return node
            
    return None


def assign_canonical_metadata(graph: XmlGraph):
    """
    Phân tích và gán canonical_path, alias_of cho toàn bộ node trong đồ thị.
    Tự động chọn Canonical Node duy nhất cho mỗi nhóm logical controller.
    """
    import re
    
    # 1. Nhóm các node vật lý theo logical key (logical_folder_type, normalized_name)
    groups = {}
    
    standard_folders = {"dir", "grid", "filter", "report", "lookup", "form"}
    existing_standard_controllers = set()
    for node in graph.nodes.values():
        f_type_lower = node.folder_type.lower()
        if f_type_lower in standard_folders:
            stem = Path(node.relative_path).stem
            norm_name = normalize_controller_name(stem).lower()
            existing_standard_controllers.add((f_type_lower, norm_name))

    for node in graph.nodes.values():
        stem = Path(node.relative_path).stem
        norm_name = normalize_controller_name(stem)
        
        rel_parts = Path(node.relative_path.replace("\\", "/")).parts
        f_type = node.folder_type
        f_subtype = node.folder_subtype
        
        logical_f_type = f_type
        if f_type.lower() == "templates" or f_subtype.lower() == "upload":
            norm_name_lower = norm_name.lower()
            if ("grid", norm_name_lower) in existing_standard_controllers:
                logical_f_type = "Grid"
            elif ("dir", norm_name_lower) in existing_standard_controllers:
                logical_f_type = "Dir"
            else:
                logical_f_type = "Grid"
        elif f_subtype.lower() == "fields" or "config/fields" in node.relative_path.replace("\\", "/").lower():
            if len(rel_parts) > 1 and rel_parts[0].lower() in standard_folders:
                logical_f_type = rel_parts[0]
            else:
                logical_f_type = "Grid"
        else:
            if f_type.lower() in standard_folders:
                logical_f_type = f_type
            else:
                logical_f_type = "Grid"
                
        logical_f_type = logical_f_type.capitalize()
        canonical_rel_path = f"{logical_f_type}\\{norm_name}.xml"
        key = (logical_f_type.lower(), norm_name.lower())
        groups.setdefault(key, []).append((canonical_rel_path, node))

    # 2. Với mỗi nhóm, chọn Canonical Node duy nhất
    for key, group_items in groups.items():
        canonical_rel_path = group_items[0][0]
        nodes_in_group = [item[1] for item in group_items]
        
        selected_node = None
        
        # Tiêu chí 1: File chính xác trùng khớp canonical_rel_path và không encrypted
        for node in nodes_in_group:
            if node.relative_path.replace("/", "\\").lower() == canonical_rel_path.lower():
                if not getattr(node, "is_encrypted", False) and not getattr(node, "needs_xml", False):
                    selected_node = node
                    break
        
        # Tiêu chí 2: File chính xác trùng khớp canonical_rel_path (kể cả encrypted)
        if not selected_node:
            for node in nodes_in_group:
                if node.relative_path.replace("/", "\\").lower() == canonical_rel_path.lower():
                    selected_node = node
                    break
                    
        # Tiêu chí 3: Bản copy hoặc backup không encrypted (để kế thừa code)
        if not selected_node:
            for node in nodes_in_group:
                if not getattr(node, "is_encrypted", False) and not getattr(node, "needs_xml", False):
                    selected_node = node
                    break
                    
        # Tiêu chí 4: Chọn node đầu tiên trong group
        if not selected_node:
            selected_node = nodes_in_group[0]
            
        for node in nodes_in_group:
            node.canonical_path = canonical_rel_path
            node.alias_of = selected_node.node_id


def build_f_only_stub_node(path: Path, controllers_root: Path) -> GraphNode:
    """Tạo GraphNode stub cho file .f khi không có .xml"""
    import os
    relative_path = os.path.relpath(path, controllers_root)
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


class GraphBuilder:
    def __init__(self, controllers_root: Path, cache_path: Optional[Path] = None, shared_include: Optional[int] = None, progress=None, project_label: str = ""):
        self.controllers_root = Path(controllers_root).resolve()
        self.progress = progress
        self.project_label = project_label
        self.xml_parser = XmlControllerParser(self.controllers_root)
        self.sql_parser = SqlBlockParser()
        self.js_parser = JsBlockParser()
        self.shared_include = shared_include if shared_include is not None else get_extract_shared_include_yn()
        
        # Nap cache do thi cu de chay so sanh incremental (tu Kuzu)
        self.old_graph = None
        if cache_path and cache_path.exists():
            try:
                self.old_graph = KuzuIndexStore(cache_path).load_graph()
            except Exception:
                pass

    def build(self) -> XmlGraph:
        """Duyệt Dir, Grid, Filter, Report và Templates/Upload để xây dựng Graph."""
        t_walk = time.perf_counter()
        graph = XmlGraph()
        
        file_extensions = {".xml", ".f"}
        raw_files: List[Path] = []
        scan_roots = get_graph_scan_roots(self.controllers_root)
        if not scan_roots:
            print(f"[FBOGraph] No scan roots under: {self.controllers_root}")
            return graph

        for scan_root in scan_roots:
            for item in scan_root.iterdir():
                if item.is_file() and item.suffix.lower() in file_extensions:
                    raw_files.append(item)

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
                # File flat <!--C--> từng bị cache sai (encrypted + js rỗng) -> parse lại
                if getattr(cached_node, "is_encrypted", False) and not cached_node.js_blocks:
                    files_to_parse.append(file_path)
                else:
                    graph.add_node(cached_node)
            else:
                # File mới hoặc đã thay đổi -> cần parse lại
                files_to_parse.append(file_path)

        # Hàm trợ giúp xử lý parse đơn lẻ để đẩy vào luồng song song
        def parse_single_file(path: Path) -> Optional[GraphNode]:
            try:
                is_f_file = path.suffix.lower() == ".f"
                if is_f_file:
                    return build_f_only_stub_node(path, self.controllers_root)

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
                print(f"[FBOGraph] Skip build error: {path}. Detail: {e}")
        
        print(f"[TIMING] walk+stat: {time.perf_counter()-t_walk:.2f}s | {len(all_files)} files")
        t_parse = time.perf_counter()

        # Parse song song su dung ThreadPoolExecutor
        if files_to_parse:
            total_parse = len(files_to_parse)
            print(f"[FBOGraph] Parsing {total_parse} new/changed files...")
            max_workers = min(32, (os.cpu_count() or 4) * 4)
            done_parse = 0
            report_every = max(1, total_parse // 200)  # ~200 lan cap nhat tren console

            task_id = None
            if self.progress:
                task_id = self.progress.acquire_slot(self.project_label, total_parse)

            def _report_parse_progress() -> None:
                elapsed = time.perf_counter() - t_parse
                rate = done_parse / elapsed if elapsed > 0 else 0.0
                eta_s = (total_parse - done_parse) / rate if rate > 0 else 0.0
                
                if self.progress and task_id is not None:
                    self.progress.update(task_id, done_parse, total_parse, rate, eta_s)
                else:
                    pct = (done_parse * 100) // total_parse if total_parse else 100
                    bar_width = 30
                    filled = (done_parse * bar_width) // total_parse if total_parse else bar_width
                    bar = "=" * filled + "-" * (bar_width - filled)
                    msg = (
                        f"\r[FBOGraph] Parse [{bar}] {done_parse}/{total_parse} ({pct}%) "
                        f"| {rate:.1f} files/s | ETA {eta_s:.0f}s"
                    )
                    sys.stderr.write(msg)
                    sys.stderr.flush()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(parse_single_file, path) for path in files_to_parse]
                for future in as_completed(futures):
                    node = future.result()
                    if node:
                        graph.add_node(node)
                    done_parse += 1
                    if done_parse == total_parse or done_parse % report_every == 0:
                        _report_parse_progress()

            if not self.progress:
                sys.stderr.write("\n")
                sys.stderr.flush()
            elif task_id is not None and task_id >= 0:
                self.progress.finish(task_id)

        print(f"[TIMING] parse: {time.perf_counter()-t_parse:.2f}s | {len(files_to_parse)} files parsed")
        t_edges = time.perf_counter()

        # Bước 2: Thiết lập mối liên kết (Edges)
        # Phân tích và gán canonical metadata trước tiên
        assign_canonical_metadata(graph)

        def add_rewrite_edge(src_id: str, dst_id: str, edge_type: str, meta: dict):
            # Lấy canonical_id của source node
            src_node = graph.nodes.get(src_id)
            canonical_src_id = src_node.alias_of if (src_node and src_node.alias_of) else src_id
            
            # Lấy canonical_id của target node (nếu target_id là node tồn tại trong graph)
            dst_node = graph.nodes.get(dst_id)
            canonical_dst_id = dst_node.alias_of if (dst_node and dst_node.alias_of) else dst_id
            
            # Tránh self-loop vô nghĩa
            if canonical_src_id == canonical_dst_id:
                return
                
            # Sao chép và lưu thông tin vật lý gốc vào meta để phục vụ việc debug và incremental clean
            meta_copy = meta.copy()
            if src_node:
                meta_copy["parsed_from_source"] = src_node.relative_path
            if dst_node and dst_node.node_id != canonical_dst_id:
                meta_copy["parsed_from_target"] = dst_node.relative_path
                
            edge = GraphEdge(
                source_id=canonical_src_id,
                target_id=canonical_dst_id,
                edge_type=edge_type,
                meta=meta_copy
            )
            graph.add_edge(edge)

        # Quét để tạo các mối quan hệ
        for source_id, node in graph.nodes.items():
            # 2.1 Mối quan hệ SYSTEM Entity Include
            for ent in node.entities:
                target_rel_path = ent["relative_path"].replace("\\", "/").lower()
                target_id = graph.node_by_path.get(target_rel_path)
                
                if target_id:
                    add_rewrite_edge(source_id, target_id, EdgeType.ENTITY_INCLUDE, {"entity_name": ent["name"]})

            # 2.2 Mối quan hệ Parameter Entity Use
            for p_ent_name in node.param_entities:
                matched_ent_path = None
                for ent in node.entities:
                    if ent["name"] == p_ent_name:
                        matched_ent_path = ent["relative_path"].replace("\\", "/").lower()
                        break
                
                if matched_ent_path:
                    target_id = graph.node_by_path.get(matched_ent_path)
                    if target_id:
                        add_rewrite_edge(source_id, target_id, EdgeType.PARAM_ENTITY_USE, {"param_entity": p_ent_name})

            # 2.3 Phân tích các khối SQL CDATA bên trong XML
            for sql_block in node.sql_blocks:
                parsed_sql = self.sql_parser.parse(sql_block["content"])
                
                for table in parsed_sql["tables"]:
                    add_rewrite_edge(source_id, table, EdgeType.SQL_TABLE_USE, {"line": sql_block["line"]})

                for proc in parsed_sql["stored_procedures"]:
                    add_rewrite_edge(source_id, proc, EdgeType.SQL_PROC_CALL, {"line": sql_block["line"]})

            # 2.4 Phân tích các khối JS CDATA bên trong XML
            for js_block in node.js_blocks:
                parsed_js = self.js_parser.parse(js_block["content"])
                
                for field in parsed_js["client_fields"]:
                    add_rewrite_edge(source_id, field, EdgeType.JS_FUNC_CALL, {"line": js_block["line"], "js_action": "field_access"})

                # 2.5 Phân tích các cuộc gọi g.showForm
                show_form_calls = parsed_js.get("show_form_calls", [])
                for target_form in show_form_calls:
                    target_node = find_node_by_controller_name(graph, target_form)
                    if target_node:
                        add_rewrite_edge(source_id, target_node.node_id, EdgeType.RETRIEVE_DATA_SOURCE, {"line": js_block["line"], "form": target_form})
                    
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
                                add_rewrite_edge(
                                    source_id,
                                    candidate_node.node_id,
                                    EdgeType.RETRIEVE_DATA_SOURCE,
                                    {"line": js_block["line"], "relation": f"derived_{suffix}", "source_form": target_form}
                                )

            # 2.6 Mối quan hệ Master -> Detail Grid
            for grid_ref in getattr(node, "grid_refs", []):
                detail_controller = grid_ref["controller"]
                target_node = find_node_by_controller_name(graph, detail_controller)
                if target_node:
                    add_rewrite_edge(
                        source_id,
                        target_node.node_id,
                        EdgeType.GRID_MASTER_DETAIL,
                        {"field_name": grid_ref["field_name"], "foreign_key": grid_ref.get("foreign_key")}
                    )
                else:
                    print(f"[FBOGraph Builder Warning] Missing controller '{detail_controller}' for Grid '{grid_ref['field_name']}' in '{node.relative_path}'")

            # 2.7 Mối quan hệ LOOKUP_REFERENCE
            for lookup_ref in getattr(node, "lookup_refs", []):
                lookup_controller = lookup_ref["controller"]
                target_node = find_node_by_controller_name(graph, lookup_controller)
                if target_node:
                    add_rewrite_edge(
                        source_id,
                        target_node.node_id,
                        EdgeType.LOOKUP_REFERENCE,
                        {"field_name": lookup_ref["field_name"]}
                    )

        # 2.7b Detect GRID_MASTER_DETAIL từ JS pattern: f.getItem("dXX") / f.getItem("rXX")
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
                    if target_node:
                        canonical_src_id = node.alias_of if node.alias_of else source_id
                        canonical_dst_id = target_node.alias_of if target_node.alias_of else target_node.node_id
                        if canonical_src_id != canonical_dst_id:
                            existing_targets = {
                                (e.target_id, e.edge_type)
                                for e in graph.edges_from.get(canonical_src_id, [])
                            }
                            key = (canonical_dst_id, EdgeType.GRID_MASTER_DETAIL)
                            if key not in existing_targets:
                                add_rewrite_edge(
                                    source_id,
                                    target_node.node_id,
                                    EdgeType.GRID_MASTER_DETAIL,
                                    {'field_name': item_id, 'detected_from': 'js_getItem'}
                                )

        # 2.8 Phân tích mối quan hệ dùng chung (SHARED_INCLUDE)
        if self.shared_include == 1:
            print("[FBOGraph] extract_options.shared_include=1 -> build SHARED_INCLUDE edges")
            shared_includes = {}
            for edge in graph.edges:
                if edge.edge_type == EdgeType.ENTITY_INCLUDE:
                    shared_includes.setdefault(edge.target_id, []).append(edge.source_id)

            for include_id, controllers in shared_includes.items():
                if len(controllers) > 1:
                    for c1 in controllers:
                        for c2 in controllers:
                            if c1 != c2:
                                add_rewrite_edge(c1, c2, EdgeType.SHARED_INCLUDE, {"shared_resource_id": include_id})
        else:
            print("[FBOGraph] extract_options.shared_include=0 -> skip SHARED_INCLUDE edges")

        # 2.9 Phân tích mối quan hệ Companion Files (các file cùng tên ở các folder khác nhau)
        basename_groups = {} # basename -> list of canonical_node_ids
        for node_id, node in graph.nodes.items():
            # Chỉ xét các Canonical Nodes để tránh trùng lặp companion làm nhiễu đồ thị
            if node.alias_of and node.alias_of != node.node_id:
                continue
            basename = Path(node.relative_path).name.lower()
            if "." in basename:
                basename = basename.split(".")[0]
            basename_groups.setdefault(basename, []).append(node.node_id)
            
        for basename, node_ids in basename_groups.items():
            if len(node_ids) > 1:
                for i in range(len(node_ids)):
                    for j in range(i + 1, len(node_ids)):
                        id1 = node_ids[i]
                        id2 = node_ids[j]
                        add_rewrite_edge(id1, id2, EdgeType.COMPANION_FILE, {"basename": basename})
                        add_rewrite_edge(id2, id1, EdgeType.COMPANION_FILE, {"basename": basename})

        print(f"[TIMING] edges: {time.perf_counter()-t_edges:.2f}s")
        return graph

def build_and_save_graph(controllers_dir: Path, output_dir: Path, progress=None, project_label: str = "") -> XmlGraph:
    """Build graph va luu vao Kuzu."""
    controllers_dir = Path(controllers_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = output_dir / "kuzu"

    # Dung Kuzu lam incremental cache neu co
    builder = GraphBuilder(controllers_dir, cache_path=db_path, progress=progress, project_label=project_label)
    graph = builder.build()

    t_kuzu = time.perf_counter()
    kuzu_store = KuzuIndexStore(db_path)
    kuzu_store.sync_graph(graph)
    print(f"[TIMING] kuzu write: {time.perf_counter()-t_kuzu:.2f}s")

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

    if file_path.suffix.lower() == ".f":
        sibling_xml = file_path.with_suffix(".xml")
        if sibling_xml.is_file():
            # Co sibling .xml -> bo qua .f, khong ghi de node XML
            return None
        else:
            node = build_f_only_stub_node(file_path, controllers_root)
            # Thiet lap canonical_path / alias_of tinh
            stem = Path(node.relative_path).stem
            norm_name = normalize_controller_name(stem)
            f_type = node.folder_type
            f_subtype = node.folder_subtype
            rel_parts = Path(node.relative_path.replace("\\", "/")).parts
            
            logical_f_type = f_type
            standard_folders = {"dir", "grid", "filter", "report", "lookup", "form"}
            if f_type.lower() == "templates" or f_subtype.lower() == "upload":
                grid_candidate = controllers_root / "Grid" / f"{norm_name}.xml"
                dir_candidate = controllers_root / "Dir" / f"{norm_name}.xml"
                if grid_candidate.is_file():
                    logical_f_type = "Grid"
                elif dir_candidate.is_file():
                    logical_f_type = "Dir"
                else:
                    logical_f_type = "Grid"
            elif f_subtype.lower() == "fields" or "config/fields" in node.relative_path.replace("\\", "/").lower():
                if len(rel_parts) > 1 and rel_parts[0].lower() in standard_folders:
                    logical_f_type = rel_parts[0]
                else:
                    logical_f_type = "Grid"
            else:
                if f_type.lower() in standard_folders:
                    logical_f_type = f_type
                else:
                    logical_f_type = "Grid"
                    
            logical_f_type = logical_f_type.capitalize()
            node.canonical_path = f"{logical_f_type}\\{norm_name}.xml"
            # Stub .f-only: alias trỏ về chính node (không có .xml canonical trên disk)
            node.alias_of = node.node_id
            
            kuzu_store = KuzuIndexStore(db_path)
            # Cùng API với nhánh XML bên dưới — KuzuIndexStore không có upsert_node
            kuzu_store.update_single_node(node, edges=[])
            return node


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

        # Tự xác định canonical_path và alias_of tĩnh cho file đơn lẻ
        stem = Path(data["relative_path"]).stem
        norm_name = normalize_controller_name(stem)
        
        f_type = data["folder_type"]
        f_subtype = data["folder_subtype"]
        rel_parts = Path(data["relative_path"].replace("\\", "/")).parts
        
        logical_f_type = f_type
        standard_folders = {"dir", "grid", "filter", "report", "lookup", "form"}
        if f_type.lower() == "templates" or f_subtype.lower() == "upload":
            grid_candidate = controllers_root / "Grid" / f"{norm_name}.xml"
            dir_candidate = controllers_root / "Dir" / f"{norm_name}.xml"
            if grid_candidate.is_file():
                logical_f_type = "Grid"
            elif dir_candidate.is_file():
                logical_f_type = "Dir"
            else:
                logical_f_type = "Grid"
        elif f_subtype.lower() == "fields" or "config/fields" in data["relative_path"].replace("\\", "/").lower():
            if len(rel_parts) > 1 and rel_parts[0].lower() in standard_folders:
                logical_f_type = rel_parts[0]
            else:
                logical_f_type = "Grid"
        else:
            if f_type.lower() in standard_folders:
                logical_f_type = f_type
            else:
                logical_f_type = "Grid"
                
        logical_f_type = logical_f_type.capitalize()
        canonical_rel_path = f"{logical_f_type}\\{norm_name}.xml"
        
        alias_node_id = node_id
        canonical_file_path = controllers_root / logical_f_type / f"{norm_name}.xml"
        if canonical_file_path.is_file():
            alias_node_id = generate_node_id(f"{logical_f_type}/{norm_name}.xml")

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
            canonical_path  = canonical_rel_path,
            alias_of        = alias_node_id,
        )

        # Tao edges chi cho node nay (tinh toan day du ca edges nghiep vu bang cach query Kuzu DB)
        edges: List[GraphEdge] = []
        kuzu_store = KuzuIndexStore(db_path)
        conn = kuzu_store.conn

        # Helper tim canonical node bang controller name qua DB
        def find_canonical_node_db(ctrl_name: str) -> Optional[str]:
            ctrl_lower = ctrl_name.lower().strip()
            # 1. Thu cac folder chinh
            for folder in ["grid", "dir", "filter", "lookup", "report", "form"]:
                cand = f"{folder}/{ctrl_lower}.xml"
                res = conn.execute("MATCH (n:XmlFile) WHERE lcase(n.relative_path) = $path RETURN n.node_id, n.alias_of", {"path": cand.replace("/", "\\")})
                if res.has_next():
                    row = res.get_next()
                    return row[1] if row[1] else row[0]
            # 2. Quet toan bo de tim stem
            res = conn.execute("MATCH (n:XmlFile) RETURN n.node_id, n.relative_path, n.alias_of")
            candidates = []
            while res.has_next():
                row = res.get_next()
                nid, rel_path, alias_of = row[0], row[1], row[2]
                stem = Path(rel_path).stem
                if normalize_controller_name(stem).lower() == ctrl_lower:
                    candidates.append((nid, rel_path, alias_of))
            if candidates:
                canonical_cands = []
                for nid, rel_path, alias_of in candidates:
                    if not alias_of or alias_of == nid:
                        canonical_cands.append((nid, rel_path))
                if not canonical_cands:
                    first_alias = candidates[0][2]
                    return first_alias if first_alias else candidates[0][0]
                def sort_priority(item):
                    rp = item[1].replace("\\", "/").lower()
                    if "grid/" in rp: return 0
                    if "dir/" in rp: return 1
                    return 2
                canonical_cands.sort(key=sort_priority)
                return canonical_cands[0][0]
            return None

        # Helper tim node bang relative_path qua DB
        def find_node_by_rel_path_db(rel_path: str) -> Optional[str]:
            norm_path = rel_path.replace("/", "\\").lower()
            res = conn.execute("MATCH (n:XmlFile) WHERE lcase(n.relative_path) = $path RETURN n.node_id", {"path": norm_path})
            if res.has_next():
                return res.get_next()[0]
            return None

        # 1. SQL Edges
        for sql_block in node.sql_blocks:
            parsed = sql_parser.parse(sql_block["content"])
            for tbl in parsed.get("tables", []):
                edges.append(GraphEdge(node.alias_of, tbl, EdgeType.SQL_TABLE_USE, {"line": sql_block["line"], "parsed_from_source": node.relative_path}))
            for proc in parsed.get("stored_procedures", []):
                edges.append(GraphEdge(node.alias_of, proc, EdgeType.SQL_PROC_CALL, {"line": sql_block["line"], "parsed_from_source": node.relative_path}))

        # 2. JS Func Call & showForm
        for js_block in node.js_blocks:
            parsed_js = js_parser.parse(js_block["content"])
            for field in parsed_js.get("client_fields", []):
                edges.append(GraphEdge(node.alias_of, field, EdgeType.JS_FUNC_CALL, {"line": js_block["line"], "js_action": "field_access", "parsed_from_source": node.relative_path}))
                
            show_form_calls = parsed_js.get("show_form_calls", [])
            for target_form in show_form_calls:
                target_id = find_canonical_node_db(target_form)
                if target_id:
                    edges.append(GraphEdge(node.alias_of, target_id, EdgeType.RETRIEVE_DATA_SOURCE, {"line": js_block["line"], "form": target_form, "parsed_from_source": node.relative_path}))
                if target_form.endswith("Filter"):
                    prefix = target_form[:-6]
                    suffixes = [
                        ("Grid", "Grid"), ("MultiGrid", "Grid"),
                        ("Form", "Form"), ("MultiForm", "Form"),
                        ("Lookup", "Lookup")
                    ]
                    for suffix, folder_name in suffixes:
                        candidate_name = f"{prefix}{suffix}"
                        candidate_id = find_canonical_node_db(candidate_name)
                        if candidate_id:
                            edges.append(GraphEdge(
                                node.alias_of, candidate_id, EdgeType.RETRIEVE_DATA_SOURCE,
                                {"line": js_block["line"], "relation": f"derived_{suffix}", "source_form": target_form, "parsed_from_source": node.relative_path}
                            ))

        # 3. Master-Detail Grid
        for grid_ref in getattr(node, "grid_refs", []):
            detail_controller = grid_ref["controller"]
            target_id = find_canonical_node_db(detail_controller)
            if target_id:
                edges.append(GraphEdge(
                    node.alias_of, target_id, EdgeType.GRID_MASTER_DETAIL,
                    {"field_name": grid_ref["field_name"], "foreign_key": grid_ref.get("foreign_key"), "parsed_from_source": node.relative_path}
                ))

        # 4. Lookup reference
        for lookup_ref in getattr(node, "lookup_refs", []):
            lookup_controller = lookup_ref["controller"]
            target_id = find_canonical_node_db(lookup_controller)
            if target_id:
                edges.append(GraphEdge(
                    node.alias_of, target_id, EdgeType.LOOKUP_REFERENCE,
                    {"field_name": lookup_ref["field_name"], "parsed_from_source": node.relative_path}
                ))

        # 5. Entity Include & Param Entity Use
        for ent in node.entities:
            target_rel_path = ent["relative_path"].replace("\\", "/").lower()
            target_id = find_node_by_rel_path_db(target_rel_path)
            if target_id:
                edges.append(GraphEdge(node.alias_of, target_id, EdgeType.ENTITY_INCLUDE, {"entity_name": ent["name"], "parsed_from_source": node.relative_path}))

        for p_ent_name in node.param_entities:
            matched_ent_path = None
            for ent in node.entities:
                if ent["name"] == p_ent_name:
                    matched_ent_path = ent["relative_path"].replace("\\", "/").lower()
                    break
            if matched_ent_path:
                target_id = find_node_by_rel_path_db(matched_ent_path)
                if target_id:
                    edges.append(GraphEdge(node.alias_of, target_id, EdgeType.PARAM_ENTITY_USE, {"param_entity": p_ent_name, "parsed_from_source": node.relative_path}))

        # 6. Grid Master-Detail from JS getItem
        import re as _re
        _GET_ITEM_PATTERN = _re.compile(
            r'(?:f|form|parentForm)\.getItem\s*\(\s*["\']([dr]\d+)["\']\s*\)',
            _re.IGNORECASE
        )
        if node.folder_type.lower() == "dir":
            for js_block in node.js_blocks:
                content = js_block.get('content', '')
                found_items = set(_GET_ITEM_PATTERN.findall(content))
                for item_id in found_items:
                    res = conn.execute("MATCH (n:XmlFile) WHERE lcase(n.folder_type) = 'grid' AND n.code_field = $item RETURN n.node_id, n.alias_of", {"item": item_id})
                    if res.has_next():
                        row = res.get_next()
                        target_id = row[1] if row[1] else row[0]
                        edges.append(GraphEdge(
                            node.alias_of, target_id, EdgeType.GRID_MASTER_DETAIL,
                            {'field_name': item_id, 'detected_from': 'js_getItem', "parsed_from_source": node.relative_path}
                        ))

        # Update node vao Kuzu
        kuzu_store.update_single_node(node, edges)
        return node

    except Exception as e:
        print(f"[FBOGraph] incremental_update_file error for {file_path}: {e}")
        if "lock" in str(e).lower() or "io exception" in str(e).lower():
            raise e
        return None

def delete_node_by_path(controllers_root: Path, db_path: Path, file_path: Path) -> Optional[str]:
    """Xoa hoan toan node khoi Kuzu DB khi file bi xoa vat ly, va tai danh gia lai Canonical Group."""
    try:
        controllers_root = Path(controllers_root).resolve()
        file_path = Path(file_path).resolve()
        
        rel_path = os.path.relpath(file_path, controllers_root)
        node_id = generate_node_id(rel_path)
        
        kuzu_store = KuzuIndexStore(db_path)
        conn = kuzu_store.conn
        
        # 1. Lay thong tin cua node sap xoa phuc vu viec re-evaluate canonical group va backup canh
        res = conn.execute("MATCH (n:XmlFile {node_id: $nid}) RETURN n.folder_type, n.relative_path", {"nid": node_id})
        folder_type = None
        relative_path = None
        if res.has_next():
            row = res.get_next()
            folder_type, relative_path = row[0], row[1]
            
        backup_inbound = []
        backup_outbound = []
        if folder_type and relative_path:
            import json
            # Backup inbound edges
            res_in = conn.execute("MATCH (src:XmlFile)-[r:Rel]->(dst:XmlFile {node_id: $nid}) RETURN src.node_id, r.edge_type, r.meta", {"nid": node_id})
            while res_in.has_next():
                row_in = res_in.get_next()
                backup_inbound.append({"src_id": row_in[0], "edge_type": row_in[1], "meta": json.loads(row_in[2] or "{}")})
            # Backup outbound edges
            res_out = conn.execute("MATCH (src:XmlFile {node_id: $nid})-[r:Rel]->(dst:XmlFile) RETURN dst.node_id, r.edge_type, r.meta", {"nid": node_id})
            while res_out.has_next():
                row_out = res_out.get_next()
                backup_outbound.append({"dst_id": row_out[0], "edge_type": row_out[1], "meta": json.loads(row_out[2] or "{}")})
            
        # 2. Thuc hien xoa node khoi Kuzu DB
        conn.execute("MATCH (n:XmlFile {node_id: $nid}) DETACH DELETE n", {"nid": node_id})
        print(f"[FBOGraph] Detached & deleted physical node {node_id} ({rel_path})")
        
        # 3. Re-evaluate canonical group neu node bi xoa co ton tai truoc do
        if folder_type and relative_path:
            stem = Path(relative_path).stem
            normalized_name = normalize_controller_name(stem)
            
            from xml_fbograph.storage.kuzu_index import reevaluate_canonical_group_on_delete
            reevaluate_canonical_group_on_delete(conn, controllers_root, folder_type, normalized_name, node_id, backup_inbound, backup_outbound)
            
        return rel_path
    except Exception as e:
        print(f"[FBOGraph] delete_node_by_path error for {file_path}: {e}")
        if "lock" in str(e).lower() or "io exception" in str(e).lower():
            raise e
        return None
