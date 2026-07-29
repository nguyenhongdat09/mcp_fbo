import os
import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

from xml_fbograph.storage.kuzu_index import KuzuIndexStore
from xml_fbograph.builder.graph_builder import GraphBuilder, build_and_save_graph, incremental_update_file, delete_node_by_path
from xml_fbograph.utils.path_helper import get_graph_scan_roots, is_graph_scope_file

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

def run_incremental_write(file_path: Path, action: str, controllers_root: Path, graph_dir: Path, on_node_updated=None):
    """
    Thực hiện ghi thay đổi vào Kuzu DB an toàn với retry logic và proactively clear cache.
    action: 'update' (created/modified) or 'delete' (deleted)
    """
    from xml_fbograph.utils.path_helper import is_db_owner
    if not is_db_owner(controllers_root, graph_dir):
        print(f"[FBOGraph Watcher] user_multi_db_yn=0: Ignored write for {file_path} because project is not owner of {graph_dir}")
        return None

    db_path = graph_dir / "kuzu"
    max_retries = 5
    base_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            # 1. Proactively close any existing RO connections in this process to avoid self-locking
            invalidate_project_cache(graph_dir)
            
            # 2. Perform the write action (KuzuIndexStore read_only=False inside these functions will acquire lock)
            if action == 'delete':
                rel_path = delete_node_by_path(controllers_root, db_path, file_path)
                if rel_path:
                    print(f"[FBOGraph Watcher] Da xoa node '{rel_path}' khoi Kuzu.")
                # After write, invalidate again so next query gets fresh data
                invalidate_project_cache(graph_dir)
                return rel_path
            else:
                node = incremental_update_file(file_path, controllers_root, db_path)
                if node:
                    print(f"[FBOGraph Watcher] Da cap nhat thanh cong: {node.relative_path}")
                    if on_node_updated:
                        on_node_updated(node)
                # After write, invalidate again
                invalidate_project_cache(graph_dir)
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
                invalidate_project_cache(graph_dir)
                break
                
    print(f"[FBOGraph Watcher] ERROR: Failed to write {file_path} after {max_retries} retries due to lock conflicts.")
    return None


class GraphUpdateHandler(FileSystemEventHandler):
    def __init__(self, controllers_root: Path, graph_dir: Path, on_node_updated=None):
        self.controllers_root = Path(controllers_root).resolve()
        self.graph_dir = Path(graph_dir).resolve()
        self.db_path = self.graph_dir / "kuzu"
        self.last_triggered_by_path = {}
        self.debounce_seconds = 1.0  # Debounce per-file tránh trigger ghi đè liên tục
        self.on_node_updated = on_node_updated
        self.write_lock = threading.Lock() # Tranh chap giua cac event watcher ghi song song

    def on_any_event(self, event):
        if event.is_directory:
            return

        # Kiem tra file co nam trong scope scan hay khong
        src_in_scope = is_graph_scope_file(event.src_path, self.controllers_root)
        dest_in_scope = False
        if hasattr(event, 'dest_path') and event.dest_path:
            dest_in_scope = is_graph_scope_file(event.dest_path, self.controllers_root)

        if not src_in_scope and not dest_in_scope:
            return

        # Chi quan tam file xml, ent, txt, f
        for path in [event.src_path, getattr(event, 'dest_path', None)]:
            if not path:
                continue
            suffix = Path(path).suffix.lower()
            if suffix not in {".xml", ".f"}:
                # Comment: đổi nội dung Include mà không đụng XML cha -> flat trên graph
                # chỉ cập nhật khi XML được re-parse/rebuild
                return
            if "kuzu" in str(path):
                return

        # Debounce theo file path
        now = time.time()
        path_key = str(event.src_path)
        if path_key in self.last_triggered_by_path:
            if now - self.last_triggered_by_path[path_key] < self.debounce_seconds:
                return
        self.last_triggered_by_path[path_key] = now

        with self.write_lock:
            print(f"[FBOGraph Watcher] Phat hien su kien '{event.event_type}' tren: {event.src_path}")
            
            try:
                if event.event_type == 'deleted':
                    file_path = Path(event.src_path)
                    suffix = file_path.suffix.lower()
                    
                    # Logic pairing giua .xml va .f khi xoa
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
                            
                    # Xoa thuc su khoi Kuzu DB
                    print(f"[FBOGraph Watcher] Xoa node: {event.src_path}")
                    run_incremental_write(file_path, 'delete', self.controllers_root, self.graph_dir, self.on_node_updated)
                    
                elif event.event_type == 'moved':
                    print(f"[FBOGraph Watcher] Di chuyen node tu '{event.src_path}' toi '{event.dest_path}'")
                    # 1. Xoa node cu
                    if src_in_scope:
                        run_incremental_write(Path(event.src_path), 'delete', self.controllers_root, self.graph_dir, self.on_node_updated)
                    # 2. Add node moi
                    if dest_in_scope:
                        run_incremental_write(Path(event.dest_path), 'update', self.controllers_root, self.graph_dir, self.on_node_updated)
                    
                else:  # created hoặc modified
                    print(f"[FBOGraph Watcher] Cap nhat node: {event.src_path}")
                    run_incremental_write(Path(event.src_path), 'update', self.controllers_root, self.graph_dir, self.on_node_updated)
                    
            except Exception as e:
                print(f"[FBOGraph Watcher] Loi khi xu ly event watcher: {e}")

def start_watcher(controllers_root: Path, graph_dir: Path, on_node_updated=None):
    """Bat dau watchdog observer de theo doi su thay doi file."""
    controllers_root = Path(controllers_root).resolve()
    graph_dir = Path(graph_dir).resolve()
    
    event_handler = GraphUpdateHandler(controllers_root, graph_dir, on_node_updated=on_node_updated)
    
    controllers_str = str(controllers_root)
    is_unc_path = controllers_str.startswith("\\\\") or controllers_str.startswith("//")
    
    if is_unc_path:
        print(f"[FBOGraph Watcher] UNC path detected. Using PollingObserver for reliability on network shares.")
        observer = PollingObserver(timeout=1.5)
    else:
        observer = Observer()
    scan_roots = get_graph_scan_roots(controllers_root)
    if not scan_roots:
        raise FileNotFoundError(
            f"Khong tim thay scan roots hop le trong: {controllers_root}"
        )

    for scan_root in scan_roots:
        observer.schedule(event_handler, path=str(scan_root), recursive=True)

    observer.start()

    scan_labels = ", ".join(str(root.relative_to(controllers_root)) for root in scan_roots)
    print(f"[FBOGraph Watcher] Watcher da khoi dong tren: {scan_labels}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
