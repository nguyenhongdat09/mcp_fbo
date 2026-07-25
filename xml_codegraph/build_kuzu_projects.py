import sys
import os
import shutil
import subprocess
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

def install_cli() -> bool:
    """
    Cài đặt CLI fbograph bằng cách tạo file fbograph.cmd ở root workspace 
    và thêm thư mục root workspace vào User PATH của Windows.
    """
    try:
        workspace_dir = Path(__file__).parent.parent.resolve()
        cmd_file = workspace_dir / "fbograph.cmd"
        
        # 1. Tạo file fbograph.cmd
        cmd_content = f'@echo off\n"%~dp0venv\\Scripts\\python.exe" "%~dp0xml_codegraph\\build_kuzu_projects.py" %*\n'
        with open(cmd_file, "w", encoding="utf-8") as f:
            f.write(cmd_content)
        print(f"Đã tạo file thực thi CLI: {cmd_file}")
        
        # 2. Đăng ký PATH qua PowerShell
        ps_command = (
            f'$currentPath = [Environment]::GetEnvironmentVariable("Path", "User"); '
            f'if ($currentPath -notlike "*{workspace_dir}*") {{ '
            f'[Environment]::SetEnvironmentVariable("Path", $currentPath + ";{workspace_dir}", "User"); '
            f'Write-Host "SUCCESS" '
            f'}} else {{ Write-Host "ALREADY_EXISTS" }}'
        )
        
        res = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            check=True
        )
        output = res.stdout.strip()
        if "SUCCESS" in output:
            print(f"Đã thêm thành công thư mục '{workspace_dir}' vào biến môi trường PATH của User trên Windows!")
            print("LƯU Ý: Vui lòng khởi động lại Terminal (cmd/powershell) mới để thay đổi có hiệu lực.")
        elif "ALREADY_EXISTS" in output:
            print(f"Thư mục '{workspace_dir}' đã được cấu hình trong Windows PATH của User từ trước.")
        else:
            print("Đăng ký PATH hoàn tất.")
            
        print("Cài đặt CLI fbograph thành công!")
        return True
    except Exception as e:
        print(f"Lỗi trong quá trình cài đặt CLI fbograph: {e}")
        return False

def cmd_init() -> bool:
    """
    Xác định dự án ở thư mục hiện tại và build Kuzu DB.
    """
    current_dir = os.getcwd()
    helper = ProjectPathHelper(current_dir)
    project_root = helper.get_project_root()
    
    # Kiểm tra xem có phải cấu trúc thư mục FastBusiness chứa App_Data/Controllers không
    app_data_dir = project_root / "App_Data"
    if not app_data_dir.is_dir():
        print(f"Lỗi: Thư mục hiện tại '{current_dir}' không thuộc một dự án FastBusiness hợp lệ (thiếu thư mục App_Data).")
        print("Vui lòng di chuyển terminal vào trong thư mục dự án FastBusiness của bạn rồi chạy lại 'fbograph init'.")
        return False
        
    print(f"Phát hiện dự án FastBusiness tại: {project_root}")
    return build_kuzu_for_project(str(project_root), overwrite=True)

def cmd_build(paths: list[str], overwrite: bool = True) -> int:
    """
    Rebuild Kuzu cho danh sách path (file XML hoặc folder dự án).
    Dùng chung bởi fbograph CLI và fastbusiness_mcp.exe build.
    Trả về 0 nếu tất cả thành công, 1 nếu có lỗi.
    """
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if not paths:
        print("Lỗi: thiếu đường dẫn dự án/XML để build.")
        return 1

    max_workers = min(len(paths), 4)
    print(f"Đang chạy song song {len(paths)} dự án với tối đa {max_workers} luồng...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(lambda p: build_kuzu_for_project(p, overwrite=overwrite), paths))

    success_count = sum(1 for r in results if r)
    print(f"\nHoàn thành! Thành công {success_count}/{len(paths)} dự án.")
    return 0 if success_count == len(paths) else 1


def main():
    # PowerShell cũ hay lỗi font tiếng Việt — ép UTF-8 cho stdin/stdout
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("=== FastBusiness XML CodeGraph CLI (fbograph) ===")
        print("Sử dụng:")
        print("  fbograph install                     : Đăng ký CLI 'fbograph' vào hệ thống Windows")
        print("  fbograph init                        : Tự động khởi tạo/xây dựng Kuzu DB cho dự án tại thư mục hiện tại")
        print("  fbograph <đường_dẫn_xml_hoặc_folder> : Xây dựng Kuzu DB cho file XML hoặc thư mục cụ thể")
        print("\nVí dụ:")
        print("  fbograph \"\\\\172.168.5.14\\CustomerPro\\...\\Dir\\IRTran.xml\"")
        sys.exit(0)
        
    arg = sys.argv[1]
    
    if arg == "install":
        success = install_cli()
        sys.exit(0 if success else 1)
    elif arg == "init":
        success = cmd_init()
        sys.exit(0 if success else 1)
    else:
        sys.exit(cmd_build(sys.argv[1:], overwrite=True))

if __name__ == "__main__":
    main()
