import os
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from xml_codegraph.storage.kuzu_index import KuzuIndexStore
from xml_codegraph.builder.graph_builder import GraphBuilder, build_and_save_graph, incremental_update_file
from xml_codegraph.utils.path_helper import get_graph_scan_roots, is_graph_scope_file

class GraphUpdateHandler(FileSystemEventHandler):
    def __init__(self, controllers_root: Path, graph_dir: Path, on_node_updated=None):
        self.controllers_root = Path(controllers_root).resolve()
        self.graph_dir = Path(graph_dir).resolve()
        self.db_path = self.graph_dir / "kuzu"
        self.last_triggered = 0.0
        self.debounce_seconds = 1.0  # Debounce tránh trigger liên tục khi lưu file
        self.on_node_updated = on_node_updated

    def on_any_event(self, event):
        if event.is_directory:
            return

        if not is_graph_scope_file(event.src_path, self.controllers_root):
            return

        # Chỉ quan tâm các file XML, ent, txt
        suffix = Path(event.src_path).suffix.lower()
        if suffix not in {".xml", ".ent", ".txt"}:
            return

        # Tránh cập nhật file graph của chính mình
        if "kuzu" in event.src_path:
            return

        now = time.time()
        if now - self.last_triggered < self.debounce_seconds:
            return
        self.last_triggered = now

        print(f"[CodeGraph Watcher] Phát hiện sự kiện '{event.event_type}' trên file: {event.src_path}")
        print("[CodeGraph Watcher] Tiến hành cập nhật incremental...")
        
        try:
            node = incremental_update_file(Path(event.src_path), self.controllers_root, self.db_path)
            if node:
                print(f"[CodeGraph Watcher] Cập nhật thành công node: {node.relative_path}")
                if self.on_node_updated:
                    self.on_node_updated(node)
            else:
                print("[CodeGraph Watcher] Cập nhật thất bại hoặc file nằm ngoài phạm vi.")
        except Exception as e:
            print(f"[CodeGraph Watcher] Lỗi khi cập nhật incremental: {e}")

def start_watcher(controllers_root: Path, graph_dir: Path, on_node_updated=None):
    """Bắt đầu chạy watchdog phục vụ giám sát file thay đổi."""
    controllers_root = Path(controllers_root).resolve()
    graph_dir = Path(graph_dir).resolve()
    
    event_handler = GraphUpdateHandler(controllers_root, graph_dir, on_node_updated=on_node_updated)
    observer = Observer()
    scan_roots = get_graph_scan_roots(controllers_root)
    if not scan_roots:
        raise FileNotFoundError(
            f"Không tìm thấy thư mục Dir/Grid/Filter/Report hoặc Templates/Upload trong: {controllers_root}"
        )

    for scan_root in scan_roots:
        observer.schedule(event_handler, path=str(scan_root), recursive=True)

    observer.start()

    scan_labels = ", ".join(str(root.relative_to(controllers_root)) for root in scan_roots)
    print(f"[CodeGraph Watcher] Watcher đã được khởi chạy trên: {scan_labels}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
