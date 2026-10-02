import os
import time
import json
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from xml_fbograph.core.schema import GraphNode
from xml_fbograph.storage.kuzu_index import KuzuIndexStore
from xml_fbograph.builder.graph_builder import GraphBuilder, build_and_save_graph, incremental_update_file, delete_node_by_path
from xml_fbograph.utils.path_helper import get_graph_scan_roots, is_graph_scope_file
from xml_fbograph.utils.kuzu_build_spawn import _pid_alive

def invalidate_project_cache(graph_dir: Path):
    """Giai phong cache RAM cua engine va close database connection de tranh conflict lock Kuzu."""
    try:
        import gc
        graph_dir_key = str(graph_dir.resolve())
        db_path = (graph_dir / "kuzu").resolve()
        
        # 1. Invalidate engine caches
        try:
            from xml_fbograph.query import engine as qe
            qe._store_cache.pop(graph_dir_key, None)
            qe._graph_cache.pop(graph_dir_key, None)
            qe._last_sync_times.pop(graph_dir_key, None)
        except Exception:
            pass
            
        # 2. Invalidate mcp_tools caches
        try:
            from xml_fbograph import mcp_tools as mt
            mt._kuzu_stores.pop(str(db_path), None)
        except Exception:
            pass
            
        # 3. Close Kuzu connection & DB instance
        try:
            from xml_fbograph.storage import kuzu_index as ki
            ki.close_cached_database(db_path)
        except Exception:
            pass
            
        gc.collect()
        print(f"[FBOGraph Watcher] Cleared all caches & closed DB connection for: {graph_dir_key}")
    except Exception as e:
        print(f"[FBOGraph Watcher] Warning: failed to invalidate cache: {e}")

_compact_cooldown_until = {}  # graph_dir_key -> ts; tranh rebuild lap khi data that su lon

def maybe_compact_kuzu_db(graph_dir: Path, controllers_root: Path) -> bool:
    """Neu file kuzu vuot nguong -> build_and_save_graph (sync_graph gio ghi file
    moi nen file se thu nho ve dung kich thuoc data). Kuzu khong reclaim pages
    sau DELETE/DROP nen day la cach duy nhat de giam dung luong."""
    from xml_fbograph.storage.kuzu_index import kuzu_db_needs_compact
    db_path = graph_dir / "kuzu"
    if not kuzu_db_needs_compact(db_path):
        return False
    key = str(graph_dir.resolve())
    now = time.time()
    if now < _compact_cooldown_until.get(key, 0):
        return False
    try:
        size_mb = db_path.stat().st_size / (1024 * 1024)
    except Exception:
        size_mb = -1
    print(f"[FBOGraph Watcher] Kuzu DB {size_mb:.0f}MB vuot nguong compact -> rebuild file moi.")
    try:
        invalidate_project_cache(graph_dir)
        build_and_save_graph(controllers_root, graph_dir)
        # Neu sau rebuild van vuot nguong -> data that su lon, chi thu lai sau 24h
        still_big = kuzu_db_needs_compact(db_path)
        _compact_cooldown_until[key] = now + (86400 if still_big else 3600)
        return True
    except Exception as e:
        print(f"[FBOGraph Watcher] Compact Kuzu failed: {e}")
        _compact_cooldown_until[key] = now + 3600
        return False


# Mutex serialize moi thao tac ghi trong process (event watcher, reconcile,
# write-RPC tu daemon) — tranh invalidate dung giua chung mot write khac.
_incremental_write_mutex = threading.Lock()


def _running_inside_daemon() -> bool:
    return os.environ.get("FBOGRAPH_DAEMON", "").strip() == "1"


def _write_via_daemon(controllers_root: Path, graph_dir: Path, file_path: Path, action: str, timeout: float = 30.0):
    """Thu route write qua daemon named-pipe (daemon = single writer on dinh).
    Tra ve dict response neu daemon xu ly; None neu daemon khong chay/fail.
    Khong autostart — watcher tu ghi duoc khi daemon vang."""
    try:
        from xml_fbograph.service.daemon_client import daemon_rpc
        res = daemon_rpc(controllers_root, {
            "query_type": "write",
            "file_path": str(file_path),
            "action": action,
        }, timeout=timeout, autostart=False)
        if res and res.get("ok"):
            return res
    except Exception:
        pass
    return None


