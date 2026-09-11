"""Unit tests for XML seed and recursive dependency traversal (TC-XML-*, TC-DEP-*)."""

from unittest.mock import patch
from clone_things.service import clone_things


def _conn_side_effect(file_path, db_type="app"):
    return {
        "success": True,
        "parsed": {"_path": str(file_path), "_db": db_type},
    }


def test_xml_seed_success(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    xml_file = tmp_path / "SVTran.xml"
    xml_file.write_text("<controller></controller>", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.summary_xml") as mock_summary_xml, \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)
        mock_deps.return_value = []
        mock_fetch.return_value = "CREATE PROCEDURE dbo.zc_calc AS SELECT 1"

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

        # Dual lookup: per object → target app, target sys, then source app, source sys.
        # Partition normalize: d91$ → d91$000000
        def smart_exists(parsed_conn, clean_name, schema="dbo"):
            db = (parsed_conn or {}).get("_db", "app")
            path = (parsed_conn or {}).get("_path", "")
            on_target = "P2" in str(path)

            if clean_name == "dmkh":
                # Có trên target app
                return (True, "U", "USER_TABLE") if on_target and db == "app" else (False, "", "")

            if clean_name in ("zc_calc", "d91$000000"):
                if on_target:
                    return False, "", ""
                # Có trên source app
                if db == "app":
                    obj_type = "P" if clean_name == "zc_calc" else "U"
                    desc = "SQL_STORED_PROCEDURE" if clean_name == "zc_calc" else "USER_TABLE"
                    return True, obj_type, desc
                return False, "", ""

            return False, "", ""

        mock_exists.side_effect = smart_exists

        res = clone_things(
            object=str(xml_file),
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True, res
        assert res["mode_seed"] == "xml"

        skipped_names = [x["name"] for x in res["skipped_exists"]]
        assert "dbo.dmkh" in skipped_names

        cloned_names = [x["name"] for x in res["cloned"]]
        assert "dbo.zc_calc" in cloned_names
        assert "dbo.d91$000000" in cloned_names


def test_cycle_dependency_visited(tmp_path):
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("", encoding="utf-8")

    with patch("clone_things.service.get_connection_config", side_effect=_conn_side_effect), \
         patch("clone_things.service.check_object_exists_and_type") as mock_exists, \
         patch("clone_things.service.fetch_object_script") as mock_fetch, \
         patch("clone_things.service.extract_object_dependencies") as mock_deps, \
         patch("clone_things.service.open_file_for_user") as mock_open:

        mock_open.return_value = (True, None)

        def side_effect_deps(file_path, clean_name, schema, obj_type, type_desc, db_type="app"):
            if clean_name == "procA":
                return ["dbo.procB"]
            if clean_name == "procB":
                return ["dbo.procA"]
            return []

        mock_deps.side_effect = side_effect_deps
        mock_fetch.return_value = "CREATE PROCEDURE ..."

        def smart_exists(parsed_conn, clean_name, schema="dbo"):
            path = (parsed_conn or {}).get("_path", "")
            db = (parsed_conn or {}).get("_db", "app")
            on_target = "P2" in str(path)
            if on_target:
                return False, "", ""
            # Có trên source app
            if db == "app" and clean_name in ("procA", "procB"):
                return True, "P", "SQL_STORED_PROCEDURE"
            return False, "", ""

        mock_exists.side_effect = smart_exists

        res = clone_things(
            object="procA",
            project_source="E:\\FBO\\P1",
            project_target="E:\\FBO\\P2",
            path_to_pasted=str(sql_file),
            open_file=False,
        )

        assert res["success"] is True, res
        cloned_names = [x["name"] for x in res["cloned"]]
        assert len(cloned_names) == 2
        assert "dbo.procA" in cloned_names
        assert "dbo.procB" in cloned_names
        assert res["meta"]["processed_count"] == 2
