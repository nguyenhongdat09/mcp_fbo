"""API chính: truyền file path → connection string."""

from .path_resolver import get_web_config_path
from .web_config_loader import WebConfigLoader


def find_connection_by_path(file_path: str, db_type: str = "app") -> dict:
    """
    Tìm SQL Server connection string từ đường dẫn file FBO.

    Args:
        file_path: Đường dẫn file (XML, SQL, ...) trong project FBO
        db_type: ``app``, ``sys``, hoặc ``all``

    Returns:
        dict với success, connection_string, project_root, web_config_path, ...
    """
    if not file_path or not str(file_path).strip():
        return {"success": False, "error": "file_path is required"}

    db_type = (db_type or "app").lower()
    project_root, web_config_path = get_web_config_path(file_path)

    if not project_root:
        return {
            "success": False,
            "error": "Không xác định được project root từ file path (không có App_Data hoặc Web.config)",
            "file_path": file_path,
        }

    if not web_config_path:
        return {
            "success": False,
            "error": f"Không tìm thấy Web.config tại: {project_root}",
            "file_path": file_path,
            "project_root": project_root,
        }

    try:
        loader = WebConfigLoader()
        loader.load_config(web_config_path)
    except FileNotFoundError as exc:
        return {
            "success": False,
            "error": str(exc),
            "file_path": file_path,
            "project_root": project_root,
        }

    available = loader.available_db_types()
    if not available:
        return {
            "success": False,
            "error": "Web.config không chứa appConnectionString / sysConnectionString",
            "file_path": file_path,
            "project_root": project_root,
            "web_config_path": web_config_path,
        }

    if db_type == "all":
        connections = {}
        for key in available:
            connections[key] = {
                "connection_string": loader.get_raw_connection_string(key),
                "parsed": loader.get_db_connection(key),
            }
        return {
            "success": True,
            "file_path": file_path,
            "project_root": project_root,
            "web_config_path": web_config_path,
            "available_db_types": available,
            "connections": connections,
        }

    if db_type not in available:
        return {
            "success": False,
            "error": f"Không tìm thấy connection type '{db_type}'. Có sẵn: {', '.join(available)}",
            "file_path": file_path,
            "project_root": project_root,
            "web_config_path": web_config_path,
            "available_db_types": available,
        }

    return {
        "success": True,
        "file_path": file_path,
        "project_root": project_root,
        "web_config_path": web_config_path,
        "db_type": db_type,
        "connection_string": loader.get_raw_connection_string(db_type),
        "parsed": loader.get_db_connection(db_type),
        "available_db_types": available,
    }