def _graph_node_from_payload(payload):
    """Rebuild GraphNode tu dict node do daemon tra ve."""
    if not isinstance(payload, dict):
        return None
    try:
        return GraphNode(**payload)
    except Exception:
        try:
            valid = set(GraphNode.__dataclass_fields__)
            return GraphNode(**{k: v for k, v in payload.items() if k in valid})
        except Exception:
            return None


def run_incremental_write(file_path: Path, action: str, controllers_root: Path, graph_dir: Path,
                          on_node_updated=None, allow_daemon: bool = True,
                          defer_cache_invalidate: bool = False):
    """
    Thực hiện ghi thay đổi vào Kuzu DB an toàn với retry logic và proactively clear cache.
    action: 'update' (created/modified) or 'delete' (deleted)
    allow_daemon=False: bo qua route qua daemon pipe (dung trong chinh process daemon).
    defer_cache_invalidate=True: bo qua invalidate/compact moi lan ghi (caller tu invalidate
    mot lan o dau/cuoi batch — dung cho reconcile quet nhieu file).
    """
    from xml_fbograph.utils.path_helper import is_db_owner
    if not is_db_owner(controllers_root, graph_dir):
        print(f"[FBOGraph Watcher] user_multi_db_yn=0: Ignored write for {file_path} because project is not owner of {graph_dir}")
        return None

    controllers_root = Path(controllers_root)
    graph_dir = Path(graph_dir)

    # Uu tien route write qua daemon pipe: khi daemon song thi no la single
    # writer duy nhat, moi process khac chi la reader -> khong lock fight.
    if allow_daemon and not _running_inside_daemon():
        daemon_res = _write_via_daemon(controllers_root, graph_dir, Path(file_path), action)
        if daemon_res is not None:
            invalidate_project_cache(graph_dir)
            node = _graph_node_from_payload(daemon_res.get("node"))
            rel = daemon_res.get("relative_path")
            if node is not None:
                print(f"[FBOGraph Watcher] Daemon da cap nhat: {node.relative_path}")
                if on_node_updated:
                    try:
                        on_node_updated(node)
                    except Exception:
                        pass
                return node
            if rel:
                print(f"[FBOGraph Watcher] Daemon da xoa node '{rel}' khoi Kuzu.")
            return rel or None
        # Daemon khong chay -> fallback ghi truc tiep (da co election ben ngoai)

    db_path = graph_dir / "kuzu"
    max_retries = 5
    base_delay = 0.5

    with _incremental_write_mutex:
        for attempt in range(max_retries):
            try:
                # 1. Proactively close any existing RO connections in this process to avoid self-locking
                if not defer_cache_invalidate:
                    invalidate_project_cache(graph_dir)

                # 2. Perform the write action (KuzuIndexStore read_only=False inside these functions will acquire lock)
                if action == 'delete':
                    rel_path = delete_node_by_path(controllers_root, db_path, file_path)
                    if rel_path:
                        print(f"[FBOGraph Watcher] Da xoa node '{rel_path}' khoi Kuzu.")
                    # After write, invalidate again so next query gets fresh data
                    if not defer_cache_invalidate:
                        invalidate_project_cache(graph_dir)
                        maybe_compact_kuzu_db(graph_dir, controllers_root)
                    return rel_path
                else:
                    node = incremental_update_file(file_path, controllers_root, db_path)
                    if node:
                        print(f"[FBOGraph Watcher] Da cap nhat thanh cong: {node.relative_path}")
                        if on_node_updated:
                            on_node_updated(node)
                    # After write, invalidate again
                    if not defer_cache_invalidate:
                        invalidate_project_cache(graph_dir)
                        maybe_compact_kuzu_db(graph_dir, controllers_root)
                    return node

            except Exception as e:
                err_msg = str(e)
                if "lock" in err_msg.lower() or "io exception" in err_msg.lower():
                    print(f"[FBOGraph Watcher] Attempt {attempt + 1}/{max_retries}: Lock conflict on {db_path}. Retrying in {base_delay}s... ({e})")
                    time.sleep(base_delay)
                    base_delay *= 2  # Exponential backoff
                else:
                    print(f"[FBOGraph Watcher] Error during incremental write for {file_path}: {e}")
                    # Invalidate to be safe
                    if not defer_cache_invalidate:
                        invalidate_project_cache(graph_dir)
                    break

    print(f"[FBOGraph Watcher] ERROR: Failed to write {file_path} after {max_retries} retries due to lock conflicts.")
    return None


