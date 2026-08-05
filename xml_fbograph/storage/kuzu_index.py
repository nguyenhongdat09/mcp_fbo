import json
import os
import shutil
import csv
import time
import base64
import threading
import zlib
from pathlib import Path
from typing import List, Optional
import kuzu
from xml_fbograph.core.schema import XmlGraph, GraphNode, GraphEdge


def _compress_b64(data: dict | list) -> str:
    """Nén đối tượng JSON bằng zlib và mã hóa Base64."""
    if data is None:
        return ""
    json_str = json.dumps(data, ensure_ascii=False).encode('utf-8')
    compressed = zlib.compress(json_str, level=9)
    return base64.b64encode(compressed).decode('utf-8')

def _decompress_b64(b64_str: str) -> dict | list | None:
    """Giải mã Base64 và giải nén zlib thành đối tượng JSON. Fallback về uncompressed nếu là DB cũ."""
    if not b64_str:
        return None
    try:
        raw_bytes = base64.b64decode(b64_str.encode('utf-8'))
        try:
            # Thu giải nén (DB mới)
            decoded = zlib.decompress(raw_bytes).decode('utf-8')
        except Exception:
            # Fallback (DB cũ)
            decoded = raw_bytes.decode('utf-8')
        return json.loads(decoded)
    except Exception:
        return None

# Process-level singleton connection cache to avoid locking issues within the same process
_db_instances = {}
_db_locks = {}
_db_locks_lock = threading.Lock()


def get_db_lock(db_path_key: str) -> threading.RLock:
    """Lay hoac tao Lock rieng biet cho tung database file path."""
    with _db_locks_lock:
        if db_path_key not in _db_locks:
            _db_locks[db_path_key] = threading.RLock()
        return _db_locks[db_path_key]


def close_cached_database(db_path: Path) -> None:
    """Dong connection va database cached hien co de giai phong file lock."""
    db_path_key = str(Path(db_path).resolve()).replace("\\", "/").lower()
    lock = get_db_lock(db_path_key)
    with lock:
        if db_path_key in _db_instances:
            cached = _db_instances[db_path_key]
            try:
                cached["conn"].close()
            except Exception as e:
                print(f"[FBOGraph] Warning: failed to close connection for {db_path_key}: {e}")
            try:
                cached["db"].close()
            except Exception as e:
                print(f"[FBOGraph] Warning: failed to close database for {db_path_key}: {e}")
            _db_instances.pop(db_path_key, None)
            print(f"[FBOGraph] Closed cached database: {db_path_key}")
            
    invalidate_store_caches_for_db(Path(db_path))

def invalidate_store_caches_for_db(db_path: Path) -> None:
    """Xóa engine + mcp_tools cache để không trả KuzuIndexStore cũ."""
    graph_dir = db_path.parent
    graph_dir_key = str(graph_dir.resolve())

    try:
        from xml_fbograph.query import engine as qe
        qe._store_cache.pop(graph_dir_key, None)
        qe._graph_cache.pop(graph_dir_key, None)
    except Exception:
        pass

    try:
        import xml_fbograph.mcp_tools as mt
        mt._kuzu_stores.pop(str(db_path.resolve()), None)
    except Exception:
        pass

def _is_connection_closed_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "connection is closed" in msg or "connection closed" in msg or "database is closed" in msg or "database closed" in msg

def get_path_size(path: Path) -> int:
    """Tinh toan dung luong (bytes) cua file hoac thu muc."""
    total = 0
    try:
        path = Path(path).resolve()
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            for entry in os.scandir(path):
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += get_path_size(Path(entry.path))
    except Exception:
        pass
    return total

def safe_delete(path: Path, max_retries: int = 5, delay: float = 0.5) -> bool:
    """Xoa vat ly file hoac thu muc kem theo retry neu bi Windows lock."""
    path = Path(path).resolve()
    if not path.exists():
        return True
        
    for attempt in range(max_retries):
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            
            if not path.exists():
                return True
        except Exception:
            time.sleep(delay)
            
    if path.exists():
        return False
    return True

def safe_rename(src: Path, dst: Path, max_retries: int = 5, delay: float = 0.5) -> bool:
    """Doi ten thu muc kem theo retry."""
    src = Path(src).resolve()
    dst = Path(dst).resolve()
    
    if not src.exists():
        return False
        
    for attempt in range(max_retries):
        try:
            os.rename(src, dst)
            if dst.exists():
                return True
        except Exception:
            time.sleep(delay)
            
    if not dst.exists():
        return False
    return True


def reset_graph_dir(graph_dir: Path) -> bool:
    """Xoa vat ly thu muc .fbograph de tao DB moi hoan toan (Rebuild)."""
    graph_dir = Path(graph_dir).resolve()
    if not graph_dir.exists():
        return True

    # Dong ket noi kuzu cached
    kuzu_db_path = graph_dir / "kuzu"
    close_cached_database(kuzu_db_path)

    size_mb = get_path_size(graph_dir) / (1024 * 1024)
    print(f"[FBOGraph] Physical delete graph_dir: {graph_dir}")
    print(f"[FBOGraph] Size before deletion: {size_mb:.2f} MB")

    if safe_delete(graph_dir):
        print("[FBOGraph] Physical delete: SUCCESS")
        return True
    else:
        print("[FBOGraph] Physical delete: FAILED (Windows lock or permission denied)")
        return False


# Cot bat buoc tren XmlFile (dung de migrate DB cu thieu cot moi).
# Chi ADD khi thieu — khong doi type cot da co.
XMLFILE_COLUMN_TYPES = {
    "node_id": "STRING",
    "file_path": "STRING",
    "relative_path": "STRING",
    "folder_type": "STRING",
    "folder_subtype": "STRING",
    "xml_root_tag": "STRING",
    "xml_namespace": "STRING",
    "controller_type": "STRING",
    "db_table": "STRING",
    "code_field": "STRING",
    "title_v": "STRING",
    "title_e": "STRING",
    "file_size": "INT64",
    "last_modified": "DOUBLE",
    "is_encrypted": "BOOLEAN",
    "source_extension": "STRING",
    "paired_f_path": "STRING",
    "needs_xml": "BOOLEAN",
    "canonical_path": "STRING",
    "alias_of": "STRING",
    "fields_names": "STRING[]",
    "fields_headers": "STRING[]",
    "fields_json": "STRING[]",
    "sql_blocks_json": "STRING[]",
    "js_blocks_json": "STRING[]",
    "sql_text": "STRING",
    "js_text": "STRING",
    "grid_refs": "STRING[]",
    "lookup_refs": "STRING[]",
    "entity_names": "STRING[]",
    "entities_json": "STRING",
    "param_entities": "STRING[]",
}

