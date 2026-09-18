"""Path helper cho check_things — port SourcePathHelper.js.

Lexical (không qua resolve_any_path vì missing SYSTEM file không tồn tại trên
đĩa — resolve_any_path yêu cầu exists).
"""

from __future__ import annotations

import os
from pathlib import Path


def _is_fbo_project_root(p: Path) -> bool:
    """Marker project FBO: App_Data/Controllers dir hoặc Web.config."""
    try:
        return (p / "App_Data" / "Controllers").is_dir() or (
            p / "Web.config"
        ).is_file()
    except OSError:
        return False


def get_relative_after_project(abs_path: str) -> dict | None:
    """{"project_path": root, "relative_path": rel} — rel posix từ project root.
    None nếu không detect được project root (không marker FBO)."""
    from xml_fbograph.utils.path_helper import ProjectPathHelper

    try:
        helper = ProjectPathHelper(str(abs_path))
        root = Path(helper.get_project_root()).resolve()
    except Exception:
        return None
    if not root or not _is_fbo_project_root(root):
        return None
    try:
        rel = Path(str(abs_path)).resolve().relative_to(root).as_posix()
    except Exception:
        return None
    return {"project_path": str(root), "relative_path": rel}


def get_xml_short_name(abs_path: str) -> str:
    """Dir/A.xml / Grid/B.xml — đoạn sau 'Controllers\\' (lần cuối,
    case-insensitive); fallback 2 segment cuối."""
    norm = str(abs_path).replace("/", "\\")
    marker = "\\controllers\\"
    idx = norm.lower().rfind(marker)
    if idx != -1:
        return norm[idx + len(marker) :].replace("\\", "/")
    parts = [x for x in norm.split("\\") if x]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return os.path.basename(str(abs_path))


def map_to_source(source_root: str, relative_path: str) -> str:
    return os.path.join(source_root, relative_path)


def find_in_sources_by_relative(
    source_roots: list[str] | None, relative_path: str
) -> dict | None:
    """os.path.join(root, rel) exists → {source_index, source_file_path};
    fallback '.f' → '.xml' (source chứa bản xml thay vì f)."""
    for i, root in enumerate(source_roots or []):
        if not root:
            continue
        candidate = map_to_source(root, relative_path)
        if os.path.exists(candidate):
            return {"source_index": i, "source_file_path": candidate}
        if candidate.lower().endswith(".f"):
            fallback = candidate[:-2] + ".xml"
            if os.path.exists(fallback):
                return {"source_index": i, "source_file_path": fallback}
    return None


def source_label_from_index(source_index: int | None) -> str:
    if source_index is None or source_index < 0:
        return "Không tìm thấy"
    return f"Nguồn {source_index + 1}"


def is_valid_project_root(folder_path: str) -> bool:
    """Nguồn hợp lệ = folder tồn tại + marker FBO project."""
    if not folder_path:
        return False
    p = Path(str(folder_path))
    return p.is_dir() and _is_fbo_project_root(p)


def normalize_to_project_root(folder_path: str) -> str:
    """Cắt subfolder bất kỳ về project root ('' nếu không cắt được)."""
    if not folder_path:
        return ""
    from xml_fbograph.utils.path_helper import ProjectPathHelper

    try:
        root = Path(ProjectPathHelper(str(folder_path)).get_project_root()).resolve()
    except Exception:
        return ""
    return str(root) if is_valid_project_root(str(root)) else ""
