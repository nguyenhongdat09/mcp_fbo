import os
import sys
import json
import time
import hashlib
import argparse
import threading
from pathlib import Path
from multiprocessing.connection import Listener, Client

sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))

from xml_fbograph.core.schema import GraphNode
from xml_fbograph.query.engine import xml_graph_query, _graph_cache
from xml_fbograph.storage.kuzu_index import KuzuIndexStore
from xml_fbograph.utils.path_helper import ProjectPathHelper
from xml_fbograph.service.watcher import start_watcher

last_activity_time = time.time()
active_clients = 0

def get_pipe_name(ref_file: Path) -> str:
    helper = ProjectPathHelper(str(ref_file))
    root_str = str(helper.get_project_root().resolve()).lower().replace('\\', '/')
    project_hash = hashlib.sha1(root_str.encode('utf-8')).hexdigest()[:16]
    return f"\\\\.\\pipe\\xml_fbograph_{project_hash}"

def idle_checker(timeout_seconds=300):
    global last_activity_time, active_clients
    print(f"[Daemon] Idle checker started (timeout: {timeout_seconds}s)")
    while True:
        time.sleep(10)
        now = time.time()
        if active_clients == 0 and (now - last_activity_time > timeout_seconds):
            print(f"[Daemon] Shutting down due to inactivity ({timeout_seconds}s idle).")
            os._exit(0)

def handle_client(conn, helper: ProjectPathHelper):
    global last_activity_time, active_clients
    active_clients += 1
    last_activity_time = time.time()
    try:
        msg_raw = conn.recv()
        msg = json.loads(msg_raw)
        query_type = msg.get("query_type")
        target = msg.get("target")
        ref_file = msg.get("ref_file")
        kwargs = msg.get("kwargs", {})
        
        if query_type == "radar":
            from xml_fbograph.mcp_tools import mcp_query_radar
            raw_res = mcp_query_radar(target, ref_file, mode=kwargs.get("mode", "query"))
            try:
                result = json.loads(raw_res)
            except Exception:
                result = {"output": raw_res}
        elif query_type == "write":
            result = _handle_write_rpc(msg, helper)
        else:
            result = xml_graph_query(query_type, target, ref_file, **kwargs)
            
        conn.send(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        # Gate errors (invalid ref, not-FBO project, build fail) mang payload
        # structured — chuyen nguyen ve client de agent doc duoc hint.
        try:
            payload = getattr(e, "payload", None)
            body = payload if isinstance(payload, dict) else {"error": str(e)}
            conn.send(json.dumps(body, ensure_ascii=False))
        except Exception:
            pass
    finally:
        conn.close()
        active_clients -= 1
        last_activity_time = time.time()

def _handle_write_rpc(msg: dict, helper: ProjectPathHelper) -> dict:
    """Write RPC qua named pipe: watcher cua process khac route vao day de
    daemon dong vai tro single writer. allow_daemon=False de tranh vong lap."""
    from xml_fbograph.service.watcher import run_incremental_write
    fp = Path(msg.get("file_path") or "")
    action = msg.get("action") or "update"
    out = run_incremental_write(
        fp, action,
        helper.get_controllers_path(),
        helper.get_graph_dir(),
        allow_daemon=False,
    )
    resp = {"ok": True, "relative_path": None, "node": None}
    if isinstance(out, GraphNode):
        resp["node"] = dict(out.__dict__)
        resp["relative_path"] = out.relative_path
        gk = str(helper.get_graph_dir())
        cached = _graph_cache.get(gk)
        if cached:
            cached[1].add_node(out)
    elif out:
        resp["relative_path"] = str(out)
    return resp


def run_daemon(ref_file_path: Path):
    global last_activity_time
    os.environ["FBOGRAPH_DAEMON"] = "1"  # watcher trong daemon ghi truc tiep, khong vong pipe
    ref_file_path = Path(ref_file_path).resolve()
    helper = ProjectPathHelper(str(ref_file_path))
    controllers_dir = helper.get_controllers_path()
    graph_dir = helper.get_graph_dir()
    db_path = graph_dir / "kuzu"

    # Chi 1 daemon/project: named pipe AF_PIPE chap nhan nhieu listener trung
    # ten — khong election thi 2 daemon spawn cung luc cung nhan request ->
    # 2 process mo cung file Kuzu -> lock fight.
    from xml_fbograph.service.watcher import _WatcherOwnership
    daemon_ownership = _WatcherOwnership(graph_dir, lock_name=".daemon_owner")
    if not daemon_ownership.try_acquire():
        print(f"[Daemon] Mot daemon khac dang giu project nay ({graph_dir}/.daemon_owner) — thoat.")
        sys.exit(0)

    def watcher_thread():
        print(f"[Daemon Watcher] Starting file watcher for: {controllers_dir}")
        try:
            def update_in_memory_cache(node):
                global last_activity_time
                last_activity_time = time.time()
                graph_dir_key = str(graph_dir)
                if graph_dir_key in _graph_cache:
                    _, graph = _graph_cache[graph_dir_key]
                    graph.add_node(node)
                    print(f"[Daemon Cache] Hot-reloaded in-memory node: {node.relative_path}")
            start_watcher(controllers_dir, graph_dir, on_node_updated=update_in_memory_cache)
        except Exception as e:
            print(f"[Daemon Watcher] Error in watcher thread: {e}")

    w_t = threading.Thread(target=watcher_thread, daemon=True)
    w_t.start()

    idle_t = threading.Thread(target=idle_checker, daemon=True)
    idle_t.start()

    pipe_name = get_pipe_name(ref_file_path)
    print(f"[Daemon] Starting Named Pipe Server on {pipe_name}")
    try:
        listener = Listener(pipe_name, 'AF_PIPE')
    except Exception as e:
        print(f"[Daemon] Error creating named pipe: {e}")
        sys.exit(1)

    while True:
        try:
            conn = listener.accept()
            t = threading.Thread(target=handle_client, args=(conn, helper), daemon=True)
            t.start()
        except Exception as e:
            print(f"[Daemon] Connection accept error: {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XML FBOGraph Daemon Service")
    parser.add_argument("--ref", required=True, help="Reference file to identify the project")
    args = parser.parse_args()
    run_daemon(Path(args.ref))