# ---------------------------------------------------------------------------
# Reconcile dinh ky: quet lai file trong scope, diff mtime/size voi Kuzu.
# Tu chua moi event watcher bi miss (process down, polling drop, lock fail het
# retry) ma khong can full rebuild.
# ---------------------------------------------------------------------------

RECONCILE_FIRST_DELAY_SEC = 20.0


def _get_reconcile_seconds() -> float:
    """Chu ky reconcile (giay). 0 = tat. env FBOGRAPH_RECONCILE_SECONDS >
    config.yaml fbograph.reconcile_seconds > mac dinh 300s."""
    env_val = os.environ.get("FBOGRAPH_RECONCILE_SECONDS", "").strip()
    if env_val:
        try:
            return max(0.0, float(env_val))
        except ValueError:
            pass
    val = 300.0
    try:
        import yaml
        from xml_fbograph.utils.path_helper import _find_config_file
        config_file = _find_config_file()
        if config_file:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            fbograph_cfg = cfg.get("fbograph", {})
            if "reconcile_seconds" in fbograph_cfg:
                val = float(fbograph_cfg["reconcile_seconds"])
    except Exception:
        pass
    return max(0.0, val)


def reconcile_graph_with_disk(controllers_root: Path, graph_dir: Path, max_files: int = 500) -> dict:
    """Quet file trong scope tren disk, diff (last_modified, file_size) voi Kuzu,
    ghi incremental cho file moi/thay doi/mat file."""
    from xml_fbograph.utils.path_helper import is_db_owner
    controllers_root = Path(controllers_root).resolve()
    graph_dir = Path(graph_dir).resolve()
    stats = {"scanned": 0, "updated": 0, "deleted": 0, "pending": 0}
    if not is_db_owner(controllers_root, graph_dir):
        return stats
    db_path = graph_dir / "kuzu"
    if not db_path.exists():
        return stats

    # 1. Tap file expected tren disk (giong GraphBuilder.build: bo .f khi co .xml cung ten)
    raw_files = []
    for scan_root in get_graph_scan_roots(controllers_root):
        try:
            for item in scan_root.iterdir():
                if item.is_file() and item.suffix.lower() in {".xml", ".f"}:
                    raw_files.append(item)
        except Exception:
            continue
    xml_stems = {(f.parent, f.stem.lower()) for f in raw_files if f.suffix.lower() == ".xml"}
    expected = {}  # node_rel_key ('/' + lower, .f -> .xml) -> abs path
    for f in raw_files:
        if f.suffix.lower() == ".f" and (f.parent, f.stem.lower()) in xml_stems:
            continue
        rel = os.path.relpath(f, controllers_root)
        node_rel = str(Path(rel).with_suffix(".xml")) if f.suffix.lower() == ".f" else rel
        expected[node_rel.replace("\\", "/").lower()] = f
    stats["scanned"] = len(expected)

    # 2. Trang thai node hien co trong Kuzu
    try:
        store = KuzuIndexStore(db_path)
        res = store.conn.execute(
            "MATCH (n:XmlFile) RETURN n.relative_path, n.last_modified, n.file_size")
        db_rows = {}
        while res.has_next():
            row = res.get_next()
            rel_key = (row[0] or "").replace("\\", "/").lower()
            db_rows[rel_key] = (row[0] or "", row[1] or 0.0, row[2] or 0)
    except Exception as e:
        print(f"[FBOGraph Watcher] Reconcile: khong doc duoc Kuzu {db_path}: {e}")
        return stats

    # 3. Diff
    to_update = []
    for key, fpath in expected.items():
        cur = db_rows.get(key)
        if cur is None:
            to_update.append(fpath)
            continue
        try:
            st = fpath.stat()
        except OSError:
            to_update.append(fpath)
            continue
        if float(cur[1]) != st.st_mtime or int(cur[2]) != st.st_size:
            to_update.append(fpath)

    to_delete = [(controllers_root / rel) for key, (rel, _m, _s) in db_rows.items()
                 if key not in expected]

    if not to_update and not to_delete:
        return stats

    print(f"[FBOGraph Watcher] Reconcile drift: +{len(to_update)} update, -{len(to_delete)} delete (scanned {stats['scanned']})")
    invalidate_project_cache(graph_dir)
    for fpath in to_update[:max_files]:
        if run_incremental_write(fpath, 'update', controllers_root, graph_dir,
                                 defer_cache_invalidate=True) is not None:
            stats["updated"] += 1
        else:
            stats["pending"] += 1
    for fpath in to_delete[:max_files]:
        if run_incremental_write(fpath, 'delete', controllers_root, graph_dir,
                                 defer_cache_invalidate=True) is not None:
            stats["deleted"] += 1
        else:
            stats["pending"] += 1
    stats["pending"] += max(0, len(to_update) - max_files) + max(0, len(to_delete) - max_files)
    invalidate_project_cache(graph_dir)
    maybe_compact_kuzu_db(graph_dir, controllers_root)
    return stats


