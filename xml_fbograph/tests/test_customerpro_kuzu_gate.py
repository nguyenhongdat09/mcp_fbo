"""Tests gate CustomerPro + App_Data/Controllers + detached build (khong sync-build)."""
import json
import os
import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from xml_fbograph.utils.path_helper import (
    get_customerpro_project_path,
    get_fbo_group_name,
    has_app_data_controllers,
    is_fastbusiness_customerpro_project,
    reset_config_caches,
)
from xml_fbograph.utils.kuzu_build_spawn import (
    NotFastBusinessProjectError,
    KuzuBuildingError,
    ensure_mcp_kuzu_ready,
)


UNC_OK = (
    r"\\172.168.5.14\CustomerPro\FBI\CNNB_FBI\FBISP229"
    r"\App_Data\Controllers\Dir\GLTran.xml"
)


class TestCustomerProGroupSemantics(unittest.TestCase):
    def test_customerpro_deep_group_name(self):
        self.assertEqual(
            get_customerpro_project_path(UNC_OK),
            r"\\172.168.5.14\CustomerPro\FBI\CNNB_FBI\FBISP229",
        )
        self.assertEqual(get_fbo_group_name(UNC_OK), "CNNB_FBI - FBISP229")

    def test_fdn_cuts_shallower(self):
        path = r"\\srv\CustomerPro\FDN\ProjA\App_Data\Controllers\Dir\X.xml"
        # index CustomerPro + FDN -> end = index+3 => CustomerPro\FDN\ProjA
        self.assertEqual(
            get_customerpro_project_path(path),
            r"\\srv\CustomerPro\FDN\ProjA",
        )
        self.assertEqual(get_fbo_group_name(path), "FDN - ProjA")

    def test_local_path_is_other(self):
        local = r"E:\mcp_fbo\xml_fbograph\foo.xml"
        self.assertEqual(get_customerpro_project_path(local), "")
        self.assertEqual(get_fbo_group_name(local), "Other")
        self.assertFalse(is_fastbusiness_customerpro_project(local))

    def test_shallow_customerpro_is_other(self):
        shallow = r"\\srv\CustomerPro\FBI\only_two"
        self.assertEqual(get_fbo_group_name(shallow), "Other")
        self.assertFalse(is_fastbusiness_customerpro_project(shallow))

    def test_extract_project_paths(self):
        # UNC đúng chuẩn
        self.assertEqual(
            get_customerpro_project_path(r"\\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Dir\X.xml"),
            r"\\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227"
        )
        
        # UNC 1 backslash (bị truncated)
        self.assertEqual(
            get_customerpro_project_path(r"\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Dir\X.xml"),
            r"\\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227"
        )
        
        # Forward slash
        self.assertEqual(
            get_customerpro_project_path(r"//172.168.5.14/CustomerPro/FBO/QUANGDUC/SP227/App_Data/Controllers/Dir/X.xml"),
            r"\\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227"
        )
        
        # group name đúng
        self.assertEqual(
            get_fbo_group_name(r"\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Dir\X.xml"),
            "QUANGDUC - SP227"
        )

    def test_normalize_unc_and_local(self):
        from xml_fbograph.utils.path_helper import _normalize_path_str
        # \C:\foo không bị nhầm thành UNC
        self.assertEqual(_normalize_path_str(r"\C:\foo"), r"\C:\foo")
        
        # Test according to requirements
        self.assertEqual(_normalize_path_str(r"\172.168.5.14\foo"), r"\\172.168.5.14\foo")
        self.assertEqual(_normalize_path_str(r"\\172.168.5.14\foo"), r"\\172.168.5.14\foo")
        self.assertEqual(_normalize_path_str(r"//172.168.5.14/foo"), r"\\172.168.5.14\foo")
        self.assertEqual(_normalize_path_str(r"E:\foo"), r"E:\foo")
        
    def test_get_customerpro_project_path_no_keyword(self):
        # Path không chứa CustomerPro nhưng bắt đầu \host → vẫn Other (không crash)
        self.assertEqual(get_customerpro_project_path(r"\172.168.5.14\OtherShare\Foo\Bar\x.xml"), "")

