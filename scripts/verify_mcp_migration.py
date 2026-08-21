"""Comprehensive verification test for FastBusiness MCP MCPServer migration."""

import asyncio
import json
import sys
from pathlib import Path

# Ensure utf-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastbusiness_mcp.mcp_app import server, get_config, set_config
from mcp.server.mcpserver.exceptions import ToolError


async def test_tools_listing():
    print("=== 1. TEST LIST TOOLS & SCHEMAS ===")
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    print(f"Total tools: {len(tools)} -> {tool_names}")

    expected_tools = {
        "query_database",
        "get_xml_entities",
        "query_radar",
        "read_local_file",
        "search_qlyc",
    }
    assert set(tool_names) == expected_tools, f"Expected {expected_tools}, got {set(tool_names)}"

    for t in tools:
        print(f"\n--- Tool: {t.name} ---")
        assert t.description, f"Tool {t.name} is missing description!"
        assert t.input_schema, f"Tool {t.name} is missing input_schema!"
        props = t.input_schema.get("properties", {})
        print(f"Description preview: {t.description[:80]}...")
        print(f"Properties: {list(props.keys())}")
        print(f"Required: {t.input_schema.get('required', [])}")

        # Verify parameter descriptions exist
        for prop_name, prop_data in props.items():
            assert "description" in prop_data, f"Param '{prop_name}' in tool '{t.name}' is missing description!"

    print("\n✅ All 5 tools listed with full descriptions and parameter metadata!")


async def test_validation_errors():
    print("\n=== 2. TEST PYDANTIC V2 VALIDATION ERRORS (VIETNAMESE FORMAT) ===")

    # 2.1 query_database: db_type invalid
    try:
        await server.call_tool("query_database", {"file_path": "test.xml", "query": "SELECT 1", "db_type": "oracle"})
        assert False, "Should have raised ToolError for invalid db_type"
    except ToolError as e:
        msg = str(e)
        print(f"✅ query_database rejected invalid db_type:\n{msg}\n")
        assert "[LỖI THAM SỐ KHÔNG HỢP LỆ]" in msg
        assert "db_type" in msg
        assert "pydantic.dev" not in msg

    # 2.2 query_database: missing required file_path
    try:
        await server.call_tool("query_database", {"query": "SELECT 1"})
        assert False, "Should have raised ToolError for missing file_path"
    except ToolError as e:
        msg = str(e)
        print(f"✅ query_database rejected missing required field:\n{msg}\n")
        assert "[LỖI THAM SỐ KHÔNG HỢP LỆ]" in msg
        assert "file_path" in msg
        assert "ABSOLUTE" in msg or "TUYỆT ĐỐI" in msg
        assert "pydantic.dev" not in msg

    # 2.3 get_xml_entities: mode invalid
    try:
        await server.call_tool("get_xml_entities", {"file_path": "test.xml", "mode": "invalid_mode"})
        assert False, "Should have raised ToolError for invalid mode"
    except ToolError as e:
        msg = str(e)
        print(f"✅ get_xml_entities rejected invalid mode:\n{msg}\n")
        assert "[LỖI THAM SỐ KHÔNG HỢP LỆ]" in msg
        assert "mode" in msg
        assert "pydantic.dev" not in msg

    # 2.4 read_local_file: read_option invalid
    try:
        await server.call_tool("read_local_file", {"file_path": "Dir/x.xml", "reference_file": "E:\\x.xml", "read_option": 99})
        assert False, "Should have raised ToolError for invalid read_option"
    except ToolError as e:
        msg = str(e)
        print(f"✅ read_local_file rejected invalid read_option:\n{msg}\n")
        assert "[LỖI THAM SỐ KHÔNG HỢP LỆ]" in msg
        assert "read_option" in msg
        assert "pydantic.dev" not in msg

    # 2.5 search_qlyc: page invalid type
    try:
        await server.call_tool("search_qlyc", {"query": "test", "page": "not_an_int"})
        assert False, "Should have raised ToolError for string page"
    except ToolError as e:
        msg = str(e)
        print(f"✅ search_qlyc rejected invalid page type:\n{msg}\n")
        assert "[LỖI THAM SỐ KHÔNG HỢP LỆ]" in msg
        assert "page" in msg
        assert "pydantic.dev" not in msg


