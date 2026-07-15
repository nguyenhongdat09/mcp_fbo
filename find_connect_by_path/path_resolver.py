"""Resolve FBO project root and Web.config path from a file path."""

from pathlib import Path

WEB_CONFIG_NAME = "Web.config"
APP_DATA_FOLDER = "App_Data"


def get_project_root_from_path(file_path: str) -> str | None:
    """
    Lấy project root từ đường dẫn file — logic giống extension fbo-autocomplete.

    Ưu tiên: cắt path tại segment ``App_Data``.
    Fallback: đi lên parent cho đến khi gặp ``Web.config``.
    """
    normalized = str(Path(file_path))
    parts = Path(normalized).parts

    try:
        idx = parts.index(APP_DATA_FOLDER)
        if idx > 0:
            return str(Path(*parts[:idx]))
    except ValueError:
        pass

    current = Path(normalized).resolve()
    if current.is_file():
        current = current.parent

    while True:
        if (current / WEB_CONFIG_NAME).exists():
            return str(current)
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def get_web_config_path(file_path: str) -> tuple[str | None, str | None]:
    """Trả về (project_root, web_config_path)."""
    project_root = get_project_root_from_path(file_path)
    if not project_root:
        return None, None

    web_config = Path(project_root) / WEB_CONFIG_NAME
    if not web_config.exists():
        return project_root, None

    return project_root, str(web_config)
