"""Regression test cho cac fix watcher/daemon/reconcile/search_fields.

Cover cac case thuc te da boc lo khi review:
- search_fields tren blob zlib+b64 (truoc decode sai -> luon rong)
- moved .xml -> .bak xoa node; .tmp -> .xml (atomic save) tao node
- debounce theo (path, nhom): delete->create khong bi nuot,
  create+modify chi ghi 1 lan
- reconcile dinh ky: tu them file watcher miss, xoa node orphan,
  stub .f, va idempotent (round 2 khong lam gi)
- election same-process: 2 instance cung PID khong cung giu quyen
- bulk build ghi relative_path backslash (exact-match query chay duoc)
- daemon pipe end-to-end: spawn daemon that -> write RPC -> context query
  -> radar mode=schema qua pipe (kwargs forwarding)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
)

from xml_fbograph.builder.graph_builder import build_and_save_graph
from xml_fbograph.service import watcher as watcher_mod
from xml_fbograph.service.watcher import (
    GraphUpdateHandler,
    _WatcherOwnership,
    reconcile_graph_with_disk,
    run_incremental_write,
)
from xml_fbograph.storage.kuzu_index import KuzuIndexStore, close_cached_database


class BaseTempProject(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.controllers_root = self.test_dir / "Controllers"
        self.controllers_root.mkdir()
        (self.controllers_root / "Grid").mkdir()
        (self.controllers_root / "Dir").mkdir()
        (self.controllers_root / "Filter").mkdir()
        self.graph_dir = self.test_dir / "graph"
        self.graph_dir.mkdir()
        self.db_path = self.graph_dir / "kuzu"

    def tearDown(self):
        close_cached_database(self.db_path)
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception:
            pass

    def write_controller(self, relative_path: str, root_tag: str = "grid",
                         script: str = "", fields=None) -> Path:
        file_path = self.controllers_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        script_xml = f"<script><![CDATA[{script}]]></script>" if script else ""
        fields_xml = ""
        if fields:
            fields_xml = "".join(
                f'<field name="{name}"><header v="{name} label"/></field>'
                for name in fields
            )
        file_path.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f"<{root_tag}>{fields_xml}{script_xml}</{root_tag}>\n",
            encoding="utf-8",
        )
        return file_path

    def open_store(self):
        store = KuzuIndexStore(self.db_path, read_only=True)
        store._bind_live_connection()
        return store

    def node_count(self, relative_path: str) -> int:
        store = self.open_store()
        try:
            res = store.conn.execute(
                "MATCH (n:XmlFile) WHERE n.relative_path = $p RETURN count(*)",
                {"p": relative_path},
            )
            return res.get_next()[0] if res.has_next() else 0
        finally:
            close_cached_database(self.db_path)


class TestSearchFieldsRegression(BaseTempProject):
    def test_search_fields_on_compressed_blob(self):
        """fields_json la zlib+b64 — truoc fix decode sai nen search_fields
        luon tra rong. Phai tim thay field ma_kh."""
        path = self.write_controller(
            "Dir\\SearchTran.xml", "dir", fields=["ma_kh", "ten_kh"])
        run_incremental_write(path, 'update', self.controllers_root,
                              self.graph_dir, None)

        store = KuzuIndexStore(self.db_path, read_only=False)
        hits = store.search_fields(["ma_kh"])
        self.assertTrue(hits, "search_fields phai tim thay ma_kh")
        self.assertTrue(
            any(h.get("relative_path") == "Dir\\SearchTran.xml" for h in hits))
        self.assertTrue(any(h.get("field_name") == "ma_kh" for h in hits))


class TestMovedAndDebounce(BaseTempProject):
    def test_moved_xml_to_bak_deletes_node(self):
        """Bug cu: suffix .bak o dest lam return ca event -> node .xml stale.
        Gio phai xoa duoc node cu."""
        path = self.write_controller("Grid\\ToBak.xml", "grid")
        handler = GraphUpdateHandler(self.controllers_root, self.graph_dir)
        handler.debounce_seconds = 0
        handler.on_any_event(FileCreatedEvent(str(path)))
        self.assertEqual(self.node_count("Grid\\ToBak.xml"), 1)

        bak = path.with_suffix(".bak")
        path.rename(bak)
        handler.on_any_event(FileMovedEvent(str(path), str(bak)))
        self.assertEqual(self.node_count("Grid\\ToBak.xml"), 0)

    def test_moved_tmp_to_xml_creates_node(self):
        """Atomic save cua editor: ghi .tmp roi rename -> .xml. Bug cu event
        bi nuot boi src .tmp. Gio dest .xml phai tao node."""
        target = self.write_controller("Grid\\AtomicSave.xml", "grid")
        tmp = target.with_suffix(".tmp")
        handler = GraphUpdateHandler(self.controllers_root, self.graph_dir)
        handler.debounce_seconds = 0
        handler.on_any_event(FileMovedEvent(str(tmp), str(target)))
        self.assertEqual(self.node_count("Grid\\AtomicSave.xml"), 1)

    def test_delete_then_create_not_swallowed_by_debounce(self):
        """Tool save kieu delete->create trong <1s: event created phai duoc
        xu ly (debounce tach nhom), node quay lai."""
        path = self.write_controller("Grid\\DelCreate.xml", "grid")
        run_incremental_write(path, 'update', self.controllers_root,
                              self.graph_dir, None)
        self.assertEqual(self.node_count("Grid\\DelCreate.xml"), 1)

        handler = GraphUpdateHandler(self.controllers_root, self.graph_dir)
        handler.debounce_seconds = 1.0  # bat debounce that

        path.unlink()
        handler.on_any_event(FileDeletedEvent(str(path)))
        self.assertEqual(self.node_count("Grid\\DelCreate.xml"), 0)

        path.write_text(
            '<?xml version="1.0"?><grid><field name="x"/></grid>',
            encoding="utf-8")
        handler.on_any_event(FileCreatedEvent(str(path)))
        self.assertEqual(self.node_count("Grid\\DelCreate.xml"), 1,
                         "created sau deleted trong cua so debounce bi nuot")

    def test_create_then_modify_debounces_to_one_write(self):
        """Editor save ban create+modify trong <1s — cung nhom 'write' nen
        chi ghi 1 lan vao Kuzu."""
        path = self.write_controller("Grid\\BurstSave.xml", "grid")
        handler = GraphUpdateHandler(self.controllers_root, self.graph_dir)
        handler.debounce_seconds = 1.0

        with mock.patch.object(watcher_mod, "run_incremental_write") as m_write:
            handler.on_any_event(FileCreatedEvent(str(path)))
            handler.on_any_event(FileModifiedEvent(str(path)))
            handler.on_any_event(FileModifiedEvent(str(path)))
            self.assertEqual(m_write.call_count, 1,
                             "create+modify lien tiep chi nen ghi 1 lan")

            # delete va create khac nhom -> ca 2 deu chay
            handler.on_any_event(FileDeletedEvent(str(path)))
            handler.on_any_event(FileCreatedEvent(str(path)))
            self.assertEqual(m_write.call_count, 3)

    def test_debounce_dict_sweeps_stale_entries(self):
        """last_triggered phai duoc don de khong phinh vo han."""
        handler = GraphUpdateHandler(self.controllers_root, self.graph_dir)
        handler.debounce_seconds = 1.0
        old = time.time() - 3600
        handler.last_triggered = {
            (f"C:\\old\\f{i}.xml", "write"): old for i in range(2100)
        }
        p = self.write_controller("Grid\\Sweep.xml", "grid")
        handler.on_any_event(FileCreatedEvent(str(p)))
        self.assertLess(len(handler.last_triggered), 100,
                        "entry cu phai bi sweep khi dict vuot nguong")


class TestReconcile(BaseTempProject):
    def test_reconcile_adds_missed_and_removes_orphan(self):
        """Watcher miss event -> reconcile tu dua vao; file bi xoa ngoai
        watcher -> node orphan bi don."""
        # Seed 1 node qua write truc tiep (gia lap da index tu truoc)
        keep = self.write_controller("Grid\\Keep.xml", "grid")
        run_incremental_write(keep, 'update', self.controllers_root,
                              self.graph_dir, None)
        self.assertEqual(self.node_count("Grid\\Keep.xml"), 1)

        # Missed: file moi tao ra ma khong co event nao chay
        missed = self.write_controller("Grid\\Missed.xml", "grid")
        stats = reconcile_graph_with_disk(self.controllers_root, self.graph_dir)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(self.node_count("Grid\\Missed.xml"), 1)

        # Orphan: file mat tren disk nhung node con trong DB
        missed.unlink()
        stats = reconcile_graph_with_disk(self.controllers_root, self.graph_dir)
        self.assertEqual(stats["deleted"], 1)
        self.assertEqual(self.node_count("Grid\\Missed.xml"), 0)

        # Round 2: khong drift -> khong ghi gi
        stats = reconcile_graph_with_disk(self.controllers_root, self.graph_dir)
        self.assertEqual((stats["updated"], stats["deleted"], stats["pending"]),
                         (0, 0, 0))

    def test_reconcile_detects_content_change_and_f_stub(self):
        """File sua ngoai watcher (mtime/size doi) + file .f don le -> stub."""
        path = self.write_controller("Grid\\Drift.xml", "grid", fields=["a"])
        run_incremental_write(path, 'update', self.controllers_root,
                              self.graph_dir, None)

        time.sleep(0.05)
        path.write_text(
            '<?xml version="1.0"?><grid><field name="a"/>'
            '<field name="b_moi"/></grid>',
            encoding="utf-8")
        # .f khong co .xml -> node stub needs_xml
        f_only = self.controllers_root / "Grid" / "OnlyF.f"
        f_only.write_bytes(b"\x00\x00\x00encrypted")

        stats = reconcile_graph_with_disk(self.controllers_root, self.graph_dir)
        self.assertGreaterEqual(stats["updated"], 2)
        self.assertEqual(self.node_count("Grid\\OnlyF.xml"), 1)

        # .xml xuat hien sau .f: reconcile cap nhat stub -> node that
        self.write_controller("Grid\\OnlyF.xml", "grid", fields=["real_f"])
        stats = reconcile_graph_with_disk(self.controllers_root, self.graph_dir)
        store = KuzuIndexStore(self.db_path, read_only=False)
        rows = store.conn.execute(
            "MATCH (n:XmlFile {relative_path: $p}) RETURN n.needs_xml",
            {"p": "Grid\\OnlyF.xml"})
        self.assertTrue(rows.has_next())
        self.assertFalse(rows.get_next()[0],
                         "Stub .f phai duoc thay bang node XML that")


class TestElection(BaseTempProject):
    def test_two_instances_same_process(self):
        """2 watcher object cung process (cung PID) khong duoc cung giu quyen —
        phan biet bang instance token."""
        o1 = _WatcherOwnership(self.graph_dir)
        o2 = _WatcherOwnership(self.graph_dir)
        self.assertTrue(o1.try_acquire())
        try:
            self.assertFalse(o2.try_acquire(),
                             "instance thu 2 khong duoc acquire khi o1 con song")
        finally:
            o1.release()
        try:
            self.assertTrue(o2.try_acquire(),
                            "sau khi o1 release, o2 phai acquire duoc")
        finally:
            o2.release()


class TestBulkBuildPaths(BaseTempProject):
    def test_bulk_build_writes_backslash_relative_path(self):
        """sync_graph CSV writer phai ghi 'Dir\\X.xml' (backslash) — khop
        convention incremental + query exact-match."""
        self.write_controller("Dir\\BTran.xml", "dir")
        self.write_controller("Grid\\BGrid.xml", "grid")
        build_and_save_graph(self.controllers_root, self.graph_dir)

        store = self.open_store()
        try:
            res = store.conn.execute(
                "MATCH (n:XmlFile) WHERE n.relative_path = $p RETURN count(*)",
                {"p": "Dir\\BTran.xml"})
            self.assertEqual(res.get_next()[0], 1,
                             "relative_path phai la backslash Dir\\BTran.xml")
            res2 = store.conn.execute(
                "MATCH (n:XmlFile) RETURN n.relative_path")
            while res2.has_next():
                rel = res2.get_next()[0]
                self.assertNotIn("/", rel,
                                 f"relative_path khong duoc chua '/': {rel}")
        finally:
            close_cached_database(self.db_path)


@unittest.skipIf(sys.platform != "win32", "AF_PIPE chi co tren Windows")
class TestDaemonPipeEndToEnd(unittest.TestCase):
    """Spawn daemon that tren project gia -> write + query qua named pipe.
    Day la case single-accessor: test process KHONG mo file kuzu, moi thao
    tac deu di qua daemon."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.project_root = self.test_dir / "Proj"
        self.controllers = self.project_root / "App_Data" / "Controllers"
        (self.controllers / "Dir").mkdir(parents=True)
        (self.controllers / "Grid").mkdir(parents=True)
        (self.controllers / "Filter").mkdir(parents=True)
        self.kuzu_base = self.test_dir / "KuzuDB"
        self.kuzu_base.mkdir()
        self.ref_file = self.controllers / "Dir" / "RefProbe.xml"
        self.ref_file.write_text(
            '<?xml version="1.0"?><dir></dir>', encoding="utf-8")
        self.daemon_proc = None

    def tearDown(self):
        if self.daemon_proc is not None:
            try:
                self.daemon_proc.terminate()
                self.daemon_proc.wait(timeout=5)
            except Exception:
                try:
                    self.daemon_proc.kill()
                except Exception:
                    pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _start_daemon(self):
        env = dict(os.environ)
        env["FBOGRAPH_KUZU_BASE"] = str(self.kuzu_base)
        env["PYTHONIOENCODING"] = "utf-8"
        daemon_script = (Path(__file__).resolve().parent.parent
                         / "service" / "daemon.py")
        self.daemon_proc = subprocess.Popen(
            [sys.executable, str(daemon_script), "--ref", str(self.ref_file)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        from multiprocessing.connection import Client
        from xml_fbograph.service.daemon import get_pipe_name
        pipe_name = get_pipe_name(self.ref_file)
        deadline = time.time() + 25
        while time.time() < deadline:
            if self.daemon_proc.poll() is not None:
                self.fail(f"daemon chet som, exit code {self.daemon_proc.returncode}")
            try:
                conn = Client(pipe_name, 'AF_PIPE')
                conn.close()
                return
            except Exception:
                time.sleep(0.5)
        self.fail("daemon khong bind pipe trong 25s")

    def _rpc(self, payload, timeout=60):
        from xml_fbograph.service.daemon_client import daemon_rpc
        res = daemon_rpc(self.ref_file, payload, timeout=timeout)
        self.assertIsNotNone(res, "daemon_rpc tra None — daemon khong phan hoi")
        return res

    def test_daemon_write_then_query_via_pipe(self):
        self._start_daemon()

        # 1. Write RPC: file moi -> daemon ghi incremental
        new_file = self.controllers / "Dir" / "DaemonTran.xml"
        new_file.write_text(
            '<?xml version="1.0"?><dir><field name="ma_dvcs"/></dir>',
            encoding="utf-8")
        res = self._rpc({
            "query_type": "write",
            "file_path": str(new_file),
            "action": "update",
        })
        self.assertTrue(res.get("ok"), f"write RPC fail: {res}")
        self.assertEqual(res.get("relative_path"), "Dir\\DaemonTran.xml")

        # 2. Query search qua pipe: daemon doc DB (process test khong mo file)
        res = self._rpc({
            "query_type": "search",
            "target": "DaemonTran",
            "ref_file": str(self.ref_file),
            "kwargs": {},
        })
        self.assertNotIn("error", res,
                         f"search query loi: {json.dumps(res)[:400]}")
        self.assertIn("DaemonTran", json.dumps(res, ensure_ascii=False))

        # 3. Radar mode=schema qua pipe — kwargs forwarding (truoc bug drop
        # mode nen schema request bi chay nhu query voi cypher rong)
        res = self._rpc({
            "query_type": "radar",
            "target": "",
            "ref_file": str(self.ref_file),
            "kwargs": {"mode": "schema"},
        })
        self.assertNotIn("error", res,
                         f"radar schema loi: {json.dumps(res)[:400]}")
        self.assertIn("XmlFile", json.dumps(res, ensure_ascii=False))

        # 4. Xoa node qua pipe
        res = self._rpc({
            "query_type": "write",
            "file_path": str(new_file),
            "action": "delete",
        })
        self.assertTrue(res.get("ok"))

        # 5. Second daemon spawn: phai thoat vi .daemon_owner da co chu
        #    (AF_PIPE cho nhieu listener trung ten — election chan dieu do)
        env = dict(os.environ)
        env["FBOGRAPH_KUZU_BASE"] = str(self.kuzu_base)
        daemon_script = (Path(__file__).resolve().parent.parent
                         / "service" / "daemon.py")
        dup = subprocess.Popen(
            [sys.executable, str(daemon_script), "--ref", str(self.ref_file)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True)
        try:
            dup.wait(timeout=20)
            self.assertEqual(dup.returncode, 0,
                             "daemon trung phai exit(0) do election")
        except subprocess.TimeoutExpired:
            dup.kill()
            self.fail("daemon trung khong thoat — election .daemon_owner hong")


if __name__ == "__main__":
    unittest.main()
