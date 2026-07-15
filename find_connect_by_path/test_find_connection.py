"""Quick test for find_connect_by_path (no pytest required)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from find_connect_by_path import find_connection_by_path


def test_app_data_path_resolution():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        web_config = root / "Web.config"
        xml_path = root / "App_Data" / "Controllers" / "Dir" / "Test.xml"
        xml_path.parent.mkdir(parents=True)

        web_config.write_text(
            """
            <connectionStrings>
              <add name="appConnectionString"
                   connectionString="Data Source=SERVER01;Initial Catalog=FBO_App;User ID=sa;Password=secret" />
              <add name="sysConnectionString"
                   connectionString="Data Source=SERVER01;Initial Catalog=FBO_Sys;User ID=sa;Password=secret" />
            </connectionStrings>
            """,
            encoding="utf-8",
        )
        xml_path.write_text("<dir></dir>", encoding="utf-8")

        result = find_connection_by_path(str(xml_path), "app")
        assert result["success"], result
        assert result["project_root"] == str(root)
        assert "Data Source=SERVER01" in result["connection_string"]
        assert result["parsed"]["database"] == "FBO_A"

        all_result = find_connection_by_path(str(xml_path), "all")
        assert all_result["success"]
        assert set(all_result["connections"]) == {"app", "sys"}

        print("OK: find_connection_by_path tests passed")


if __name__ == "__main__":
    test_app_data_path_resolution()
