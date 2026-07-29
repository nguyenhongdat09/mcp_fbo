import os
import sys
import json
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from xml_fbograph.core.schema import XmlGraph, GraphNode
from xml_fbograph.utils.path_helper import ProjectPathHelper
from xml_fbograph.storage.kuzu_index import KuzuIndexStore
from xml_fbograph.rules.edges_rules import EdgeType

# In-memory cache: tránh load Kuzu mỗi query
# Cache được invalidate khi graph_dir thay đổi.
# ============================================================
_graph_cache: Dict[str, Tuple[float, XmlGraph]] = {}   # graph_dir -> (mtime, graph)
_store_cache: Dict[str, KuzuIndexStore] = {}          # graph_dir -> store
_last_sync_times: Dict[str, float] = {}              # graph_dir -> last checked timestamp


# Synonym canonical keys = ASCII khong dau (an toan charset / goi tool).
# Agent nen truyen: "giay bao no", "phieu chi", "dien giai", "gia ban"...
FBO_SYNONYMS = {
    "gia ban": ["gia2", "gia_nt2", "gia_ban", "gia21", "price", "t_tien2", "t_tien_nt2"],
    "ma hang": ["ma_vt", "ma_hang", "item_code", "ma_vtthue"],
    "ma giao dich": ["ma_gd", "transaction_code"],
    "khach hang": ["ma_kh", "ten_kh", "customer", "ma_khthue"],
    "kho": ["ma_kho", "warehouse"],
    "excel": ["import", "upload", "template", "excel"],
    "thue": ["thue", "thue_suat", "tax"],
    "tien te": ["ma_nt", "ty_gia", "currency"],
    "giay bao no": ["CPTran", "CPDetail", "CPTax"],
    "phieu chi": ["CDTran", "CDDetail", "CDTax"],
    "ten hang hoa": ["ten_vt", "Goods-Services", "goods", "services"],
    "dien giai": ["dien_giai", "description", "memo"],
}

# Co dau / bien the -> key ASCII canonical
FBO_SYNONYM_ALIASES = {
    "giấy báo nợ": "giay bao no",
    "giay bao no?": "giay bao no",
    "phiếu chi": "phieu chi",
    "tên hàng hóa": "ten hang hoa",
    "ten hang hoa - dich vu": "ten hang hoa",
    "tên hàng hóa - dịch vụ": "ten hang hoa",
    "diễn giải": "dien giai",
    "thuế": "thue",
    "giá bán": "gia ban",
    "mã hàng": "ma hang",
    "mã giao dịch": "ma giao dich",
    "khách hàng": "khach hang",
    "tiền tệ": "tien te",
}


def _strip_vietnamese_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _safe_log(msg: str) -> None:
    """Log stderr khong crash khi console la cp1252/charmap."""
    try:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
    except Exception:
        try:
            sys.stderr.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
            sys.stderr.flush()
        except Exception:
            pass


def _resolve_synonym_key(keyword: str) -> str:
    """Chuan hoa keyword -> key ASCII trong FBO_SYNONYMS."""
    kw_lower = keyword.lower().strip()
    if kw_lower in FBO_SYNONYMS:
        return kw_lower
    if kw_lower in FBO_SYNONYM_ALIASES:
        return FBO_SYNONYM_ALIASES[kw_lower]
    folded = _strip_vietnamese_accents(kw_lower)
    if folded in FBO_SYNONYMS:
        return folded
    if folded in FBO_SYNONYM_ALIASES:
        return FBO_SYNONYM_ALIASES[folded]
    for key in FBO_SYNONYMS:
        if _strip_vietnamese_accents(key) == folded:
            return key
    return folded or kw_lower


def expand_keyword(keyword: str) -> List[str]:
    """Mo rong tu khoa: luon uu tien key ASCII + synonym field/file."""
    canonical = _resolve_synonym_key(keyword)
    synonyms = FBO_SYNONYMS.get(canonical)
    if synonyms:
        # canonical ASCII truoc, giu ca tu khoa goc neu khac
        out = [canonical] + list(synonyms)
        if keyword and keyword.lower().strip() not in {x.lower() for x in out}:
            out.append(keyword)
        return out
    return [keyword]

