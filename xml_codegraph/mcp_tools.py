import json
import threading
import sys
from pathlib import Path

# Setup paths to ensure clean execution and imports
sys.path.append(str(Path(__file__).parent.parent.resolve()))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from xml_codegraph.utils.path_helper import ProjectPathHelper
from xml_codegraph.service.watcher import start_watcher
from xml_codegraph.storage.kuzu_index import KuzuIndexStore
from xml_codegraph.query.engine import xml_graph_query, _safe_log

# Cache connections and watcher
_watched_projects = set()
_kuzu_stores = {}


def _kuzu_db_ready(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    if db_path.is_file():
        return db_path.stat().st_size > 0
    try:
        return any(db_path.iterdir())
    except Exception:
        return False


def _ensure_graph_built(reference_file: str) -> Path:
    """Build graph neu kuzu chua co / rong. Tra ve db_path."""
    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    db_path = graph_dir / "kuzu"
    if _kuzu_db_ready(db_path):
        return db_path

    _safe_log(f"[FboCodeGraph MCP] Building graph for {helper.get_project_root()} ...")
    from xml_codegraph.builder.graph_builder import build_and_save_graph

    # Invalidate caches before rebuild
    db_key = str(db_path)
    _kuzu_stores.pop(db_key, None)
    from xml_codegraph.query import engine as qe

    qe._store_cache.pop(str(graph_dir), None)
    qe._graph_cache.pop(str(graph_dir), None)

    build_and_save_graph(helper.get_controllers_path(), graph_dir)
    _safe_log("[FboCodeGraph MCP] Graph build finished.")
    return db_path


def start_watcher_for_project(reference_file: str):
    """Khoi chay file watcher trong background thread neu project nay chua duoc giam sat."""
    try:
        helper = ProjectPathHelper(reference_file)
        project_root = str(helper.get_project_root().resolve())
        controllers_dir = helper.get_controllers_path()
        graph_dir = helper.get_graph_dir()

        from xml_codegraph.utils.path_helper import is_db_owner
        if not is_db_owner(controllers_dir, graph_dir):
            sys.stderr.write(f"[FboCodeGraph MCP] user_multi_db_yn=0: Watcher disabled for {controllers_dir} because it is not owner of Kuzu DB ({graph_dir.parent.name})\n")
            return

        _watched_projects.add(project_root)

        def watcher_thread():
            try:
                import os
                sys.stderr.write(f"[FboCodeGraph MCP] Starting file watcher thread for {controllers_dir} (PID: {os.getpid()})\n")
                sys.stderr.write(f"[FboCodeGraph MCP] WARNING: Recommend using a single MCP instance per machine for same KuzuDB to avoid lock conflicts.\n")
                start_watcher(controllers_dir, graph_dir)
            except Exception as e:
                sys.stderr.write(f"[FboCodeGraph MCP] Watcher thread failed: {e}\n")

        t = threading.Thread(target=watcher_thread, daemon=True)
        t.start()
    except Exception as e:
        sys.stderr.write(f"[FboCodeGraph MCP] Error starting watcher: {e}\n")


def get_kuzu_store(reference_file: str):
    """Lay hoac khoi tao ket noi Kuzu DB cho du an (build-if-missing truoc read_only)."""
    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir().resolve()
    db_path = (graph_dir / "kuzu").resolve()
    db_key = str(db_path)
    graph_key = str(graph_dir)

    from xml_codegraph.query import engine as qe

    # Tự động đồng bộ gia tăng nếu đã quá 5 phút
    import time
    now = time.time()
    if now - qe._last_sync_times.get(graph_key, 0.0) > 300.0:
        # Gọi xml_graph_query với target rỗng / dummy để kích hoạt kiểm tra/đồng bộ tự động
        try:
            qe.xml_graph_query("search", "", reference_file, limit=1)
        except Exception:
            pass

    if not _kuzu_db_ready(db_path):
        _ensure_graph_built(reference_file)
    start_watcher_for_project(reference_file)

    # Luon kiem tra mtime cua KuzuDB va reopen neu can thiet
    store = qe.ensure_fresh_readonly_store(db_path, graph_dir)
    _kuzu_stores[db_key] = store
    return store



# Tool 1
def _get_radar_schema(store: KuzuIndexStore) -> dict:
    """Doc schema Kuzu live va bo sung quy tac nghiep vu de agent viet Cypher."""
    from xml_codegraph.rules.edges_rules import EDGE_DESCRIPTIONS, EdgeType

    tables = store.execute_cypher("CALL show_tables() RETURN *")
    node_info = store.execute_cypher("CALL table_info('XmlFile') RETURN *")
    rel_info = store.execute_cypher("CALL table_info('Rel') RETURN *")
    live_edge_rows = store.execute_cypher(
        """
        MATCH (:XmlFile)-[r:Rel]->(:XmlFile)
        RETURN DISTINCT r.edge_type AS edge_type
        ORDER BY edge_type
        """
    )
    live_edge_types = {row["edge_type"] for row in live_edge_rows}

    node_columns = {row["name"]: row["type"] for row in node_info}
    rel_columns = {row["name"]: row["type"] for row in rel_info}
    edge_types = {}
    for edge_type in EdgeType:
        edge_types[edge_type.value] = {
            "description": EDGE_DESCRIPTIONS.get(edge_type, ""),
            "present_in_database": edge_type.value in live_edge_types,
        }

    return {
        "mode": "schema",
        "source": "Live Kuzu schema + FBO edge semantics",
        "tables": tables,
        "node_table": {
            "name": "XmlFile",
            "primary_key": "node_id",
            "columns": node_columns,
        },
        "relationship_table": {
            "name": "Rel",
            "from": "XmlFile",
            "to": "XmlFile",
            "columns": rel_columns,
        },
        "edge_types": edge_types,
        "rules": [
            "Kuzu chi co relationship table :Rel; loai nghiep vu nam trong r.edge_type.",
            "Dung MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile), khong dung label Neo4j [:GRID_MASTER_DETAIL].",
            "Luon filter r.edge_type va them LIMIT khi query relationship (SHARED_INCLUDE phu thuoc extract_options.shared_include).",
            "relative_path dung backslash, vi du Dir\\\\CPTran.xml.",
            "Dung js_text CONTAINS 'HandlerName' de tim JavaScript; dung size(string), khong dung length(string).",
            "canonical_path/alias_of gom nhieu file vat ly ve mot logical controller.",
        ],
        "examples": [
            {
                "name": "Master voucher -> detail grid",
                "cypher": (
                    "MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile) "
                    "WHERE a.relative_path = 'Dir\\\\CPTran.xml' "
                    "AND r.edge_type = 'GRID_MASTER_DETAIL' "
                    "RETURN a.relative_path, b.relative_path, r.meta LIMIT 20"
                ),
            },
            {
                "name": "Reverse lookup: ai goi RequestFilter",
                "cypher": (
                    "MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile) "
                    "WHERE b.relative_path CONTAINS 'RequestFilter' "
                    "AND r.edge_type = 'RETRIEVE_DATA_SOURCE' "
                    "RETURN a.relative_path, b.relative_path, r.meta LIMIT 20"
                ),
            },
            {
                "name": "Chuoi 2 cap voucher -> detail -> filter",
                "cypher": (
                    "MATCH (a:XmlFile)-[r1:Rel]->(b:XmlFile)-[r2:Rel]->(c:XmlFile) "
                    "WHERE r1.edge_type = 'GRID_MASTER_DETAIL' "
                    "AND r2.edge_type = 'RETRIEVE_DATA_SOURCE' "
                    "RETURN a.relative_path, b.relative_path, c.relative_path LIMIT 20"
                ),
            },
        ],
    }


def mcp_query_radar(
    cypher_query: str,
    reference_file: str,
    mode: str = "query",
) -> str:
    try:
        normalized_mode = (mode or "query").strip().lower()
        if normalized_mode not in {"query", "schema"}:
            return json.dumps(
                {"error": "mode phai la 'query' hoac 'schema'"},
                indent=2,
                ensure_ascii=False,
            )

        store = get_kuzu_store(reference_file)
        if normalized_mode == "schema":
            return json.dumps(_get_radar_schema(store), indent=2, ensure_ascii=False)

        if not (cypher_query or "").strip():
            return json.dumps(
                {"error": "cypher_query la bat buoc khi mode='query'"},
                indent=2,
                ensure_ascii=False,
            )

        is_rel_query = "-" in cypher_query and "MATCH" in cypher_query.upper()
        has_limit = "LIMIT" in cypher_query.upper()
        has_edge_filter = "EDGE_TYPE" in cypher_query.upper()

        warning = None
        if is_rel_query and not has_limit and not has_edge_filter:
            cypher_query = cypher_query.rstrip().rstrip(";") + " LIMIT 50"
            warning = (
                "Warning: Query MATCHes relationships without LIMIT or edge_type filter. "
                "Automatically applied LIMIT 50 to prevent context window overflow."
            )

        results = store.execute_cypher(cypher_query)

        if warning:
            return json.dumps({"warning": warning, "results": results}, indent=2, ensure_ascii=False)
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Loi thuc thi Cypher: {str(e)}"


# Tool 2
def mcp_search_nodes(
    query: str,
    reference_file: str,
    match_type: str = "all",
    folder_filter: str = None,
    limit: int = 20,
) -> str:
    try:
        if not folder_filter:
            folder_filter = "Dir,Grid,Filter,Report,Lookup"
        res = xml_graph_query(
            "search",
            query,
            reference_file,
            match_type=match_type,
            folder_filter=folder_filter,
            limit=limit,
        )
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Loi search_nodes: {str(e)}"


# Tool 3
def mcp_get_related_nodes(
    target: str,
    reference_file: str,
    mode: str = "navigate",
    include_shared: bool = False,
) -> str:
    try:
        res = xml_graph_query(mode, target, reference_file)
        if not include_shared and isinstance(res, dict):
            for key in ("dependencies", "dependents", "results"):
                if key in res and isinstance(res[key], list):
                    res[key] = [
                        item
                        for item in res[key]
                        if not (isinstance(item, dict) and item.get("type") == "SHARED_INCLUDE")
                    ]
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Loi get_related_nodes: {str(e)}"


# Tool 4
def mcp_query_node_details(target: str, reference_file: str, view: str = "context") -> str:
    try:
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
        return f"Loi query_node_details: {str(e)}"


# Tool 5
def mcp_read_local_file(file_path: str, reference_file: str, read_option: int = 1) -> str:
    try:
        helper = ProjectPathHelper(reference_file)
        project_root = helper.get_project_root()

        p = Path(file_path)
        if not p.is_absolute():
            controllers_root = helper.get_controllers_path()
            p1 = controllers_root / file_path
            if p1.exists():
                p = p1
            else:
                p = project_root / file_path

        p = p.resolve()

        # Sandbox check
        if not str(p).lower().startswith(str(project_root.resolve()).lower()):
            return f"Loi: Duong dan nam ngoai thu muc du an: {file_path}"

        if not p.exists():
            return f"Loi: File khong ton tai: {file_path}"

        from xml_codegraph.parsers.xml_parser import read_file_content, read_flat_file_content

        if read_option == 2:
            try:
                content = read_flat_file_content(p)
            except Exception as e:
                # Fallback to original content or display error
                return f"Loi khi doc flat XML: {str(e)}\n\nNoidung goc:\n{read_file_content(p)}"
        else:
            content = read_file_content(p)
        return content
    except Exception as e:
        return f"Loi doc file: {str(e)}"
