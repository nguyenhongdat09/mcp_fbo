import sys
import os
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add the parent directory of xml_codegraph to sys.path so we can import modules
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from xml_codegraph.builder.graph_builder import build_and_save_graph
from xml_codegraph.utils.path_helper import ProjectPathHelper
from xml_codegraph.storage.kuzu_index import _db_instances

def build_kuzu_for_project(path_str: str, overwrite: bool = True) -> bool:
    """
    Builds the Kuzu graph for a project given a file path or directory path.
    """
    try:
        path = Path(path_str).resolve()
        print(f"\n==================================================")
        print(f"Xử lý dự án từ đường dẫn: {path}")
        
        # Sử dụng ProjectPathHelper để tìm project root và controllers path
        helper = ProjectPathHelper(str(path))
        project_root = helper.get_project_root()
        controllers_dir = helper.get_controllers_path()
        graph_dir = helper.get_graph_dir()
        
        print(f"Project Root: {project_root}")
        print(f"Controllers Dir: {controllers_dir}")
        print(f"Graph Output Dir: {graph_dir}")
        
        if not controllers_dir.is_dir():
            print(f"Lỗi: Thư mục Controllers không tồn tại: {controllers_dir}")
            return False

        kuzu_db_path = graph_dir / "kuzu"
        
        if overwrite:
            print(f"Đang xóa database cũ để chạy đè (nếu có): {graph_dir}")
            # Xóa cache in-memory trong cùng process nếu có
            cache_key = str(kuzu_db_path).replace("\\", "/").lower()
            if cache_key in _db_instances:
                print(f"Giải phóng kết nối Kuzu cũ trong bộ nhớ: {cache_key}")
                _db_instances.pop(cache_key)
                
            # Xóa thư mục .fbograph
            if graph_dir.exists():
                try:
                    shutil.rmtree(graph_dir, ignore_errors=True)
                    print(f"Đã xóa thành công thư mục: {graph_dir}")
                except Exception as e:
                    print(f"Không thể xóa hoàn toàn thư mục {graph_dir}: {e}")
        
        print(f"Đang xây dựng graph Kuzu cho dự án: {project_root}")
        build_and_save_graph(controllers_dir, graph_dir)
        print(f"Xây dựng thành công Kuzu DB tại: {kuzu_db_path}")
        return True
    except Exception as e:
        print(f"Lỗi khi xử lý dự án {path_str}: {e}")
        return False

def main():
    # PowerShell cũ hay lỗi font tiếng Việt — ép UTF-8 cho stdin/stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("Sử dụng: python xml_codegraph/build_kuzu_projects.py <đường_dẫn_xml_hoặc_thư_mục_1> [đường_dẫn_xml_hoặc_thư_mục_2] ...")
        sys.exit(1)
        
    paths = sys.argv[1:]
    
    # Sử dụng ThreadPoolExecutor để chạy song song (concurrently) các dự án
    max_workers = min(len(paths), 4)  # Giới hạn số worker song song để tránh quá tải
    print(f"Đang chạy song song {len(paths)} dự án với tối đa {max_workers} luồng...")
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(lambda p: build_kuzu_for_project(p, overwrite=True), paths))
        success_count = sum(1 for r in results if r)
            
    print(f"\nHoàn thành! Thành công {success_count}/{len(paths)} dự án.")

if __name__ == "__main__":
    main()
