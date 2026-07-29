import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from xml_fbograph.mcp_tools import mcp_query_radar
from xml_fbograph.storage.kuzu_index import KuzuIndexStore, close_cached_database


class TestRadarSchemaMode(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.db_path = self.test_dir / "kuzu"
        self.store = KuzuIndexStore(self.db_path, read_only=False)

    def tearDown(self):
        close_cached_database(self.db_path)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def call_radar(self, cypher_query: str = "", mode: str = "query"):
        with patch(
            "xml_fbograph.mcp_tools.get_kuzu_store",
            return_value=self.store,
        ):
            return json.loads(
                mcp_query_radar(
                    cypher_query=cypher_query,
                    reference_file="dummy.xml",
                    mode=mode,
                )
            )

    def test_schema_mode_returns_live_tables_columns_rules_and_examples(self):
        result = self.call_radar(mode="schema")

        self.assertEqual(result["mode"], "schema")
        self.assertEqual(
            {table["name"] for table in result["tables"]},
            {"XmlFile", "Rel"},
        )
        self.assertIn("relative_path", result["node_table"]["columns"])
        self.assertEqual(result["node_table"]["columns"]["fields_names"], "STRING[]")
        self.assertEqual(result["relationship_table"]["columns"]["edge_type"], "STRING")
        self.assertIn("GRID_MASTER_DETAIL", result["edge_types"])
        self.assertIn("RETRIEVE_DATA_SOURCE", result["edge_types"])
        self.assertTrue(result["rules"])
        self.assertTrue(result["examples"])

    def test_query_mode_remains_backward_compatible(self):
        result = self.call_radar(
            "MATCH (n:XmlFile) RETURN count(*) AS node_count",
        )

        self.assertEqual(result, [{"node_count": 0}])

    def test_invalid_mode_returns_actionable_error(self):
        result = self.call_radar(mode="invalid")

        self.assertIn("error", result)
        self.assertIn("query", result["error"])
        self.assertIn("schema", result["error"])


if __name__ == "__main__":
    unittest.main()
