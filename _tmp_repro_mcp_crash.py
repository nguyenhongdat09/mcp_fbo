# -*- coding: utf-8 -*-
"""Reproduce MCP tool crash outside Cursor."""
import traceback
import sys

sys.path.insert(0, r"E:\mcp_fbo")

ref = r"\\172.168.5.14\CustomerPro\FBI\TMSG\FBISP242\App_Data\Controllers\Dir\CPTran.xml"

print("1) query_database...", flush=True)
try:
    from queryDatabase import query_database
    from queryDatabase.formatter import format_query_result
    r = query_database(ref, "SELECT 1 AS ok", query_type=1)
    print(format_query_result(r)[:500], flush=True)
except Exception:
    traceback.print_exc()

print("2) search_nodes giay bao no...", flush=True)
try:
    from xml_codegraph.mcp_tools import mcp_search_nodes
    r = mcp_search_nodes("giay bao no", ref, match_type="file", folder_filter="Dir,Grid", limit=5)
    print(r[:800], flush=True)
except Exception:
    traceback.print_exc()

print("3) get_related_nodes...", flush=True)
try:
    from xml_codegraph.mcp_tools import mcp_get_related_nodes
    r = mcp_get_related_nodes("Dir/CPTran.xml", ref, mode="navigate")
    print(r[:800], flush=True)
except Exception:
    traceback.print_exc()

print("DONE", flush=True)
