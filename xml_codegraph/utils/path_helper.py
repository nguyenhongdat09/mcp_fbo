import os
import sys
import base64
from pathlib import Path
from typing import List, Union, Optional

# Thư mục top-level trong Controllers được đưa vào graph
GRAPH_TOP_LEVEL_FOLDERS = frozenset({"Dir", "Grid", "Filter", "Report", "Lookup", "Form"})

# Thư mục con Templates/Upload (Upload template import)
GRAPH_TEMPLATES_UPLOAD = ("Templates", "Upload")

# Cache đường dẫn base KuzuDB — tránh đọc config.yaml nhiều lần
_kuzu_db_base_cache: Optional[Path] = None
_user_multi_db_yn_cache: Optional[int] = None
_extract_shared_include_cache: Optional[int] = None


def reset_config_caches() -> None:
    """Xóa cache cấu hình (dùng cho testing/reload)."""
    global _kuzu_db_base_cache, _user_multi_db_yn_cache, _extract_shared_include_cache
    _kuzu_db_base_cache = None
    _user_multi_db_yn_cache = None
    _extract_shared_include_cache = None


def _normalize_project_root(path: Path) -> str:
    """Chuẩn hóa project root để base64 nhất quán (UNC Windows)."""
    resolved = path.resolve()
    normalized = os.path.normpath(str(resolved))
    return normalized.rstrip("\\/")


def _encode_project_root(project_root: Union[str, Path]) -> str:
    """Mã hóa base64 url-safe tên folder lưu Kuzu theo project root."""
    root_str = _normalize_project_root(Path(project_root))
    return base64.urlsafe_b64encode(root_str.encode("utf-8")).decode("utf-8")


def _find_config_file() -> Optional[Path]:
    """Tìm config.yaml từ package, CWD, exe hoặc script đang chạy."""
    candidates: List[Path] = []

    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable).resolve()
        candidates.extend([exe_path.parent / "config.yaml", exe_path.parent.parent / "config.yaml"])

    candidates.append(Path(__file__).resolve().parent.parent.parent / "config.yaml")
    candidates.append(Path.cwd() / "config.yaml")

    if sys.argv and sys.argv[0]:
        try:
            script = Path(sys.argv[0]).resolve()
            candidates.extend([script.parent / "config.yaml", script.parent.parent / "config.yaml"])
        except Exception:
            pass

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def resolve_kuzu_db_base() -> Path:
    """
    Trả về thư mục gốc lưu Kuzu DB local.
    Ưu tiên: biến môi trường FBOGRAPH_KUZU_BASE > config.yaml fbograph.kuzu_db_base > C:/KuzuDB
    """
    global _kuzu_db_base_cache
    if _kuzu_db_base_cache is not None:
        return _kuzu_db_base_cache

    default_base = "C:/KuzuDB"
    env_base = os.environ.get("FBOGRAPH_KUZU_BASE", "").strip()
    if env_base:
        _kuzu_db_base_cache = Path(env_base)
        return _kuzu_db_base_cache

    kuzu_db_base = default_base
    try:
        import yaml

        config_file = _find_config_file()
        if config_file:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            kuzu_db_base = (
                cfg.get("fbograph", {}).get("kuzu_db_base")
                or default_base
            )
    except Exception:
        pass

    _kuzu_db_base_cache = Path(kuzu_db_base)
    return _kuzu_db_base_cache


def get_user_multi_db_yn() -> int:
    """
    Đọc cấu hình user_multi_db_yn từ config.yaml.
    Mặc định = 1 (mỗi dự án 1 DB riêng).
    Nếu = 0: dùng 1 DB Kuzu đại diện duy nhất trong C:/KuzuDB.
    Ưu tiên: Biến môi trường FBOGRAPH_MULTI_DB (1 hoặc 0) > config.yaml user_multi_db_yn (hoặc use_multi_db_yn) > 1
    """
    global _user_multi_db_yn_cache
    if _user_multi_db_yn_cache is not None:
        return _user_multi_db_yn_cache

    env_val = os.environ.get("FBOGRAPH_MULTI_DB", "").strip()
    if env_val in ("0", "1"):
        _user_multi_db_yn_cache = int(env_val)
        return _user_multi_db_yn_cache

    multi_db_val = 1
    try:
        import yaml

        config_file = _find_config_file()
        if config_file:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            fbograph_cfg = cfg.get("fbograph", {})
            if "user_multi_db_yn" in fbograph_cfg:
                multi_db_val = int(fbograph_cfg["user_multi_db_yn"])
            elif "use_multi_db_yn" in fbograph_cfg:
                multi_db_val = int(fbograph_cfg["use_multi_db_yn"])
    except Exception:
        pass

    _user_multi_db_yn_cache = multi_db_val
    return _user_multi_db_yn_cache


