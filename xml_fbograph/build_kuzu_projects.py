import sys
import os
import shutil
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add the parent directory of xml_fbograph to sys.path so we can import modules
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from xml_fbograph.builder.graph_builder import build_and_save_graph
from xml_fbograph.utils.path_helper import (
    ProjectPathHelper,
    discover_registered_projects,
    resolve_kuzu_db_base,
)
from xml_fbograph.storage.kuzu_index import _db_instances
from xml_fbograph.save_disk import touch_kuzu_access, maybe_cleanup_stale_kuzu

def build_kuzu_for_project(path_str: str, overwrite: bool = True, progress=None) -> bool:
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
            from xml_fbograph.storage.kuzu_index import reset_graph_dir
            if not reset_graph_dir(graph_dir):
                print(f"Lỗi: Không thể xóa vật lý thư mục {graph_dir}.")
                print("Bỏ qua project này để tránh làm phình DB hoặc lỗi mix data.")
                return False
                
        print(f"Đang xây dựng graph Kuzu cho dự án: {project_root}")
        build_and_save_graph(controllers_dir, graph_dir, progress=progress, project_label=str(project_root))
        
        # Touch access log & try cleanup
        touch_kuzu_access(str(project_root))
        maybe_cleanup_stale_kuzu()
        
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
        cmd_content = f'@echo off\n"%~dp0venv\\Scripts\\python.exe" "%~dp0xml_fbograph\\build_kuzu_projects.py" %*\n'
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

def cmd_rebuild_all(overwrite: bool = True) -> int:
    """
    Quét toàn bộ folder KuzuDB (base64 project root), rebuild lại mọi dự án còn truy cập được.
    Đọc kuzu_db_base từ config.yaml (fbograph.kuzu_db_base) hoặc FBOGRAPH_KUZU_BASE.
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

    base_dir = resolve_kuzu_db_base()
    projects = discover_registered_projects(base_dir)

    print(f"=== Rebuild tất cả dự án KuzuDB ===")
    print(f"Thư mục Kuzu: {base_dir}")

    if not projects:
        print(f"Không tìm thấy dự án nào (folder con có .fbograph) trong {base_dir}")
        return 1

    paths_to_build: list[str] = []
    skipped: list[str] = []

    for project_root in projects:
        helper = ProjectPathHelper(str(project_root))
        controllers_dir = helper.get_controllers_path()
        app_data_dir = project_root / "App_Data"

        if not app_data_dir.is_dir():
            skipped.append(f"{project_root} (thiếu App_Data)")
            continue
        if not controllers_dir.is_dir():
            skipped.append(f"{project_root} (Controllers không tồn tại / không truy cập được)")
            continue

        paths_to_build.append(str(project_root))

    print(f"Tìm thấy {len(projects)} folder Kuzu, {len(paths_to_build)} dự án sẽ rebuild:")
    for idx, path_str in enumerate(paths_to_build, 1):
        print(f"  [{idx}] {path_str}")

    if skipped:
        print(f"\nBỏ qua {len(skipped)} dự án:")
        for item in skipped:
            print(f"  - {item}")

    if not paths_to_build:
        print("\nKhông có dự án nào khả dụng để rebuild.")
        return 1

    return cmd_build(paths_to_build, overwrite=overwrite)


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

    # 2 project song song: giảm OOM VirtualAlloc khi flatten + COPY Kuzu (trước đây 4 dễ hết RAM)
    max_workers = min(len(paths), 2)
    print(f"Đang chạy song song {len(paths)} dự án với tối đa {max_workers} luồng...")

    from xml_fbograph.utils.progress import MultiProjectParseProgress

    with MultiProjectParseProgress(max_slots=max_workers) as progress:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(lambda p: build_kuzu_for_project(p, overwrite=overwrite, progress=progress), paths))

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
        print("=== FastBusiness XML FBOGraph CLI (fbograph) ===")
        print("Sử dụng:")
        print("  fbograph install                     : Đăng ký CLI 'fbograph' vào hệ thống Windows")
        print("  fbograph init                        : Tự động khởi tạo/xây dựng Kuzu DB cho dự án tại thư mục hiện tại")
        print("  fbograph rebuild                     : Rebuild tất cả dự án đã có trong thư mục KuzuDB (config.yaml)")
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
    elif arg == "rebuild":
        sys.exit(cmd_rebuild_all(overwrite=True))
    else:
        sys.exit(cmd_build(sys.argv[1:], overwrite=True))

if __name__ == "__main__":
    main()
