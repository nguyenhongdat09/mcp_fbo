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
        if project_root in _watched_projects:
            return

        _watched_projects.add(project_root)
        controllers_dir = helper.get_controllers_path()
        graph_dir = helper.get_graph_dir()

        def watcher_thread():
            try:
                sys.stderr.write(f"[FboCodeGraph MCP] Starting file watcher thread for {controllers_dir}\n")
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

    # Tai su dung store neu xml_graph_query da mo (tranh build 2 lan)
    from xml_codegraph.query import engine as qe

    graph_key = str(graph_dir)
    if graph_key in qe._store_cache:
        _kuzu_stores[db_key] = qe._store_cache[graph_key]
        return _kuzu_stores[db_key]

    # Tự động đồng bộ gia tăng nếu đã quá 5 phút
    import time
    now = time.time()
    if now - qe._last_sync_times.get(graph_key, 0.0) > 300.0:
        # Gọi xml_graph_query với target rỗng / dummy để kích hoạt kiểm tra/đồng bộ tự động
        try:
            xml_graph_query("search", "", reference_file, limit=1)
        except Exception:
            pass

    if db_key not in _kuzu_stores or graph_key not in qe._store_cache:
        if not _kuzu_db_ready(db_path):
            _ensure_graph_built(reference_file)
        start_watcher_for_project(reference_file)
        _kuzu_stores[db_key] = KuzuIndexStore(db_path, read_only=True)
        qe._store_cache[graph_key] = _kuzu_stores[db_key]

    return qe._store_cache[graph_key]



# Tool 1
def mcp_query_radar(cypher_query: str, reference_file: str) -> str:
    try:
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

        store = get_kuzu_store(reference_file)
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
def mcp_read_local_file(file_path: str, reference_file: str) -> str:
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

        from xml_codegraph.parsers.xml_parser import read_file_content

        content = read_file_content(p)
        return content
    except Exception as e:
        return f"Loi doc file: {str(e)}"
