"""Catalog 14 Cypher template chuẩn của query_radar (Kuzu FBOGraph).

Nguồn: skill fbo-mcp-query-radar — reference-radar-templates.md /
reference-radar-rules.md (C:\\Users\\Windows 10\\.cursor\\skills_mcp_backup\\
fbo-mcp-query-radar). Khi rules file đổi phải sync tay vào đây.

- ``when``     : mô tả ngắn cho agent đọc trong payload.radar_templates.
- ``jev_desc`` : bản telegraphic gửi Jev làm criteria/state — convention
  giống _JEV_TASK_DESCS trong cards.py (dense, kèm discriminator not:).
- ``cypher``   : skeleton nguyên văn, giữ placeholder <PARAM>.
- ``params``   : tên placeholder agent phải thay (mỗi cái xuất hiện dạng
  <NAME> trong cypher — test integrity bắt buộc).

Phân biệt cặp hay nhầm: T8 = hàng xóm 1 hop; T9 = chuỗi outbound 2 bước;
T11 = cụm/xung quanh depth-2 (T8 KHÔNG đủ khi file nối gián tiếp).
"""

RADAR_TEMPLATES = {
    "template_1": {
        "when": "find controller by file name/path",
        "jev_desc": "tim controller theo ten file/path — ENDS WITH "
                    "'<FILE_NAME>.xml'",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE a.relative_path ENDS WITH '<FILE_NAME>.xml'\n"
                   "RETURN a.relative_path, a.folder_type, a.db_table, "
                   "a.title_v, a.code_field\n"
                   "LIMIT 20"),
        "params": ["FILE_NAME"],
    },
    "template_2": {
        "when": "list controllers by folder_type (Dir/Grid/Filter/Report/"
                "Templates)",
        "jev_desc": "liet ke controller theo folder_type Dir|Grid|Filter|"
                    "Report|Templates",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE a.folder_type = '<FOLDER_TYPE>'\n"
                   "RETURN a.relative_path, a.db_table, a.title_v\n"
                   "LIMIT 50"),
        "params": ["FOLDER_TYPE"],
    },
    "template_3": {
        "when": "controllers containing keyword(s) in js_text (JS "
                "handler/code)",
        "jev_desc": "tim controller chua keyword trong js_text (JS "
                    "handler/code) — tach keyword ngan + AND",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE a.js_text CONTAINS '<KEYWORD_1>'\n"
                   "  AND a.js_text CONTAINS '<KEYWORD_2>'\n"
                   "RETURN a.relative_path, a.folder_type, a.title_v\n"
                   "LIMIT 20"),
        "params": ["KEYWORD_1", "KEYWORD_2"],
    },
    "template_4": {
        "when": "controllers containing keyword(s) in sql_text (proc/SQL "
                "embedded)",
        "jev_desc": "tim controller chua keyword trong sql_text (proc/SQL "
                    "embedded) — tach keyword ngan + AND",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE a.sql_text CONTAINS '<KEYWORD_1>'\n"
                   "  AND a.sql_text CONTAINS '<KEYWORD_2>'\n"
                   "RETURN a.relative_path, a.db_table, a.title_v\n"
                   "LIMIT 20"),
        "params": ["KEYWORD_1", "KEYWORD_2"],
    },
    "template_5": {
        "when": "controllers declaring a field in fields_names",
        "jev_desc": "tim controller khai bao field trong fields_names — "
                    "list_contains(fields_names,'<FIELD_NAME>')",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE list_contains(a.fields_names, '<FIELD_NAME>')\n"
                   "RETURN a.relative_path, a.folder_type, a.title_v, "
                   "a.db_table\n"
                   "LIMIT 20"),
        "params": ["FIELD_NAME"],
    },
    "template_6": {
        "when": "controllers working with a DB table (db_table)",
        "jev_desc": "tim controller thao tac voi bang DB — db_table "
                    "CONTAINS '<TABLE_NAME>'",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE a.db_table CONTAINS '<TABLE_NAME>'\n"
                   "RETURN a.relative_path, a.db_table, a.title_v, "
                   "a.code_field\n"
                   "LIMIT 20"),
        "params": ["TABLE_NAME"],
    },
    "template_7": {
        "when": "directed relation from one file with edge_type filter "
                "(master-detail, field-lookup, data-source)",
        "jev_desc": "quan he 1 chieu tu file nguon + filter edge_type "
                    "(GRID_MASTER_DETAIL|LOOKUP_REFERENCE|RETRIEVE_DATA_"
                    "SOURCE...) — not: neighbor moi huong (template_8)",
        "cypher": ("MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)\n"
                   "WHERE a.relative_path ENDS WITH '<SOURCE_FILE>.xml'\n"
                   "  AND r.edge_type = '<EDGE_TYPE_ENUM>'\n"
                   "RETURN a.relative_path AS source, r.edge_type AS "
                   "relationship, b.relative_path AS target\n"
                   "LIMIT 50"),
        "params": ["SOURCE_FILE", "EDGE_TYPE_ENUM"],
    },
    "template_8": {
        "when": "neighbors of a file — any direction, 1 hop only",
        "jev_desc": "hang xom 1 hop moi huong cua 1 file — not: chuoi 2 "
                    "buoc outbound (template_9), cum/xung quanh depth-2 "
                    "(template_11)",
        "cypher": ("MATCH (a:XmlFile)-[r:Rel]-(b:XmlFile)\n"
                   "WHERE a.relative_path ENDS WITH '<FILE_NAME>.xml'\n"
                   "RETURN a.relative_path AS node_a, r.edge_type AS edge, "
                   "b.relative_path AS node_b\n"
                   "LIMIT 50"),
        "params": ["FILE_NAME"],
    },
    "template_9": {
        "when": "directed 2-hop chain outbound from a source file "
                "(a)->(b)->(c)",
        "jev_desc": "chuoi quan he co huong 2 buoc outbound tu file nguon "
                    "(a)->(b)->(c) — not: 1 hop (template_8), cum depth-2 "
                    "moi huong (template_11)",
        "cypher": ("MATCH (a:XmlFile)-[r1:Rel]->(b:XmlFile)-[r2:Rel]->"
                   "(c:XmlFile)\n"
                   "WHERE a.relative_path ENDS WITH '<START_FILE>.xml'\n"
                   "RETURN a.relative_path AS start_node, r1.edge_type AS "
                   "edge1, b.relative_path AS mid_node, r2.edge_type AS "
                   "edge2, c.relative_path AS end_node\n"
                   "LIMIT 30"),
        "params": ["START_FILE"],
    },
    "template_10": {
        "when": "count controllers grouped by folder_type (aggregation)",
        "jev_desc": "dem so controller theo folder_type (thong ke/"
                    "aggregation)",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "RETURN a.folder_type, COUNT(a) AS total_files\n"
                   "ORDER BY total_files DESC"),
        "params": [],
    },
    "template_11": {
        "when": "neighborhood depth-2 — 'xung quanh', 'liên quan', 'cụm', "
                "master + retrieve/lookup siblings",
        "jev_desc": "file xung quanh/lien quan/cum depth-2: master + anh "
                    "em retrieve/lookup ke ca khi khong noi thang — "
                    "signals:xung quanh|lien quan|cum|anh em; not: chi 1 "
                    "hop (template_8), chuoi outbound (template_9)",
        "cypher": ("MATCH (a:XmlFile)-[r1:Rel]-(b:XmlFile)\n"
                   "WHERE a.relative_path ENDS WITH '<FILE_NAME>.xml'\n"
                   "OPTIONAL MATCH (b)-[r2:Rel]-(c:XmlFile)\n"
                   "WHERE c.relative_path IS NOT NULL\n"
                   "  AND c.relative_path <> a.relative_path\n"
                   "RETURN DISTINCT\n"
                   "  b.relative_path AS hop1,\n"
                   "  r1.edge_type AS edge1,\n"
                   "  c.relative_path AS hop2,\n"
                   "  r2.edge_type AS edge2\n"
                   "LIMIT 50"),
        "params": ["FILE_NAME"],
    },
    "template_12": {
        "when": "global search across path/title/db_table/code_field",
        "jev_desc": "search chung toan cuc: relative_path|title_v|"
                    "db_table|code_field CONTAINS keyword — CAM ILIKE",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE a.relative_path CONTAINS '<KEYWORD>'\n"
                   "   OR a.title_v CONTAINS '<KEYWORD>'\n"
                   "   OR a.db_table CONTAINS '<KEYWORD>'\n"
                   "   OR a.code_field CONTAINS '<KEYWORD>'\n"
                   "RETURN a.relative_path, a.folder_type, a.title_v, "
                   "a.db_table\n"
                   "LIMIT 30"),
        "params": ["KEYWORD"],
    },
    "template_13": {
        "when": "dependency analysis — inbound (who calls this file) or "
                "outbound (what this file calls)",
        "jev_desc": "phan tich phu thuoc: inbound ai goi file nay / "
                    "outbound file nay goi ai — signals:dependencies|"
                    "dependents|ai goi|goi ai",
        "cypher": ("MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)\n"
                   "WHERE b.relative_path ENDS WITH '<TARGET_FILE>.xml'\n"
                   "RETURN a.relative_path AS related_file, r.edge_type "
                   "AS relation_type, 'INBOUND' AS direction\n"
                   "LIMIT 50"),
        "params": ["TARGET_FILE"],
    },
    "template_14": {
        "when": "node metadata arrays — fields_names, grid_refs, "
                "lookup_refs, param_entities of one file",
        "jev_desc": "lay metadata mang cua 1 file: fields_names|"
                    "grid_refs|lookup_refs|param_entities",
        "cypher": ("MATCH (a:XmlFile)\n"
                   "WHERE a.relative_path ENDS WITH '<TARGET_FILE>.xml'\n"
                   "RETURN a.relative_path, a.fields_names, a.grid_refs, "
                   "a.lookup_refs, a.param_entities\n"
                   "LIMIT 1"),
        "params": ["TARGET_FILE"],
    },
}

# Catalog telegraphic gửi Jev (criteria keys + state.radar_template_catalog)
RADAR_TEMPLATE_CATALOG = {k: v["jev_desc"] for k, v in RADAR_TEMPLATES.items()}

# Quy tắc cứng nén từ reference-radar-rules.md — hiển thị trong
# payload.radar_templates._rules.
RADAR_RULES = [
    "CẤM ILIKE/LIKE — chỉ CONTAINS (không %)",
    "path: ENDS WITH / CONTAINS — không dùng = 'Grid\\\\X.xml'",
    "CẤM RETURN node đầy đủ (js_text/sql_text dài tràn token) — chỉ cột "
    "cần",
    "Luôn có LIMIT (20/30/50)",
    "Chuỗi có nháy lồng/JS dài → tách keyword ngắn + AND",
    "Edge chỉ có :Rel + r.edge_type — BẮT BUỘC filter edge_type "
    "(SHARED_INCLUDE ~99% edges)",
    "Mảng fields_names/...: list_contains() hoặc ANY x IN ...",
]
