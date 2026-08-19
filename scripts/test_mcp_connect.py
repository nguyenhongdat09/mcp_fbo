"""Test MCP server startup and initialize handshake."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


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
                
                # Check if Pydantic validation is active
                res = await session.call_tool("query_database", {
                    "file_path": "x.xml",
                    "query": "SELECT 1",
                    "db_type": "oracle",
                })
                text = res.content[0].text if res.content else ""
                if "[LỖI THAM SỐ" in text or "Input should be 'app' or 'sys'" in text or "app" in text and "sys" in text:
                    print("✅ Pydantic validation active (NEW build)")
                else:
                    print("⚠️ WARN: exe may be OLD build (no Pydantic validation active)")
                return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    targets = [
        (str(repo_root / "dist" / "fastbusiness_mcp" / "fastbusiness_mcp.exe"), str(repo_root / "dist" / "fastbusiness_mcp")),
        (r"E:\fastbusiness_mcp\fastbusiness_mcp.exe", r"E:\fastbusiness_mcp"),
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
