"""Đọc connection string từ Web.config — port từ fbo-autocomplete DBQuery."""

import re
from pathlib import Path

CONNECTION_NAME_PATTERN = re.compile(
    r'<add\s+name="(appConnectionString|syncConnectionString|sysConnectionString)"\s+'
    r'connectionString="([^"]+)"',
    re.IGNORECASE,
)


class WebConfigLoader:
    """Load app/sys connection strings from FastBusiness Web.config."""

    def __init__(self) -> None:
        self.db_connections: dict[str, dict | None] = {"app": None, "sys": None}
        self.raw_connection_strings: dict[str, str] = {}

    def load_config(self, web_config_path: str) -> None:
        path = Path(web_config_path)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file Web.config tại: {web_config_path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        self.db_connections = {"app": None, "sys": None}
        self.raw_connection_strings = {}

        for match in CONNECTION_NAME_PATTERN.finditer(content):
            name, connection_string = match.group(1), match.group(2)
            bucket = "app" if ("app" in name.lower() or "sync" in name.lower()) else "sys"
            self.raw_connection_strings[bucket] = connection_string
            self.db_connections[bucket] = self.parse_connection_string(connection_string)

        if self.db_connections["sys"] and self.db_connections["app"]:
            sys_db = self.db_connections["sys"]["database"]
            normalized = re.sub(r"_(S|Sys)$", "_A", sys_db)
            normalized = re.sub(r"_Sys$", "_App", normalized)
            self.db_connections["app"]["database"] = normalized

    @staticmethod
    def parse_connection_string(connection_string: str) -> dict[str, str]:
        """Parse ADO.NET connection string thành dict — giống extension."""
        parts: dict[str, str] = {}
        for segment in connection_string.split(";"):
            if not segment.strip() or "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            if key.strip() and value.strip():
                parts[key.strip().lower()] = value.strip()

        return {
            "server": parts.get("data source", ""),
            "database": parts.get("initial catalog", ""),
            "app_name": "vscode",
            "user": parts.get("uid", parts.get("user id", "")),
            "password": parts.get("pwd", parts.get("password", "")),
        }

    def get_db_connection(self, db_type: str) -> dict[str, str]:
        db_type = db_type.lower()
        if db_type not in self.db_connections or not self.db_connections[db_type]:
            raise KeyError(f"Không tìm thấy thông tin kết nối cho: {db_type}")
        return self.db_connections[db_type]

    def get_raw_connection_string(self, db_type: str) -> str:
        db_type = db_type.lower()
        if db_type not in self.raw_connection_strings:
            raise KeyError(f"Không tìm thấy connection string cho: {db_type}")
        return self.raw_connection_strings[db_type]

    def available_db_types(self) -> list[str]:
        return [key for key, value in self.db_connections.items() if value]
