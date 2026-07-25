import sys
import argparse
import json
import subprocess
import time
from pathlib import Path
from multiprocessing.connection import Client

sys.path.append(str(Path(__file__).parent.resolve()))

from xml_codegraph.builder.graph_builder import build_and_save_graph
from xml_codegraph.query.engine import xml_graph_query
from xml_codegraph.utils.path_helper import ProjectPathHelper
from xml_codegraph.service.daemon import get_pipe_name

def cmd_build(args):
    controllers_dir = Path(args.root).resolve()
    if not controllers_dir.is_dir():
        print(f"Lỗi: Thư mục Controllers không tồn tại: {controllers_dir}")
        sys.exit(1)
        
    helper = ProjectPathHelper(controllers_dir / "dummy.xml")
    graph_dir = helper.get_graph_dir()
    
    print(f"Bắt đầu xây dựng graph cho: {controllers_dir}")
    print(f"Phạm vi quét: Dir, Grid, Filter, Report, Templates/Upload")
    print(f"Đầu ra graph sẽ được lưu tại: {graph_dir}")
    
    try:
        build_and_save_graph(controllers_dir, graph_dir)
        print("Xây dựng XML CodeGraph thành công!")
    except Exception as e:
        print(f"Lỗi khi xây dựng graph: {e}")
        sys.exit(1)

def query_via_daemon(args, reference_file: Path) -> dict:
    pipe_name = get_pipe_name(reference_file)
    
    # Chuẩn bị payload gửi daemon
    payload = {
        "query_type": args.type,
        "target": args.target,
        "ref_file": str(reference_file),
        "kwargs": {
            "folder_filter": getattr(args, "folder", None),
            "type_filter": getattr(args, "type_filter", None),
            "limit": getattr(args, "limit", 10),
            "compact": getattr(args, "compact", False),
            "match_type": getattr(args, "match_type", "all")
        }
    }
    
    for attempt in range(2):
        try:
            conn = Client(pipe_name, 'AF_PIPE')
            conn.send(json.dumps(payload))
            res = conn.recv()
            conn.close()
            return json.loads(res)
        except Exception:
            if attempt == 0:
                sys.stderr.write("[CodeGraph CLI] Không tìm thấy Daemon đang chạy. Đang tự khởi chạy Daemon...\n")
                sys.stderr.flush()
                # Spawning daemon process in background
                daemon_script = Path(__file__).parent / "xml_codegraph" / "service" / "daemon.py"
                subprocess.Popen(
                    [sys.executable, str(daemon_script), "--ref", str(reference_file)],
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True
                )
                time.sleep(1.2)  # Đợi daemon khởi động và bind Named Pipe
            else:
                # Nếu lần 2 vẫn lỗi, fallback query trực tiếp trong process hiện tại
                sys.stderr.write("[CodeGraph CLI] Fallback: Chạy query trực tiếp...\n")
                sys.stderr.flush()
                return xml_graph_query(
                    args.type, args.target, str(reference_file),
                    folder_filter=getattr(args, "folder", None),
                    type_filter=getattr(args, "type_filter", None),
                    limit=getattr(args, "limit", 10),
                    compact=getattr(args, "compact", False),
                    match_type=getattr(args, "match_type", "all")
                )

