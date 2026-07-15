import os
from pathlib import Path
from typing import List, Union

# Thư mục top-level trong Controllers được đưa vào graph
GRAPH_TOP_LEVEL_FOLDERS = frozenset({"Dir", "Grid", "Filter", "Report", "Lookup", "Form"})

# Thư mục con Templates/Upload (Upload template import)
GRAPH_TEMPLATES_UPLOAD = ("Templates", "Upload")


def get_graph_scan_roots(controllers_root: Union[str, Path]) -> List[Path]:
    """Trả về danh sách thư mục gốc cần quét khi build graph."""
    controllers_root = Path(controllers_root).resolve()
    scan_roots: List[Path] = []

    for folder_name in sorted(GRAPH_TOP_LEVEL_FOLDERS):
        folder_path = controllers_root / folder_name
        if folder_path.is_dir():
            scan_roots.append(folder_path)

    upload_path = controllers_root.joinpath(*GRAPH_TEMPLATES_UPLOAD)
    if upload_path.is_dir():
        scan_roots.append(upload_path)

    return scan_roots


def is_graph_scope_relative_path(relative_path: Union[str, Path]) -> bool:
    """Kiểm tra file (đường dẫn tương đối từ Controllers) có nằm trong phạm vi graph không."""
    parts = Path(relative_path).parts
    if not parts:
        return False

    if parts[0] in GRAPH_TOP_LEVEL_FOLDERS:
        return True

    return (
        len(parts) >= 2
        and parts[0] == GRAPH_TEMPLATES_UPLOAD[0]
        and parts[1] == GRAPH_TEMPLATES_UPLOAD[1]
    )


def is_graph_scope_file(file_path: Union[str, Path], controllers_root: Union[str, Path]) -> bool:
    """Kiểm tra file tuyệt đối có nằm trong phạm vi graph không."""
    file_path = Path(file_path).resolve()
    controllers_root = Path(controllers_root).resolve()

    try:
        relative_path = file_path.relative_to(controllers_root)
    except ValueError:
        return False

    return is_graph_scope_relative_path(relative_path)


class ProjectPathHelper:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path).resolve()

    def get_project_root(self) -> Path:
        """
        Tìm ngược lên từ file_path để xác định thư mục root của dự án chứa nó
        (là thư mục cha trực tiếp của App_Data).
        """
        current = self.file_path
        # Duyệt ngược lên trên để tìm thư mục có chứa App_Data
        for parent in [current] + list(current.parents):
            if (parent / "App_Data").is_dir():
                return parent
        
        # Fallback 1: Nếu đường dẫn chứa controllers/app_data
        for parent in current.parents:
            if parent.name.lower() == "controllers" and parent.parent.name.lower() == "app_data":
                return parent.parent.parent
                
        # Fallback 2: Trả về thư mục cha hiện tại
        return current.parent

    def get_controllers_path(self) -> Path:
        """Trả về đường dẫn tuyệt đối đến thư mục Controllers"""
        root = self.get_project_root()
        controllers_dir = root / "App_Data" / "Controllers"
        if not controllers_dir.is_dir():
            # Nếu dự án không theo cấu trúc App_Data/Controllers chuẩn, trả về root
            return root
        return controllers_dir

    def get_graph_dir(self) -> Path:
        """Trả về đường dẫn thư mục lưu trữ graph (.fbograph)"""
        root = self.get_project_root()
        graph_dir = root / ".fbograph"
        return graph_dir

    def get_graph_scan_roots(self) -> List[Path]:
        """Trả về các thư mục Dir/Grid/Filter/Report và Templates/Upload cần build graph."""
        return get_graph_scan_roots(self.get_controllers_path())
