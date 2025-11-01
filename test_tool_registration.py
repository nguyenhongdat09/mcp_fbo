#!/usr/bin/env python3
"""Test script to verify generate_field_from_db tool is registered."""

import asyncio
from fastbusiness_mcp.server import FastBusinessMCPServer


async def test_tool_registration():
    """Test that all tools are registered correctly."""
    print("Initializing FastBusiness MCP Server...")
    server = FastBusinessMCPServer()

    print("\nListing registered tools...")
    tools_response = await server.list_tools()

    print(f"\n✅ Total tools registered: {len(tools_response.tools)}\n")

    # Check if generate_field_from_db is registered
    tool_names = [t.name for t in tools_response.tools]

    if "generate_field_from_db" in tool_names:
        print("✅ SUCCESS: generate_field_from_db tool is registered!\n")
    else:
        print("❌ ERROR: generate_field_from_db tool NOT found!\n")

    print("All registered tools:")
    print("-" * 80)
    for tool in tools_response.tools:
        marker = "⭐" if tool.name == "generate_field_from_db" else "  "
        print(f"{marker} {tool.name}")
        print(f"   {tool.description}")
        print()


if __name__ == "__main__":
    asyncio.run(test_tool_registration())
