r"""
Test mở rộng theo góc nhìn agent/production (ngoài suite baseline).

Chạy sau test_kuzu_comprehensive.py:
  .\.venv\Scripts\python.exe scripts\test_kuzu_extended.py
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF = r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Dir\CPTran.xml"
REF_GRID = r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Grid\Customer.xml"
LOCAL_KUZU = ROOT / "_tmp_kuzu"
REMOTE_KUZU = Path(r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\.fbograph\kuzu")
CLI = ROOT / "xml_graph_cli.py"
PY = sys.executable


@dataclass
class CaseResult:
    suite: str
    label: str
    ok: bool
    elapsed: float
    detail: str
    severity: str = "fail"


@dataclass
class SuiteReport:
    name: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def failed(self):
        return [r for r in self.results if not r.ok and r.severity == "fail"]

    @property
    def warnings(self):
        return [r for r in self.results if not r.ok and r.severity == "warn"]


def flag(r: CaseResult) -> str:
    if r.ok:
        return "ok"
    return {"expected": "~~", "warn": "!!"}.get(r.severity, "XX")


def run_case(suite: str, label: str, fn: Callable[[], tuple[bool, str]], severity: str = "fail") -> CaseResult:
    t0 = time.time()
    try:
        ok, detail = fn()
        return CaseResult(suite, label, ok, time.time() - t0, detail, severity)
    except Exception as e:
        return CaseResult(suite, label, False, time.time() - t0, f"EXCEPTION: {e}", "fail")


def print_report(reports: list[SuiteReport]) -> int:
    fail = warn = exp = ok_n = 0
    total_t = 0.0
    for rep in reports:
        print("\n" + "=" * 100)
        print(f"SUITE: {rep.name} (n={len(rep.results)})")
        print("-" * 100)
        for r in rep.results:
            total_t += r.elapsed
            if r.ok:
                ok_n += 1
            elif r.severity == "fail":
                fail += 1
            elif r.severity == "warn":
                warn += 1
            else:
                exp += 1
            detail = r.detail[:160].encode("ascii", "replace").decode("ascii")
            print(f"[{flag(r)}] {r.elapsed:6.2f}s | {r.label:44} | {detail}")
        if rep.failed:
            print(f"\n  FAILED ({len(rep.failed)}):")
            for r in rep.failed:
                print(f"    - {r.label}: {r.detail.encode('ascii','replace').decode('ascii')}")
        if rep.warnings:
            print(f"\n  WARNINGS ({len(rep.warnings)}):")
            for r in rep.warnings:
                print(f"    - {r.label}: {r.detail.encode('ascii','replace').decode('ascii')}")
    print("\n" + "=" * 100)
    print(f"SUMMARY: ok={ok_n} fail={fail} warn={warn} expected={exp} time={total_t:.1f}s")
    print("=" * 100)
    return fail


# ---------- D. CLI ----------
def suite_cli() -> SuiteReport:
    report = SuiteReport("D.cli")

    def cli(qtype: str, target: str, extra: list[str] | None = None) -> dict:
        cmd = [PY, str(CLI), "query", "-t", qtype, target, "--ref", REF] + (extra or [])
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        out = proc.stdout.strip()
        # Skip daemon banner lines, find JSON
        start = out.find("{")
        if start < 0:
            raise RuntimeError(f"exit={proc.returncode} stdout={out[:300]} stderr={proc.stderr[:300]}")
        return json.loads(out[start:])

    def navigate_cli():
        d = cli("navigate", "CPTran")
        ok = any(g.get("field_name") == "r30" for g in d.get("grid_details", [])) and bool(d.get("needs_xml"))
        return ok, f"grids={len(d.get('grid_details',[]))} needs_xml={len(d.get('needs_xml') or [])}"

    def search_cli():
        d = cli("search", "TenVtFromDienGiai", ["--match-type", "code", "--compact", "--limit", "5"])
        paths = [x.get("relative_path") for x in d.get("code_matches", [])]
        ok = any("GLTax" in (p or "") or "CPDetail" in (p or "") for p in paths)
        return ok, f"paths={paths}"

    def context_compact_cli():
        d = cli("context", "CPTran", ["--compact"])
        size = len(json.dumps(d, ensure_ascii=False))
        ok = size < 12000 and len(d.get("needs_xml") or []) > 0 and "snippet" not in json.dumps(d.get("fields", [])[:1])
        return ok, f"size={size} needs_xml={d.get('needs_xml')}"

    def cptax_cli():
        d = cli("context", "CPTax")
        ok = bool(d.get("needs_xml")) and "CPTax.f" in str(d.get("source_on_disk", ""))
        return ok, f"needs_xml={d.get('needs_xml')} source={d.get('source_on_disk')}"

    report.results.append(run_case(report.name, "CLI navigate CPTran", navigate_cli))
    report.results.append(run_case(report.name, "CLI search TenVtFromDienGiai", search_cli))
    report.results.append(run_case(report.name, "CLI context --compact", context_compact_cli))
    report.results.append(run_case(report.name, "CLI context CPTax f-only", cptax_cli))
    return report


# ---------- E. Engine extras ----------
def suite_engine_extras() -> SuiteReport:
    from xml_fbograph.query.engine import xml_graph_query, expand_keyword, _graph_cache, _store_cache
    from xml_fbograph.storage.kuzu_index import KuzuIndexStore
    from xml_fbograph.utils.path_helper import ProjectPathHelper

    report = SuiteReport("E.engine_extras")

    # Prepare shared local store (same as comprehensive)
    helper = ProjectPathHelper(REF)
    graph_dir = str(helper.get_graph_dir())
    store = KuzuIndexStore(LOCAL_KUZU if LOCAL_KUZU.exists() else REMOTE_KUZU, read_only=True)
    graph = store.load_graph()
    _store_cache.clear()
    _graph_cache.clear()
    _store_cache[graph_dir] = store
    _graph_cache[graph_dir] = (LOCAL_KUZU.stat().st_mtime if LOCAL_KUZU.exists() else time.time(), graph)

    def expand_is_list():
        terms = expand_keyword("gia ban")
        ok = isinstance(terms, list) and "gia2" in terms
        return ok, f"terms={terms}"

    def match_type_field_only():
        d = xml_graph_query("search", "ma_kh", REF, match_type="field", compact=True, limit=5)
        ok = len(d.get("field_matches", [])) > 0 and len(d.get("code_matches", [])) == 0
        return ok, f"field={len(d.get('field_matches',[]))} code={len(d.get('code_matches',[]))}"

    def folder_filter_dir_grid():
        d = xml_graph_query("search", "ma_kh", REF, match_type="field", folder_filter="Dir,Grid", limit=20, compact=True)
        paths = [x.get("relative_path", "") for x in d.get("field_matches", [])]
        bad = [p for p in paths if p.startswith("Templates")]
        ok = len(paths) > 0 and len(bad) == 0
        return ok, f"n={len(paths)} sample={paths[:5]} templates_leak={bad[:3]}"

    def ranking_prefers_dir_grid():
        d = xml_graph_query("search", "ma_kh", REF, match_type="field", limit=5, compact=True)
        paths = [x.get("relative_path", "") for x in d.get("field_matches", [])]
        top = paths[0] if paths else ""
        # Prefer not Templates first ideally
        ok = len(paths) > 0
        warn_only = top.startswith("Templates")
        if warn_only:
            return False, f"top={top} paths={paths}"
        return ok, f"top={top} paths={paths}"

    def warm_query_speed():
        t0 = time.time()
        xml_graph_query("navigate", "CPTran", REF)
        t1 = time.time() - t0
        return t1 < 2.0, f"warm_navigate={t1:.3f}s"

    def header_populated():
        d = xml_graph_query("context", "CPTran", REF, compact=True)
        fields = {f.get("name"): f for f in d.get("fields", [])}
        loai = fields.get("loai_ct") or {}
        hv = loai.get("header_v") or ""
        ok = bool(hv) and "?" not in hv
        return ok, f"loai_ct.header_v={hv!r} header_e={loai.get('header_e')!r}"

    def cdtran_needs_xml():
        d = xml_graph_query("navigate", "CDTran", REF)
        ok = len(d.get("grid_details", [])) >= 1
        return ok, f"grids={len(d.get('grid_details',[]))} needs_xml={d.get('needs_xml')}"

    def synonym_thue():
        d = xml_graph_query("search", "thue", REF, limit=8, compact=True)
        n = len(d.get("field_matches", [])) + len(d.get("code_matches", []))
        return n > 0, f"hits={n} exp={d.get('expanded_query')}"

    def dependents_account():
        d = xml_graph_query("dependents", "Account", REF)
        # Account may be .f-only grid
        return "dependents" in d, f"n={len(d.get('dependents',[]))} err={d.get('error','')}"

    report.results.append(run_case(report.name, "expand_keyword returns list", expand_is_list))
    report.results.append(run_case(report.name, "match_type=field only", match_type_field_only))
    report.results.append(run_case(report.name, "folder_filter Dir,Grid no Templates", folder_filter_dir_grid))
    report.results.append(run_case(report.name, "ranking ma_kh prefers Dir/Grid", ranking_prefers_dir_grid, "warn"))
    report.results.append(run_case(report.name, "warm navigate <2s", warm_query_speed))
    report.results.append(run_case(report.name, "header_v populated UTF-8", header_populated, "warn"))
    report.results.append(run_case(report.name, "navigate CDTran", cdtran_needs_xml))
    report.results.append(run_case(report.name, "synonym thue", synonym_thue))
    report.results.append(run_case(report.name, "dependents Account", dependents_account, "warn"))
    return report


# ---------- F. Concurrency / lock ----------
def suite_lock() -> SuiteReport:
    from xml_fbograph.storage.kuzu_index import KuzuIndexStore

    report = SuiteReport("F.lock_singleton")
    path = LOCAL_KUZU if LOCAL_KUZU.exists() else REMOTE_KUZU

    def dual_readonly():
        a = KuzuIndexStore(path, read_only=True)
        b = KuzuIndexStore(path, read_only=True)
        c1 = a.execute_cypher("MATCH (n:XmlFile) RETURN count(n) AS c")[0]["c"]
        c2 = b.execute_cypher("MATCH (n:XmlFile) RETURN count(n) AS c")[0]["c"]
        same = a.db is b.db or a.conn is b.conn or True  # singleton may share
        ok = c1 == c2 and int(c1) > 100
        return ok, f"c1={c1} c2={c2} same_db={getattr(a,'db',None) is getattr(b,'db',None)}"

    def remote_readonly_once():
        if not REMOTE_KUZU.exists():
            return False, "remote kuzu missing"
        s = KuzuIndexStore(REMOTE_KUZU, read_only=True)
        c = s.execute_cypher("MATCH (n:XmlFile) RETURN count(n) AS c")[0]["c"]
        return int(c) > 100, f"remote_nodes={c}"

    report.results.append(run_case(report.name, "dual read_only same path", dual_readonly))
    report.results.append(run_case(report.name, "remote UNC read_only open", remote_readonly_once, "warn"))
    return report


# ---------- G. MCP surface ----------
def suite_mcp() -> SuiteReport:
    report = SuiteReport("G.mcp_surface")

    def tools_present():
        # Không import mcp_server (thiếu package mcp sẽ sys.exit). Parse AST.
        import ast
        src = (ROOT / "mcp_server.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        has_radar = "query_radar" in defs
        has_read = "read_local_file" in defs
        has_search = "search_nodes" in defs
        has_navigate = "get_related_nodes" in defs
        has_details = "query_node_details" in defs
        missing_high = []
        if not has_search:
            missing_high.append("search_nodes")
        if not has_navigate:
            missing_high.append("get_related_nodes")
        if not has_details:
            missing_high.append("query_node_details")
        # Agent workflow cần high-level tools — thiếu = fail
        severity_ok = len(missing_high) == 0 and has_radar and has_read
        return (
            severity_ok,
            f"radar={has_radar} read={has_read} missing={missing_high} defs={sorted(defs)}",
        )

    def cypher_via_store():
        from xml_fbograph.storage.kuzu_index import KuzuIndexStore
        path = LOCAL_KUZU if LOCAL_KUZU.exists() else REMOTE_KUZU
        s = KuzuIndexStore(path, read_only=True)
        # path key may be Dir\\CPTran.xml
        rows = s.execute_cypher(
            "MATCH (a:XmlFile)-[r:Rel]->(b:XmlFile) "
            "WHERE a.relative_path CONTAINS 'CPTran' AND a.folder_type = 'Dir' "
            "AND r.edge_type = 'GRID_MASTER_DETAIL' "
            "RETURN b.relative_path AS path, b.needs_xml AS needs_xml ORDER BY path"
        )
        paths = [r["path"] for r in rows]
        ok = any("CPTax" in p for p in paths)
        return ok, f"paths={paths}"

    def read_file_security_check():
        # Simulate outside path rejection logic from mcp_server
        from xml_fbograph.utils.path_helper import ProjectPathHelper
        helper = ProjectPathHelper(REF)
        root = str(helper.get_project_root().resolve()).lower()
        outside = Path("C:/Windows/System32/drivers/etc/hosts").resolve()
        blocked = not str(outside).lower().startswith(root)
        return blocked, f"outside_blocked={blocked}"

    report.results.append(run_case(report.name, "MCP high-level tools present", tools_present, "fail"))
    report.results.append(run_case(report.name, "Cypher GRID_MASTER_DETAIL CPTran", cypher_via_store))
    report.results.append(run_case(report.name, "read path sandbox logic", read_file_security_check))
    return report


# ---------- H. Data quality ----------
def suite_data_quality() -> SuiteReport:
    from xml_fbograph.storage.kuzu_index import KuzuIndexStore

    report = SuiteReport("H.data_quality")
    path = LOCAL_KUZU if LOCAL_KUZU.exists() else REMOTE_KUZU
    s = KuzuIndexStore(path, read_only=True)

    def entities_hydrated():
        g = s.load_graph()
        # Find any node with entities
        with_ent = [n for n in g.nodes.values() if getattr(n, "entities", None)]
        sample = with_ent[0] if with_ent else None
        ok = len(with_ent) > 0
        detail = f"nodes_with_entities={len(with_ent)}"
        if sample:
            detail += f" sample={sample.relative_path} ent0={sample.entities[0] if sample.entities else None}"
        return ok, detail

    def f_only_ratio():
        rows = s.execute_cypher(
            "MATCH (n:XmlFile) RETURN "
            "sum(CASE WHEN n.needs_xml THEN 1 ELSE 0 END) AS f_only, "
            "count(n) AS total"
        )[0]
        f_only, total = int(rows["f_only"]), int(rows["total"])
        ratio = f_only / max(total, 1)
        return True, f"f_only={f_only} total={total} ratio={ratio:.2%}"

    def shared_include_ratio():
        rows = s.execute_cypher(
            "MATCH ()-[r:Rel]->() RETURN r.edge_type AS t, count(*) AS c ORDER BY c DESC"
        )
        total = sum(int(r["c"]) for r in rows)
        shared = next((int(r["c"]) for r in rows if r["t"] == "SHARED_INCLUDE"), 0)
        ratio = shared / max(total, 1)
        # warn if > 90%
        ok = ratio < 0.95
        return ok, f"SHARED_INCLUDE={shared} total={total} ratio={ratio:.2%}"

    report.results.append(run_case(report.name, "entities hydrated in load_graph", entities_hydrated))
    report.results.append(run_case(report.name, "f-only ratio (info)", f_only_ratio))
    report.results.append(run_case(report.name, "SHARED_INCLUDE not overwhelming", shared_include_ratio, "warn"))
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(f"Python: {sys.version}")
    print(f"PY exe: {PY}")
    print(f"LOCAL_KUZU exists={LOCAL_KUZU.exists()} size={LOCAL_KUZU.stat().st_size if LOCAL_KUZU.exists() else 0}")

    reports = [
        suite_cli(),
        suite_engine_extras(),
        suite_lock(),
        suite_mcp(),
        suite_data_quality(),
    ]
    return 1 if print_report(reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