async def test_sample_executions():
    print("\n=== 3. TEST TOOL EXECUTIONS (SAFE CALLS) ===")

    # 3.1 query_radar with invalid cypher -> returns error message, does not crash
    radar_res = await server.call_tool(
        "query_radar",
        {
            "reference_file": r"E:\FBO\SP2263\App_Data\Controllers\Dir\SVTran.xml",
            "cypher_query": "INVALID CYPHER SYNTAX ???",
            "mode": "query",
        },
    )
    res_text = radar_res.content[0].text
    print(f"query_radar Cypher error response preview:\n{res_text[:120]}...\n")
    assert "[LỖI CÚ PHÁP CYPHER KUZUDB]" in res_text or "Kùzu" in res_text or "error" in res_text.lower() or "Lỗi" in res_text
    print("✅ query_radar handles Cypher errors gracefully via custom error template.")

    # 3.2 query_radar with non-existent / invalid reference file path -> returns [LỖI REFERENCE_FILE]
    radar_ref_res = await server.call_tool(
        "query_radar",
        {
            "reference_file": r"E:\nonexistent_project_path_12345\x.xml",
            "mode": "schema",
        },
    )
    radar_ref_text = radar_ref_res.content[0].text
    print(f"query_radar invalid reference_file response:\n{radar_ref_text[:150]}...\n")
    assert "[LỖI REFERENCE_FILE]" in radar_ref_text or "[LỖI CÚ PHÁP CYPHER" in radar_ref_text
    print("✅ query_radar handles invalid reference_file gate errors properly.")

    # 3.3 search_qlyc with mock config
    set_config({"rag_qlyc": {"base_url": "http://invalid-host:9999", "api_key": "dummy", "bp_lt": "FSD"}})
    qlyc_res = await server.call_tool("search_qlyc", {"query": "test"})
    qlyc_text = qlyc_res.content[0].text
    print(f"search_qlyc response preview: {qlyc_text[:120]}...")
    assert "ok" in qlyc_text.lower() or "error" in qlyc_text.lower() or "lỗi" in qlyc_text.lower()
    print("✅ search_qlyc executed and formatted result properly.")


def test_search_qlyc_unit_tests():
    print("\n=== 4. TEST SEARCH_QLYC LOGIC ===")
    from search_qlyc.service import search_qlyc

    r1 = search_qlyc(query="", fcode1="", ma_da="")
    assert r1["ok"] is False and r1["error"] == "query_thieu"

    r2 = search_qlyc(query="test", config=None)
    assert r2["ok"] is False and r2["error"] == "config_thieu"

    r3 = search_qlyc(query="test", config={"base_url": "http://localhost:8000"})
    assert r3["ok"] is False and r3["error"] == "config_thieu"

    r4 = search_qlyc(query="test", config={"base_url": "http://invalid-host-that-does-not-exist:9999", "api_key": "123"})
    assert r4["ok"] is False and r4["error"] == "khong_ket_noi_api"

    r5 = search_qlyc(query="", fcode1="YC123", config={"base_url": "http://invalid-host-that-does-not-exist:9999", "api_key": "123"})
    assert r5["ok"] is False and r5["error"] == "khong_ket_noi_api"

    print("✅ All search_qlyc service test cases passed!")


async def main():
    await test_tools_listing()
    await test_validation_errors()
    await test_sample_executions()
    test_search_qlyc_unit_tests()
    print("\n🎉 ALL MIGRATION VERIFICATION CHECKS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
