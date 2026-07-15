"""Gọi MCP server thật qua stdio và test get_xml_entities."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

FILE_PATH = (
    r"\\172.168.5.14\CustomerPro\FBI\NHM_FBI\FBISP2422"
    r"\App_Data\Controllers\Dir\CRTran.xml"
)
ENTITIES = ["XMLWhenVoucherInit", "XMLVoucherBookAndNumberFields", "ListField"]


def _server_params() -> StdioServerParameters:
    exe = Path(r"E:\fastbusiness_mcp\fastbusiness_mcp.exe")
    if exe.is_file():
        return StdioServerParameters(command=str(exe), args=[], env=os.environ.copy())

    root = Path(__file__).resolve().parent.parent
    return StdioServerParameters(
        command=str(root / "venv" / "Scripts" / "python.exe"),
        args=["-m", "fastbusiness_mcp.server"],
        cwd=str(root),
        env=os.environ.copy(),
    )


async def run() -> int:
    params = _server_params()
    print(f"MCP server: {params.command} {' '.join(params.args)}")
    print(f"File: {FILE_PATH}")
    print(f"Entities: {ENTITIES}")
    print("-" * 60)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("Tools:", ", ".join(names))
            if "get_xml_entities" not in names:
                print("[ERROR] get_xml_entities not in tool list")
                return 1

            result = await session.call_tool(
                "get_xml_entities",
                arguments={
                    "file_path": FILE_PATH,
                    "entities": ENTITIES,
                },
            )

            for block in result.content:
                if isinstance(block, types.TextContent):
                    print(block.text)
                else:
                    print(block)

            if getattr(result, "isError", False):
                return 1

    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