# Cot load_graph can doc (thu tu co dinh de map an toan).
LOAD_GRAPH_COLUMNS = [
    "node_id", "file_path", "relative_path", "folder_type", "folder_subtype",
    "xml_root_tag", "xml_namespace", "controller_type", "db_table", "code_field",
    "title_v", "title_e", "file_size", "last_modified", "is_encrypted",
    "source_extension", "paired_f_path", "needs_xml", "fields_json",
    "sql_blocks_json", "js_blocks_json", "grid_refs", "lookup_refs",
    "entities_json", "param_entities", "canonical_path", "alias_of",
]

# Mặc định max_db_size của Kuzu là 8TB. Trên Windows, điều này thường gây ra lỗi
# VirtualAlloc fail (lỗi code 8) khi mở nhiều connection hoặc chạy song song.
# Ta giới hạn mặc định về 64 GiB (BẮT BUỘC là power of 2).
KUZU_MAX_DB_SIZE = 64 * 1024**3  # 64 GiB

def _get_kuzu_max_db_size() -> int:
    """Đọc max_db_size từ env hoặc config.yaml và đảm bảo trả về lũy thừa của 2."""
    val_gb = 64
    env_val = os.environ.get("FBOGRAPH_KUZU_MAX_DB_SIZE_GB", "").strip()
    if env_val.isdigit():
        val_gb = int(env_val)
    else:
        try:
            import yaml
            from xml_fbograph.utils.path_helper import _find_config_file
            config_file = _find_config_file()
            if config_file:
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                fbograph_cfg = cfg.get("fbograph", {})
                if "max_db_size_gb" in fbograph_cfg:
                    val_gb = int(fbograph_cfg["max_db_size_gb"])
        except Exception:
            pass

    import math
    if val_gb <= 0:
        val_gb = 64
    p2_gb = 2 ** math.ceil(math.log2(val_gb))
    return p2_gb * 1024**3

def _create_kuzu_database(db_path: str, read_only: bool = False) -> kuzu.Database:
    """Helper tạo Kuzu Database với dung lượng VirtualAlloc an toàn."""
    import inspect
    sig = inspect.signature(kuzu.Database.__init__)
    kwargs = {'read_only': read_only}
    if 'max_db_size' in sig.parameters:
        kwargs['max_db_size'] = _get_kuzu_max_db_size()
    if 'buffer_pool_size' in sig.parameters:
        # Buffer pool chiếm RAM thật sự, mặc định kuzu = 0.8 * total_RAM, ta giới hạn 1GB
        kwargs['buffer_pool_size'] = 1024 * 1024 * 1024
    return kuzu.Database(db_path, **kwargs)