def get_node_by_target(graph: XmlGraph, target: str) -> Optional[GraphNode]:
    """Tìm GraphNode trong graph dựa trên target (tên file hoặc relative path)."""
    target_clean = target.replace("\\", "/").lower()
    
    # 1. Tìm chính xác theo relative_path
    node_id = graph.node_by_path.get(target_clean)
    if node_id:
        return graph.nodes[node_id]
        
    # 2. Tìm theo tên file (không cần folder, ví dụ: "SVTran.xml" hoặc "SVTran"), ưu tiên Dir và Grid
    candidates = []
    for node in graph.nodes.values():
        filename = Path(node.relative_path).name.lower()
        basename = Path(node.relative_path).stem.lower()
        if filename == target_clean or basename == target_clean:
            candidates.append(node)
            
    if candidates:
        def sort_priority(n):
            f = n.folder_type.lower()
            if f == "dir":
                return 0
            if f == "grid":
                return 1
            return 2
        candidates.sort(key=sort_priority)
        return candidates[0]
            
    return None

def _xml_availability_payload(node: GraphNode) -> dict:
    """Trả payload cho agent khi file .f-only."""
    if not getattr(node, "needs_xml", False):
        return {}
    xml_path = node.relative_path  # đã chuẩn hóa .xml
    paired_f_path = getattr(node, "paired_f_path", None) or ""
    return {
        "needs_xml": [xml_path],
        "source_on_disk": paired_f_path,
        "is_f_only": True,
        "agent_hint": (
            f"Tồn tại {paired_f_path} (mã hóa) nhưng không có {xml_path}. "
            "Cần xin/cập nhật file XML từ quản trị trước khi chỉnh sửa."
        )
    }

def ensure_fresh_readonly_store(db_path: Path, graph_dir: Path) -> KuzuIndexStore:
    """Reopen RO store if kuzu mtime/size changed since last open."""
    graph_dir_key = str(graph_dir.resolve())
    db_key = str(db_path.resolve())
    
    try:
        if db_path.is_file():
            current_mtime = db_path.stat().st_mtime
        else:
            current_mtime = max(f.stat().st_mtime for f in db_path.iterdir() if f.is_file())
    except Exception:
        current_mtime = 0.0

    needs_reopen = False
    if graph_dir_key not in _graph_cache or graph_dir_key not in _store_cache:
        needs_reopen = True
    else:
        cached_mtime, _ = _graph_cache[graph_dir_key]
        if cached_mtime != current_mtime:
            needs_reopen = True

    if needs_reopen:
        _safe_log(f"[FBOGraph] Kuzu mtime changed or not cached -> reopening read-only store")
        from xml_fbograph.storage.kuzu_index import close_cached_database
        close_cached_database(db_path)
        
        # Xóa cache cũ
        _store_cache.pop(graph_dir_key, None)
        _graph_cache.pop(graph_dir_key, None)
        
        # Xóa reference bên mcp_tools để query_radar cũng phải lấy mới
        try:
            import sys
            if 'xml_fbograph.mcp_tools' in sys.modules:
                mt = sys.modules['xml_fbograph.mcp_tools']
                mt._kuzu_stores.pop(db_key, None)
        except Exception:
            pass

        # Tạo mới
        new_store = KuzuIndexStore(db_path, read_only=True)
        new_store._bind_live_connection()
        _store_cache[graph_dir_key] = new_store
        _graph_cache[graph_dir_key] = (current_mtime, new_store.load_graph())
        
    return _store_cache[graph_dir_key]

