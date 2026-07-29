import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from xml_fbograph.utils.path_helper import (
    get_extract_shared_include_yn,
    reset_config_caches,
)
from xml_fbograph.builder.graph_builder import GraphBuilder
from xml_fbograph.rules.edges_rules import EdgeType


class TestExtractSharedIncludeConfig(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fbo_extract_test_")
        reset_config_caches()

    def tearDown(self):
        os.environ.pop("FBOGRAPH_SHARED_INCLUDE", None)
        os.environ.pop("FBOGRAPH_KUZU_BASE", None)
        reset_config_caches()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_shared_include_is_zero(self):
        """Mặc định khi không có config hay env var thì shared_include = 0 (tắt)."""
        os.environ.pop("FBOGRAPH_SHARED_INCLUDE", None)
        reset_config_caches()
        self.assertEqual(get_extract_shared_include_yn(), 0)

    def test_env_var_override_truthy_and_falsy(self):
        """Biến môi trường FBOGRAPH_SHARED_INCLUDE phải ghi đè cấu hình."""
        for val in ("1", "true", "yes", "TRUE"):
            os.environ["FBOGRAPH_SHARED_INCLUDE"] = val
            reset_config_caches()
            self.assertEqual(get_extract_shared_include_yn(), 1, f"Failed for env val {val}")

        for val in ("0", "false", "no", "FALSE"):
            os.environ["FBOGRAPH_SHARED_INCLUDE"] = val
            reset_config_caches()
            self.assertEqual(get_extract_shared_include_yn(), 0, f"Failed for env val {val}")

    def test_nested_fbograph_shared_include_ignored(self):
        """Nếu cố tình nhét shared_include dưới block fbograph:, phải bị lờ đi và trả về 0."""
        config_path = Path(self.temp_dir) / "config.yaml"
        config_content = """
fbograph:
  kuzu_db_base: "C:/KuzuDB"
  user_multi_db_yn: 1
  shared_include: 1
"""
        config_path.write_text(config_content, encoding="utf-8")
        
        from xml_fbograph.utils import path_helper
        orig_find = path_helper._find_config_file
        path_helper._find_config_file = lambda: config_path
        try:
            reset_config_caches()
            self.assertEqual(get_extract_shared_include_yn(), 0)
        finally:
            path_helper._find_config_file = orig_find

    def test_top_level_extract_options_parsed_correctly(self):
        """Block top-level extract_options.shared_include hoạt động chính xác."""
        config_path = Path(self.temp_dir) / "config.yaml"
        
        # Test = 1
        config_path.write_text("extract_options:\n  shared_include: 1\n", encoding="utf-8")
        from xml_fbograph.utils import path_helper
        orig_find = path_helper._find_config_file
        path_helper._find_config_file = lambda: config_path
        try:
            reset_config_caches()
            self.assertEqual(get_extract_shared_include_yn(), 1)
            
            # Test = 0
            config_path.write_text("extract_options:\n  shared_include: 0\n", encoding="utf-8")
            reset_config_caches()
            self.assertEqual(get_extract_shared_include_yn(), 0)

            # Test = false
            config_path.write_text("extract_options:\n  shared_include: false\n", encoding="utf-8")
            reset_config_caches()
            self.assertEqual(get_extract_shared_include_yn(), 0)
        finally:
            path_helper._find_config_file = orig_find

    def test_graph_builder_shared_include_toggle(self):
        """GraphBuilder phải tôn trọng cờ shared_include khi xây dựng cạnh SHARED_INCLUDE."""
        controllers_dir = Path(self.temp_dir) / "Controllers"
        dir_folder = controllers_dir / "Dir"
        dir_folder.mkdir(parents=True, exist_ok=True)

        # Tạo file entity dùng chung trong Dir/
        common_ent = dir_folder / "Common.ent"
        common_ent.write_text("<!ELEMENT common EMPTY>", encoding="utf-8")

        # Tạo 2 XML controller cùng include file entity Common.ent
        xml1_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
  <!ENTITY Common SYSTEM "Common.ent">
]>
<dir table="m01">
  &Common;
</dir>
"""
        xml2_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE dir [
  <!ENTITY Common SYSTEM "Common.ent">
]>
<dir table="m02">
  &Common;
</dir>
"""
        (dir_folder / "A1Tran.xml").write_text(xml1_content, encoding="utf-8")
        (dir_folder / "A2Tran.xml").write_text(xml2_content, encoding="utf-8")

        # Case 1: shared_include = 0 (tắt)
        builder0 = GraphBuilder(controllers_dir, shared_include=0)
        graph0 = builder0.build()
        shared_edges0 = [e for e in graph0.edges if e.edge_type == EdgeType.SHARED_INCLUDE]
        entity_edges0 = [e for e in graph0.edges if e.edge_type == EdgeType.ENTITY_INCLUDE]
        
        self.assertEqual(len(shared_edges0), 0)
        self.assertEqual(len(entity_edges0), 0)

        # Case 2: shared_include = 1 (bật)
        builder1 = GraphBuilder(controllers_dir, shared_include=1)
        graph1 = builder1.build()
        shared_edges1 = [e for e in graph1.edges if e.edge_type == EdgeType.SHARED_INCLUDE]
        entity_edges1 = [e for e in graph1.edges if e.edge_type == EdgeType.SHARED_INCLUDE or e.edge_type == EdgeType.ENTITY_INCLUDE]
        
        self.assertEqual(len(shared_edges1), 0)


if __name__ == "__main__":
    unittest.main()
