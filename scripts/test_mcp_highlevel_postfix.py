"""
Retest toàn diện sau khi Antigravity thêm MCP high-level tools.
Gọi trực tiếp hàm trong mcp_server (nếu import được) + fallback xml_graph_query.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF = str(
    Path(r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Dir\CPTran.xml")
)


def _load_json(s: str):
    if isinstance(s, str) and s.startswith("Lỗi"):
        raise RuntimeError(s)
    return json.loads(s) if isinstance(s, str) else s


def main() -> int:
    results = []

    # --- Import MCP tool functions (không chạy FastMCP transport) ---
    tools = {}
    try:
        # Patch: tránh sys.exit nếu thiếu mcp — mcp_server vẫn cần FastMCP
        import mcp_server as ms

        tools["search_nodes"] = ms.search_nodes
        tools["get_related_nodes"] = ms.get_related_nodes
        tools["query_node_details"] = ms.query_node_details
        tools["query_radar"] = ms.query_radar
        tools["read_local_file"] = ms.read_local_file
        import_ok = True
        import_detail = "imported mcp_server tools"
    except SystemExit as e:
        import_ok = False
        import_detail = f"mcp_server SystemExit (thiếu package mcp?): {e}"
    except Exception as e:
        import_ok = False
        import_detail = f"import fail: {e}"

    results.append(("import_mcp_server", import_ok, import_detail))

    if not import_ok:
        # Fallback: test engine path tương đương tools
        from xml_codegraph.query.engine import xml_graph_query

        def search_nodes(query, reference_file, match_type="all", folder_filter=None, limit=20):
            if not folder_filter:
                folder_filter = "Dir,Grid,Filter,Report,Lookup"
            return json.dumps(
                xml_graph_query(
                    "search",
                    query,
                    reference_file,
                    match_type=match_type,
                    folder_filter=folder_filter,
                    limit=limit,
                ),
                ensure_ascii=False,
            )

        def get_related_nodes(target, reference_file, mode="navigate", include_shared=False):
            res = xml_graph_query(mode, target, reference_file)
            if not include_shared and isinstance(res, dict):
                for key in ("dependencies", "dependents", "results"):
                    if key in res and isinstance(res[key], list):
                        res[key] = [
                            item
                            for item in res[key]
                            if not (isinstance(item, dict) and item.get("type") == "SHARED_INCLUDE")
                        ]
            return json.dumps(res, ensure_ascii=False)

        def query_node_details(target, reference_file, view="context"):
            res = xml_graph_query(view, target, reference_file, compact=True)
            if isinstance(res, dict):
                res.setdefault("needs_xml", [])
                res.setdefault("agent_hint", "")
                res.setdefault("source_on_disk", "")
            return json.dumps(res, ensure_ascii=False)

        tools = {
            "search_nodes": search_nodes,
            "get_related_nodes": get_related_nodes,
            "query_node_details": query_node_details,
        }

    # 1) navigate CPTran via get_related_nodes
    try:
        nav = _load_json(tools["get_related_nodes"]("Dir/CPTran.xml", REF, mode="navigate"))
        grids = nav.get("grid_details") or []
        needs = set(nav.get("needs_xml") or [])
        names = {g.get("controller") or g.get("path") for g in grids if isinstance(g, dict)}
        ok = any("CPTax" in (n or "") for n in names) and any("CPTax" in x for x in needs)
        results.append(
            (
                "mcp_get_related_navigate_CPTran",
                ok,
                f"grids={len(grids)} needs={sorted(needs)[:6]} controllers={sorted(names)[:6]}",
            )
        )
    except Exception as e:
        results.append(("mcp_get_related_navigate_CPTran", False, str(e)[:200]))

    # 2) search synonym gia ban
    try:
        s = _load_json(tools["search_nodes"]("gia ban", REF, match_type="field", limit=10))
        # shape linh hoạt
        n = 0
        for k, v in (s.items() if isinstance(s, dict) else []):
            if isinstance(v, list) and k not in ("needs_xml",):
                n = max(n, len(v))
        ok = n > 0 or (isinstance(s, dict) and s.get("field_matches"))
        results.append(("mcp_search_gia_ban", bool(ok), f"keys={list(s)[:8] if isinstance(s, dict) else type(s)} n≈{n}"))
    except Exception as e:
        results.append(("mcp_search_gia_ban", False, str(e)[:200]))

    # 3) search handler TenVtFromDienGiai code
    try:
        s = _load_json(
            tools["search_nodes"]("TenVtFromDienGiai", REF, match_type="code", limit=10)
        )
        blob = json.dumps(s, ensure_ascii=False)
        ok = "GLTax" in blob or "CPDetail" in blob
        results.append(("mcp_search_TenVtFromDienGiai", ok, blob[:180]))
    except Exception as e:
        results.append(("mcp_search_TenVtFromDienGiai", False, str(e)[:200]))

    # 4) CPTax details needs_xml + source
    try:
        d = _load_json(tools["query_node_details"]("Grid/CPTax.xml", REF, view="context"))
        needs = d.get("needs_xml") or []
        source = d.get("source_on_disk") or d.get("source") or ""
        ok = any("CPTax" in str(x) for x in needs) and (".f" in str(source) or d.get("agent_hint"))
        results.append(
            (
                "mcp_details_CPTax_f_only",
                ok,
                f"needs_xml={needs} source={source} hint={str(d.get('agent_hint'))[:80]}",
            )
        )
    except Exception as e:
        results.append(("mcp_details_CPTax_f_only", False, str(e)[:200]))

    # 5) path normalize via execute_cypher / query_radar
    try:
        from xml_codegraph.storage.kuzu_index import KuzuIndexStore

        local = ROOT / "_tmp_kuzu"
        store = KuzuIndexStore(local if local.exists() else Path(REF).parents[2] / ".fbograph" / "kuzu", read_only=True)
        rows = store.execute_cypher(
            "MATCH (a:XmlFile {relative_path: 'Dir/CPTran.xml'})-[r:Rel]->(b:XmlFile) "
            "WHERE r.edge_type = 'GRID_MASTER_DETAIL' "
            "RETURN b.relative_path AS path ORDER BY path"
        )
        ok = len(rows) >= 5 and any("CPTax" in (r.get("path") or "") for r in rows)
        results.append(("path_normalize_forward_slash", ok, f"n={len(rows)} paths={[r.get('path') for r in rows]}"))
    except Exception as e:
        results.append(("path_normalize_forward_slash", False, str(e)[:220]))

    # 6) query_radar guardrail auto LIMIT
    if "query_radar" in tools:
        try:
            raw = tools["query_radar"](
                "MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile) "
                "WHERE a.relative_path CONTAINS 'CPTran.xml' AND a.folder_type = 'Dir' "
                "RETURN r.edge_type, b.relative_path",
                REF,
            )
            data = _load_json(raw)
            has_warning = isinstance(data, dict) and "warning" in data
            rows = data.get("results") if has_warning else data
            n = len(rows) if isinstance(rows, list) else -1
            ok = has_warning and n <= 50
            results.append(("query_radar_autolimit", ok, f"warning={has_warning} n={n}"))
        except Exception as e:
            results.append(("query_radar_autolimit", False, str(e)[:220]))
    else:
        results.append(("query_radar_autolimit", False, "query_radar not available (mcp import failed)"))

    # 7) dependencies default no SHARED_INCLUDE
    try:
        deps = _load_json(
            tools["get_related_nodes"]("Dir/CPTran.xml", REF, mode="dependencies", include_shared=False)
        )
        items = deps.get("dependencies") or deps.get("results") or []
        shared = [i for i in items if isinstance(i, dict) and i.get("type") == "SHARED_INCLUDE"]
        ok = len(shared) == 0
        types = sorted({i.get("type") for i in items if isinstance(i, dict)})
        results.append(("deps_no_shared_default", ok, f"n={len(items)} types={types} shared={len(shared)}"))
    except Exception as e:
        results.append(("deps_no_shared_default", False, str(e)[:200]))

    print("=" * 100)
    print("POST-FIX FULL MCP / AGENT RETEST")
    print("=" * 100)
    fails = 0
    for name, ok, detail in results:
        flag = "[ok]" if ok else "[XX]"
        if not ok:
            fails += 1
        print(f"{flag} {name}")
        print(f"     {detail[:300]}")
    print("-" * 100)
    print(f"SUMMARY: ok={len(results)-fails} fail={fails}")
    print("=" * 100)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
