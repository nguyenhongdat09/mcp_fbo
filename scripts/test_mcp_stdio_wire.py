"""Test MCP Server over stdio wire protocol (simulating Cursor / Claude / Inspector)."""

import asyncio
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_wire():
    python_exe = sys.executable
    repo_root = str(Path(__file__).resolve().parent.parent)

    params = StdioServerParameters(
        command=python_exe,
        args=["-m", "fastbusiness_mcp.server"],
        cwd=repo_root,
        env=os.environ.copy(),
    )

    print(f"Connecting to MCP server via stdio: {python_exe} -m fastbusiness_mcp.server ...")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_res = await session.initialize()
            print(f"✅ Handshake initialized: server={init_res.server_info.name} v{init_res.server_info.version}")

            tools_res = await session.list_tools()
            tools_list = [t.name for t in tools_res.tools]
            print(f"✅ Tools listed ({len(tools_list)}): {tools_list}")
            assert set(tools_list) == {
                "query_database",
                "get_xml_entities",
                "query_radar",
                "read_local_file",
                "search_qlyc",
            }

            # Call search_qlyc tool over wire
            res = await session.call_tool("search_qlyc", arguments={"query": "test_wire"})
            print(f"✅ Call tool 'search_qlyc' result: {res.content[0].text[:80]}...")

            # Call query_database with invalid db_type over wire
            val_res = await session.call_tool("query_database", arguments={"file_path": "x.xml", "query": "SELECT 1", "db_type": "oracle"})
            assert val_res.is_error, "Should be marked as error result"
            val_text = val_res.content[0].text
            print(f"✅ Wire validation error received:\n{val_text[:120]}...\n")
            assert "[LỖI THAM SỐ KHÔNG HỢP LỆ]" in val_text
            assert "pydantic.dev" not in val_text

    print("🎉 MCP Wire Protocol test passed perfectly!")


if __name__ == "__main__":
    asyncio.run(test_mcp_wire())