def cmd_query(args):
    reference_file = Path(args.ref).resolve()
    if not reference_file.exists():
        sys.stderr.write(f"Lỗi: File tham chiếu không tồn tại: {reference_file}\n")
        sys.exit(1)

    helper = ProjectPathHelper(str(reference_file))
    graph_dir = helper.get_graph_dir()
    kuzu_path = helper.get_kuzu_path()
    sys.stderr.write(f"[CodeGraph CLI] Project root : {helper.get_project_root()}\n")
    sys.stderr.write(f"[CodeGraph CLI] Kuzu graph dir: {graph_dir}\n")
    sys.stderr.write(f"[CodeGraph CLI] Kuzu DB file  : {kuzu_path}\n")
    sys.stderr.flush()

    if args.type == "radar":
        from xml_codegraph.mcp_tools import mcp_query_radar
        # Khi dùng radar, target chính là câu lệnh Cypher truyền vào
        cypher_query = args.target
        if not cypher_query or not cypher_query.strip():
            sys.stderr.write("Lỗi: Câu lệnh Cypher không được để trống.\n")
            sys.exit(1)
            
        if getattr(args, "direct", False):
            # Chạy trực tiếp không qua daemon
            raw_res = mcp_query_radar(cypher_query, str(reference_file))
            try:
                result = json.loads(raw_res)
            except Exception:
                result = {"output": raw_res}
        else:
            # Query thông qua daemon
            result = query_via_daemon(args, reference_file)
    else:
        if getattr(args, "direct", False):
            result = xml_graph_query(
                args.type, args.target, str(reference_file),
                folder_filter=getattr(args, "folder", None),
                type_filter=getattr(args, "type_filter", None),
                limit=getattr(args, "limit", 10),
                compact=getattr(args, "compact", False),
                match_type=getattr(args, "match_type", "all")
            )
        else:
            result = query_via_daemon(args, reference_file)
    
    if args.type in {"visualize", "mermaid"} and "mermaid" in result:
        print("\n--- MÃ BIỂU ĐỒ MERMAID (Copy nội dung dưới đây và dán vào file Markdown) ---")
        print("```mermaid")
        print(result["mermaid"])
        print("```")
        print("------------------------------------------------------------------------\n")
    else:
        # Nếu output là chuỗi JSON thô (như khi lỗi từ mcp_query_radar trả về chuỗi text bình thường)
        if isinstance(result, dict) or isinstance(result, list):
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(result)

def cmd_watch(args):
    ref_file = Path(args.ref).resolve()
    helper = ProjectPathHelper(ref_file)
    controllers_dir = helper.get_controllers_path()
    
    sys.stderr.write(f"Đang khởi chạy Watchdog giám sát: Dir, Grid, Filter, Report, Templates/Upload\n")
    sys.stderr.write(f"Thư mục Controllers: {controllers_dir}\n")
    sys.stderr.flush()
    from xml_codegraph.service.watcher import start_watcher
    start_watcher(controllers_dir, helper.get_graph_dir())

def main():
    # PowerShell cũ hay lỗi font tiếng Việt — ép UTF-8 cho stdin/stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
        
    parser = argparse.ArgumentParser(description="XML CodeGraph CLI Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_build = subparsers.add_parser("build", help="Xây dựng graph từ đầu")
    parser_build.add_argument("--root", required=True, help="Đường dẫn thư mục Controllers")
    
    parser_query = subparsers.add_parser("query", help="Truy vấn thông tin graph")
    parser_query.add_argument("-t", "--type", required=True, choices=["search", "context", "dependencies", "dependents", "entity", "impact", "use_case", "visualize", "mermaid", "blocks", "navigate", "radar"], help="Loại truy vấn")
    parser_query.add_argument("target", help="Đối tượng cần truy vấn (keyword, tên file, tên entity...)")
    parser_query.add_argument("--ref", required=True, help="Đường dẫn một file XML bất kỳ trong dự án để xác định ngữ cảnh")
    parser_query.add_argument("--folder", help="Lọc theo tên thư mục (ví dụ: Dir hoặc Dir,Grid)")
    parser_query.add_argument("--type-filter", dest="type_filter", help="Lọc theo loại controller (ví dụ: dir hoặc grid)")
    parser_query.add_argument("--limit", type=int, default=10, help="Số kết quả tối đa trả về (mặc định: 10, tối đa khuyến nghị: 20)")
    parser_query.add_argument("--compact", action="store_true", help="Ẩn các thông tin chi tiết / XML snippet của fields")
    parser_query.add_argument("--match-type", dest="match_type", default="all", choices=["all", "code", "field", "file"], help="Lọc tìm kiếm theo loại khớp")
    parser_query.add_argument("--direct", action="store_true", help="Bỏ qua daemon, query trực tiếp (khuyến nghị khi debug đường dẫn Kuzu)")

    parser_watch = subparsers.add_parser("watch", help="Khởi chạy Watchdog tự động cập nhật graph khi file thay đổi")
    parser_watch.add_argument("--ref", required=True, help="Đường dẫn một file XML bất kỳ trong dự án để xác định ngữ cảnh")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "query":
        cmd_query(args)
    elif args.command == "watch":
        cmd_watch(args)

if __name__ == "__main__":
    main()
