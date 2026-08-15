import re
from pathlib import Path

SYS_KEY_PATTERN = re.compile(
    r'<add\s+(?:key="sysDatabaseName"\s+value="([^"]+)"|value="([^"]+)"\s+key="sysDatabaseName")',
    re.IGNORECASE,
)

CONNECTION_NAME_PATTERN = re.compile(
    r'<add\s+name="(appConnectionString|syncConnectionString|sysConnectionString)"\s+'
    r'connectionString="([^"]+)"',
    re.IGNORECASE,
)


class WebConfigLoader:
    """Load app/sys connection strings từ FastBusiness Web.config."""

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

        # 1. Tìm sysDatabaseName từ <appSettings>
        sys_db = None
        sys_key_match = SYS_KEY_PATTERN.search(content)
        if sys_key_match:
            sys_db = (sys_key_match.group(1) or sys_key_match.group(2)).strip()

        # 2. Đọc connection string từ <connectionStrings>
        raw_conns: dict[str, str] = {}
        parsed_conns: dict[str, dict] = {}
        base_parsed = None

        for match in CONNECTION_NAME_PATTERN.finditer(content):
            name, connection_string = match.group(1), match.group(2)
            bucket = "app" if ("app" in name.lower() or "sync" in name.lower()) else "sys"
            raw_conns[bucket] = connection_string
            parsed = self.parse_connection_string(connection_string)
            parsed_conns[bucket] = parsed
            if not base_parsed and parsed.get("server"):
                base_parsed = parsed.copy()

        # Nếu không tìm thấy key sysDatabaseName, lấy fallback từ connectionStrings
        if not sys_db:
            if "sys" in parsed_conns and parsed_conns["sys"].get("database"):
                sys_db = parsed_conns["sys"]["database"]
            elif "app" in parsed_conns and parsed_conns["app"].get("database"):
                db_in_app = parsed_conns["app"]["database"]
                if db_in_app.endswith("_A"):
                    sys_db = db_in_app[:-2] + "_S"
                elif db_in_app.endswith("_a"):
                    sys_db = db_in_app[:-2] + "_s"
                elif db_in_app.endswith("_App"):
                    sys_db = db_in_app[:-4] + "_Sys"
                elif db_in_app.endswith("_app"):
                    sys_db = db_in_app[:-4] + "_sys"
                else:
                    sys_db = db_in_app

        if not sys_db:
            return

        # 3. Phân tích đuôi DB SYS để suy ra DB APP:
        # - _S -> _A
        # - _Sys -> _App
        if sys_db.endswith("_S"):
            app_db = sys_db[:-2] + "_A"
        elif sys_db.endswith("_s"):
            app_db = sys_db[:-2] + "_a"
        elif sys_db.endswith("_Sys"):
            app_db = sys_db[:-4] + "_App"
        elif sys_db.endswith("_SYS"):
            app_db = sys_db[:-4] + "_APP"
        elif sys_db.endswith("_sys"):
            app_db = sys_db[:-4] + "_app"
        elif re.search(r"_S$", sys_db, re.IGNORECASE):
            app_db = re.sub(r"_S$", "_A", sys_db, flags=re.IGNORECASE)
        elif re.search(r"_Sys$", sys_db, re.IGNORECASE):
            app_db = re.sub(r"_Sys$", "_App", sys_db, flags=re.IGNORECASE)
        else:
            app_db = sys_db

        # Gán connection info cho sys và app
        sys_info = (parsed_conns.get("sys") or base_parsed or {}).copy()
        sys_info["database"] = sys_db
        self.db_connections["sys"] = sys_info

        app_info = (parsed_conns.get("app") or base_parsed or {}).copy()
        app_info["database"] = app_db
        self.db_connections["app"] = app_info

        # Rebuild raw connection strings
        if "sys" in raw_conns:
            self.raw_connection_strings["sys"] = self._replace_catalog(raw_conns["sys"], sys_db)
        elif base_parsed:
            orig_raw = raw_conns.get("app", "")
            self.raw_connection_strings["sys"] = self._replace_catalog(orig_raw, sys_db)

        if "app" in raw_conns:
            self.raw_connection_strings["app"] = self._replace_catalog(raw_conns["app"], app_db)
        elif base_parsed:
            orig_raw = raw_conns.get("sys", "")
            self.raw_connection_strings["app"] = self._replace_catalog(orig_raw, app_db)

    @staticmethod
    def _resolve_app_name(raw: str | None) -> str:
        """App=%UserID trong Web.config là placeholder runtime FBO — MCP dùng FSD."""
        value = (raw or "").strip()
        if not value or "%" in value:
            return "FSD"
        return value

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
            "app_name": WebConfigLoader._resolve_app_name(
                parts.get("app") or parts.get("application name")
            ),
            "user": parts.get("uid", parts.get("user id", "")),
            "password": parts.get("pwd", parts.get("password", "")),
        }

    @staticmethod
    def _replace_catalog(conn_str: str, new_db: str) -> str:
        if not conn_str:
            return ""
        pattern = re.compile(r"((?:Initial Catalog|Database)\s*=\s*)([^;]+)", re.IGNORECASE)
        if pattern.search(conn_str):
            return pattern.sub(rf"\1{new_db}", conn_str)
        return conn_str + f";Initial Catalog={new_db}"

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