def _reconcile_loop(controllers_root: Path, graph_dir: Path, stop_event: threading.Event):
    interval = _get_reconcile_seconds()
    if interval <= 0:
        return
    # Pass dau som sau khi watcher khoi dong: chua cac thay doi xay ra luc
    # khong process nao dang watch (MCP down, daemon chua chay).
    if stop_event.wait(RECONCILE_FIRST_DELAY_SEC):
        return
    while not stop_event.is_set():
        try:
            stats = reconcile_graph_with_disk(controllers_root, graph_dir)
            if stats.get("updated") or stats.get("deleted") or stats.get("pending"):
                print(f"[FBOGraph Watcher] Reconcile xong: scanned={stats['scanned']} "
                      f"updated={stats['updated']} deleted={stats['deleted']} pending={stats['pending']}")
        except Exception as e:
            print(f"[FBOGraph Watcher] Reconcile error: {e}")
        stop_event.wait(interval)


# ---------------------------------------------------------------------------
# Election: chi 1 process duoc giu watcher cho 1 graph_dir (file lock + pid +
# heartbeat). Tranh nhieu MCP/agent process cung spawn watcher -> cung ghi vao
# 1 file Kuzu (Kuzu chi cho 1 writer, RO reader process khac cung block).
# ---------------------------------------------------------------------------

WATCHER_OWNER_FILE = ".watcher_owner"
WATCHER_HEARTBEAT_SEC = 15.0
WATCHER_STALE_SEC = 45.0
WATCHER_RETRY_SEC = 30.0