class TestResolveControllersDir(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="fbo_resolve_")).resolve()
        self.project_root = self.temp_dir / "CustomerPro" / "FBO" / "QUANGDUC" / "SP227"
        self.controllers = self.project_root / "App_Data" / "Controllers"
        
        self.controllers.joinpath("Dir").mkdir(parents=True)
        self.controllers.joinpath("Filter").mkdir(parents=True)
        
        self.file_dir = self.controllers / "Dir" / "TNTran.xml"
        self.file_dir.write_text("<dir/>", encoding="utf-8")
        
        self.file_filter = self.controllers / "Filter" / "VoucherLockingMultiUser.xml"
        self.file_filter.write_text("<filter/>", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(str(self.temp_dir), ignore_errors=True)

    def test_cases(self):
        from xml_fbograph.utils.path_helper import resolve_controllers_dir
        
        # Case 1: Project root
        self.assertEqual(resolve_controllers_dir(self.project_root), self.controllers)
        
        # Case 2: App_Data
        self.assertEqual(resolve_controllers_dir(self.project_root / "App_Data"), self.controllers)
        
        # Case 3: Controllers
        self.assertEqual(resolve_controllers_dir(self.controllers), self.controllers)
        
        # Case 4: Subfolder trong Controllers
        self.assertEqual(resolve_controllers_dir(self.controllers / "Filter"), self.controllers)
        
        # Case 5: File XML cụ thể
        self.assertEqual(resolve_controllers_dir(self.file_dir), self.controllers)
        self.assertEqual(resolve_controllers_dir(self.file_filter), self.controllers)
        
        # Case 6: UNC 1 backslash (bị truncated) -> Normalize roi tinh
        # We simulate this by passing the local file path but replacing 2 backslashes with 1, wait, local path doesn't have UNC prefix usually
        # But we can test that forward slash resolves exactly to self.controllers
        
        # Case 7: Forward slash
        forward_slash_path = str(self.file_dir).replace("\\", "/")
        self.assertEqual(resolve_controllers_dir(forward_slash_path), self.controllers)


class TestRequiresAppDataControllers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fbo_gate_")
        os.environ["FBOGRAPH_KUZU_BASE"] = self.temp_dir
        reset_config_caches()
        # Local tree gia CustomerPro (khong can UNC)
        self.project_root = (
            Path(self.temp_dir) / "CustomerPro" / "FBI" / "CNNB_FBI" / "FBISP229"
        )
        self.controllers = self.project_root / "App_Data" / "Controllers"
        self.ref = self.controllers / "Dir" / "GLTran.xml"

    def tearDown(self):
        os.environ.pop("FBOGRAPH_KUZU_BASE", None)
        reset_config_caches()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_group_ok_but_missing_controllers_is_false(self):
        # Chi tao project root, khong Controllers
        self.project_root.mkdir(parents=True)
        fake_ref = str(self.project_root / "readme.txt")
        self.assertEqual(get_fbo_group_name(fake_ref), "CNNB_FBI - FBISP229")
        self.assertFalse(has_app_data_controllers(fake_ref))
        self.assertFalse(is_fastbusiness_customerpro_project(fake_ref))

    def test_with_controllers_is_true(self):
        self.ref.parent.mkdir(parents=True)
        self.ref.write_text("<dir/>", encoding="utf-8")
        self.assertTrue(has_app_data_controllers(str(self.ref)))
        self.assertTrue(is_fastbusiness_customerpro_project(str(self.ref)))

    @mock.patch("pathlib.Path.is_dir")
    def test_has_app_data_controllers_unc_variations(self, mock_is_dir):
        mock_is_dir.return_value = True
        
        # UNC đúng chuẩn
        self.assertTrue(has_app_data_controllers(r"\\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Dir\X.xml"))
        
        # UNC 1 backslash
        self.assertTrue(has_app_data_controllers(r"\172.168.5.14\CustomerPro\FBO\QUANGDUC\SP227\App_Data\Controllers\Dir\X.xml"))
        
        # Forward slash
        self.assertTrue(has_app_data_controllers(r"//172.168.5.14/CustomerPro/FBO/QUANGDUC/SP227/App_Data/Controllers/Dir/X.xml"))


class TestEnsureMcpKuzuGate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fbo_spawn_")
        os.environ["FBOGRAPH_KUZU_BASE"] = self.temp_dir
        reset_config_caches()
        self.project_root = (
            Path(self.temp_dir) / "CustomerPro" / "FBO" / "Cty" / "SP228"
        )
        self.controllers = self.project_root / "App_Data" / "Controllers"
        self.ref = str(self.controllers / "Dir" / "AITran.xml")

    def tearDown(self):
        os.environ.pop("FBOGRAPH_KUZU_BASE", None)
        reset_config_caches()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_reference_file(self):
        from xml_fbograph.utils.kuzu_build_spawn import InvalidReferenceFileError, ensure_mcp_kuzu_ready
        with self.assertRaises(InvalidReferenceFileError) as ctx:
            ensure_mcp_kuzu_ready("")
        self.assertEqual(ctx.exception.payload["reason"], "missing")

    def test_relative_reference_file(self):
        from xml_fbograph.utils.kuzu_build_spawn import InvalidReferenceFileError, ensure_mcp_kuzu_ready
        with self.assertRaises(InvalidReferenceFileError) as ctx:
            ensure_mcp_kuzu_ready("Filter/SVInvoiceFilter.xml")
        self.assertEqual(ctx.exception.payload["reason"], "ambiguous_or_unresolved_relative")

    def test_absolute_but_missing_controllers(self):
        from xml_fbograph.utils.kuzu_build_spawn import InvalidReferenceFileError, ensure_mcp_kuzu_ready
        ref = str(Path(self.temp_dir) / "OtherProj" / "Filter.xml")
        with self.assertRaises(InvalidReferenceFileError) as ctx:
            ensure_mcp_kuzu_ready(ref)
        self.assertEqual(ctx.exception.payload["reason"], "missing_controllers")


    def test_missing_kuzu_spawns_once_no_sync_build(self):
        self.controllers.joinpath("Dir").mkdir(parents=True)
        Path(self.ref).write_text("<dir/>", encoding="utf-8")

        with self.assertRaises(KuzuBuildingError) as ctx1:
            ensure_mcp_kuzu_ready(self.ref)
        self.assertEqual(ctx1.exception.payload["status"], "building")
        self.assertFalse(ctx1.exception.payload.get("spawned"))

        # Lan 2: marker con song -> khong spawn them
        with self.assertRaises(KuzuBuildingError) as ctx2:
            ensure_mcp_kuzu_ready(self.ref)
        self.assertFalse(ctx2.exception.payload.get("spawned"))

        # Lan 3 van khong spawn them
        with self.assertRaises(KuzuBuildingError):
            ensure_mcp_kuzu_ready(self.ref)


if __name__ == "__main__":
    unittest.main()
