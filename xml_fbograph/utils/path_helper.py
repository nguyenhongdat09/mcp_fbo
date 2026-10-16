from pathlib import Path
from typing import List, Union, Optional


def _normalize_path_str(file_path: Union[str, Path]) -> str:
    r"""
    Chuẩn hóa separator về backslash và sửa UNC 1 backslash → 2 backslash.
    \\server\share  →  \\server\share (giu nguyen)
    \server\share   →  \\server\share (them backslash)
    //server/share  →  \\server\share
    E:\foo          →  E:\foo
    """
    s = str(file_path).replace("/", "\\")
    if s.startswith("\\\\"):
        return s
    if s.startswith("\\") and not s.startswith("\\\\"):
        parts = s.split("\\", 2)
        if len(parts) > 1:
            next_seg = parts[1]
            is_drive_letter = len(next_seg) >= 2 and next_seg[0].isalpha() and next_seg[1] == ":"
            if not is_drive_letter and len(next_seg) >= 1:
                return "\\" + s
    return s


def _split_path_parts(file_path: Union[str, Path]) -> List[str]:
    """Tách path giống TreeFile (Windows \\), không resolve."""
    normalized = _normalize_path_str(file_path)
    return normalized.split("\\")


def _is_unc_path(file_path: Union[str, Path]) -> bool:
    """True nếu path là UNC sau normalize."""
    return _normalize_path_str(file_path).startswith("\\\\")


def get_customerpro_project_path(file_path: Union[str, Path]) -> str:
    """
    Port AppDataPathHelper.getProjectPath (TreeFile).
    Bắt buộc có segment CustomerPro + đủ độ sâu; có FDN thì cắt nông hơn.
    Trả về '' nếu không hợp lệ (Other).
    Bảo toàn UNC prefix \\\\ khi join lại.
    """
    raw = _normalize_path_str(file_path)
    unc_prefix = "\\\\" if raw.startswith("\\\\") else ("\\" if raw.startswith("\\") else "")
    
    non_empty_parts = [p for p in raw.split("\\") if p]
    
    index = next((i for i, p in enumerate(non_empty_parts) if p.lower() == "customerpro"), -1)
    if index == -1 or len(non_empty_parts) < index + 4:
        return ""
    
    has_fdn = any(p.lower() == "fdn" for p in non_empty_parts)
    end = index + (3 if has_fdn else 4)
    
    joined = unc_prefix + "\\".join(non_empty_parts[:end])
    return joined


def get_fbo_group_name(file_path: Union[str, Path]) -> str:
    """
    Port AppDataPathHelper.getGroupName.
    Hợp lệ → 'FOLDER2 - FOLDER3'; không → 'Other'.
    """
    project_path = get_customerpro_project_path(file_path)
    # JS: projectPath.split('\\'); length == 1 (kể cả '') → Other
    parts = project_path.split("\\")
    if len(parts) == 1:
        return "Other"
    return " - ".join(parts[-2:])


def get_controllers_dir_for_customerpro(file_path: Union[str, Path]) -> Optional[Path]:
    """
    Tra ve <project>/App_Data/Controllers neu group CustomerPro hop le.
    Khong check ton tai tren disk.
    """
    project_path = get_customerpro_project_path(file_path)
    if not project_path:
        return None
    return Path(project_path) / "App_Data" / "Controllers"


def has_app_data_controllers(file_path: Union[str, Path]) -> bool:
    """True khi project co thu muc App_Data/Controllers (Dir/Grid...)."""
    return resolve_controllers_dir(file_path) is not None


def resolve_controllers_dir(root: Union[str, Path]) -> Optional[Path]:
    """
    Chấp nhận BẤT KỲ đường dẫn nào thuộc dự án (project root, App_Data, Controllers,
    thư mục con, hoặc file cụ thể).
    Walk ngược lên tìm App_Data/Controllers.
    """
    raw = _normalize_path_str(root)
    root_path = Path(raw).resolve()

    if root_path.suffix or root_path.is_file():
        current = root_path.parent
    else:
        current = root_path

    walk_curr = current
    while walk_curr and walk_curr.name:
        if walk_curr.name.lower() == "controllers" and walk_curr.parent.name.lower() == "app_data":
            return walk_curr
        if walk_curr.parent == walk_curr:
            break
        walk_curr = walk_curr.parent

    joined_full = current / "App_Data" / "Controllers"
    if joined_full.is_dir():
        return joined_full

    if current.name.lower() == "app_data":
        joined_controllers = current / "Controllers"
        if joined_controllers.is_dir():
            return joined_controllers

    return None


def is_fastbusiness_customerpro_project(file_path: Union[str, Path]) -> bool:
    """
    True khi project co thu muc App_Data/Controllers.
    Chap nhan ca du an khong co group CustomerPro (cho truong hop build local).
    """
    return has_app_data_controllers(file_path)


class ProjectPathHelper:
    def __init__(self, file_path: str):
        self._raw_path = str(file_path)
        try:
            self.file_path = Path(file_path).resolve()
        except Exception:
            self.file_path = Path(file_path)

    def get_customerpro_project_path(self) -> str:
        """Project root kiểu TreeFile (chuỗi rỗng nếu Other)."""
        return get_customerpro_project_path(self._raw_path)

    def get_fbo_group_name(self) -> str:
        """Tên group TreeFile hoặc 'Other'."""
        return get_fbo_group_name(self._raw_path)

    def is_fastbusiness_customerpro_project(self) -> bool:
        return is_fastbusiness_customerpro_project(self._raw_path)

    def get_project_root(self) -> Path:
        """
        Ưu tiên root CustomerPro (TreeFile) nếu path hợp lệ.
        Fallback: walk lên tìm cha của App_Data (CLI / test local).
        """
        cp = get_customerpro_project_path(self._raw_path)
        if cp:
            return Path(cp)

        current = self.file_path
        for parent in [current] + list(current.parents):
            if (parent / "App_Data").is_dir():
                return parent

        for parent in current.parents:
            if parent.name.lower() == "controllers" and parent.parent.name.lower() == "app_data":
                return parent.parent.parent

        return current.parent

    def get_controllers_path(self) -> Path:
        """Trả về đường dẫn tuyệt đối đến thư mục Controllers"""
        root = self.get_project_root()
        controllers_dir = root / "App_Data" / "Controllers"
        if not controllers_dir.is_dir():
            return root
        return controllers_dir

