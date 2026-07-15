"""
Mô phỏng lỗi agent khi CHỈ dùng query_radar (Cypher thô)
so với QueryEngine/CLI đã có sẵn.

Mục tiêu: chứng minh bằng số liệu case agent hay fail,
không chỉ lý thuyết.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOCAL_KUZU = ROOT / "_tmp_kuzu"
REF = Path(r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Dir\CPTran.xml")


def _ok(name: str, detail: str) -> dict:
    return {"status": "ok", "case": name, "detail": detail}


def _fail(name: str, detail: str, severity: str = "high") -> dict:
    return {"status": "FAIL", "severity": severity, "case": name, "detail": detail}


def _warn(name: str, detail: str) -> dict:
    return {"status": "WARN", "case": name, "detail": detail}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    from xml_codegraph.storage.kuzu_index import KuzuIndexStore
    from xml_codegraph.query.engine import xml_graph_query, expand_keyword

    path = LOCAL_KUZU if LOCAL_KUZU.exists() else (REF.parent.parent.parent / ".fbograph" / "kuzu")
    store = KuzuIndexStore(path, read_only=True)
    results: list[dict] = []

    # ------------------------------------------------------------------
    # BASELINE: engine đúng
    # ------------------------------------------------------------------
    t0 = time.time()
    engine_nav = xml_graph_query("navigate", "Dir/CPTran.xml", str(REF))
    print(f"[base] navigate keys={list(engine_nav.keys())} sample={json.dumps(engine_nav, ensure_ascii=False)[:500]}")
    engine_search_tax = xml_graph_query(
        "search", "TenVtFromDienGiai", str(REF), match_type="code"
    )
    engine_ctx = xml_graph_query("context", "Dir/CPTran.xml", str(REF), compact=True)
    engine_cptax = xml_graph_query("context", "Grid/CPTax.xml", str(REF), compact=True)
    engine_syn = expand_keyword("giay bao no")
    print(f"[base] engine calls {time.time()-t0:.2f}s")

    nav_grids = set()
    for g in engine_nav.get("grids") or []:
        if isinstance(g, dict):
            nav_grids.add(g.get("path") or g.get("file") or g.get("relative_path") or str(g))
        elif isinstance(g, (list, tuple)) and len(g) >= 2:
            nav_grids.add(g[1])
        else:
            nav_grids.add(str(g))
    # fallback: related grids embedded elsewhere
    for key in ("grid_refs", "related_grids"):
        for g in engine_nav.get(key) or []:
            if isinstance(g, dict):
                nav_grids.add(g.get("path") or g.get("relative_path"))
            else:
                nav_grids.add(str(g))
    nav_grids = {x for x in nav_grids if x}
    needs_xml_engine = set(engine_ctx.get("needs_xml") or [])
    cptax_needs = set(engine_cptax.get("needs_xml") or [])
    cptax_source = engine_cptax.get("source_on_disk") or engine_cptax.get("source")

    print(f"[base] navigate grids={sorted(nav_grids)}")
    print(f"[base] needs_xml={sorted(needs_xml_engine)}")
    print(f"[base] CPTax needs_xml={sorted(cptax_needs)} source={cptax_source}")
    print(f"[base] synonym giay bao no -> {engine_syn[:6]}...")

    # ------------------------------------------------------------------
    # CASE 1: Path slash — docstring MCP dùng '/', DB thường '\'
    # ------------------------------------------------------------------
    q_slash = """
    MATCH (a:XmlFile {relative_path: 'Dir/CPTran.xml'})-[r:Rel]->(b:XmlFile)
    RETURN r.edge_type, b.relative_path LIMIT 20
    """
    r_slash = store.execute_cypher(q_slash)
    q_bslash = """
    MATCH (a:XmlFile {relative_path: 'Dir\\\\CPTran.xml'})-[r:Rel]->(b:XmlFile)
    WHERE r.edge_type = 'GRID_MASTER_DETAIL'
    RETURN r.edge_type, b.relative_path, b.needs_xml
    """
    r_bslash = store.execute_cypher(q_bslash)
    # Also try what relative_path actually looks like
    sample_paths = store.execute_cypher(
        "MATCH (f:XmlFile) WHERE f.relative_path CONTAINS 'CPTran' RETURN f.relative_path LIMIT 5"
    )

    if not r_slash and r_bslash:
        results.append(
            _fail(
                "path_slash_docstring",
                f"Cypher với '/' (như docstring MCP) trả 0 hàng; với '\\\\' được {len(r_bslash)} rows. "
                f"sample_paths={sample_paths}",
            )
        )
    elif not r_slash and not r_bslash:
        results.append(
            _fail(
                "path_slash_docstring",
                f"Cả '/' và '\\\\' đều fail/empty. sample={sample_paths}",
            )
        )
    else:
        results.append(_ok("path_slash_docstring", f"slash={len(r_slash)} bslash={len(r_bslash)} sample={sample_paths}"))

    # ------------------------------------------------------------------
    # CASE 2: Quên filter edge_type → SHARED_INCLUDE làm ngập
    # ------------------------------------------------------------------
    q_all_rel = """
    MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)
    WHERE a.relative_path CONTAINS 'CPTran'
    RETURN r.edge_type, count(*) AS c
    ORDER BY c DESC
    """
    by_type = store.execute_cypher(q_all_rel)
    shared = next((x for x in by_type if (x.get("r.edge_type") or x.get("edge_type")) == "SHARED_INCLUDE"), None)
    grid = next((x for x in by_type if (x.get("r.edge_type") or x.get("edge_type")) == "GRID_MASTER_DETAIL"), None)
    shared_c = (shared or {}).get("c") or (shared or {}).get("count(*)") or 0
    grid_c = (grid or {}).get("c") or (grid or {}).get("count(*)") or 0
    if shared_c > grid_c * 5:
        results.append(
            _fail(
                "shared_include_flood",
                f"CPTran outgoing by type: {by_type}. SHARED_INCLUDE={shared_c} >> GRID_MASTER={grid_c}. "
                "Agent MATCH (a)-[r]->(b) không filter sẽ nhận toàn Include chung.",
            )
        )
    else:
        results.append(_ok("shared_include_flood", str(by_type)))

    # ------------------------------------------------------------------
    # CASE 3: Agent nghĩ relationship typed Neo4j-style [:GRID_MASTER_DETAIL]
    # ------------------------------------------------------------------
    try:
        r_typed = store.execute_cypher(
            "MATCH (a:XmlFile)-[r:GRID_MASTER_DETAIL]->(b:XmlFile) RETURN b.relative_path LIMIT 5"
        )
        results.append(
            _fail(
                "wrong_rel_label",
                f"Typed rel [:GRID_MASTER_DETAIL] KHÔNG phải schema — nếu không throw thì kết quả lạ: {r_typed}",
            )
        )
    except Exception as e:
        results.append(
            _fail(
                "wrong_rel_label",
                f"Agent viết MATCH ()-[:GRID_MASTER_DETAIL]->() sẽ lỗi (schema thật: :Rel + edge_type property). err={e}",
            )
        )

    # ------------------------------------------------------------------
    # CASE 4: list_contains exact vs synonym / tiếng Việt
    # ------------------------------------------------------------------
    q_gia_ban = """
    MATCH (f:XmlFile)
    WHERE list_contains(f.fields_names, 'gia ban') OR list_contains(f.fields_names, 'giá bán')
    RETURN f.relative_path LIMIT 10
    """
    r_gia_literal = store.execute_cypher(q_gia_ban)
    expanded = expand_keyword("gia ban")
    # Engine path
    eng_gia = xml_graph_query("search", "gia ban", str(REF), match_type="field", limit=10)
    eng_field_hits = len(eng_gia.get("field_matches") or eng_gia.get("fields") or [])
    # rough: any matches in result
    eng_n = 0
    if isinstance(eng_gia, dict):
        for k in ("field_matches", "fields", "matches", "results"):
            if isinstance(eng_gia.get(k), list):
                eng_n = max(eng_n, len(eng_gia[k]))
        # compact search shape
        if eng_n == 0 and "items" in eng_gia:
            eng_n = len(eng_gia["items"])
        if eng_n == 0:
            # often top-level list under keys from format
            eng_n = sum(1 for k, v in eng_gia.items() if isinstance(v, list) and k not in ("needs_xml",))

    if len(r_gia_literal) == 0 and eng_n > 0:
        results.append(
            _fail(
                "no_synonym_in_cypher",
                f"Cypher literal 'gia ban'/'giá bán' = 0 hits. expand_keyword={expanded}. "
                f"Engine search có ~{eng_n} hits. Agent không biết gọi expand_keyword.",
            )
        )
    else:
        results.append(
            _warn(
                "no_synonym_in_cypher",
                f"literal={len(r_gia_literal)} engine≈{eng_n} expanded={expanded}",
            )
        )

    # ------------------------------------------------------------------
    # CASE 5: Tìm handler TenVtFromDienGiai bằng fields_names thay vì js_text
    # ------------------------------------------------------------------
    q_wrong_field = """
    MATCH (f:XmlFile)
    WHERE list_contains(f.fields_names, 'TenVtFromDienGiai')
    RETURN f.relative_path LIMIT 10
    """
    r_wrong = store.execute_cypher(q_wrong_field)
    q_js = """
    MATCH (f:XmlFile)
    WHERE f.js_text CONTAINS 'TenVtFromDienGiai'
    RETURN f.relative_path LIMIT 10
    """
    r_js = store.execute_cypher(q_js)
    eng_paths = []
    for m in engine_search_tax.get("code_matches") or engine_search_tax.get("matches") or []:
        if isinstance(m, dict):
            eng_paths.append(m.get("path") or m.get("relative_path"))
    if not eng_paths and isinstance(engine_search_tax.get("results"), list):
        eng_paths = [
            x.get("path") for x in engine_search_tax["results"] if isinstance(x, dict)
        ]

    if len(r_wrong) == 0 and len(r_js) > 0:
        results.append(
            _fail(
                "handler_search_wrong_property",
                f"Agent hay search fields_names → 0. Đúng là js_text → {r_js}. Engine code search paths≈{eng_paths}",
            )
        )
    else:
        results.append(
            _ok(
                "handler_search_wrong_property",
                f"wrong_field={r_wrong} js={r_js} eng={eng_paths}",
            )
        )

    # ------------------------------------------------------------------
    # CASE 6: Đọc CPTax.xml qua path mà không check needs_xml → .f only
    # ------------------------------------------------------------------
    q_cptax = """
    MATCH (f:XmlFile)
    WHERE f.relative_path CONTAINS 'CPTax'
    RETURN f.relative_path, f.needs_xml, f.source_extension, f.is_encrypted, f.paired_f_path
    """
    r_cptax = store.execute_cypher(q_cptax)
    needs_flags = [row for row in r_cptax if row.get("f.needs_xml") or row.get("needs_xml")]
    if needs_flags:
        # Simulate agent blindly reading .xml path
        results.append(
            _fail(
                "needs_xml_ignored",
                f"CPTax nodes={r_cptax}. Engine context needs_xml={sorted(cptax_needs)} source={cptax_source}. "
                "Agent Cypher lấy relative_path rồi read_local_file('.xml') sẽ fail/empty nếu không đọc hint needs_xml.",
                severity="critical",
            )
        )
    else:
        results.append(_warn("needs_xml_ignored", f"rows={r_cptax}"))

    # ------------------------------------------------------------------
    # CASE 7: Docstring MCP example list_contains ma_kh — thiếu folder filter → Templates nhiễu
    # ------------------------------------------------------------------
    q_makh = """
    MATCH (f:XmlFile)
    WHERE list_contains(f.fields_names, 'ma_kh')
    RETURN f.relative_path, f.folder_type LIMIT 15
    """
    r_makh = store.execute_cypher(q_makh)
    templates = [
        x for x in r_makh
        if "Template" in str(x.get("f.relative_path") or x.get("relative_path") or "")
        or (x.get("f.folder_type") or x.get("folder_type")) == "Templates"
    ]
    if len(templates) >= 3:
        results.append(
            _fail(
                "no_folder_filter",
                f"Docstring example search ma_kh không filter Dir/Grid. "
                f"Top hits có Templates={len(templates)}/{len(r_makh)}: {r_makh[:8]}",
            )
        )
    else:
        results.append(_ok("no_folder_filter", f"n={len(r_makh)} templates={len(templates)}"))

    # ------------------------------------------------------------------
    # CASE 8: Agent trả grids nhưng không kèm needs_xml từ target nodes
    # ------------------------------------------------------------------
    q_grids = """
    MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)
    WHERE a.relative_path CONTAINS 'CPTran.xml' AND r.edge_type = 'GRID_MASTER_DETAIL'
    RETURN b.relative_path AS path, b.needs_xml AS needs_xml, b.db_table AS db_table
    """
    r_grids = store.execute_cypher(q_grids)
    # If agent omits needs_xml in RETURN (common)
    q_grids_naive = """
    MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)
    WHERE a.relative_path CONTAINS 'CPTran.xml' AND r.edge_type = 'GRID_MASTER_DETAIL'
    RETURN b.relative_path
    """
    r_naive = store.execute_cypher(q_grids_naive)
    naive_paths = [x.get("b.relative_path") or x.get("path") for x in r_naive]
    full_needs = [x for x in r_grids if x.get("needs_xml") or x.get("b.needs_xml")]
    if full_needs and naive_paths:
        results.append(
            _fail(
                "navigate_without_needs_xml",
                f"Cypher 'đúng' về edge vẫn có thể bỏ RETURN needs_xml. "
                f"paths={naive_paths}; nodes needs_xml=true: {full_needs}. Engine needs_xml={sorted(needs_xml_engine)}",
            )
        )
    else:
        results.append(_ok("navigate_without_needs_xml", f"grids={r_grids}"))

    # ------------------------------------------------------------------
    # CASE 9: Token/noise — unlimited related without LIMIT/type
    # ------------------------------------------------------------------
    q_noise = """
    MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile)
    WHERE a.relative_path CONTAINS 'CPTran.xml'
    RETURN r.edge_type, b.relative_path
    """
    r_noise = store.execute_cypher(q_noise)
    payload = json.dumps(r_noise, ensure_ascii=False)
    if len(r_noise) > 50 or len(payload) > 8000:
        results.append(
            _fail(
                "token_blowup_unlimited_rel",
                f"MATCH all Rel from CPTran = {len(r_noise)} rows, json≈{len(payload)} chars. "
                "query_radar không default LIMIT/filter → agent dễ nổ context.",
            )
        )
    else:
        results.append(_ok("token_blowup_unlimited_rel", f"n={len(r_noise)} bytes={len(payload)}"))

    # ------------------------------------------------------------------
    # CASE 10: Schema names agent hay sai
    # ------------------------------------------------------------------
    wrong_queries = {
        "File instead of XmlFile": "MATCH (f:File) RETURN f LIMIT 1",
        "fields instead of fields_names": "MATCH (f:XmlFile) WHERE 'ma_kh' IN f.fields RETURN f.relative_path LIMIT 1",
        "Edge instead of Rel": "MATCH ()-[r:Edge]->() RETURN r LIMIT 1",
        "AS table reserved keyword": (
            "MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile) "
            "WHERE r.edge_type = 'GRID_MASTER_DETAIL' "
            "RETURN b.db_table AS table LIMIT 1"
        ),
    }
    for label, q in wrong_queries.items():
        try:
            store.execute_cypher(q)
            results.append(_warn(f"schema_guess:{label}", "không throw — kiểm tra thủ công"))
        except Exception as e:
            results.append(
                _fail(
                    f"schema_guess:{label}",
                    f"Cypher agent-sai → error: {str(e)[:200]}",
                    severity="medium",
                )
            )

    # ------------------------------------------------------------------
    # CASE 11: So sánh đúng — Cypher tốt (có filter) ≈ engine navigate
    # ------------------------------------------------------------------
    good_paths = {x.get("path") or x.get("b.relative_path") for x in r_grids}
    # Normalize slashes
    def norm(p):
        return str(p or "").replace("/", "\\")

    eng_norm = {norm(p) for p in nav_grids if p}
    good_norm = {norm(p) for p in good_paths if p}
    if eng_norm and good_norm & eng_norm:
        results.append(
            _ok(
                "cypher_can_work_if_expert",
                f"Cypher đúng schema+edge_type overlap engine: {sorted(good_norm & eng_norm)}",
            )
        )
    else:
        results.append(
            _warn(
                "cypher_can_work_if_expert",
                f"engine={sorted(eng_norm)} cypher={sorted(good_norm)}",
            )
        )

    # ------------------------------------------------------------------
    # MCP High-level Tools Verification
    # ------------------------------------------------------------------
    import mcp_server
    
    # Tool 1: search_nodes with synonyms
    try:
        search_res = json.loads(mcp_server.search_nodes("gia ban", str(REF)))
        has_hits = len(search_res.get("field_matches", [])) > 0 or len(search_res.get("code_matches", [])) > 0
        if has_hits:
            results.append(_ok("mcp_tool:search_nodes_synonyms", f"Found synonyms: {search_res.get('expanded_query')}"))
        else:
            results.append(_fail("mcp_tool:search_nodes_synonyms", "No synonym results found"))
    except Exception as e:
        results.append(_fail("mcp_tool:search_nodes_synonyms", f"Error: {e}"))
        
    # Tool 2: get_related_nodes (navigate without SHARED_INCLUDE)
    try:
        rel_res = json.loads(mcp_server.get_related_nodes("Dir/CPTran.xml", str(REF), include_shared=False))
        grids = rel_res.get("grid_details", [])
        has_cptax_needs = any(g.get("controller") == "Grid\\CPTax.xml" and g.get("needs_xml") for g in grids)
        has_shared = any(dep.get("type") == "SHARED_INCLUDE" for dep in rel_res.get("dependencies", []))
        if has_cptax_needs and not has_shared:
            results.append(_ok("mcp_tool:get_related_nodes_navigate", f"Grids={len(grids)} (CPTax has needs_xml: True, no SHARED_INCLUDE)"))
        else:
            results.append(_fail("mcp_tool:get_related_nodes_navigate", f"Failed: CPTax needs_xml={has_cptax_needs}, has_shared={has_shared}"))
    except Exception as e:
        results.append(_fail("mcp_tool:get_related_nodes_navigate", f"Error: {e}"))

    # Tool 3: query_node_details (compact context with needs_xml)
    try:
        details_res = json.loads(mcp_server.query_node_details("Grid/CPTax.xml", str(REF)))
        needs_xml = details_res.get("needs_xml")
        source = details_res.get("source_on_disk")
        if needs_xml == ["Grid\\CPTax.xml"] and "CPTax.f" in str(source):
            results.append(_ok("mcp_tool:query_node_details_cptax", f"needs_xml={needs_xml} source={source}"))
        else:
            results.append(_fail("mcp_tool:query_node_details_cptax", f"Failed: needs_xml={needs_xml} source={source}"))
    except Exception as e:
        results.append(_fail("mcp_tool:query_node_details_cptax", f"Error: {e}"))

    # ------------------------------------------------------------------
    # Print report
    # ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("AGENT CYPHER TRAP REPORT")
    print("=" * 100)
    fails = [r for r in results if r["status"] == "FAIL"]
    warns = [r for r in results if r["status"] == "WARN"]
    oks = [r for r in results if r["status"] == "ok"]
    for r in results:
        flag = {"ok": "[ok]", "FAIL": "[XX]", "WARN": "[!!]"}[r["status"]]
        print(f"{flag} {r['case']}")
        print(f"     {r['detail'][:300]}")
    print("-" * 100)
    print(f"SUMMARY: ok={len(oks)} fail={len(fails)} warn={len(warns)}")
    print("=" * 100)

    # Write markdown for Antigravity
    out = ROOT / "scripts" / "AGENT_CYPHER_FIXES_FOR_ANTIGRAVITY.md"
    lines = [
        "# Agent + Kuzu Cypher — Bug/Gap report cho Antigravity",
        "",
        "## Kết luận test",
        "",
        f"- ok={len(oks)} fail={len(fails)} warn={len(warns)}",
        "- `query_radar` **đủ khả năng** nếu agent viết Cypher đúng schema.",
        "- Thực tế agent FBO **dễ fail** ở path slash, SHARED_INCLUDE, synonym, needs_xml, schema guess.",
        "",
        "## Evidence (auto test `scripts/test_agent_cypher_traps.py`)",
        "",
    ]
    for r in results:
        lines.append(f"### [{r['status']}] {r['case']}")
        lines.append("")
        lines.append(r["detail"])
        lines.append("")
    lines.extend(
        [
            "## Hướng chỉnh (bắt buộc làm)",
            "",
            "### A. MCP: thêm 3 tool mỏng wrap QueryEngine (không bỏ query_radar)",
            "",
            "1. `search_nodes(query, reference_file, match_type='all|field|code|file', folder_filter=None, limit=20)`",
            "   - Gọi `handle_query('search', ...)` + `expand_keyword`",
            "   - Default ưu tiên folder Dir/Grid/Filter (loại Templates nếu không hỏi)",
            "2. `get_related_nodes(target, reference_file, mode='navigate'|'dependencies'|'dependents')`",
            "   - `navigate` = GRID_MASTER_DETAIL + needs_xml + source_on_disk",
            "   - **Không** trả SHARED_INCLUDE trừ khi `include_shared=true`",
            "3. `query_node_details(target, reference_file, view='context'|'blocks')`",
            "   - Trả JSON có `needs_xml`, `agent_hint`, `source_on_disk`, fields compact",
            "",
            "### B. Sửa docstring `query_radar` (giảm đoán sai)",
            "",
            "1. Document schema thật:",
            "   - Node: `XmlFile` (PK `node_id`)",
            "   - Rel: **chỉ** `:Rel` với property `edge_type` — KHÔNG có typed rel Neo4j",
            "   - `relative_path` dùng backslash `Dir\\CPTran.xml` (hoặc normalize cả hai)",
            "2. Liệt kê `edge_type` values + cảnh báo: `SHARED_INCLUDE` ≈ 99% edges → **PHẢI filter**",
            "3. Ví dụ Cypher **đã verify** (copy-paste được):",
            "   - Grids của form: filter `edge_type = 'GRID_MASTER_DETAIL'`, RETURN `needs_xml`",
            "   - Search field: dùng tool search_nodes, không khuyến khích list_contains thuần",
            "   - Search JS handler: `f.js_text CONTAINS '...'` (không dùng fields_names)",
            "4. Thêm `LIMIT` mặc định / reject query không LIMIT khi MATCH Rel",
            "",
            "### C. Normalize path trong execute_cypher hoặc helper",
            "",
            "- Accept cả `Dir/CPTran.xml` và `Dir\\CPTran.xml`",
            "- Hoặc rewrite relative_path lookup trước khi chạy",
            "- Docstring MCP hiện dùng `/` — **đang gây fail** (đã chứng minh bằng test)",
            "",
            "### D. Không cần SQLite",
            "",
            "- Mọi logic trên đã có trong `xml_codegraph/query/engine.py` + Kuzu",
            "- Chỉ expose lại qua MCP tools",
            "",
            "## Acceptance",
            "",
            "- [ ] 3 tool high-level có trên MCP",
            "- [ ] Case CPTran navigate trả đủ grids + needs_xml (CPTax.f) không cần Cypher tay",
            "- [ ] Case search `gia ban` / `giay bao no` / `TenVtFromDienGiai` qua search_nodes OK",
            "- [ ] Docstring query_radar không còn ví dụ `/` sai hoặc đã normalize",
            "- [ ] `scripts/test_agent_cypher_traps.py` fail giảm; thêm test MCP high-level pass",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
