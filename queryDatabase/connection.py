"""Resolve SQL Server connection config from FBO file path."""

from find_connect_by_path import find_connection_by_path


def get_connection_config(file_path: str, db_type: str = "app") -> dict:
    """
    Lấy thông tin kết nối DB từ file path (qua Web.config).

    Returns:
        dict với keys: success, parsed, connection_string, project_root, ...
    """
    return find_connection_by_path(file_path, db_type)
