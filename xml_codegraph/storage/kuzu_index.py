import json
import os
import shutil
import csv
import time
import base64
from pathlib import Path
from typing import List, Optional
import kuzu
from xml_codegraph.core.schema import XmlGraph, GraphNode, GraphEdge


# Process-level singleton connection cache to avoid locking issues within the same process
_db_instances = {}


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
                print(f"[CodeGraph] Failed to copy remote Kuzu to local cache: {e}")

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        cache_key = str(self.db_path).replace("\\", "/").lower()
        if cache_key not in _db_instances:
            db = kuzu.Database(str(self.db_path), read_only=read_only)
            conn = kuzu.Connection(db)
            _db_instances[cache_key] = (db, conn)
            
        self.db, self.conn = _db_instances[cache_key]
        
        if not read_only:
            self._init_schema()

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
            # Strip brackets, quotes, and replace commas with spaces to avoid Kuzu list parser bugs
            s = str(item).replace('[', '').replace(']', '').replace("'", "").replace('"', '').replace(',', ' ')
            s = " ".join(s.split())
            if s:
                cleaned.append(s)
        return "[" + ",".join(cleaned) + "]"

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
            writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
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

                fields_json = [base64.b64encode(json.dumps(f, ensure_ascii=False).encode('utf-8')).decode('utf-8') for f in cleaned_fields]
                sql_blocks_json = [base64.b64encode(json.dumps(sql, ensure_ascii=False).encode('utf-8')).decode('utf-8') for sql in cleaned_sql]
                js_blocks_json = [base64.b64encode(json.dumps(js, ensure_ascii=False).encode('utf-8')).decode('utf-8') for js in cleaned_js]
                
                sql_text = " ".join([sql.get('content', '').replace('\n', ' ').replace('\r', ' ') for sql in node.sql_blocks])
                js_text = " ".join([js.get('content', '').replace('\n', ' ').replace('\r', ' ') for js in node.js_blocks])
                
                grid_refs = getattr(node, 'grid_refs', [])
                lookup_refs = getattr(node, 'lookup_refs', [])
                entity_names = [ent.get('name', '') for ent in node.entities if ent.get('name')]
                entities_json_str = base64.b64encode(json.dumps(node.entities, ensure_ascii=False).encode('utf-8')).decode('utf-8')
                param_entities = getattr(node, 'param_entities', []) or []
                
                writer.writerow([
                    node.node_id,
                    node.file_path or "",
                    node.relative_path or "",
                    node.folder_type or "",
                    node.folder_subtype or "",
                    node.xml_root_tag or "",
                    node.xml_namespace or "",
                    node.controller_type or "",
                    node.table or "",
                    node.code_field or "",
                    getattr(node, 'title_v', '') or '',
                    getattr(node, 'title_e', '') or '',
                    int(node.file_size or 0),
                    float(node.last_modified or 0.0),
                    "true" if getattr(node, 'is_encrypted', False) else "false",
                    getattr(node, 'source_extension', '.xml') or '.xml',
                    getattr(node, 'paired_f_path', '') or '',
                    "true" if getattr(node, 'needs_xml', False) else "false",
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
        # Relationship table: FROM, TO, edge_type, meta
        with open(edges_csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for edge in graph.edges:
                # Ensure both nodes exist in the graph to satisfy foreign key constraint in Kuzu
                if edge.source_id in graph.nodes and edge.target_id in graph.nodes:
                    meta_str = json.dumps(edge.meta, ensure_ascii=False)
                    writer.writerow([edge.source_id, edge.target_id, edge.edge_type, meta_str])

        # COPY FROM into Kuzu
        try:
            self.conn.execute(f'COPY XmlFile FROM "{str(nodes_csv_path.resolve()).replace(os.sep, "/")}" (header=false, parallel=false)')
            if edges_csv_path.stat().st_size > 0:
                self.conn.execute(f'COPY Rel FROM "{str(edges_csv_path.resolve()).replace(os.sep, "/")}" (header=false, parallel=false)')
        finally:
            # Clean up CSV files
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
                
        elapsed = time.time() - t0
        print(f"[CodeGraph] Synced {len(graph.nodes)} nodes, {len(graph.edges)} edges to Kuzu ({elapsed:.1f}s)")

    def update_single_node(self, node: GraphNode, edges: List[GraphEdge]) -> None:
        """
        Incremental update: DETACH DELETE the node, and CREATE it + its edges.
        """
        nid = node.node_id
        
        # 1. Delete node and all its relationships
        self.conn.execute("MATCH (n:XmlFile {node_id: $nid}) DETACH DELETE n", {"nid": nid})
        
        # 2. Re-create the node using parameters
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

        fields_json = [base64.b64encode(json.dumps(f, ensure_ascii=False).encode('utf-8')).decode('utf-8') for f in cleaned_fields]
        sql_blocks_json = [base64.b64encode(json.dumps(sql, ensure_ascii=False).encode('utf-8')).decode('utf-8') for sql in cleaned_sql]
        js_blocks_json = [base64.b64encode(json.dumps(js, ensure_ascii=False).encode('utf-8')).decode('utf-8') for js in cleaned_js]
        
        sql_text = " ".join([sql.get('content', '').replace('\n', ' ').replace('\r', ' ') for sql in node.sql_blocks])
        js_text = " ".join([js.get('content', '').replace('\n', ' ').replace('\r', ' ') for js in node.js_blocks])
        
        grid_refs = getattr(node, 'grid_refs', [])
        lookup_refs = getattr(node, 'lookup_refs', [])
        entity_names = [ent.get('name', '') for ent in node.entities if ent.get('name')]
        entities_json_str = base64.b64encode(json.dumps(node.entities, ensure_ascii=False).encode('utf-8')).decode('utf-8')
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
        
        # 3. Create edges if target nodes exist
        for edge in edges:
            # We must verify if the target node exists in Kuzu before creating the edge
            res = self.conn.execute("MATCH (n:XmlFile {node_id: $target_id}) RETURN count(*)", {"target_id": edge.target_id})
            if res.has_next() and res.get_next()[0] > 0:
                edge_query = """
                MATCH (src:XmlFile {node_id: $src_id}), (dst:XmlFile {node_id: $dst_id})
                CREATE (src)-[:Rel {edge_type: $edge_type, meta: $meta}]->(dst)
                """
                self.conn.execute(edge_query, {
                    "src_id": edge.source_id,
                    "dst_id": edge.target_id,
                    "edge_type": edge.edge_type,
                    "meta": json.dumps(edge.meta, ensure_ascii=False)
                })

    def load_graph(self) -> XmlGraph:
        """
        Load the entire graph from Kuzu database into memory.
        """
        t0 = time.time()
        graph = XmlGraph()
        
        # 1. Fetch all nodes
        nodes_res = self.conn.execute("""
            MATCH (n:XmlFile) 
            RETURN n.node_id, n.file_path, n.relative_path, n.folder_type, n.folder_subtype, 
                   n.xml_root_tag, n.xml_namespace, n.controller_type, n.db_table, n.code_field, 
                   n.title_v, n.title_e, n.file_size, n.last_modified, n.is_encrypted, 
                   n.source_extension, n.paired_f_path, n.needs_xml, n.fields_json, 
                   n.sql_blocks_json, n.js_blocks_json, n.grid_refs, n.lookup_refs,
                   n.entities_json, n.param_entities
        """)
        
        while nodes_res.has_next():
            row = nodes_res.get_next()
            
            # Map fields_json back to list of dicts (decoding base64)
            fields = []
            for f_str in row[18]:
                try: 
                    decoded = base64.b64decode(f_str.encode('utf-8')).decode('utf-8')
                    fields.append(json.loads(decoded))
                except Exception: pass
                
            sql_blocks = []
            for s_str in row[19]:
                try: 
                    decoded = base64.b64decode(s_str.encode('utf-8')).decode('utf-8')
                    sql_blocks.append(json.loads(decoded))
                except Exception: pass
                
            js_blocks = []
            for j_str in row[20]:
                try: 
                    decoded = base64.b64decode(j_str.encode('utf-8')).decode('utf-8')
                    js_blocks.append(json.loads(decoded))
                except Exception: pass
                
            entities = []
            try:
                if row[23]:
                    decoded = base64.b64decode(row[23].encode('utf-8')).decode('utf-8')
                    entities = json.loads(decoded)
            except Exception: pass
            
            param_entities = row[24] or []
            
            node = GraphNode(
                node_id         = row[0],
                file_path       = row[1] or "",
                relative_path   = row[2] or "",
                folder_type     = row[3] or "",
                folder_subtype  = row[4] or "",
                xml_root_tag    = row[5] or "",
                xml_namespace   = row[6] or "",
                controller_type = row[7] or "",
                table           = row[8],
                code_field      = row[9],
                title_v         = row[10] or "",
                title_e         = row[11] or "",
                file_size       = row[12] or 0,
                last_modified   = row[13] or 0.0,
                summary         = "",  # Not used in current logic
                is_encrypted    = bool(row[14]),
                entities        = entities,
                param_entities  = param_entities,
                fields          = fields,
                sql_blocks      = sql_blocks,
                js_blocks       = js_blocks,
                grid_refs       = row[21] or [],
                lookup_refs     = row[22] or [],
                source_extension = row[15] or ".xml",
                paired_f_path   = row[16] or None,
                needs_xml       = bool(row[17]),
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
        print(f"[CodeGraph] Loaded {len(graph.nodes)} nodes, {len(graph.edges)} edges from Kuzu ({elapsed:.2f}s)")
        return graph

    def search_fields(self, keywords: List[str] | str, limit: int = 10) -> list:
        """
        Search for fields matching keywords (CONTAINS search on name or headers).
        """
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
            print(f"[CodeGraph] search_fields error: {e}")
            raise e
            
        return results[:limit]

    def search_code(self, keywords: List[str] | str, limit: int = 10) -> list:
        """
        Search for code blocks (SQL/JS) matching keywords.
        """
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
                        decoded = base64.b64decode(s_str.encode('utf-8')).decode('utf-8')
                        sql = json.loads(decoded)
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
                        decoded = base64.b64decode(j_str.encode('utf-8')).decode('utf-8')
                        js = json.loads(decoded)
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
            print(f"[CodeGraph] search_code error: {e}")
            
        return results[:limit]

    def execute_cypher(self, query: str, params: Optional[dict] = None) -> list:
        """
        Execute arbitrary Cypher query. Returns a list of dictionaries.
        """
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

