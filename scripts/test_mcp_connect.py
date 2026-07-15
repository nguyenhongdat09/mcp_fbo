"""Test MCP server startup and initialize handshake."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_server(exe_path: str, cwd: str | None = None) -> int:
    params = StdioServerParameters(
        command=exe_path,
        args=[],
        cwd=cwd,
        env=os.environ.copy(),
    )
    print(f"Testing: {exe_path}")
    if cwd:
        print(f"CWD: {cwd}")
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print(f"OK - {len(tools.tools)} tools: {[t.name for t in tools.tools]}")
                return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


def main() -> None:
    targets = [
        (r"E:\fastbusiness_mcp\fastbusiness_mcp.exe", r"E:\fastbusiness_mcp"),
        (r"e:\mcp_fbo\dist\fastbusiness_mcp\fastbusiness_mcp.exe", r"e:\mcp_fbo\dist\fastbusiness_mcp"),
    ]
    code = 0
    for exe, cwd in targets:
        if not Path(exe).is_file():
            print(f"SKIP missing: {exe}")
            continue
        code = max(code, asyncio.run(test_server(exe, cwd)))
        print()
    sys.exit(code)


if __name__ == "__main__":
    main()
