import unittest
import shutil
import tempfile
import time
import os
import json
from pathlib import Path

import kuzu
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileModifiedEvent, FileMovedEvent
from xml_fbograph.storage.kuzu_index import KuzuIndexStore, close_cached_database
from xml_fbograph.builder.graph_builder import GraphBuilder, incremental_update_file, delete_node_by_path, generate_node_id
from xml_fbograph.core.schema import GraphNode, GraphEdge
from xml_fbograph.rules.edges_rules import EdgeType
from xml_fbograph.service.watcher import GraphUpdateHandler, invalidate_project_cache

class TestWatcherAdvanced(unittest.TestCase):
    def setUp(self):
        # Tạo thư mục tạm làm controllers_root và graph_dir
        self.test_dir = Path(tempfile.mkdtemp())
        self.controllers_root = self.test_dir / "Controllers"
        self.controllers_root.mkdir()
        
        self.graph_dir = self.test_dir / "graph"
        self.graph_dir.mkdir()
        self.db_path = self.graph_dir / "kuzu"
        
        # Tạo các subfolder chuẩn trong Controllers
        (self.controllers_root / "Grid").mkdir()
        (self.controllers_root / "Dir").mkdir()

    def tearDown(self):
        # Đóng tất cả database connections và xóa thư mục tạm
        close_cached_database(self.db_path)
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def write_controller(self, relative_path: str, root_tag: str, script: str = "") -> Path:
        file_path = self.controllers_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        script_xml = f"<script><![CDATA[{script}]]></script>" if script else ""
        file_path.write_text(
            f'<?xml version="1.0" encoding="utf-8"?>\n'
            f"<{root_tag}>{script_xml}</{root_tag}>\n",
            encoding="utf-8",
        )
        return file_path

    def write_master_controller(self, detail_controller: str) -> Path:
        file_path = self.controllers_root / "Dir" / "ArchTran.xml"
        file_path.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<dir table="m_arch" code="stt_rec">\n'
            '  <field name="d01">\n'
            f'    <items style="Grid" controller="{detail_controller}">\n'
            '      <item value="ForeignKey"><text v="String: stt_rec"/></item>\n'
            '    </items>\n'
            '  </field>\n'
            '</dir>\n',
            encoding="utf-8",
        )
        return file_path

    def query_rows(self, cypher_query: str, params: dict = None) -> list:
        from xml_fbograph.query.engine import ensure_fresh_readonly_store
        store = ensure_fresh_readonly_store(self.db_path, self.graph_dir)
        return store.execute_cypher(cypher_query, params)

    def node_count(self, relative_path: str) -> int:
        rows = self.query_rows(
            """
            MATCH (n:XmlFile)
            WHERE n.relative_path = $relative_path
            RETURN count(*) AS node_count
            """,
            {"relative_path": relative_path},
        )
        return rows[0]["node_count"] if rows else 0

    def edge_count(self, source_path: str, target_path: str, edge_type: str) -> int:
        rows = self.query_rows(
            """
            MATCH (src:XmlFile)-[r:Rel]->(dst:XmlFile)
            WHERE src.relative_path = $source_path
              AND dst.relative_path = $target_path
              AND r.edge_type = $edge_type
            RETURN count(*) AS edge_count
            """,
            {
                "source_path": source_path,
                "target_path": target_path,
                "edge_type": edge_type,
            },
        )
        return rows[0]["edge_count"] if rows else 0

    def test_t1_read_first_then_write(self):
        """Test T1: Mở read-only DB trước, sau đó thực hiện ghi gia tăng (update_single_node), đảm bảo không bị lock file."""
        # 1. Khởi tạo DB bằng cách ghi 1 node dummy
        store_write = KuzuIndexStore(self.db_path, read_only=False)
        nid1 = generate_node_id("Grid\\Dummy.xml")
        node = GraphNode(
            node_id=nid1,
            file_path=str(self.controllers_root / "Grid" / "Dummy.xml"),
            relative_path="Grid\\Dummy.xml",
            folder_type="Grid",
            folder_subtype="",
            xml_root_tag="grid",
            xml_namespace="",
            controller_type="Grid",
            table="dummy_table",
            code_field="dummy_code",
            title_v="Tiêu đề",
            title_e="Title",
            entities=[],
            param_entities=[],
            fields=[],
            sql_blocks=[],
            js_blocks=[],
            file_size=100,
            last_modified=time.time(),
            is_encrypted=False,
            source_extension=".xml",
            paired_f_path=None,
            needs_xml=False
        )
        node.alias_of = node.node_id
        store_write.update_single_node(node, [])
        
        # 2. Mở read-only DB (giống mcp radar query)
        store_read = KuzuIndexStore(self.db_path, read_only=True)
        res = store_read.conn.execute("MATCH (n:XmlFile) RETURN count(*)")
        self.assertTrue(res.has_next())
        self.assertEqual(res.get_next()[0], 1)
        
        # 3. Thực hiện ghi tiếp (giống watcher cập nhật gia tăng)
        # Hệ thống phải tự động đóng connection read-only cũ để mở write connection mới
        store_write2 = KuzuIndexStore(self.db_path, read_only=False)
        nid2 = generate_node_id("Grid\\Dummy2.xml")
        node2 = GraphNode(
            node_id=nid2,
            file_path=str(self.controllers_root / "Grid" / "Dummy2.xml"),
            relative_path="Grid\\Dummy2.xml",
            folder_type="Grid",
            folder_subtype="",
            xml_root_tag="grid",
            xml_namespace="",
            controller_type="Grid",
            table="dummy_table2",
            code_field="dummy_code2",
            title_v="Tiêu đề 2",
            title_e="Title 2",
            entities=[],
            param_entities=[],
            fields=[],
            sql_blocks=[],
            js_blocks=[],
            file_size=120,
            last_modified=time.time(),
            is_encrypted=False,
            source_extension=".xml",
            paired_f_path=None,
            needs_xml=False
        )
        node2.alias_of = node2.node_id
        store_write2.update_single_node(node2, [])
        
        # Kiểm tra ghi thành công
        res2 = store_write2.conn.execute("MATCH (n:XmlFile) RETURN count(*)")
        self.assertTrue(res2.has_next())
        self.assertEqual(res2.get_next()[0], 2)

    def test_t2_save_three_times_no_duplicate_edge(self):
        """Test T2: Gọi cập nhật gia tăng cùng một file 3 lần liên tiếp, verify số cạnh luôn là 1."""
        store_write = KuzuIndexStore(self.db_path, read_only=False)
        
        src_id = generate_node_id("Dir\\CPTran.xml")
        dst_id = generate_node_id("Grid\\CPDetail.xml")
        
        # Tạo node nguồn và node đích
        src_node = GraphNode(
            node_id=src_id,
            file_path=str(self.controllers_root / "Dir" / "CPTran.xml"),
            relative_path="Dir\\CPTran.xml",
            folder_type="Dir",
            folder_subtype="",
            xml_root_tag="dir",
            xml_namespace="",
            controller_type="Dir",
            table="m66$000000",
            code_field="stt_rec",
            title_v="Voucher",
            title_e="Voucher",
            entities=[],
            param_entities=[],
            fields=[],
            sql_blocks=[],
            js_blocks=[],
            file_size=100,
            last_modified=time.time(),
            is_encrypted=False,
            source_extension=".xml",
            paired_f_path=None,
            needs_xml=False
        )
        src_node.alias_of = src_node.node_id
        
        dst_node = GraphNode(
            node_id=dst_id,
            file_path=str(self.controllers_root / "Grid" / "CPDetail.xml"),
            relative_path="Grid\\CPDetail.xml",
            folder_type="Grid",
            folder_subtype="",
            xml_root_tag="grid",
            xml_namespace="",
            controller_type="Grid",
            table="d66$000000",
            code_field="ma_vt",
            title_v="Grid Detail",
            title_e="Grid Detail",
            entities=[],
            param_entities=[],
            fields=[],
            sql_blocks=[],
            js_blocks=[],
            file_size=100,
            last_modified=time.time(),
            is_encrypted=False,
            source_extension=".xml",
            paired_f_path=None,
            needs_xml=False
        )
        dst_node.alias_of = dst_node.node_id
        
        store_write.update_single_node(dst_node, [])
        
        # 1. Update lần 1 với 1 edge
        edge = GraphEdge(
            source_id=src_node.node_id,
            target_id=dst_node.node_id,
            edge_type=EdgeType.GRID_MASTER_DETAIL,
            meta={"field_name": "detail_grid", "parsed_from_source": src_node.relative_path}
        )
        store_write.update_single_node(src_node, [edge])
        
        # Verify edge
        res = store_write.conn.execute(
            "MATCH (src:XmlFile {node_id: $src_id})-[r:Rel]->(dst:XmlFile {node_id: $dst_id}) RETURN count(*)",
            {"src_id": src_id, "dst_id": dst_id}
        )
        self.assertEqual(res.get_next()[0], 1)
        
        # 2. Update lần 2
        store_write.update_single_node(src_node, [edge])
        res = store_write.conn.execute(
            "MATCH (src:XmlFile {node_id: $src_id})-[r:Rel]->(dst:XmlFile {node_id: $dst_id}) RETURN count(*)",
            {"src_id": src_id, "dst_id": dst_id}
        )
        self.assertEqual(res.get_next()[0], 1)
        
        # 3. Update lần 3
        store_write.update_single_node(src_node, [edge])
        res = store_write.conn.execute(
            "MATCH (src:XmlFile {node_id: $src_id})-[r:Rel]->(dst:XmlFile {node_id: $dst_id}) RETURN count(*)",
            {"src_id": src_id, "dst_id": dst_id}
        )
        self.assertEqual(res.get_next()[0], 1)

    def test_t3_reevaluate_canonical_group_on_delete(self):
        """Test T3: Khi xóa canonical node, alias còn sống tự động được thăng cấp làm canonical mới và định tuyến lại các cạnh."""
        store_write = KuzuIndexStore(self.db_path, read_only=False)
        conn = store_write.conn
        
        n1_id = generate_node_id("Grid\\CPDetail.xml")
        n2_id = generate_node_id("Grid\\Config\\Fields\\CPDetail.xml")
        n_other_id = generate_node_id("Dir\\CPTran.xml")
        
        # Tạo canonical node và alias node
        # Nhóm "grid", normalized_name = "cpdetail"
        # Node 1: Canonical
        n1 = GraphNode(
            node_id=n1_id,
            file_path=str(self.controllers_root / "Grid" / "CPDetail.xml"),
            relative_path="Grid\\CPDetail.xml",
            folder_type="Grid",
            folder_subtype="",
            xml_root_tag="grid",
            xml_namespace="",
            controller_type="Grid",
            table="d66$000000",
            code_field="ma_vt",
            title_v="Detail",
            title_e="Detail",
            entities=[],
            param_entities=[],
            fields=[],
            sql_blocks=[],
            js_blocks=[],
            file_size=100,
            last_modified=time.time(),
            is_encrypted=False,
            source_extension=".xml",
            paired_f_path=None,
            needs_xml=False
        )
        n1.alias_of = n1.node_id
        n1.canonical_path = n1.relative_path
        store_write.update_single_node(n1, [])
        
        # Node 2: Alias
        n2 = GraphNode(
            node_id=n2_id,
            file_path=str(self.controllers_root / "Grid" / "Config" / "Fields" / "CPDetail.xml"),
            relative_path="Grid\\Config\\Fields\\CPDetail.xml",
            folder_type="Grid",
            folder_subtype="fields",
            xml_root_tag="fields",
            xml_namespace="",
            controller_type="Grid",
            table="d66$000000",
            code_field="ma_vt",
            title_v="Detail Alias",
            title_e="Detail Alias",
            entities=[],
            param_entities=[],
            fields=[],
            sql_blocks=[],
            js_blocks=[],
            file_size=100,
            last_modified=time.time(),
            is_encrypted=False,
            source_extension=".xml",
            paired_f_path=None,
            needs_xml=False
        )
        n2.alias_of = n1.node_id
        n2.canonical_path = n1.relative_path
        store_write.update_single_node(n2, [])
        
        # Tạo node trung gian khác để liên kết
        n_other = GraphNode(
            node_id=n_other_id,
            file_path=str(self.controllers_root / "Dir" / "CPTran.xml"),
            relative_path="Dir\\CPTran.xml",
            folder_type="Dir",
            folder_subtype="",
            xml_root_tag="dir",
            xml_namespace="",
            controller_type="Dir",
            table="m66$000000",
            code_field="stt_rec",
            title_v="Voucher",
            title_e="Voucher",
            entities=[],
            param_entities=[],
            fields=[],
            sql_blocks=[],
            js_blocks=[],
            file_size=100,
            last_modified=time.time(),
            is_encrypted=False,
            source_extension=".xml",
            paired_f_path=None,
            needs_xml=False
        )
        n_other.alias_of = n_other.node_id
        # Tạo cạnh nối tới canonical node n1
        edge = GraphEdge(
            source_id=n_other.node_id,
            target_id=n1.node_id,
            edge_type=EdgeType.GRID_MASTER_DETAIL,
            meta={"field_name": "detail", "parsed_from_source": n_other.relative_path}
        )
        store_write.update_single_node(n_other, [edge])
        
        # Kiểm tra trước khi xóa: n2 có alias_of là n1_id
        res_alias = conn.execute("MATCH (n:XmlFile {node_id: $nid}) RETURN n.alias_of", {"nid": n2_id})
        self.assertEqual(res_alias.get_next()[0], n1_id)
        
        # Xóa canonical node n1 thông qua delete_node_by_path
        # Điều này sẽ kích hoạt reevaluate_canonical_group_on_delete
        delete_node_by_path(self.controllers_root, self.db_path, Path(n1.file_path))
        
        # Kiểm tra sau khi xóa:
        # 1. n2 phải được tự động thăng cấp thành canonical mới (alias_of = chính nó)
        res_alias_post = conn.execute("MATCH (n:XmlFile {node_id: $nid}) RETURN n.alias_of, n.canonical_path", {"nid": n2_id})
        row = res_alias_post.get_next()
        self.assertEqual(row[0], n2_id)
        self.assertEqual(row[1], "Grid\\Config\\Fields\\CPDetail.xml")
        
        # 2. Cạnh ban đầu nối từ Dir.CPTran -> Grid.CPDetail phải được tự động chuyển hướng thành Dir.CPTran -> Grid.CPDetail_Alias!
        res_edge = conn.execute(
            "MATCH (src:XmlFile {node_id: $src_id})-[r:Rel]->(dst:XmlFile {node_id: $dst_id}) RETURN count(*)",
            {"src_id": n_other_id, "dst_id": n2_id}
        )
        self.assertEqual(res_edge.get_next()[0], 1)

    def test_t4_cached_connection_does_not_keep_self_reference(self):
        """Connection wrapper không tự giữ chính nó qua _orig_conn."""
        store = KuzuIndexStore(self.db_path, read_only=False)
        self.assertFalse(
            hasattr(store.conn, "_orig_conn"),
            "Connection cache must not retain a self-referential _orig_conn",
        )

    def test_t5_watcher_create_modify_rename_delete_updates_kuzu(self):
        """Mỗi filesystem event phải làm node/edge Kuzu đổi đúng theo kiến trúc."""
        handler = GraphUpdateHandler(self.controllers_root, self.graph_dir)
        handler.debounce_seconds = 0

        first_filter = self.write_controller("Filter\\ArchFirstFilter.xml", "filter")
        second_filter = self.write_controller("Filter\\ArchSecondFilter.xml", "filter")
        handler.on_any_event(FileCreatedEvent(str(first_filter)))
        handler.on_any_event(FileCreatedEvent(str(second_filter)))

        detail_path = self.write_controller(
            "Grid\\ArchDetail.xml",
            "grid",
            "g.showForm('ArchFirstFilter');",
        )
        handler.on_any_event(FileCreatedEvent(str(detail_path)))

        self.assertEqual(self.node_count("Grid\\ArchDetail.xml"), 1)
        self.assertEqual(
            self.edge_count(
                "Grid\\ArchDetail.xml",
                "Filter\\ArchFirstFilter.xml",
                EdgeType.RETRIEVE_DATA_SOURCE,
            ),
            1,
        )

        master_path = self.write_master_controller("ArchDetail")
        handler.on_any_event(FileCreatedEvent(str(master_path)))
        self.assertEqual(
            self.edge_count(
                "Dir\\ArchTran.xml",
                "Grid\\ArchDetail.xml",
                EdgeType.GRID_MASTER_DETAIL,
            ),
            1,
        )

        # Modify: quan hệ cũ phải biến mất, quan hệ mới phải xuất hiện.
        self.write_controller(
            "Grid\\ArchDetail.xml",
            "grid",
            "g.showForm('ArchSecondFilter');",
        )
        handler.on_any_event(FileModifiedEvent(str(detail_path)))

        self.assertEqual(
            self.edge_count(
                "Grid\\ArchDetail.xml",
                "Filter\\ArchFirstFilter.xml",
                EdgeType.RETRIEVE_DATA_SOURCE,
            ),
            0,
        )
        self.assertEqual(
            self.edge_count(
                "Grid\\ArchDetail.xml",
                "Filter\\ArchSecondFilter.xml",
                EdgeType.RETRIEVE_DATA_SOURCE,
            ),
            1,
        )

        # Rename/move: path cũ mất, path mới có và edge vẫn đúng.
        renamed_path = detail_path.with_name("ArchDetailRenamed.xml")
        detail_path.rename(renamed_path)
        handler.on_any_event(FileMovedEvent(str(detail_path), str(renamed_path)))
        self.write_master_controller("ArchDetailRenamed")
        handler.on_any_event(FileModifiedEvent(str(master_path)))

        self.assertEqual(self.node_count("Grid\\ArchDetail.xml"), 0)
        self.assertEqual(self.node_count("Grid\\ArchDetailRenamed.xml"), 1)
        self.assertEqual(
            self.edge_count(
                "Grid\\ArchDetailRenamed.xml",
                "Filter\\ArchSecondFilter.xml",
                EdgeType.RETRIEVE_DATA_SOURCE,
            ),
            1,
        )
        self.assertEqual(
            self.edge_count(
                "Dir\\ArchTran.xml",
                "Grid\\ArchDetail.xml",
                EdgeType.GRID_MASTER_DETAIL,
            ),
            0,
        )
        self.assertEqual(
            self.edge_count(
                "Dir\\ArchTran.xml",
                "Grid\\ArchDetailRenamed.xml",
                EdgeType.GRID_MASTER_DETAIL,
            ),
            1,
        )

        # Delete: node và mọi edge liên quan phải biến mất.
        renamed_path.unlink()
        handler.on_any_event(FileDeletedEvent(str(renamed_path)))

        self.assertEqual(self.node_count("Grid\\ArchDetailRenamed.xml"), 0)
        rows = self.query_rows(
            """
            MATCH (src:XmlFile)-[r:Rel]->(dst:XmlFile)
            WHERE src.relative_path = $relative_path
               OR dst.relative_path = $relative_path
            RETURN count(*) AS edge_count
            """,
            {"relative_path": "Grid\\ArchDetailRenamed.xml"},
        )
        self.assertEqual(rows[0]["edge_count"], 0)

    def test_t6_watcher_updates_two_files_inside_global_debounce_window(self):
        """Hai file khác nhau trong <1 giây đều phải được ghi vào Kuzu."""
        handler = GraphUpdateHandler(self.controllers_root, self.graph_dir)
        handler.debounce_seconds = 1.0

        first_path = self.write_controller("Grid\\ArchFastOne.xml", "grid")
        second_path = self.write_controller("Grid\\ArchFastTwo.xml", "grid")

        handler.on_any_event(FileCreatedEvent(str(first_path)))
        handler.on_any_event(FileCreatedEvent(str(second_path)))

        self.assertEqual(self.node_count("Grid\\ArchFastOne.xml"), 1)
        self.assertEqual(self.node_count("Grid\\ArchFastTwo.xml"), 1)

    def test_t7_ro_then_incremental_then_ro(self):
        """Test T7: Read-only -> incremental update -> read-only (cache invalidate test)."""
        from xml_fbograph.service.watcher import run_incremental_write
        import time
        
        # 1. Khởi tạo file ban đầu
        filter_path = self.write_controller("Filter\\CPOSTranFilter.xml", "filter")
        run_incremental_write(filter_path, 'update', self.controllers_root, self.graph_dir, None)
        
        detail_path = self.write_controller(
            "Grid\\CPDetail.xml",
            "grid",
            "g.showForm('CPOSTranFilter');",
        )
        
        # Gọi run_incremental_write lần đầu để tạo node
        run_incremental_write(detail_path, 'update', self.controllers_root, self.graph_dir, None)
        
        # 2. Query Read-Only (như MCP server đang làm)
        edge_count_before = self.edge_count("Grid\\CPDetail.xml", "Filter\\CPOSTranFilter.xml", EdgeType.RETRIEVE_DATA_SOURCE)
        self.assertEqual(edge_count_before, 1, "Ban đầu phải có 1 cạnh nối tới CPOSTranFilter")
        
        # 3. Sửa file (giả lập xóa dòng showForm)
        time.sleep(0.1) # Đảm bảo mtime thay đổi
        self.write_controller(
            "Grid\\CPDetail.xml",
            "grid",
            "// không còn g.showForm",
        )
        
        # Watcher phát hiện file thay đổi, gọi run_incremental_write
        # Nó phải tự đóng cache của chính process này và ghi an toàn
        run_incremental_write(detail_path, 'update', self.controllers_root, self.graph_dir, None)
        
        # 4. Query Read-Only lại lần nữa
        # Lần này cache phải bị xóa, graph load lại từ ổ đĩa
        edge_count_after = self.edge_count("Grid\\CPDetail.xml", "Filter\\CPOSTranFilter.xml", EdgeType.RETRIEVE_DATA_SOURCE)
        self.assertEqual(edge_count_after, 0, "Sau incremental update, cache phải bị clear và cạnh bị xóa")
    def test_t8_f_file_incremental(self):
        """Test T8: Xử lý incremental trên file .f (needs_xml)"""
        from xml_fbograph.service.watcher import run_incremental_write
        import time
        import os
        
        # 1. Incremental trên .f KHÔNG có .xml
        f_only_path = self.controllers_root / "Grid" / "OnlyF.f"
        f_only_path.parent.mkdir(parents=True, exist_ok=True)
        f_only_path.write_bytes(b"\x00\x00\x00encrypted garbage")
        
        run_incremental_write(f_only_path, 'update', self.controllers_root, self.graph_dir, None)
        
        # Kiểm tra node stub được tạo ra
        self.assertEqual(self.node_count("Grid\\OnlyF.xml"), 1, "Phải tạo node đại diện cho OnlyF.f")
        rows = self.query_rows(
            "MATCH (n:XmlFile {relative_path: $path}) RETURN n.needs_xml as needs_xml, n.is_encrypted as is_encrypted, n.source_extension as ext, n.paired_f_path as paired",
            {"path": "Grid\\OnlyF.xml"}
        )
        self.assertTrue(rows[0]["needs_xml"])
        self.assertTrue(rows[0]["is_encrypted"])
        self.assertEqual(rows[0]["ext"], ".f")
        self.assertEqual(rows[0]["paired"], "Grid\\OnlyF.f")
        
        # 2. Incremental trên .f CÓ sibling .xml
        xml_path = self.write_controller("Dir\\HasXml.xml", "dir", "some valid js")
        run_incremental_write(xml_path, 'update', self.controllers_root, self.graph_dir, None)
        
        # Tạo thêm file .f
        f_sibling = xml_path.with_suffix(".f")
        f_sibling.write_bytes(b"\x00\x00\x00garbage")
        
        # Incremental update trên .f này phải bị skip (return None)
        # Tức là node HasXml.xml vẫn giữ nguyên (không bị ghi đè thành needs_xml=True)
        run_incremental_write(f_sibling, 'update', self.controllers_root, self.graph_dir, None)
        
        rows2 = self.query_rows(
            "MATCH (n:XmlFile {relative_path: $path}) RETURN n.needs_xml as needs_xml, n.source_extension as ext",
            {"path": "Dir\\HasXml.xml"}
        )
        self.assertFalse(rows2[0]["needs_xml"], "Node XML không bị ghi đè bởi sibling .f")
        self.assertEqual(rows2[0]["ext"], ".xml")
        
        # 3. Xóa .xml rồi update từ .f (watcher flow)
        xml_path.unlink()
        run_incremental_write(xml_path, 'delete', self.controllers_root, self.graph_dir, None)
        
        # Node XML đã bị xóa
        self.assertEqual(self.node_count("Dir\\HasXml.xml"), 0)
        
        # Watcher gọi update .f
        run_incremental_write(f_sibling, 'update', self.controllers_root, self.graph_dir, None)
        
        # Node lại được tạo nhưng lần này là stub needs_xml=True
        self.assertEqual(self.node_count("Dir\\HasXml.xml"), 1)
        rows3 = self.query_rows(
            "MATCH (n:XmlFile {relative_path: $path}) RETURN n.needs_xml as needs_xml, n.source_extension as ext",
            {"path": "Dir\\HasXml.xml"}
        )
        self.assertTrue(rows3[0]["needs_xml"], "Phục hồi từ .f phải tạo node stub needs_xml=True")
        self.assertEqual(rows3[0]["ext"], ".f")

if __name__ == "__main__":
    unittest.main()
