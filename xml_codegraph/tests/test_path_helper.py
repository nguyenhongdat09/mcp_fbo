import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Thêm thư mục root vào sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from xml_codegraph.utils.path_helper import (
    resolve_graph_dir,
    get_user_multi_db_yn,
    reset_config_caches,
    ProjectPathHelper,
)


class TestPathHelperMultiDB(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="kuzu_test_base_")
        os.environ["FBOGRAPH_KUZU_BASE"] = self.temp_dir
        reset_config_caches()

        self.project1 = Path("/dummy/project/alpha")
        self.project2 = Path("/dummy/project/beta")

    def tearDown(self):
        os.environ.pop("FBOGRAPH_KUZU_BASE", None)
        os.environ.pop("FBOGRAPH_MULTI_DB", None)
        reset_config_caches()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_multi_db_mode_enabled_default(self):
        """Khi user_multi_db_yn = 1 (mặc định), mỗi dự án tạo 1 DB riêng biệt."""
        os.environ["FBOGRAPH_MULTI_DB"] = "1"
        reset_config_caches()

        dir1 = resolve_graph_dir(self.project1)
        dir2 = resolve_graph_dir(self.project2)

        self.assertEqual(get_user_multi_db_yn(), 1)
        self.assertNotEqual(dir1, dir2)
        self.assertTrue(str(dir1).startswith(self.temp_dir))
        self.assertTrue(str(dir2).startswith(self.temp_dir))

    def test_single_db_mode_no_existing_db(self):
        """Khi user_multi_db_yn = 0 và chưa có DB nào, khởi tạo DB đầu tiên."""
        os.environ["FBOGRAPH_MULTI_DB"] = "0"
        reset_config_caches()

        dir1 = resolve_graph_dir(self.project1)
        self.assertEqual(get_user_multi_db_yn(), 0)
        self.assertTrue(str(dir1).startswith(self.temp_dir))

    def test_single_db_mode_reuse_existing_db(self):
        """Khi user_multi_db_yn = 0 và đã có DB dự án A, dự án B sẽ reuse DB đại diện đó."""
        os.environ["FBOGRAPH_MULTI_DB"] = "0"
        reset_config_caches()

        # Tạo giả lập DB của dự án 1
        dir1 = resolve_graph_dir(self.project1)
        dir1.mkdir(parents=True, exist_ok=True)
        (dir1 / "kuzu").mkdir(parents=True, exist_ok=True)

        # Dự án 2 gọi resolve_graph_dir -> Phải trả về dir1 thay vì tạo dir mới theo project 2
        dir2 = resolve_graph_dir(self.project2)
        self.assertEqual(dir1, dir2)

    def test_project_path_helper_integration(self):
        """Kiểm tra ProjectPathHelper tích hợp get_graph_dir đúng theo cấu hình."""
        os.environ["FBOGRAPH_MULTI_DB"] = "0"
        reset_config_caches()

        # Tạo giả định DB đại diện
        dir1 = resolve_graph_dir(self.project1)
        dir1.mkdir(parents=True, exist_ok=True)

        helper2 = ProjectPathHelper(str(self.project2 / "App_Data" / "Controllers" / "Dir" / "AITran.xml"))
        self.assertEqual(helper2.get_graph_dir(), dir1)

    def test_is_db_owner_single_db_mode(self):
        """Kiểm tra is_db_owner khi user_multi_db_yn = 0."""
        from xml_codegraph.utils.path_helper import is_db_owner
        os.environ["FBOGRAPH_MULTI_DB"] = "0"
        reset_config_caches()

        proj1 = Path(self.temp_dir) / "project_alpha"
        proj2 = Path(self.temp_dir) / "project_beta"

        (proj1 / "App_Data" / "Controllers" / "Dir").mkdir(parents=True, exist_ok=True)
        (proj2 / "App_Data" / "Controllers" / "Dir").mkdir(parents=True, exist_ok=True)

        file1 = proj1 / "App_Data" / "Controllers" / "Dir" / "AITran.xml"
        file2 = proj2 / "App_Data" / "Controllers" / "Dir" / "AITran.xml"
        file1.touch()
        file2.touch()

        # Tạo DB cho proj1
        dir1 = resolve_graph_dir(proj1)
        dir1.mkdir(parents=True, exist_ok=True)

        helper1 = ProjectPathHelper(str(file1))
        helper2 = ProjectPathHelper(str(file2))

        # Project 1 là owner
        self.assertTrue(helper1.is_db_owner())
        self.assertTrue(is_db_owner(proj1, dir1))
        
        # Project 2 không phải owner
        self.assertFalse(helper2.is_db_owner())
        self.assertFalse(is_db_owner(proj2, dir1))


if __name__ == "__main__":
    unittest.main()
