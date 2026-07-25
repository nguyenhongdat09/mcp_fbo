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
            <appSettings>
              <add key="sysDatabaseName" value="AMERICAN_FBISP2422_S" />
            </appSettings>
            <connectionStrings>
              <add name="appConnectionString"
                   connectionString="Data Source=SERVER01;Initial Catalog=AMERICAN_FBISP2422_S;User ID=sa;Password=secret" />
            </connectionStrings>
            """,
            encoding="utf-8",
        )
        xml_path.write_text("<dir></dir>", encoding="utf-8")

        result = find_connection_by_path(str(xml_path), "app")
        assert result["success"], result
        assert result["project_root"] == str(root)
        assert result["parsed"]["database"] == "AMERICAN_FBISP2422_A"

        sys_result = find_connection_by_path(str(xml_path), "sys")
        assert sys_result["success"]
        assert sys_result["parsed"]["database"] == "AMERICAN_FBISP2422_S"

        # Test case _Sys -> _App
        web_config.write_text(
            """
            <appSettings>
              <add key="sysDatabaseName" value="AMERICAN_FBISP2422_Sys" />
            </appSettings>
            <connectionStrings>
              <add name="appConnectionString"
                   connectionString="Data Source=SERVER01;Initial Catalog=AMERICAN_FBISP2422_Sys;User ID=sa;Password=secret" />
            </connectionStrings>
            """,
            encoding="utf-8",
        )

        result_sys = find_connection_by_path(str(xml_path), "app")
        assert result_sys["success"]
        assert result_sys["parsed"]["database"] == "AMERICAN_FBISP2422_App"

        sys_result2 = find_connection_by_path(str(xml_path), "sys")
        assert sys_result2["success"]
        assert sys_result2["parsed"]["database"] == "AMERICAN_FBISP2422_Sys"

        print("OK: find_connection_by_path tests passed")


if __name__ == "__main__":
    test_app_data_path_resolution()
