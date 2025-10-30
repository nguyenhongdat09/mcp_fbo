"""Database schema definitions."""

# SQL schema for fields database
SCHEMA_SQL = """
-- Fields registry table
CREATE TABLE IF NOT EXISTS fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'String',
    header_vi TEXT,
    header_en TEXT,
    width INTEGER,
    align TEXT,
    allow_nulls INTEGER DEFAULT 1,
    read_only INTEGER DEFAULT 0,
    hidden INTEGER DEFAULT 0,
    external INTEGER DEFAULT 0,
    is_lookup INTEGER DEFAULT 0,
    lookup_controller TEXT,
    lookup_reference TEXT,
    companion_field TEXT,
    file_path TEXT,
    controller TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_fields_name ON fields(name);
CREATE INDEX IF NOT EXISTS idx_fields_controller ON fields(controller);
CREATE INDEX IF NOT EXISTS idx_fields_lookup ON fields(is_lookup);

-- Controllers registry
CREATE TABLE IF NOT EXISTS controllers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    table_name TEXT,
    has_partition INTEGER DEFAULT 0,
    partition_field TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_controllers_name ON controllers(name);

-- Patterns registry (for common code patterns)
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    language TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patterns_category ON patterns(category);
CREATE INDEX IF NOT EXISTS idx_patterns_language ON patterns(language);

-- Validation rules
CREATE TABLE IF NOT EXISTS validation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL,
    pattern TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    auto_fix INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scan history
CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_path TEXT NOT NULL,
    files_scanned INTEGER DEFAULT 0,
    errors_found INTEGER DEFAULT 0,
    warnings_found INTEGER DEFAULT 0,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_initial_patterns() -> list[tuple[str, str, str, str, str, str]]:
    """
    Get initial code patterns to insert.

    Returns:
        List of (category, name, language, code, description, tags) tuples
    """
    return [
        (
            "field",
            "basic_text_field",
            "xml",
            '<field name="{name}">\n  <header v="{header_vi}" e="{header_en}"/>\n</field>',
            "Basic text field definition",
            "field,text,basic",
        ),
        (
            "field",
            "lookup_field",
            "xml",
            '<field name="{name}">\n  <items style="AutoComplete"\n        controller="{controller}"\n        reference="{reference}"/>\n</field>',
            "Lookup field with autocomplete",
            "field,lookup,autocomplete",
        ),
        (
            "sql",
            "insert_partition",
            "sql",
            "insert into @@prime$partition$current\nselect * from @{table}",
            "Insert with partition placeholder",
            "sql,insert,partition",
        ),
        (
            "sql",
            "update_partition",
            "sql",
            "update @@prime$partition$current\nset {fields}\nwhere stt_rec = @stt_rec",
            "Update with partition placeholder",
            "sql,update,partition",
        ),
        (
            "javascript",
            "form_init",
            "javascript",
            "function init$Form$(f) {\n  // Initialization code\n}",
            "Form initialization function",
            "javascript,form,init",
        ),
        (
            "javascript",
            "grid_load",
            "javascript",
            "function load$Grid$(g) {\n  var f = g.get_element().parentForm;\n  // Grid initialization\n}",
            "Grid detail load function",
            "javascript,grid,load,detail",
        ),
        (
            "javascript",
            "response_handler",
            "javascript",
            "function on$Form$ResponseComplete(sender, e) {\n  var f = e.object;\n  var context = e.type.Context;\n  var result = e.type.Result;\n  \n  switch(context) {\n    case 'ActionName':\n      var value = result[0].Value;\n      break;\n  }\n}",
            "Response complete handler",
            "javascript,response,handler",
        ),
    ]
