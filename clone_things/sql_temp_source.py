"""Ghi nhớ nguồn file .sql temp để extension fbo-autocomplete auto-switch DB.

Extension lưu link file->project trong globalState 'fbo.sqlTempSourceMap' —
storage nội bộ IDE, process ngoài (MCP) không ghi được. Thay vào đó MCP ghi
manifest JSON nằm cạnh file .sql:

    <folder>/.fbo_sql_temp_source.json
        { "<file_path.lower()>": {object_name, group_label, db_type,
                                   server, database, created_at} }

Extension đọc manifest làm fallback khi globalState miss (xem
SqlObjectLinkProvider.getSourceInfo). group_label/db_type phải khớp format
status bar: group_label = 2 segment cuối project root join ' - ' + UPPER
(vd. 'ANNHIEN - FBISP24'), db_type = 'app' | 'sys'.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("clone_things.sql_temp_source")

MANIFEST_NAME = ".fbo_sql_temp_source.json"
MAX_ENTRIES = 500


def group_label_from_project(project_path: str) -> str:
    """
    Parity AppDataPathHelper.getGroupName + tree .toUpperCase():
    2 segment cuối project root join ' - ' rồi UPPER.

    \\\\172.168.5.14\\CustomerPro\\FBI\\ANNHIEN\\FBISP24 -> 'ANNHIEN - FBISP24'
    E:\\FBO\\VLOTUS\\SP228                            -> 'VLOTUS - SP228'
    """
    if not project_path or not str(project_path).strip():
        return ""
    try:
        from find_connect_by_path.path_resolver import get_project_root_from_path
        root = get_project_root_from_path(project_path) or str(project_path).strip()
    except Exception:
        root = str(project_path).strip()
    parts = [
        p for p in Path(root).parts
        if p not in ("\\", "/") and not (len(p) == 2 and p.endswith(":"))
    ]
    if len(parts) >= 2:
        return f"{parts[-2]} - {parts[-1]}".upper()
    return parts[-1].upper() if parts else ""


def _resolve_db_info(project_path: str, db_type: str) -> tuple[str, str]:
    """Best-effort lấy (server, database) từ Web.config của project."""
    try:
        from query_database.connection import get_connection_config

        res = get_connection_config(project_path, db_type)
        if res.get("success") and res.get("parsed"):
            parsed = res["parsed"]
            return (parsed.get("server") or "", parsed.get("database") or "")
    except Exception:
        pass
    return "", ""


def remember_sql_temp_source(
    file_path: str,
    object_name: str = "",
    project_path: str = "",
    db_type: str = "app",
) -> bool:
    """
    Upsert entry vào manifest cạnh file .sql. Không bao giờ raise —
    bookkeeping không được phép phá flow clone.
    """
    try:
        if not file_path:
            return False
        group_label = group_label_from_project(project_path)
        if not group_label:
            return False

        fp = Path(file_path).resolve()
        dt = (db_type or "app").lower()
        server, database = _resolve_db_info(project_path, dt)

        manifest_path = fp.parent / MANIFEST_NAME
        data: dict = {}
        if manifest_path.exists():
            try:
                loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}

        data[str(fp).lower()] = {
            "object_name": object_name or "",
            "group_label": group_label,
            "db_type": dt,
            "server": server,
            "database": database,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        while len(data) > MAX_ENTRIES:
            data.pop(next(iter(data)))

        manifest_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return True
    except Exception as e:
        logger.warning("remember_sql_temp_source failed for %s: %s", file_path, e)
        return False
