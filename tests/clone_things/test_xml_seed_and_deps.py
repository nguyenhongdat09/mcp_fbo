"""Unit tests for XML seed and recursive dependency traversal (TC-XML-*, TC-DEP-*)."""

from unittest.mock import patch
from pathlib import Path
from clone_things.service import clone_things


def test_xml_seed_success(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    xml_file = tmp_path / "SVTran.xml"
    xml_file.write_text("<controller></controller>", encoding="utf-8")

    with patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.summary_xml") as mock_summary_xml, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_conn.return_value = {"success": True, "parsed": {}}
        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_calc AS SELECT 1"

        # Mock XML summary structure
        mock_summary_xml.return_value = {
            "success": True,
            "sql": {
                "procs": ["zc_calc"],
                "tables": ["dmkh"],
                "views": [],
            },
            "controller": {
                "db_table": "d91$@@prime$partition$current",
            },
        }

        # Target has dmkh, but missing zc_calc and d91$
        # Source has zc_calc and d91$
        def side_effect_exists(parsed_conn, clean_name, schema="dbo"):
            if clean_name == "dmkh":
                return True, "U", "USER_TABLE"
            elif clean_name in ("zc_calc", "d91$"):
                # Missing on target, present on source
                # Identify if target by checking mock call order or return
                return False, "", ""
            return False, "", ""

        # Let's mock exists specifically for source vs target:
        call_tracker = {}
        def smart_exists(parsed_conn, clean_name, schema="dbo"):
            # Target is called first
            key = f"{clean_name}_count"
            call_tracker[key] = call_tracker.get(key, 0) + 1
            if call_tracker[key] == 1:
                # Target
                if clean_name == "dmkh":
                    return True, "U", "USER_TABLE"
                return False, "", ""
            else:
                # Source
                if clean_name == "zc_calc":
                    return True, "P", "SQL_STORED_PROCEDURE"
                if clean_name == "d91$":
                    return True, "U", "USER_TABLE"
                return False, "", ""

        mock_exists.side_effect = smart_exists

        res = clone_things(
            object=str(xml_file),
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        assert res["mode_seed"] == "xml"

        # dmkh should be in skipped_exists
        skipped_names = [x["name"] for x in res["skipped_exists"]]
        assert "dbo.dmkh" in skipped_names

        # zc_calc and d91$ should be cloned
        cloned_names = [x["name"] for x in res["cloned"]]
        assert "dbo.zc_calc" in cloned_names
        assert "dbo.d91$" in cloned_names


def test_cycle_dependency_visited(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config") as mock_conn, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_conn.return_value = {"success": True, "parsed": {}}
        mock_open.return_value = (True, None)

        # procA calls procB, procB calls procA (cycle)
        def side_effect_deps(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
            if clean_name == "procA":
                return ["dbo.procB"]
            if clean_name == "procB":
                return ["dbo.procA"]
            return []

        mock_deps.side_effect = side_effect_deps
        mock_fetch.return_value = "CREATE PROCEDURE ..."

        # Missing on target, exists on source
        call_tracker = {}
        def smart_exists(parsed_conn, clean_name, schema="dbo"):
            key = f"{clean_name}_count"
            call_tracker[key] = call_tracker.get(key, 0) + 1
            if call_tracker[key] == 1:
                return False, "", ""
            return True, "P", "SQL_STORED_PROCEDURE"

        mock_exists.side_effect = smart_exists

        res = clone_things(
            object="procA",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True
        cloned_names = [x["name"] for x in res["cloned"]]
        assert len(cloned_names) == 2
        assert "dbo.procA" in cloned_names
        assert "dbo.procB" in cloned_names
        assert res["meta"]["processed_count"] == 2