class _WatcherOwnership:
    """File-lock election (pid + inst + heartbeat) tren 1 graph_dir.
    Reuse cho ca watcher (.watcher_owner) lan daemon (.daemon_owner)."""

    def __init__(self, graph_dir: Path, lock_name: str = WATCHER_OWNER_FILE):
        self.graph_dir = Path(graph_dir)
        self.lock_path = self.graph_dir / lock_name
        self.pid = os.getpid()
        import uuid
        self.inst = uuid.uuid4().hex[:12]  # phan biet 2 instance cung process (test/debug)
        self._stop = threading.Event()
        self._hb_thread = None

    def _read_owner(self):
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            return (int(data.get("pid") or 0),
                    float(data.get("heartbeat") or 0.0),
                    str(data.get("inst") or ""))
        except Exception:
            return 0, 0.0, ""

    def _write_owner(self):
        payload = {"pid": self.pid, "inst": self.inst, "heartbeat": time.time()}
        tmp = self.lock_path.with_name(f"{self.lock_path.name}.{self.inst}.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, self.lock_path)

    def try_acquire(self) -> bool:
        pid, hb, inst = self._read_owner()
        foreign = inst != self.inst
        if foreign and pid and _pid_alive(pid) and (time.time() - hb) < WATCHER_STALE_SEC:
            return False
        try:
            self.graph_dir.mkdir(parents=True, exist_ok=True)
            self._write_owner()
            time.sleep(0.2)
            pid2, _, inst2 = self._read_owner()
            if pid2 == self.pid and inst2 == self.inst:
                self._start_heartbeat()
                return True
        except Exception:
            pass
        return False

    def _start_heartbeat(self):
        if self._hb_thread is not None:
            return

        def beat():
            while not self._stop.wait(WATCHER_HEARTBEAT_SEC):
                try:
                    self._write_owner()
                except Exception:
                    pass

        self._hb_thread = threading.Thread(target=beat, daemon=True)
        self._hb_thread.start()

    def release(self):
        self._stop.set()
        try:
            pid, _, inst = self._read_owner()
            if pid == self.pid and inst == self.inst:
                self.lock_path.unlink()
        except Exception:
            pass


class GraphUpdateHandler(FileSystemEventHandler):
    def __init__(self, controllers_root: Path, graph_dir: Path, on_node_updated=None):
        self.controllers_root = Path(controllers_root).resolve()
        self.graph_dir = Path(graph_dir).resolve()
        self.db_path = self.graph_dir / "kuzu"
        self.last_triggered = {}           # (src_path, debounce_group) -> ts
        self.debounce_seconds = 1.0        # Debounce per-file-per-type tranh trigger ghi de lien tuc
        self.on_node_updated = on_node_updated
        self.write_lock = threading.Lock() # Tranh chap giua cac event watcher ghi song song
        self._debounce_sweep_at = 0.0

    def _path_relevant(self, path) -> bool:
        """File co thuoc scope graph va la .xml/.f hay khong (check doc lap tung phia cua event)."""
        if not path:
            return False
        if Path(path).suffix.lower() not in {".xml", ".f"}:
            # Comment: đổi nội dung Include mà không đụng XML cha -> flat trên graph
            # chỉ cập nhật khi XML được re-parse/rebuild
            return False
        if "kuzu" in str(path):
            return False
        return is_graph_scope_file(path, self.controllers_root)

    def _debounced(self, event) -> bool:
        """Debounce theo (path, nhom event). 'deleted' tach rieng de cap
        delete->create (atomic rewrite) khong bi nuot; 'created'/'modified' gop
        chung nhom 'write' de mot lan save khong ghi 2 lan."""
        now = time.time()
        group = "deleted" if event.event_type == "deleted" else (
            "moved" if event.event_type == "moved" else "write")
        key = (str(event.src_path), group)
        last = self.last_triggered.get(key)
        if last is not None and now - last < self.debounce_seconds:
            return True
        self.last_triggered[key] = now
        # 'deleted' la ranh gioi phien file: xoa entry nhom 'write' de create
        # ngay sau delete (atomic rewrite/git checkout) khong bi nuot boi
        # timestamp cua event write truoc do.
        if event.event_type == "deleted":
            self.last_triggered.pop((str(event.src_path), "write"), None)

        # Don dep dinh ky de dict khong phinh vo han trong process song lau
        if now >= self._debounce_sweep_at or len(self.last_triggered) > 2048:
            cutoff = now - max(300.0, self.debounce_seconds * 10)
            self.last_triggered = {k: v for k, v in self.last_triggered.items() if v >= cutoff}
            self._debounce_sweep_at = now + 300.0
        return False

    def _handle_deleted(self, file_path: Path):
        suffix = file_path.suffix.lower()
        # Logic pairing giua .xml va .f khi xoa/move di
        if suffix == ".xml":
            f_paired = file_path.with_suffix(".f")
            if f_paired.is_file():
                print(f"[FBOGraph Watcher] File .xml bi xoa, phuc hoi node tu file .f cung ten: {f_paired}")
                run_incremental_write(f_paired, 'update', self.controllers_root, self.graph_dir, self.on_node_updated)
                return
        elif suffix == ".f":
            xml_paired = file_path.with_suffix(".xml")
            if xml_paired.is_file():
                print(f"[FBOGraph Watcher] File .f bi xoa, nhung file .xml cung ten van con, khong can xoa node.")
                return
        print(f"[FBOGraph Watcher] Xoa node: {file_path}")
        run_incremental_write(file_path, 'delete', self.controllers_root, self.graph_dir, self.on_node_updated)

    def _handle_updated(self, file_path: Path):
        print(f"[FBOGraph Watcher] Cap nhat node: {file_path}")
        run_incremental_write(file_path, 'update', self.controllers_root, self.graph_dir, self.on_node_updated)

    def on_any_event(self, event):
        if event.is_directory:
            return

        # Kiem tra doc lap tung phia: src quyet dinh nhanh xoa, dest quyet dinh
        # nhanh tao — move '.xml -> .bak' van xoa node cu, '.tmp -> .xml'
        # (atomic save) van tao node moi.
        src_ok = self._path_relevant(event.src_path)
        dest_path = getattr(event, 'dest_path', None)
        dest_ok = self._path_relevant(dest_path)

        if not src_ok and not dest_ok:
            return
        if self._debounced(event):
            return

        with self.write_lock:
            print(f"[FBOGraph Watcher] Phat hien su kien '{event.event_type}' tren: {event.src_path}")

            try:
                if event.event_type == 'deleted':
                    if src_ok:
                        self._handle_deleted(Path(event.src_path))
                elif event.event_type == 'moved':
                    print(f"[FBOGraph Watcher] Di chuyen node tu '{event.src_path}' toi '{dest_path}'")
                    if src_ok:
                        self._handle_deleted(Path(event.src_path))
                    if dest_ok:
                        self._handle_updated(Path(dest_path))
                else:  # created hoặc modified
                    if src_ok:
                        self._handle_updated(Path(event.src_path))

            except Exception as e:
                print(f"[FBOGraph Watcher] Loi khi xu ly event watcher: {e}")


def _watcher_enabled() -> bool:
    return os.environ.get("FBOGRAPH_WATCHER", "1").strip().lower() not in ("0", "false", "no")


def start_watcher(controllers_root: Path, graph_dir: Path, on_node_updated=None):
    """Bat dau watchdog observer de theo doi su thay doi file.
    Chi process thang election (.watcher_owner) moi thuc su watch — cac process
    khac standby va cuop quyen lai khi owner chet."""
    controllers_root = Path(controllers_root).resolve()
    graph_dir = Path(graph_dir).resolve()

    if not _watcher_enabled():
        print("[FBOGraph Watcher] Disabled by FBOGRAPH_WATCHER=0")
        return

    event_handler = GraphUpdateHandler(controllers_root, graph_dir, on_node_updated=on_node_updated)

    controllers_str = str(controllers_root)
    is_unc_path = controllers_str.startswith("\\\\") or controllers_str.startswith("//")

    scan_roots = get_graph_scan_roots(controllers_root)
    if not scan_roots:
        raise FileNotFoundError(
            f"Khong tim thay scan roots hop le trong: {controllers_root}"
        )

    # Election: cho toi khi process nay giu quyen watcher
    ownership = _WatcherOwnership(graph_dir)
    announced_standby = False
    while not ownership.try_acquire():
        if not announced_standby:
            print(f"[FBOGraph Watcher] Process khac dang giu watcher cho {graph_dir} — standby, retry moi {WATCHER_RETRY_SEC:.0f}s.")
            announced_standby = True
        time.sleep(WATCHER_RETRY_SEC)
    if announced_standby:
        print(f"[FBOGraph Watcher] Da nhan quyen watcher (PID {ownership.pid}).")

    if is_unc_path:
        print(f"[FBOGraph Watcher] UNC path detected. Using PollingObserver for reliability on network shares.")
        observer = PollingObserver(timeout=1.5)
    else:
        observer = Observer()

    for scan_root in scan_roots:
        observer.schedule(event_handler, path=str(scan_root), recursive=True)

    observer.start()

    stop_event = threading.Event()
    reconcile_t = threading.Thread(
        target=_reconcile_loop,
        args=(controllers_root, graph_dir, stop_event),
        daemon=True,
    )
    reconcile_t.start()

    scan_labels = ", ".join(str(root.relative_to(controllers_root)) for root in scan_roots)
    print(f"[FBOGraph Watcher] Watcher da khoi dong tren: {scan_labels} (PID {ownership.pid}, reconcile {_get_reconcile_seconds():.0f}s)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        observer.stop()
        ownership.release()
    observer.join()