def xml_graph_query(query_type: str, target: str, reference_file: str, **kwargs) -> Dict[str, Any]:
    """
    HÀM TRUY VẤN DUY NHẤT cho XML FBOGraph.
    
    query_type: 'search', 'context', 'dependencies', 'dependents', 'entity', 'impact', 'use_case'
    target: Đối tượng truy vấn (tên file, tên entity, keyword...)
    reference_file: File XML hiện tại của dự án để auto-detect dự án.
    
    kwargs bổ sung cho search:
      folder_filter: str hoặc list, lọc theo thư mục (ví dụ: 'Dir' hoặc ['Dir', 'Grid'])
      type_filter: str hoặc list, lọc theo loại controller (ví dụ: 'dir' hoặc 'grid')
    """
    # 1. Xác định dự án và tự động build graph nếu chưa có
    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    controllers_dir = helper.get_controllers_path()
    
    db_path = graph_dir / "kuzu"

    def _kuzu_ready(path: Path) -> bool:
        if not path.exists():
            return False
        if path.is_file():
            return path.stat().st_size > 0
        try:
            return any(path.iterdir())
        except Exception:
            return False

    if not _kuzu_ready(db_path):
        _safe_log(f"[FBOGraph] Graph missing at {graph_dir}. Auto-building...")
        from xml_fbograph.builder.graph_builder import build_and_save_graph
        # Drop stale read-only handles before rebuild
        _store_cache.pop(str(graph_dir), None)
        _graph_cache.pop(str(graph_dir), None)
        build_and_save_graph(controllers_dir, graph_dir)
        _safe_log("[FBOGraph] Auto-build finished.")
        _graph_cache.pop(str(graph_dir), None)
        _last_sync_times[str(graph_dir)] = time.time()
    elif os.environ.get("FBOGRAPH_AUTO_SYNC", "").strip() == "1":
        # Chỉ sync gia tăng khi bật FBOGRAPH_AUTO_SYNC=1 (tránh lock khi chỉ query read-only)
        graph_dir_key = str(graph_dir)
        now = time.time()
        if now - _last_sync_times.get(graph_dir_key, 0.0) > 300.0:  # 5 phút
            _safe_log(f"[FBOGraph] Auto-syncing graph (incremental) for {graph_dir_key}...")
            from xml_fbograph.builder.graph_builder import build_and_save_graph
            _store_cache.pop(graph_dir_key, None)
            _graph_cache.pop(graph_dir_key, None)

            from xml_fbograph.storage.kuzu_index import _db_instances
            kuzu_db_path = graph_dir / "kuzu"
            cache_key = str(kuzu_db_path).replace("\\", "/").lower()
            _db_instances.pop(cache_key, None)

            try:
                build_and_save_graph(controllers_dir, graph_dir)
                _last_sync_times[graph_dir_key] = now
                _safe_log("[FBOGraph] Auto-sync finished.")
            except Exception as e:
                _safe_log(f"[FBOGraph] Auto-sync failed: {e}")
                _last_sync_times[graph_dir_key] = now


    # 2. Load Graph và Kuzu Index (ưu tiên cache in-memory, auto reopen nếu mtime đổi)
    kuzu_store = ensure_fresh_readonly_store(db_path, graph_dir)
    _, graph = _graph_cache[str(graph_dir)]

    # 3. Phân nhánh xử lý các kiểu query
    query_type = query_type.lower().strip()
    
    # --- QUERY: SEARCH ---
    if query_type == "search":
        # Mở rộng từ khóa tìm kiếm thông minh
        expanded_query = expand_keyword(target)
        
        # Trích xuất các tên controller để ưu tiên xếp hạng
        expanded_controllers = {kw.lower() for kw in expanded_query if kw.lower() in {
            "cptran", "cdtran", "artran", "aptran", "pgtran", "jrtran", "gltax",
            "svtran", "satran", "ditran"
        }}
        
        # Đọc bộ lọc từ kwargs
        folder_filter = kwargs.get("folder_filter")
        type_filter = kwargs.get("type_filter")
        match_type = kwargs.get("match_type") or "all"
        result_limit = int(kwargs.get("limit", 10))
        
        match_types_set = {t.strip().lower() for t in match_type.split(",")}
        
        # Chuẩn hóa bộ lọc thành tập hợp (set) để tra cứu nhanh
        folders_set = set()
        if folder_filter:
            if isinstance(folder_filter, str):
                folders_set = {f.strip().lower() for f in folder_filter.split(",")}
            elif isinstance(folder_filter, (list, tuple, set)):
                folders_set = {f.strip().lower() for f in folder_filter}
                
        types_set = set()
        if type_filter:
            if isinstance(type_filter, str):
                types_set = {t.strip().lower() for t in type_filter.split(",")}
            elif isinstance(type_filter, (list, tuple, set)):
                types_set = {t.strip().lower() for t in type_filter}

        # Tìm kiếm trong code SQL/JS
        code_matches = []
        if "all" in match_types_set or "code" in match_types_set:
            code_matches = kuzu_store.search_code(expanded_query, limit=result_limit)
            
        # Tìm kiếm trong các field định nghĩa
        field_matches = []
        if "all" in match_types_set or "field" in match_types_set:
            field_matches = kuzu_store.search_fields(expanded_query, limit=result_limit)
        
        # Áp dụng bộ lọc cho code_matches và field_matches
        filtered_code_matches = []
        seen_code_snippets = set()  # Lưu (node_id, clean_snippet) để khử trùng
        for match in code_matches:
            node_id = match["node_id"]
            node = graph.nodes.get(node_id)
            if node:
                if folders_set and node.folder_type.lower() not in folders_set:
                    continue
                if types_set and node.controller_type.lower() not in types_set:
                    continue
                
                # Không trả code_matches từ node bị mã hóa nếu compact
                is_encrypted = getattr(node, "is_encrypted", False)
                if is_encrypted and kwargs.get("compact"):
                    continue
                
                snippet_text = match.get("match_snippet", "")
                # Bỏ qua snippet rỗng hoặc chỉ chứa khoảng trắng/thẻ b bôi đậm
                clean_snippet = snippet_text.replace("<b>", "").replace("</b>", "").strip()
                if not clean_snippet or clean_snippet.lower() in {"encrypted", "<encrypted>", "[encrypted]"}:
                    continue
                
                dup_key = (node_id, clean_snippet.lower())
                if dup_key in seen_code_snippets:
                    continue
                seen_code_snippets.add(dup_key)

                match = dict(match)
                match["is_encrypted"] = is_encrypted
                if match["is_encrypted"]:
                    match["relative_path"] = match.get("relative_path", "") + " [Encrypted]"
                if getattr(node, "needs_xml", False):
                    match["needs_xml"] = True
                    match["is_f_only"] = True
                if kwargs.get("compact"):
                    # Compact: giữ match_snippet nhưng cắt ngắn xuống 80 ký tự
                    match["match_snippet"] = snippet_text[:80] + "..." if snippet_text else ""
            filtered_code_matches.append(match)
            
        filtered_field_matches = []
        seen_fields = set()  # Lưu (node_id, field_name) để khử trùng
        for match in field_matches:
            node_id = match["node_id"]
            node = graph.nodes.get(node_id)
            if node:
                if folders_set and node.folder_type.lower() not in folders_set:
                    continue
                if types_set and node.controller_type.lower() not in types_set:
                    continue
                
                match = dict(match)
                field_name = match.get("field_name", "")
                dup_key = (node_id, field_name.lower())
                if dup_key in seen_fields:
                    continue
                seen_fields.add(dup_key)

                match["is_encrypted"] = getattr(node, "is_encrypted", False)
                if match["is_encrypted"]:
                    match["relative_path"] = match.get("relative_path", "") + " [Encrypted]"
                if getattr(node, "needs_xml", False):
                    match["needs_xml"] = True
                    match["is_f_only"] = True
                
                # Tiết kiệm token: mặc định bỏ snippet dài trong compact hoặc match_type=all
                if kwargs.get("compact") or "field" not in match_types_set or match_type == "all":
                    match.pop("snippet", None)
                    match.pop("match_snippet", None)
            filtered_field_matches.append(match)

        # Tim theo ten file / title — dung ca synonym da expand (vd: giay bao no -> CPTran)
        file_matches = []
        if "all" in match_types_set or "file" in match_types_set:
            search_terms = [str(t).lower() for t in expanded_query if t]
            for node in graph.nodes.values():
                rel = (node.relative_path or "").lower()
                title_v = (getattr(node, "title_v", None) or "").lower()
                title_e = (getattr(node, "title_e", None) or "").lower()
                stem = Path(node.relative_path).stem.lower() if node.relative_path else ""
                hit = False
                for term in search_terms:
                    if (
                        term in rel
                        or term == stem
                        or (title_v and term in title_v)
                        or (title_e and term in title_e)
                    ):
                        hit = True
                        break
                if hit:
                    if folders_set and node.folder_type.lower() not in folders_set:
                        continue
                    if types_set and node.controller_type.lower() not in types_set:
                        continue
                    match_item = {
                        "node_id": node.node_id,
                        "relative_path": node.relative_path,
                        "controller_type": node.controller_type,
                        "folder_type": node.folder_type,
                        "title_v": getattr(node, "title_v", ""),
                        "title_e": getattr(node, "title_e", ""),
                        "is_encrypted": getattr(node, "is_encrypted", False),
                    }
                    if getattr(node, "needs_xml", False):
                        match_item["needs_xml"] = True
                        match_item["is_f_only"] = True
                    file_matches.append(match_item)

        # Sắp xếp kết quả theo mức độ liên quan tới reference_file
        ref_path = Path(reference_file).resolve()
        ref_folder = ""
        ref_basename = ""
        ref_prefix = ""
        try:
            ref_parts = ref_path.parts
            if len(ref_parts) >= 2:
                ref_folder = ref_parts[-2].lower()
                ref_basename = ref_path.stem.lower()
                if len(ref_basename) >= 2:
                    ref_prefix = ref_basename[:2]
        except Exception:
            pass

        def get_relevance_score(match_item):
            node_id = match_item.get("node_id")
            node = graph.nodes.get(node_id) if node_id else None
            if not node:
                return 0
            score = 0
            node_rel_path = node.relative_path.replace("\\", "/").lower()
            node_folder = node.folder_type.lower()
            node_basename = Path(node_rel_path).stem.lower()
            
            # Ưu tiên hoặc hạ rank theo controller được tìm kiếm
            if expanded_controllers:
                if node_basename in expanded_controllers:
                    score += 200
                    if node_folder == "dir":
                        score += 100
                else:
                    # Hạ rank các field/code của node khác khi đang tìm đích danh controller
                    is_field_or_code = "field_name" in match_item or "match_snippet" in match_item
                    if is_field_or_code:
                        score -= 150
            
            if ref_basename and ref_basename in node_basename:
                score += 100
                if ref_basename == node_basename:
                    score += 50
            if ref_prefix and node_basename.startswith(ref_prefix):
                score += 60
            if ref_folder and node_folder == ref_folder:
                score += 40
            if node_folder in {"dir", "grid"}:
                score += 80  # Boost mạnh thư mục chính
            elif node_folder == "templates":
                score -= 120  # Phạt rất mạnh thư mục phụ
            elif node_folder == "report":
                score -= 30   # Phạt nhẹ thư mục report
            return score

        filtered_code_matches.sort(key=get_relevance_score, reverse=True)
        filtered_field_matches.sort(key=get_relevance_score, reverse=True)
        file_matches.sort(key=get_relevance_score, reverse=True)

        return {
            "query": target,
            "expanded_query": " OR ".join(f'"{kw}"' for kw in expanded_query) if len(expanded_query) > 1 else expanded_query[0],
            "file_matches": file_matches[:result_limit],
            "field_matches": filtered_field_matches[:result_limit],
            "code_matches": filtered_code_matches[:result_limit]
        }

    # --- QUERY: CONTEXT ---
    elif query_type == "context":
        node = get_node_by_target(graph, target)
        if not node:
            return {"error": f"Không tìm thấy node phù hợp với '{target}'"}
            
        deps = []
        grid_details = []
        retrieve_sources = []
        lookup_references = []
        companion_files = []
        master_controllers = []
        
        needs_xml_list = []
        
        # 1. Cạnh đi ra
        if node.node_id in graph.edges_from:
            for edge in graph.edges_from[node.node_id]:
                target_node = graph.nodes.get(edge.target_id)
                target_path = target_node.relative_path if target_node else edge.target_id
                
                if edge.edge_type in {EdgeType.ENTITY_INCLUDE, EdgeType.PARAM_ENTITY_USE}:
                    deps.append({
                        "relative_path": target_path,
                        "type": edge.edge_type
                    })
                elif edge.edge_type == EdgeType.GRID_MASTER_DETAIL:
                    item = {
                        "field_name": edge.meta.get("field_name"),
                        "controller": target_path,
                        "foreign_key": edge.meta.get("foreign_key")
                    }
                    if target_node and getattr(target_node, "needs_xml", False):
                        item["needs_xml"] = True
                        item["source_on_disk"] = getattr(target_node, "paired_f_path", None)
                        needs_xml_list.append(target_node.relative_path)
                    grid_details.append(item)
                elif edge.edge_type == EdgeType.RETRIEVE_DATA_SOURCE:
                    retrieve_sources.append({
                        "relation": edge.meta.get("relation") or "direct",
                        "controller": target_path,
                        "line": edge.meta.get("line"),
                        "source_form": edge.meta.get("source_form")
                    })
                elif edge.edge_type == EdgeType.LOOKUP_REFERENCE:
                    item = {
                        "field_name": edge.meta.get("field_name"),
                        "controller": target_path
                    }
                    if target_node and getattr(target_node, "needs_xml", False):
                        item["needs_xml"] = True
                        item["source_on_disk"] = getattr(target_node, "paired_f_path", None)
                        needs_xml_list.append(target_node.relative_path)
                    lookup_references.append(item)
                elif edge.edge_type == EdgeType.COMPANION_FILE:
                    companion_files.append({
                        "relative_path": target_path,
                        "folder_type": target_node.folder_type if target_node else ""
                    })

        # 2. Cạnh đi vào
        if node.node_id in graph.edges_to:
            for edge in graph.edges_to[node.node_id]:
                source_node = graph.nodes.get(edge.source_id)
                source_path = source_node.relative_path if source_node else edge.source_id
                
                if edge.edge_type == EdgeType.GRID_MASTER_DETAIL:
                    master_controllers.append({
                        "field_name": edge.meta.get("field_name"),
                        "controller": source_path
                    })

        # compact check
        fields_output = []
        for f in node.fields:
            f_out = dict(f)
            if kwargs.get("compact"):
                f_out.pop("snippet", None)
            fields_output.append(f_out)

        # alternative check if encrypted
        encrypted_note = ""
        if getattr(node, "is_encrypted", False):
            candidates = []
            for f in companion_files:
                target_node = get_node_by_target(graph, f["relative_path"])
                if target_node and not getattr(target_node, "is_encrypted", False):
                    candidates.append(f["relative_path"])
            if candidates:
                encrypted_note = f"File này bị mã hóa. Bạn có thể xem thay thế ở: {', '.join(candidates)}"
            else:
                encrypted_note = "File này bị mã hóa và không tìm thấy file companion đọc được."

        res = {
            "node_id": node.node_id,
            "relative_path": node.relative_path,
            "folder_type": node.folder_type,
            "controller_type": node.controller_type,
            "table": node.table,
            "code_field": node.code_field,
            "fields": fields_output,
            "dependencies": deps,
            "grid_details": grid_details,
            "retrieve_sources": retrieve_sources,
            "lookup_references": lookup_references,
            "companion_files": companion_files,
            "master_controllers": master_controllers,
            "sql_blocks_count": len(node.sql_blocks),
            "js_blocks_count": len(node.js_blocks),
            "file_size": node.file_size
        }
        if getattr(node, "is_encrypted", False):
            res["readable"] = False
        if encrypted_note:
            res["encrypted_note"] = encrypted_note
        if needs_xml_list:
            res["needs_xml"] = sorted(list(set(needs_xml_list)))
            res["agent_hint"] = "Một số grid chỉ có file .f (mã hóa), thiếu .xml readable. Xin cấp XML từ quản trị."
        res.update(_xml_availability_payload(node))
        return res

    # --- QUERY: BLOCKS (SQL & JS) ---
    elif query_type == "blocks":
        node = get_node_by_target(graph, target)
        if not node:
            return {"error": f"Không tìm thấy node phù hợp với '{target}'"}
            
        encrypted_note = ""
        if getattr(node, "is_encrypted", False):
            companion_paths = []
            if node.node_id in graph.edges_from:
                for edge in graph.edges_from[node.node_id]:
                    if edge.edge_type == EdgeType.COMPANION_FILE:
                        target_node = graph.nodes.get(edge.target_id)
                        if target_node and not getattr(target_node, "is_encrypted", False):
                            companion_paths.append(target_node.relative_path)
            if companion_paths:
                encrypted_note = f"File này bị mã hóa. Bạn có thể xem thay thế ở: {', '.join(companion_paths)}"
            else:
                encrypted_note = "File này bị mã hóa và không tìm thấy file companion đọc được."

        res = {
            "controller": node.relative_path,
            "sql_blocks": node.sql_blocks,
            "js_blocks": node.js_blocks
        }
        if encrypted_note:
            res["encrypted_note"] = encrypted_note
        res.update(_xml_availability_payload(node))
        return res

    # --- QUERY: NAVIGATE ---
    elif query_type == "navigate":
        node = get_node_by_target(graph, target)
        if not node:
            return {"error": f"Không tìm thấy node phù hợp với '{target}'"}
            
        grid_details = []
        retrieve_sources = []
        lookup_references = []
        companion_files = []
        master_controllers = []
        needs_xml_list = []
        
        if node.node_id in graph.edges_from:
            for edge in graph.edges_from[node.node_id]:
                target_node = graph.nodes.get(edge.target_id)
                target_path = target_node.relative_path if target_node else edge.target_id
                
                if edge.edge_type == EdgeType.GRID_MASTER_DETAIL:
                    item = {
                        "field_name": edge.meta.get("field_name"),
                        "controller": target_path,
                        "foreign_key": edge.meta.get("foreign_key")
                    }
                    if target_node and getattr(target_node, "needs_xml", False):
                        item["needs_xml"] = True
                        item["source_on_disk"] = getattr(target_node, "paired_f_path", None)
                        needs_xml_list.append(target_node.relative_path)
                    grid_details.append(item)
                elif edge.edge_type == EdgeType.RETRIEVE_DATA_SOURCE:
                    retrieve_sources.append({
                        "relation": edge.meta.get("relation") or "direct",
                        "controller": target_path,
                        "line": edge.meta.get("line"),
                        "source_form": edge.meta.get("source_form")
                    })
                elif edge.edge_type == EdgeType.LOOKUP_REFERENCE:
                    item = {
                        "field_name": edge.meta.get("field_name"),
                        "controller": target_path
                    }
                    if target_node and getattr(target_node, "needs_xml", False):
                        item["needs_xml"] = True
                        item["source_on_disk"] = getattr(target_node, "paired_f_path", None)
                        needs_xml_list.append(target_node.relative_path)
                    lookup_references.append(item)
                elif edge.edge_type == EdgeType.COMPANION_FILE:
                    companion_files.append({
                        "relative_path": target_path,
                        "folder_type": target_node.folder_type if target_node else ""
                    })

        if node.node_id in graph.edges_to:
            for edge in graph.edges_to[node.node_id]:
                source_node = graph.nodes.get(edge.source_id)
                source_path = source_node.relative_path if source_node else edge.source_id
                
                if edge.edge_type == EdgeType.GRID_MASTER_DETAIL:
                    master_controllers.append({
                        "field_name": edge.meta.get("field_name"),
                        "controller": source_path
                    })
                    
        res = {
            "controller": node.relative_path,
            "folder_type": node.folder_type,
            "companion_files": companion_files,
            "grid_details": grid_details,
            "retrieve_sources": retrieve_sources,
            "lookup_references": lookup_references,
            "master_controllers": master_controllers
        }
        if needs_xml_list:
            res["needs_xml"] = sorted(list(set(needs_xml_list)))
            res["agent_hint"] = "Một số grid chỉ có file .f (mã hóa), thiếu .xml readable. Xin cấp XML từ quản trị."
        return res

    # --- QUERY: DEPENDENCIES ---
    elif query_type == "dependencies":
        node = get_node_by_target(graph, target)
        if not node:
            return {"error": f"Không tìm thấy node phù hợp với '{target}'"}
            
        deps = []
        if node.node_id in graph.edges_from:
            for edge in graph.edges_from[node.node_id]:
                if edge.edge_type == "JS_FUNC_CALL":
                    # Bỏ qua JS function/field noise gây nhiễu cho dependencies
                    continue
                target_node = graph.nodes.get(edge.target_id)
                dep_item = {
                    "target": target_node.relative_path if target_node else edge.target_id,
                    "type": edge.edge_type,
                    "meta": edge.meta
                }
                if target_node and getattr(target_node, "needs_xml", False):
                    dep_item["needs_xml"] = [target_node.relative_path]
                deps.append(dep_item)
        return {"file": node.relative_path, "dependencies": deps}

    # --- QUERY: DEPENDENTS ---
    elif query_type == "dependents":
        node = get_node_by_target(graph, target)
        # Nếu target không là file, tìm kiếm theo chuỗi ID thực tế
        node_id = node.node_id if node else target
        
        dependents = []
        if node_id in graph.edges_to:
            for edge in graph.edges_to[node_id]:
                source_node = graph.nodes.get(edge.source_id)
                dependents.append({
                    "source": source_node.relative_path if source_node else edge.source_id,
                    "type": edge.edge_type,
                    "meta": edge.meta
                })
        return {"target": node.relative_path if node else target, "dependents": dependents}

    # --- QUERY: ENTITY ---
    elif query_type == "entity":
        # Tra cứu xem entity này được khai báo ở đâu và có giá trị gì
        # Quét qua toàn bộ node để tìm thực thể có tên là target
        declarations = []
        usages = []
        
        for node in graph.nodes.values():
            for ent in node.entities:
                if ent["name"].lower() == target.lower():
                    declarations.append({
                        "defined_in": node.relative_path,
                        "entity_name": ent["name"],
                        "target_path": ent["relative_path"]
                    })
            if target.lower() in [pe.lower() for pe in node.param_entities]:
                usages.append({
                    "used_in": node.relative_path,
                    "type": "parameter_entity"
                })

        res = {
            "entity": target,
            "declarations": declarations,
            "usages": usages
        }
        if not declarations and not usages:
            res["note"] = f"Entity có thể nằm trong Include/. Dùng: python read_entity.py {target} --xml <any_xml_in_project>"
        return res

    # --- QUERY: IMPACT ---
    elif query_type == "impact":
        node = get_node_by_target(graph, target)
        if not node:
            return {"error": f"Không tìm thấy node phù hợp với '{target}'"}
            
        # Thuật toán BFS tìm các Node bị ảnh hưởng gián tiếp
        visited = set()
        queue = [node.node_id]
        visited.add(node.node_id)
        
        impact_chain = []
        
        while queue:
            current_id = queue.pop(0)
            if current_id in graph.edges_to:
                for edge in graph.edges_to[current_id]:
                    # Chỉ quét các liên kết phụ thuộc code
                    if edge.edge_type in {EdgeType.ENTITY_INCLUDE, EdgeType.PARAM_ENTITY_USE, EdgeType.SHARED_INCLUDE}:
                        if edge.source_id not in visited:
                            visited.add(edge.source_id)
                            queue.append(edge.source_id)
                            
                            source_node = graph.nodes.get(edge.source_id)
                            if source_node:
                                impact_chain.append({
                                    "relative_path": source_node.relative_path,
                                    "controller_type": source_node.controller_type,
                                    "folder_type": source_node.folder_type,
                                    "dependency_type": edge.edge_type
                                })
                                
        return {
            "target": node.relative_path,
            "impacted_count": len(impact_chain),
            "impacted_files": impact_chain
        }

    # --- QUERY: USE_CASE ---
    elif query_type == "use_case":
        node = get_node_by_target(graph, target)
        if not node:
            return {"error": f"Không tìm thấy node phù hợp với '{target}'"}
            
        # Thu thập các bảng SQL liên quan
        tables = []
        procedures = []
        client_fields = []
        
        # Nếu có liên kết đi từ node này
        if node.node_id in graph.edges_from:
            for edge in graph.edges_from[node.node_id]:
                if edge.edge_type == EdgeType.SQL_TABLE_USE:
                    tables.append(edge.target_id)
                elif edge.edge_type == EdgeType.SQL_PROC_CALL:
                    procedures.append(edge.target_id)
                elif edge.edge_type == EdgeType.JS_FUNC_CALL:
                    client_fields.append(edge.target_id)

        # Trích xuất trực tiếp từ sql_blocks để không bỏ sót bảng/proc
        from xml_fbograph.parsers.sql_parser import SqlBlockParser
        sql_parser = SqlBlockParser()
        for sql_block in node.sql_blocks:
            parsed = sql_parser.parse(sql_block.get("content", ""))
            for t in parsed.get("tables", []):
                tables.append(t)
            for p in parsed.get("stored_procedures", []):
                procedures.append(p)
 
        # Trích xuất bảng chính từ schema
        main_table = node.table
        
        # Thêm ghi chú khi không tìm thấy sql tables/procs nhưng file có chứa sql_blocks (thường là entity Include)
        sql_note = ""
        if not tables and not procedures and node.sql_blocks:
            sql_note = "SQL nằm trong entity Include — dùng `blocks` sau khi flat hoặc `python read_entity.py <entity> --xml <file>`"

        res = {
            "controller": node.relative_path,
            "purpose": f"Xử lý dữ liệu màn hình {node.folder_type}",
            "main_db_table": main_table,
            "related_db_tables": sorted(list(set(tables))),
            "stored_procedures_executed": sorted(list(set(procedures))),
            "client_fields_interacted": sorted(list(set(client_fields))),
            "fields_count": len(node.fields)
        }
        if sql_note:
            res["sql_note"] = sql_note
        return res

    # --- QUERY: VISUALIZE (MERMAID) ---
    elif query_type in {"visualize", "mermaid"}:
        node = get_node_by_target(graph, target)
        if not node:
            return {"error": f"Không tìm thấy node phù hợp với '{target}'"}
            
        from xml_fbograph.visual.visualizer import generate_mermaid_graph
        mermaid_code = generate_mermaid_graph(graph, node.node_id, max_depth=kwargs.get("max_depth", 2))
        return {
            "node_id": node.node_id,
            "relative_path": node.relative_path,
            "mermaid": mermaid_code
        }

    else:
        return {"error": f"Không hỗ trợ query_type '{query_type}'"}