class KuzuIndexStore:
    """
    Kuzu Graph DB storage layer for FBOGraph.
    Replaces legacy store with 100% Kuzu DB.
    """
    def __init__(self, db_path: Path, read_only: bool = False):
        self.db_path = Path(db_path).resolve()
        self.read_only = read_only
        
        path_str = str(self.db_path)
        if read_only and path_str.startswith(("//", "\\\\")):
            import hashlib
            import tempfile
            import shutil
            try:
                path_hash = hashlib.md5(path_str.encode('utf-8')).hexdigest()[:12]
                local_dir = Path(tempfile.gettempdir()) / "fbo_kuzu_cache" / path_hash
                local_dir.mkdir(parents=True, exist_ok=True)
                
                local_db_path = local_dir / self.db_path.name
                
                remote_files = [self.db_path]
                wal_remote = self.db_path.with_name(self.db_path.name + ".wal")
                if wal_remote.exists():
                    remote_files.append(wal_remote)
                    
                for r_file in remote_files:
                    l_file = local_dir / r_file.name
                    if not l_file.exists() or r_file.stat().st_mtime > l_file.stat().st_mtime or r_file.stat().st_size != l_file.stat().st_size:
                        shutil.copy2(r_file, l_file)
                
                if local_db_path.exists():
                    self.db_path = local_db_path
            except Exception as e:
                print(f"[FBOGraph] Failed to copy remote Kuzu to local cache: {e}")

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bind_live_connection()
        
        if not read_only:
            self._init_schema()

    def _db_path_key(self) -> str:
        return str(self.db_path).replace("\\", "/").lower()

    def _bind_live_connection(self, force_reopen: bool = False) -> None:
        db_path_key = self._db_path_key()
        self.lock = get_db_lock(db_path_key)
        
        with self.lock:
            if db_path_key in _db_instances:
                cached = _db_instances[db_path_key]
                if force_reopen or cached["read_only"] != self.read_only:
                    if cached["read_only"] != self.read_only:
                        print(f"[FBOGraph] Connection mode mismatch for {db_path_key} (cached: read_only={cached['read_only']}, requested: read_only={self.read_only}). Re-opening database...")
                    try:
                        cached["conn"].close()
                    except Exception:
                        pass
                    try:
                        cached["db"].close()
                    except Exception:
                        pass
                    _db_instances.pop(db_path_key, None)
            
            if db_path_key not in _db_instances:
                db = _create_kuzu_database(str(self.db_path), read_only=self.read_only)
                conn = kuzu.Connection(db)
                
                # Boc conn.execute voi lock de tranh deadlock/conflict trong da luong
                orig_execute = conn.execute
                lock = get_db_lock(db_path_key)
                def locked_execute(*args, **kwargs):
                    with lock:
                        return orig_execute(*args, **kwargs)
                conn.execute = locked_execute
                
                _db_instances[db_path_key] = {"db": db, "conn": conn, "read_only": self.read_only}
                
            self.db = _db_instances[db_path_key]["db"]
            self.conn = _db_instances[db_path_key]["conn"]

    def _init_schema(self) -> None:
        # Create XmlFile node table if not exists
        try:
            self.conn.execute("""
                CREATE NODE TABLE XmlFile (
                    node_id STRING,
                    file_path STRING,
                    relative_path STRING,
                    folder_type STRING,
                    folder_subtype STRING,
                    xml_root_tag STRING,
                    xml_namespace STRING,
                    controller_type STRING,
                    db_table STRING,
                    code_field STRING,
                    title_v STRING,
                    title_e STRING,
                    file_size INT64,
                    last_modified DOUBLE,
                    is_encrypted BOOLEAN,
                    source_extension STRING,
                    paired_f_path STRING,
                    needs_xml BOOLEAN,
                    canonical_path STRING,
                    alias_of STRING,
                    fields_names STRING[],
                    fields_headers STRING[],
                    fields_json STRING[],
                    sql_blocks_json STRING[],
                    js_blocks_json STRING[],
                    sql_text STRING,
                    js_text STRING,
                    grid_refs STRING[],
                    lookup_refs STRING[],
                    entity_names STRING[],
                    entities_json STRING,
                    param_entities STRING[],
                    PRIMARY KEY (node_id)
                )
            """)
        except Exception:
            pass  # Already exists

        # Create Rel relationship table if not exists
        try:
            self.conn.execute("""
                CREATE REL TABLE Rel (
                    FROM XmlFile TO XmlFile,
                    edge_type STRING,
                    meta STRING
                )
            """)
        except Exception:
            pass  # Already exists

        self._migrate_schema()

    def _get_table_columns(self, table_name: str) -> dict:
        """Tra ve {column_name: type} tu CALL table_info."""
        cols = {}
        try:
            res = self.conn.execute(f"CALL table_info('{table_name}') RETURN *")
            col_names = res.get_column_names()
            while res.has_next():
                row = dict(zip(col_names, res.get_next()))
                name = row.get("name") or row.get("property_name") or row.get("col_name")
                col_type = row.get("type") or row.get("property_type") or row.get("col_type") or ""
                if name:
                    cols[str(name)] = str(col_type)
        except Exception as e:
            print(f"[FBOGraph] Warning: table_info({table_name}) failed: {e}")
        return cols

    def _migrate_schema(self) -> None:
        """Them cot thieu tren XmlFile (DB build truoc khi them canonical_path/alias_of...)."""
        if self.read_only:
            return
        existing = self._get_table_columns("XmlFile")
        if not existing:
            return
        for col_name, col_type in XMLFILE_COLUMN_TYPES.items():
            if col_name in existing:
                continue
            default_clause = ""
            if col_type == "STRING":
                default_clause = " DEFAULT ''"
            elif col_type == "BOOLEAN":
                default_clause = " DEFAULT false"
            elif col_type == "INT64":
                default_clause = " DEFAULT 0"
            elif col_type == "DOUBLE":
                default_clause = " DEFAULT 0.0"
            try:
                ddl = f"ALTER TABLE XmlFile ADD {col_name} {col_type}{default_clause}"
                self.conn.execute(ddl)
                print(f"[FBOGraph] Migrated XmlFile: added column {col_name} {col_type}")
            except Exception as e:
                # Mot so version Kuzu khong chap nhan DEFAULT — thu khong DEFAULT
                try:
                    self.conn.execute(f"ALTER TABLE XmlFile ADD {col_name} {col_type}")
                    print(f"[FBOGraph] Migrated XmlFile: added column {col_name} {col_type} (no default)")
                except Exception as e2:
                    print(f"[FBOGraph] Warning: failed to add column {col_name}: {e2} (first: {e})")

    def _clear_tables(self) -> None:
        try:
            self.conn.execute("DROP TABLE Rel")
        except Exception:
            pass
        try:
            self.conn.execute("DROP TABLE XmlFile")
        except Exception:
            pass
        self._init_schema()

    def _format_kuzu_list(self, lst: List[str]) -> str:
        if not lst:
            return "[]"
        cleaned = []
        for item in lst:
            # Strip brackets, quotes, and replace commas/tabs with spaces to avoid Kuzu list parser bugs
            s = str(item).replace('[', '').replace(']', '').replace("'", "").replace('"', '').replace(',', ' ').replace('\t', ' ')
            s = " ".join(s.split())
            if s:
                cleaned.append(s)
        return "[" + ",".join(cleaned) + "]"

    def _sanitize_string(self, s) -> str:
        if not s:
            return ""
        return str(s).replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').replace('\x00', '')

    @staticmethod
    def _edge_type_str(edge_type) -> str:
        """Enum EdgeType: str(enum)='EdgeType.X' trên Py3.12 — phải dùng .value để khớp query agent."""
        if edge_type is None:
            return ""
        return str(getattr(edge_type, "value", edge_type))

    def sync_graph(self, graph: XmlGraph) -> None:
        """
        Bulk load nodes and edges using Kuzu COPY FROM with intermediate CSVs.
        """
        t0 = time.time()
        
        # Clear existing data by recreating tables
        self._clear_tables()
        
        # Create temp directory for CSVs
        temp_dir = self.db_path.parent / "temp_csv"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        nodes_csv_path = temp_dir / "nodes.csv"
        edges_csv_path = temp_dir / "edges.csv"
        
        # Write nodes CSV
        # Kuzu expects values matching the order of columns in CREATE NODE TABLE.
        with open(nodes_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=',', quoting=csv.QUOTE_ALL)
            for node in graph.nodes.values():
                # Prepare fields_names, fields_headers, fields_json
                fields_names = [f.get('name', '') for f in node.fields if f.get('name')]
                fields_headers = []
                for f in node.fields:
                    hv = f.get('header_v', '')
                    he = f.get('header_e', '')
                    if hv: fields_headers.append(hv)
                    if he: fields_headers.append(he)
                
                # Sanitize newlines in nested objects to prevent Kuzu CSV parsing issues
                cleaned_fields = []
                for field in node.fields:
                    f_copy = field.copy()
                    if 'snippet' in f_copy:
                        f_copy['snippet'] = str(f_copy['snippet']).replace('\n', ' ').replace('\r', ' ')
                    cleaned_fields.append(f_copy)
                    
                cleaned_sql = []
                for sql in node.sql_blocks:
                    sql_copy = sql.copy()
                    if 'content' in sql_copy:
                        sql_copy['content'] = str(sql_copy['content']).replace('\n', ' ').replace('\r', ' ')
                    cleaned_sql.append(sql_copy)
                    
                cleaned_js = []
                for js in node.js_blocks:
                    js_copy = js.copy()
                    if 'content' in js_copy:
                        js_copy['content'] = str(js_copy['content']).replace('\n', ' ').replace('\r', ' ')
                    cleaned_js.append(js_copy)

                fields_json = [_compress_b64(f) for f in cleaned_fields]
                sql_blocks_json = [_compress_b64(sql) for sql in cleaned_sql]
                js_blocks_json = [_compress_b64(js) for js in cleaned_js]
                
                sql_text = " ".join([sql.get('content', '').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ') for sql in node.sql_blocks])
                js_text = " ".join([js.get('content', '').replace('\n', ' ').replace('\r', ' ').replace('\t', ' ') for js in node.js_blocks])
                
                grid_refs = getattr(node, 'grid_refs', [])
                lookup_refs = getattr(node, 'lookup_refs', [])
                entity_names = [ent.get('name', '') for ent in node.entities if ent.get('name')]
                entities_json_str = _compress_b64(node.entities)
                param_entities = getattr(node, 'param_entities', []) or []
                
                writer.writerow([
                    self._sanitize_string(node.node_id),
                    self._sanitize_string(node.file_path).replace('\\', '/'),
                    self._sanitize_string(node.relative_path).replace('\\', '/'),
                    self._sanitize_string(node.folder_type),
                    self._sanitize_string(node.folder_subtype),
                    self._sanitize_string(node.xml_root_tag),
                    self._sanitize_string(node.xml_namespace),
                    self._sanitize_string(node.controller_type),
                    self._sanitize_string(node.table),
                    self._sanitize_string(node.code_field),
                    self._sanitize_string(getattr(node, 'title_v', '')),
                    self._sanitize_string(getattr(node, 'title_e', '')),
                    int(node.file_size or 0),
                    float(node.last_modified or 0.0),
                    "true" if getattr(node, 'is_encrypted', False) else "false",
                    self._sanitize_string(getattr(node, 'source_extension', '.xml')),
                    self._sanitize_string(getattr(node, 'paired_f_path', '')).replace('\\', '/'),
                    "true" if getattr(node, 'needs_xml', False) else "false",
                    self._sanitize_string(getattr(node, 'canonical_path', '')).replace('\\', '/'),
                    self._sanitize_string(getattr(node, 'alias_of', '')),
                    self._format_kuzu_list(fields_names),
                    self._format_kuzu_list(fields_headers),
                    self._format_kuzu_list(fields_json),
                    self._format_kuzu_list(sql_blocks_json),
                    self._format_kuzu_list(js_blocks_json),
                    sql_text,
                    js_text,
                    self._format_kuzu_list(grid_refs),
                    self._format_kuzu_list(lookup_refs),
                    self._format_kuzu_list(entity_names),
                    entities_json_str,
                    self._format_kuzu_list(param_entities)
                ])

        # Write edges CSV
        # Rel = XmlFile -> XmlFile: chỉ COPY cạnh khi CẢ hai đầu là node_id thật trong graph.
        # SQL_TABLE_USE / SQL_PROC_CALL / JS_FUNC_CALL thường target = tên bảng/proc/field
        # (vd. options, dmquyen) — KHÔNG phải XmlFile → ghi vào CSV sẽ làm COPY fail:
        #   "Unable to find primary key value options"
        with open(edges_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=',', quoting=csv.QUOTE_ALL)
            for edge in graph.edges:
                if edge.source_id not in graph.nodes or edge.target_id not in graph.nodes:
                    continue
                meta_json = ""
                if edge.meta:
                    meta_json = json.dumps(edge.meta, ensure_ascii=False)
                writer.writerow([
                    self._sanitize_string(edge.source_id),
                    self._sanitize_string(edge.target_id),
                    self._sanitize_string(self._edge_type_str(edge.edge_type)),
                    self._sanitize_string(meta_json)
                ])

        # COPY FROM into Kuzu
        try:
            # We must escape backslashes in Windows paths if any remain, but Kuzu handles forward slashes fine
            nodes_csv_str = str(nodes_csv_path).replace('\\', '/')
            self.conn.execute(f"COPY XmlFile FROM '{nodes_csv_str}' (header=false, parallel=false, delim=',')")
            
            if edges_csv_path.stat().st_size > 0:
                edges_csv_str = str(edges_csv_path).replace('\\', '/')
                self.conn.execute(f"COPY Rel FROM '{edges_csv_str}' (header=false, parallel=false, delim=',')")
        finally:
            # Clean up CSV files
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
                
        elapsed = time.time() - t0
        print(f"[FBOGraph] Synced {len(graph.nodes)} nodes, {len(graph.edges)} edges to Kuzu ({elapsed:.1f}s)")

    def create_edge_if_not_exists(self, src_id: str, dst_id: str, edge_type: str, meta: dict) -> None:
        """Kiem tra va tao canh neu chua ton tai trong database de tranh duplicate."""
        if src_id == dst_id:
            return
            
        meta_str = json.dumps(meta, ensure_ascii=False)
        edge_type = self._edge_type_str(edge_type)
        res = self.conn.execute("""
            MATCH (src:XmlFile {node_id: $src_id})-[r:Rel {edge_type: $edge_type}]->(dst:XmlFile {node_id: $dst_id})
            WHERE r.meta = $meta
            RETURN count(*)
        """, {"src_id": src_id, "dst_id": dst_id, "edge_type": edge_type, "meta": meta_str})
        
        if res.has_next() and res.get_next()[0] > 0:
            return
            
        self.conn.execute("""
            MATCH (src:XmlFile {node_id: $src_id}), (dst:XmlFile {node_id: $dst_id})
            CREATE (src)-[:Rel {edge_type: $edge_type, meta: $meta}]->(dst)
        """, {"src_id": src_id, "dst_id": dst_id, "edge_type": edge_type, "meta": meta_str})

    def update_single_node(self, node: GraphNode, edges: List[GraphEdge]) -> None:
        """
        Incremental update: Backup inbound edges, DETACH DELETE the node,
        CREATE it + its outgoing edges, and RESTORE inbound edges + companion files.
        """
        nid = node.node_id
        
        # 1. Backup inbound relationships before deleting
        inbound_edges = []
        try:
            res = self.conn.execute("""
                MATCH (src:XmlFile)-[r:Rel]->(dst:XmlFile {node_id: $nid})
                RETURN src.node_id, r.edge_type, r.meta
            """, {"nid": nid})
            while res.has_next():
                row = res.get_next()
                inbound_edges.append({
                    "source_id": row[0],
                    "edge_type": row[1],
                    "meta": json.loads(row[2] or "{}")
                })
        except Exception as e:
            print(f"[FBOGraph] Warning: failed to backup inbound edges for {nid}: {e}")

        # 2. Xoa cac canh outbound cu do chinh file vat ly nay sinh ra
        try:
            res_out = self.conn.execute("""
                MATCH (src:XmlFile {node_id: $src_id})-[r:Rel]->(dst:XmlFile)
                RETURN dst.node_id, r.edge_type, r.meta
            """, {"src_id": node.alias_of})
            
            to_delete = []
            while res_out.has_next():
                row = res_out.get_next()
                dst_id, edge_type, meta_str = row[0], row[1], row[2]
                try:
                    meta = json.loads(meta_str or "{}")
                    # Khop chinh xac file vat ly dong gop
                    if meta.get("parsed_from_source") == node.relative_path:
                        to_delete.append((dst_id, edge_type, meta_str))
                except Exception:
                    pass
            
            for dst_id, edge_type, meta_str in to_delete:
                self.conn.execute("""
                    MATCH (src:XmlFile {node_id: $src_id})-[r:Rel {edge_type: $edge_type}]->(dst:XmlFile {node_id: $dst_id})
                    WHERE r.meta = $meta
                    DELETE r
                """, {
                    "src_id": node.alias_of,
                    "dst_id": dst_id,
                    "edge_type": edge_type,
                    "meta": meta_str
                })
        except Exception as e:
            print(f"[FBOGraph] Warning: failed to clean old outbound edges for {node.relative_path}: {e}")

        # 3. Delete node and all its relationships (physical node)
        self.conn.execute("MATCH (n:XmlFile {node_id: $nid}) DETACH DELETE n", {"nid": nid})
        
        # 4. Re-create the node using parameters
        fields_names = [f.get('name', '') for f in node.fields if f.get('name')]
        fields_headers = []
        for f in node.fields:
            hv = f.get('header_v', '')
            he = f.get('header_e', '')
            if hv: fields_headers.append(hv)
            if he: fields_headers.append(he)
        
        # Sanitize and base64 encode nested JSON to prevent Kuzu Cypher parameter issues
        cleaned_fields = []
        for field in node.fields:
            f_copy = field.copy()
            if 'snippet' in f_copy:
                f_copy['snippet'] = str(f_copy['snippet']).replace('\n', ' ').replace('\r', ' ')
            cleaned_fields.append(f_copy)
            
        cleaned_sql = []
        for sql in node.sql_blocks:
            sql_copy = sql.copy()
            if 'content' in sql_copy:
                sql_copy['content'] = str(sql_copy['content']).replace('\n', ' ').replace('\r', ' ')
            cleaned_sql.append(sql_copy)
            
        cleaned_js = []
        for js in node.js_blocks:
            js_copy = js.copy()
            if 'content' in js_copy:
                js_copy['content'] = str(js_copy['content']).replace('\n', ' ').replace('\r', ' ')
            cleaned_js.append(js_copy)

        fields_json = [_compress_b64(f) for f in cleaned_fields]
        sql_blocks_json = [_compress_b64(sql) for sql in cleaned_sql]
        js_blocks_json = [_compress_b64(js) for js in cleaned_js]
        
        sql_text = " ".join([sql.get('content', '').replace('\n', ' ').replace('\r', ' ') for sql in node.sql_blocks])
        js_text = " ".join([js.get('content', '').replace('\n', ' ').replace('\r', ' ') for js in node.js_blocks])
        
        grid_refs = getattr(node, 'grid_refs', [])
        lookup_refs = getattr(node, 'lookup_refs', [])
        entity_names = [ent.get('name', '') for ent in node.entities if ent.get('name')]
        entities_json_str = _compress_b64(node.entities)
        param_entities = getattr(node, 'param_entities', []) or []

        query = """
        CREATE (n:XmlFile {
            node_id: $node_id,
            file_path: $file_path,
            relative_path: $relative_path,
            folder_type: $folder_type,
            folder_subtype: $folder_subtype,
            xml_root_tag: $xml_root_tag,
            xml_namespace: $xml_namespace,
            controller_type: $controller_type,
            db_table: $db_table,
            code_field: $code_field,
            title_v: $title_v,
            title_e: $title_e,
            file_size: $file_size,
            last_modified: $last_modified,
            is_encrypted: $is_encrypted,
            source_extension: $source_extension,
            paired_f_path: $paired_f_path,
            needs_xml: $needs_xml,
            canonical_path: $canonical_path,
            alias_of: $alias_of,
            fields_names: $fields_names,
            fields_headers: $fields_headers,
            fields_json: $fields_json,
            sql_blocks_json: $sql_blocks_json,
            js_blocks_json: $js_blocks_json,
            sql_text: $sql_text,
            js_text: $js_text,
            grid_refs: $grid_refs,
            lookup_refs: $lookup_refs,
            entity_names: $entity_names,
            entities_json: $entities_json,
            param_entities: $param_entities
        })
        """
        
        params = {
            "node_id": node.node_id,
            "file_path": node.file_path or "",
            "relative_path": node.relative_path or "",
            "folder_type": node.folder_type or "",
            "folder_subtype": node.folder_subtype or "",
            "xml_root_tag": node.xml_root_tag or "",
            "xml_namespace": node.xml_namespace or "",
            "controller_type": node.controller_type or "",
            "db_table": node.table or "",
            "code_field": node.code_field or "",
            "title_v": getattr(node, 'title_v', '') or '',
            "title_e": getattr(node, 'title_e', '') or '',
            "file_size": int(node.file_size or 0),
            "last_modified": float(node.last_modified or 0.0),
            "is_encrypted": bool(getattr(node, 'is_encrypted', False)),
            "source_extension": getattr(node, 'source_extension', '.xml') or '.xml',
            "paired_f_path": getattr(node, 'paired_f_path', '') or '',
            "needs_xml": bool(getattr(node, 'needs_xml', False)),
            "canonical_path": getattr(node, 'canonical_path', '') or '',
            "alias_of": getattr(node, 'alias_of', '') or '',
            "fields_names": fields_names,
            "fields_headers": fields_headers,
            "fields_json": fields_json,
            "sql_blocks_json": sql_blocks_json,
            "js_blocks_json": js_blocks_json,
            "sql_text": sql_text,
            "js_text": js_text,
            "grid_refs": grid_refs,
            "lookup_refs": lookup_refs,
            "entity_names": entity_names,
            "entities_json": entities_json_str,
            "param_entities": param_entities
        }
        
        self.conn.execute(query, params)
        
        # 5. Create outgoing edges if target nodes exist
        for edge in edges:
            res = self.conn.execute("MATCH (n:XmlFile {node_id: $target_id}) RETURN count(*)", {"target_id": edge.target_id})
            if res.has_next() and res.get_next()[0] > 0:
                self.create_edge_if_not_exists(edge.source_id, edge.target_id, edge.edge_type, edge.meta)

        # 6. Restore inbound edges
        for edge in inbound_edges:
            try:
                check_res = self.conn.execute("MATCH (n:XmlFile {node_id: $src_id}) RETURN count(*)", {"src_id": edge["source_id"]})
                if check_res.has_next() and check_res.get_next()[0] > 0:
                    self.create_edge_if_not_exists(edge["source_id"], nid, edge["edge_type"], edge["meta"])
            except Exception as e:
                print(f"[FBOGraph] Warning: failed to restore inbound edge from {edge['source_id']} to {nid}: {e}")

        # 7. Rebuild COMPANION_FILE relationships for this node
        if not node.alias_of or node.alias_of == nid:
            try:
                basename = Path(node.relative_path).name.lower()
                if "." in basename:
                    basename = basename.split(".")[0]
                
                from xml_fbograph.builder.graph_builder import normalize_controller_name
                norm_basename = normalize_controller_name(basename).lower()
                
                comp_res = self.conn.execute("""
                    MATCH (n:XmlFile)
                    WHERE (n.alias_of IS NULL OR n.alias_of = n.node_id) AND n.node_id <> $nid
                    RETURN n.node_id, n.relative_path
                """, {"nid": nid})
                
                companions = []
                while comp_res.has_next():
                    row = comp_res.get_next()
                    other_nid, other_rel_path = row[0], row[1]
                    other_basename = Path(other_rel_path).name.lower()
                    if "." in other_basename:
                        other_basename = other_basename.split(".")[0]
                    if normalize_controller_name(other_basename).lower() == norm_basename:
                        companions.append(other_nid)
                        
                for other_nid in companions:
                    meta = {"basename": basename}
                    # Edge nid -> other_nid
                    self.create_edge_if_not_exists(nid, other_nid, 'COMPANION_FILE', meta)
                    # Edge other_nid -> nid
                    self.create_edge_if_not_exists(other_nid, nid, 'COMPANION_FILE', meta)
            except Exception as e:
                print(f"[FBOGraph] Warning: failed to rebuild companion edges for {nid}: {e}")

    def load_graph(self) -> XmlGraph:
        """
        Load the entire graph from Kuzu database into memory.
        """
        self._bind_live_connection()
        try:
            return self._load_graph_impl()
        except Exception as exc:
            if not _is_connection_closed_error(exc):
                raise
            close_cached_database(self.db_path)
            self._bind_live_connection(force_reopen=True)
            return self._load_graph_impl()

    def _load_graph_impl(self) -> XmlGraph:
        t0 = time.time()
        graph = XmlGraph()

        # Chi SELECT cot thuc su ton tai (DB cu co the thieu canonical_path/alias_of).
        available = self._get_table_columns("XmlFile")
        select_cols = [c for c in LOAD_GRAPH_COLUMNS if not available or c in available]
        if not select_cols:
            select_cols = list(LOAD_GRAPH_COLUMNS)
        return_clause = ", ".join(f"n.{c}" for c in select_cols)

        # 1. Fetch all nodes
        nodes_res = self.conn.execute(f"""
            MATCH (n:XmlFile)
            RETURN {return_clause}
        """)

        while nodes_res.has_next():
            row = nodes_res.get_next()
            data = dict(zip(select_cols, row))

            # Map fields_json back to list of dicts (decoding base64)
            fields = []
            for f_str in (data.get("fields_json") or []):
                decoded_obj = _decompress_b64(f_str)
                if decoded_obj is not None:
                    fields.append(decoded_obj)

            sql_blocks = []
            for s_str in (data.get("sql_blocks_json") or []):
                decoded_obj = _decompress_b64(s_str)
                if decoded_obj is not None:
                    sql_blocks.append(decoded_obj)

            js_blocks = []
            for j_str in (data.get("js_blocks_json") or []):
                decoded_obj = _decompress_b64(j_str)
                if decoded_obj is not None:
                    js_blocks.append(decoded_obj)

            entities = []
            try:
                entities_json = data.get("entities_json")
                if entities_json:
                    decoded_obj = _decompress_b64(entities_json)
                    if decoded_obj is not None:
                        entities = decoded_obj
            except Exception:
                pass

            param_entities = data.get("param_entities") or []

            node = GraphNode(
                node_id         = data.get("node_id") or "",
                file_path       = data.get("file_path") or "",
                relative_path   = data.get("relative_path") or "",
                folder_type     = data.get("folder_type") or "",
                folder_subtype  = data.get("folder_subtype") or "",
                xml_root_tag    = data.get("xml_root_tag") or "",
                xml_namespace   = data.get("xml_namespace") or "",
                controller_type = data.get("controller_type") or "",
                table           = data.get("db_table"),
                code_field      = data.get("code_field"),
                title_v         = data.get("title_v") or "",
                title_e         = data.get("title_e") or "",
                file_size       = data.get("file_size") or 0,
                last_modified   = data.get("last_modified") or 0.0,
                summary         = "",  # Not used in current logic
                is_encrypted    = bool(data.get("is_encrypted")),
                entities        = entities,
                param_entities  = param_entities,
                fields          = fields,
                sql_blocks      = sql_blocks,
                js_blocks       = js_blocks,
                grid_refs       = data.get("grid_refs") or [],
                lookup_refs     = data.get("lookup_refs") or [],
                source_extension = data.get("source_extension") or ".xml",
                paired_f_path   = data.get("paired_f_path") or None,
                needs_xml       = bool(data.get("needs_xml")),
                canonical_path  = data.get("canonical_path") or "",
                alias_of        = data.get("alias_of") or "",
            )
            graph.add_node(node)

        # 2. Fetch all relationships
        edges_res = self.conn.execute("""
            MATCH (src:XmlFile)-[r:Rel]->(dst:XmlFile)
            RETURN src.node_id, dst.node_id, r.edge_type, r.meta
        """)

        while edges_res.has_next():
            row = edges_res.get_next()
            meta = {}
            try:
                meta = json.loads(row[3] or "{}")
            except Exception:
                pass
            graph.add_edge(GraphEdge(
                source_id = row[0],
                target_id = row[1],
                edge_type = row[2],
                meta      = meta
            ))

        elapsed = time.time() - t0
        print(f"[FBOGraph] Loaded {len(graph.nodes)} nodes, {len(graph.edges)} edges from Kuzu ({elapsed:.2f}s)")
        return graph

    def search_fields(self, keywords: List[str] | str, limit: int = 10) -> list:
        """
        Search for fields matching keywords (CONTAINS search on name or headers).
        """
        self._bind_live_connection()
        try:
            return self._search_fields_impl(keywords, limit)
        except Exception as exc:
            if not _is_connection_closed_error(exc):
                raise
            close_cached_database(self.db_path)
            self._bind_live_connection(force_reopen=True)
            return self._search_fields_impl(keywords, limit)

    def _search_fields_impl(self, keywords: List[str] | str, limit: int = 10) -> list:
        if isinstance(keywords, str):
            keywords = [keywords]
        keywords_l = [kw.lower() for kw in keywords]
        
        # Fetch list metadata and filter in Python to avoid Kuzu binder any/contains crashes
        query = """
            MATCH (n:XmlFile) 
            RETURN n.node_id, n.relative_path, n.fields_names, n.fields_headers, n.fields_json
        """
        results = []
        try:
            res = self.conn.execute(query)
            while res.has_next():
                row = res.get_next()
                node_id, relative_path, fields_names, fields_headers, fields_json = row[0], row[1], row[2], row[3], row[4]
                
                # Check names and headers for any matching keyword
                match = False
                matching_kw = None
                for kw_l in keywords_l:
                    for name in fields_names:
                        if kw_l in name.lower():
                            match = True
                            matching_kw = kw_l
                            break
                    if match:
                        break
                    for header in fields_headers:
                        if kw_l in header.lower():
                            match = True
                            matching_kw = kw_l
                            break
                    if match:
                        break
                            
                if match and matching_kw:
                    for f_str in fields_json:
                        try:
                            decoded = base64.b64decode(f_str.encode('utf-8')).decode('utf-8')
                            field = json.loads(decoded)
                            fname = field.get('name', '')
                            hv = field.get('header_v', '')
                            he = field.get('header_e', '')
                            if matching_kw in fname.lower() or matching_kw in hv.lower() or matching_kw in he.lower():
                                results.append({
                                    "node_id": node_id,
                                    "relative_path": relative_path,
                                    "field_name": fname,
                                    "header_v": hv,
                                    "header_e": he,
                                    "snippet": field.get('snippet', '')
                                })
                        except Exception:
                            pass
        except Exception as e:
            print(f"[FBOGraph] search_fields error: {e}")
            raise e
            
        return results[:limit]

    def search_code(self, keywords: List[str] | str, limit: int = 10) -> list:
        """
        Search for code blocks (SQL/JS) matching keywords.
        """
        self._bind_live_connection()
        try:
            return self._search_code_impl(keywords, limit)
        except Exception as exc:
            if not _is_connection_closed_error(exc):
                raise
            close_cached_database(self.db_path)
            self._bind_live_connection(force_reopen=True)
            return self._search_code_impl(keywords, limit)

    def _search_code_impl(self, keywords: List[str] | str, limit: int = 10) -> list:
        if isinstance(keywords, str):
            keywords = [keywords]
            
        clauses = []
        params = {"limit": limit}
        for i, kw in enumerate(keywords):
            clauses.append(f"n.sql_text CONTAINS $kw{i} OR n.js_text CONTAINS $kw{i}")
            params[f"kw{i}"] = kw
            
        where_clause = " OR ".join(clauses)
        query = f"""
            MATCH (n:XmlFile) 
            WHERE {where_clause}
            RETURN n.node_id, n.relative_path, n.sql_blocks_json, n.js_blocks_json
            LIMIT $limit
        """
        results = []
        try:
            res = self.conn.execute(query, params)
            while res.has_next():
                row = res.get_next()
                node_id, relative_path, sql_json, js_json = row[0], row[1], row[2], row[3]
                
                # Check SQL blocks
                for s_str in sql_json:
                    try:
                        sql = _decompress_b64(s_str)
                        if not sql:
                            continue
                        content = sql.get('content', '')
                        content_lower = content.lower()
                        # Match any keyword
                        for kw in keywords:
                            if kw.lower() in content_lower:
                                results.append({
                                    "node_id": node_id,
                                    "relative_path": relative_path,
                                    "tag": "sql",
                                    "match_snippet": content[:120] + "..." if len(content) > 120 else content
                                })
                                break
                    except Exception:
                        pass
                
                # Check JS blocks
                for j_str in js_json:
                    try:
                        js = _decompress_b64(j_str)
                        if not js:
                            continue
                        content = js.get('content', '')
                        content_lower = content.lower()
                        # Match any keyword
                        for kw in keywords:
                            if kw.lower() in content_lower:
                                results.append({
                                    "node_id": node_id,
                                    "relative_path": relative_path,
                                    "tag": "javascript",
                                    "match_snippet": content[:120] + "..." if len(content) > 120 else content
                                })
                                break
                    except Exception:
                        pass
        except Exception as e:
            print(f"[FBOGraph] search_code error: {e}")
            
        return results[:limit]

    def execute_cypher(self, query: str, params: Optional[dict] = None) -> list:
        """
        Execute arbitrary Cypher query. Returns a list of dictionaries.
        """
        self._bind_live_connection()
        try:
            return self._execute_cypher_impl(query, params)
        except Exception as exc:
            if not _is_connection_closed_error(exc):
                raise
            close_cached_database(self.db_path)
            self._bind_live_connection(force_reopen=True)
            return self._execute_cypher_impl(query, params)

    def _execute_cypher_impl(self, query: str, params: Optional[dict] = None) -> list:
        # Normalize forward slashes to double backslashes for folder paths in query literals
        import re
        def _norm_path(match):
            quote = match.group(1)
            prefix = match.group(2)
            rest = match.group(3)
            rest_clean = rest.replace('/', '\\\\')
            return f"{quote}{prefix}\\\\{rest_clean}{quote}"
            
        normalized_query = re.sub(
            r"(['\"])(Dir|Grid|Filter|Report|Templates|Lookup|Include)/([^\'\"]+?)(\1)",
            _norm_path,
            query,
            flags=re.IGNORECASE
        )
        
        # Rewrite is_f_only to needs_xml for Kuzu schema compatibility
        normalized_query = normalized_query.replace("is_f_only", "needs_xml")
        
        p = params or {}
        res = self.conn.execute(normalized_query, p)
        cols = res.get_column_names()
        results = []
        while res.has_next():
            row = res.get_next()
            row_dict = dict(zip(cols, row))
            
            # Map needs_xml back to is_f_only in output keys to support agent expectations
            mapped_dict = {}
            for k, v in row_dict.items():
                mapped_dict[k] = v
                if "needs_xml" in k:
                    mapped_key = k.replace("needs_xml", "is_f_only")
                    mapped_dict[mapped_key] = v
            results.append(mapped_dict)
        return results


def reevaluate_canonical_group_on_delete(conn, controllers_root: Path, folder_type: str, normalized_name: str, deleted_node_id: str, backup_inbound: list = None, backup_outbound: list = None) -> None:
    """Tu dong dinh vi canonical node moi dai dien cho nhom, cap nhat alias_of cho cac node alias con song, va dinh tuyen lai tat ca cac canh tu node bi xoa sang node moi."""
    try:
        folder_lower = folder_type.lower()
        norm_lower = normalized_name.lower()
        
        # 1. Quet tat ca cac node con lai trong Kuzu DB de tim cac node cung group
        res = conn.execute("MATCH (n:XmlFile) RETURN n.node_id, n.relative_path, n.is_encrypted, n.folder_type, n.folder_subtype")
        group_nodes = []
        
        from xml_fbograph.builder.graph_builder import normalize_controller_name
        
        standard_folders = {"dir", "grid", "filter", "report", "lookup", "form"}
        
        while res.has_next():
            row = res.get_next()
            nid, rel_path, is_enc, f_type, f_subtype = row[0], row[1], row[2], row[3], row[4]
            if nid == deleted_node_id:
                continue
                
            stem = Path(rel_path).stem
            cur_norm = normalize_controller_name(stem).lower()
            if cur_norm != norm_lower:
                continue
                
            rel_parts = Path(rel_path.replace("\\", "/")).parts
            logical_f_type = f_type
            if f_type.lower() == "templates" or f_subtype.lower() == "upload":
                logical_f_type = "Grid"
            elif f_subtype.lower() == "fields" or "config/fields" in rel_path.replace("\\", "/").lower():
                if len(rel_parts) > 1 and rel_parts[0].lower() in standard_folders:
                    logical_f_type = rel_parts[0]
                else:
                    logical_f_type = "Grid"
            else:
                if f_type.lower() in standard_folders:
                    logical_f_type = f_type
                else:
                    logical_f_type = "Grid"
                    
            if logical_f_type.lower() == folder_lower:
                group_nodes.append({
                    "node_id": nid,
                    "relative_path": rel_path,
                    "is_encrypted": is_enc,
                    "logical_f_type": logical_f_type
                })
                
        if not group_nodes:
            return
            
        # 2. Chon canonical node moi trong so cac node con song
        canonical_rel_path = f"{folder_type.capitalize()}\\{normalized_name}.xml".lower()
        selected = None
        
        # Tieu chi 1: File chinh xac trung khop canonical_rel_path va khong encrypted
        for item in group_nodes:
            if item["relative_path"].lower() == canonical_rel_path and not item["is_encrypted"]:
                selected = item
                break
        # Tieu chi 2: File chinh xac trung khop canonical_rel_path (ke ca encrypted)
        if not selected:
            for item in group_nodes:
                if item["relative_path"].lower() == canonical_rel_path:
                    selected = item
                    break
        # Tieu chi 3: File bien the khong bi encrypted
        if not selected:
            for item in group_nodes:
                if not item["is_encrypted"]:
                    selected = item
                    break
        # Tieu chi 4: Chon node dau tien
        if not selected:
            selected = group_nodes[0]
            
        new_canonical_id = selected["node_id"]
        new_canonical_path = selected["relative_path"]
        
        # 3. Cap nhat Kuzu DB: dat alias_of va canonical_path moi cho tat ca cac node trong nhom
        for item in group_nodes:
            nid = item["node_id"]
            conn.execute("""
                MATCH (n:XmlFile {node_id: $nid})
                SET n.alias_of = $alias_of, n.canonical_path = $canonical_path
            """, {"nid": nid, "alias_of": new_canonical_id, "canonical_path": new_canonical_path})
            
        # 4. Dinh tuyen lai cac canh tu backup list sang new_canonical_id
        def create_edge_helper(src_id, dst_id, edge_type, meta):
            if src_id == dst_id: return
            meta_str = json.dumps(meta, ensure_ascii=False)
            res = conn.execute("""
                MATCH (src:XmlFile {node_id: $src_id})-[r:Rel {edge_type: $edge_type}]->(dst:XmlFile {node_id: $dst_id})
                WHERE r.meta = $meta
                RETURN count(*)
            """, {"src_id": src_id, "dst_id": dst_id, "edge_type": edge_type, "meta": meta_str})
            if res.has_next() and res.get_next()[0] > 0:
                return
            conn.execute("""
                MATCH (src:XmlFile {node_id: $src_id}), (dst:XmlFile {node_id: $dst_id})
                CREATE (src)-[:Rel {edge_type: $edge_type, meta: $meta}]->(dst)
            """, {"src_id": src_id, "dst_id": dst_id, "edge_type": edge_type, "meta": meta_str})
            
        if backup_outbound:
            for edge in backup_outbound:
                create_edge_helper(new_canonical_id, edge["dst_id"], edge["edge_type"], edge["meta"])
        if backup_inbound:
            for edge in backup_inbound:
                create_edge_helper(edge["src_id"], new_canonical_id, edge["edge_type"], edge["meta"])
            
        print(f"[FBOGraph] Successfully reevaluated canonical group for {folder_type}/{normalized_name}. New canonical node: {new_canonical_path}")
    except Exception as e:
        print(f"[FBOGraph] Warning: failed to reevaluate canonical group for deleted node {deleted_node_id}: {e}")


