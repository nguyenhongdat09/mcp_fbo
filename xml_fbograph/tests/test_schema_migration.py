"""
Reproduce: get_related_nodes fails on old Kuzu DB missing canonical_path/alias_of.

Binder exception: Cannot find property canonical_path for n.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

import kuzu

from xml_fbograph.storage.kuzu_index import KuzuIndexStore, close_cached_database, _create_kuzu_database


OLD_XMLFILE_DDL = """
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
"""


def _create_old_schema_db(db_path: Path) -> None:
    """Tao DB mo phong ban build truoc khi them canonical_path/alias_of."""
    db = _create_kuzu_database(str(db_path))
    conn = kuzu.Connection(db)
    conn.execute(OLD_XMLFILE_DDL)
    conn.execute("""
        CREATE REL TABLE Rel (
            FROM XmlFile TO XmlFile,
            edge_type STRING,
            meta STRING
        )
    """)
    conn.execute("""
        CREATE (n:XmlFile {
            node_id: 'n1',
            file_path: 'C:/x/Dir/CPTran.xml',
            relative_path: 'Dir\\\\CPTran.xml',
            folder_type: 'Dir',
            folder_subtype: '',
            xml_root_tag: 'dir',
            xml_namespace: '',
            controller_type: 'dir',
            db_table: 'c91$',
            code_field: 'stt_rec',
            title_v: 'GBN',
            title_e: '',
            file_size: 100,
            last_modified: 1.0,
            is_encrypted: false,
            source_extension: '.xml',
            paired_f_path: '',
            needs_xml: false,
            fields_names: [],
            fields_headers: [],
            fields_json: [],
            sql_blocks_json: [],
            js_blocks_json: [],
            sql_text: '',
            js_text: '',
            grid_refs: [],
            lookup_refs: [],
            entity_names: [],
            entities_json: '',
            param_entities: []
        })
    """)
    conn.close()
    db.close()


class TestSchemaMigration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "kuzu"
        _create_old_schema_db(self.db_path)

    def tearDown(self):
        close_cached_database(self.db_path)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_graph_read_only_old_db_missing_canonical_path(self):
        """MCP mo read_only: load_graph khong duoc crash Binder exception."""
        store = KuzuIndexStore(self.db_path, read_only=True)
        graph = store.load_graph()
        self.assertEqual(len(graph.nodes), 1)
        node = next(iter(graph.nodes.values()))
        self.assertEqual(node.relative_path, "Dir\\CPTran.xml")
        self.assertEqual(node.canonical_path, "")
        self.assertEqual(node.alias_of, "")

    def test_write_mode_migrates_missing_columns(self):
        """Watcher/build mo write: them cot thieu roi load_graph thanh cong."""
        store = KuzuIndexStore(self.db_path, read_only=False)
        cols = store._get_table_columns("XmlFile")
        self.assertIn("canonical_path", cols)
        self.assertIn("alias_of", cols)
        graph = store.load_graph()
        self.assertEqual(len(graph.nodes), 1)


if __name__ == "__main__":
    unittest.main()