def get_extract_shared_include_yn() -> int:
    """
    Đọc extract_options.shared_include từ config.yaml.
    Mặc định = 0 (tắt SHARED_INCLUDE).
    Ưu tiên: Biến môi trường FBOGRAPH_SHARED_INCLUDE (0|1|true|false) > config.yaml extract_options.shared_include > 0
    """
    global _extract_shared_include_cache
    if _extract_shared_include_cache is not None:
        return _extract_shared_include_cache

    env_val = os.environ.get("FBOGRAPH_SHARED_INCLUDE", "").strip().lower()
    if env_val in ("1", "true", "yes"):
        _extract_shared_include_cache = 1
        return _extract_shared_include_cache
    elif env_val in ("0", "false", "no"):
        _extract_shared_include_cache = 0
        return _extract_shared_include_cache

    shared_inc_val = 0
    try:
        import yaml

        config_file = _find_config_file()
        if config_file:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            extract_cfg = cfg.get("extract_options")
            if isinstance(extract_cfg, dict) and "shared_include" in extract_cfg:
                raw_val = extract_cfg["shared_include"]
                if isinstance(raw_val, bool):
                    shared_inc_val = 1 if raw_val else 0
                else:
                    str_val = str(raw_val).strip().lower()
                    if str_val in ("1", "true", "yes"):
                        shared_inc_val = 1
                    else:
                        shared_inc_val = 0
    except Exception:
        pass

    _extract_shared_include_cache = shared_inc_val
    return _extract_shared_include_cache


def resolve_graph_dir(project_root: Union[str, Path]) -> Path:
    """
    Map project root -> thư mục .fbograph lưu Kuzu DB local.
    - user_multi_db_yn == 1 (Mặc định): Trả về C:/KuzuDB/<base64(project_root)>/.fbograph
    - user_multi_db_yn == 0:
        Quét trong C:/KuzuDB xem có folder dự án nào đã có .fbograph chưa:
        + Nếu có -> lấy folder .fbograph đại diện đang có mà không so sánh project_root.
        + Nếu chưa có -> khởi tạo C:/KuzuDB/<base64(project_root)>/.fbograph làm DB đại diện.
    """
    base_dir = resolve_kuzu_db_base()

    if get_user_multi_db_yn() != 0:
        folder_name = _encode_project_root(project_root)
        return base_dir / folder_name / ".fbograph"

    # Mode user_multi_db_yn == 0 (Single/shared DB representative)
    if base_dir.exists() and base_dir.is_dir():
        try:
            for item in sorted(base_dir.iterdir()):
                if item.is_dir():
                    candidate = item / ".fbograph"
                    if candidate.is_dir():
                        return candidate
        except Exception:
            pass

    folder_name = _encode_project_root(project_root)
    return base_dir / folder_name / ".fbograph"


def is_db_owner(controllers_root: Union[str, Path], graph_dir: Union[str, Path]) -> bool:
    """
    Kiểm tra controllers_root (hoặc dự án chứa nó) có phải là chủ sở hữu chính thức của graph_dir hay không.
    - Khi user_multi_db_yn == 1: Mọi dự án sở hữu DB riêng của nó -> True.
    - Khi user_multi_db_yn == 0: Chỉ trả về True nếu hash encoded của project_root trùng với tên folder đại diện trong C:/KuzuDB.
    """
    if get_user_multi_db_yn() != 0:
        return True

    helper = ProjectPathHelper(str(controllers_root))
    project_root = helper.get_project_root()
    current_encoded = _encode_project_root(project_root)

    graph_dir = Path(graph_dir).resolve()
    owner_encoded = graph_dir.parent.name

    return current_encoded == owner_encoded




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

    def get_graph_dir(self) -> Path:
        """Trả về thư mục .fbograph local (C:/KuzuDB/<base64 project root>/.fbograph)."""
        return resolve_graph_dir(self.get_project_root())

    def get_kuzu_path(self) -> Path:
        """Trả về file Kuzu DB local của project."""
        return self.get_graph_dir() / "kuzu"

    def get_graph_scan_roots(self) -> List[Path]:
        """Trả về các thư mục Dir/Grid/Filter/Report và Templates/Upload cần build graph."""
        return get_graph_scan_roots(self.get_controllers_path())

    def is_db_owner(self) -> bool:
        """Kiểm tra dự án hiện tại có phải chủ sở hữu Kuzu DB đại diện hay không."""
        return is_db_owner(self.get_controllers_path(), self.get_graph_dir())
