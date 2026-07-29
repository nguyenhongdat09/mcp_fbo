"""
Test toàn diện FBOGraph + Kuzu.

Khuyến nghị:
  1) Copy DB về local (tránh UNC lock)
  2) Chạy bằng Python 3.12 (có wheel kuzu), không dùng .venv 3.14

  C:\\Python312\\python.exe scripts\\test_kuzu_comprehensive.py

Env optional:
  FBOGRAPH_KUZU=E:\\path\\to\\kuzu
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF = r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Dir\CPTran.xml"
REF_GRID = r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\App_Data\Controllers\Grid\Customer.xml"
DEFAULT_REMOTE_KUZU = Path(r"\\172.168.5.14\CustomerPro\FBO\PHELA\SP2261\.fbograph\kuzu")
DEFAULT_LOCAL_KUZU = ROOT / "_tmp_kuzu"


@dataclass
class CaseResult:
    suite: str
    label: str
    ok: bool
    elapsed: float
    detail: str
    severity: str = "fail"  # fail | warn | expected


@dataclass
class SuiteReport:
    name: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CaseResult]:
        return [r for r in self.results if not r.ok and r.severity == "fail"]

    @property
    def warnings(self) -> list[CaseResult]:
        return [r for r in self.results if not r.ok and r.severity == "warn"]


def _flag(r: CaseResult) -> str:
    if r.ok:
        return "ok"
    if r.severity == "expected":
        return "~~"
    if r.severity == "warn":
        return "!!"
    return "XX"


def run_case(suite: str, label: str, fn: Callable[[], tuple[bool, str]], severity: str = "fail") -> CaseResult:
    t0 = time.time()
    try:
        ok, detail = fn()
        return CaseResult(suite, label, ok, time.time() - t0, detail, severity)
    except Exception as e:
        return CaseResult(suite, label, False, time.time() - t0, f"EXCEPTION: {e}", "fail")


class ReadOnlyKuzuStore:
    """Mở Kuzu read_only — tránh lock/multi-writer trên cùng path."""

    def __init__(self, db_path: Path):
        import kuzu
        from xml_fbograph.storage.kuzu_index import KuzuIndexStore

        self.db_path = Path(db_path)
        self.db = kuzu.Database(str(self.db_path), read_only=True)
        self.conn = kuzu.Connection(self.db)
        # Reuse methods that only need conn
        self._impl = object.__new__(KuzuIndexStore)
        self._impl.db_path = self.db_path
        self._impl.db = self.db
        self._impl.conn = self.conn

    def execute_cypher(self, query: str, params: Optional[dict] = None) -> list:
        return self._impl.execute_cypher(query, params)

    def load_graph(self):
        return self._impl.load_graph()

    def search_fields(self, keyword: str, limit: int = 10) -> list:
        return self._impl.search_fields(keyword, limit)

    def search_code(self, keyword: str, limit: int = 10) -> list:
        return self._impl.search_code(keyword, limit)

    def close(self) -> None:
        try:
            del self.conn
            del self.db
        except Exception:
            pass


def ensure_local_kuzu() -> Path:
    env = os.environ.get("FBOGRAPH_KUZU")
    if env:
        return Path(env)
    src = DEFAULT_REMOTE_KUZU
    dst = DEFAULT_LOCAL_KUZU
    if dst.exists() and dst.stat().st_size > 1_000_000:
        # Reuse if roughly same size
        try:
            if abs(dst.stat().st_size - src.stat().st_size) < 1024:
                return dst
        except Exception:
            return dst
    print(f"[setup] Copy Kuzu DB -> {dst} ...")
    if dst.exists():
        if dst.is_dir():
            shutil.rmtree(dst, ignore_errors=True)
        else:
            dst.unlink(missing_ok=True)
    shutil.copy2(src, dst)
    return dst


def prepare_engine_cache(store: ReadOnlyKuzuStore, graph) -> None:
    """Inject store+graph vào engine cache để tránh mở DB lần 2."""
    from xml_fbograph.query import engine
    from xml_fbograph.utils.path_helper import ProjectPathHelper

    helper = ProjectPathHelper(REF)
    graph_dir = str(helper.get_graph_dir())
    mtime = store.db_path.stat().st_mtime
    engine._store_cache.clear()
    engine._graph_cache.clear()
    engine._store_cache[graph_dir] = store  # type: ignore[assignment]
    engine._graph_cache[graph_dir] = (mtime, graph)


# ============================================================
# A. HEALTH
# ============================================================
def suite_health(store: ReadOnlyKuzuStore) -> tuple[SuiteReport, Any]:
    report = SuiteReport("A.kuzu_health")
    graph_holder: dict[str, Any] = {}

    def count_nodes():
        c = int(store.execute_cypher("MATCH (n:XmlFile) RETURN count(n) AS c")[0]["c"])
        return c > 100, f"nodes={c}"

    def count_edges():
        c = int(store.execute_cypher("MATCH ()-[r:Rel]->() RETURN count(r) AS c")[0]["c"])
        return c > 0, f"edges={c}"

    def edge_types():
        rows = store.execute_cypher(
            "MATCH ()-[r:Rel]->() RETURN r.edge_type AS t, count(*) AS c ORDER BY c DESC"
        )
        types = {r["t"] for r in rows}
        need = {"GRID_MASTER_DETAIL", "LOOKUP_REFERENCE", "COMPANION_FILE"}
        missing = need - types
        detail = ", ".join(f"{r['t']}={r['c']}" for r in rows[:8])
        return len(missing) == 0, f"{detail} | missing={missing or '-'}"

    def needs_xml_count():
        c = int(store.execute_cypher("MATCH (n:XmlFile) WHERE n.needs_xml = true RETURN count(n) AS c")[0]["c"])
        return c > 0, f"needs_xml_nodes={c}"

    def fields_names_quoting_bug():
        """Detect CSV quoting bug: array items stored as 'ma_kh' instead of ma_kh."""
        rows = store.execute_cypher(
            "MATCH (n:XmlFile) WHERE n.relative_path = 'Dir\\\\CPTran.xml' RETURN n.fields_names AS names"
        )
        names = rows[0]["names"] if rows else []
        if not names:
            return False, "fields_names empty for Dir\\CPTran.xml"
        sample = names[0]
        quoted = sample.startswith("'") and sample.endswith("'")
        has_exact = "ma_kh" in names
        has_quoted = "'ma_kh'" in names
        # Fail if quoted (data bug)
        ok = has_exact and not quoted
        return ok, f"sample={sample!r} has_ma_kh={has_exact} has_quoted_ma_kh={has_quoted} n={len(names)}"

    def list_contains_ma_kh():
        rows = store.execute_cypher(
            "MATCH (n:XmlFile) WHERE list_contains(n.fields_names, 'ma_kh') RETURN count(n) AS c"
        )
        c = int(rows[0]["c"])
        # Expect >0 if data correct
        return c > 0, f"list_contains(ma_kh) count={c}"

    def list_contains_quoted_ma_kh():
        rows = store.execute_cypher(
            "MATCH (n:XmlFile) WHERE list_contains(n.fields_names, \"'ma_kh'\") RETURN count(n) AS c"
        )
        c = int(rows[0]["c"])
        return True, f"list_contains('ma_kh') count={c} (diagnostic)"

    def search_fields_api():
        rows = store.search_fields("ma_kh", 5)
        return len(rows) > 0, f"hits={len(rows)} sample={[r.get('relative_path') for r in rows[:3]]}"

    def search_code_api():
        rows = store.search_code("TenVtFromDienGiai", 5)
        paths = [r.get("relative_path") for r in rows]
        ok = any("GLTax" in p or "CPDetail" in p for p in paths)
        return ok, f"hits={len(rows)} paths={paths}"

    def load_graph():
        t0 = time.time()
        graph = store.load_graph()
        elapsed = time.time() - t0
        graph_holder["graph"] = graph
        ok = len(graph.nodes) > 100
        return ok, f"load={elapsed:.2f}s nodes={len(graph.nodes)} edges={len(graph.edges)}"

    def cptran_edges_cypher():
        rows = store.execute_cypher(
            """
            MATCH (n:XmlFile)-[r:Rel]->(m:XmlFile)
            WHERE n.relative_path = 'Dir\\\\CPTran.xml' AND r.edge_type = 'GRID_MASTER_DETAIL'
            RETURN m.relative_path AS path, m.needs_xml AS needs_xml
            ORDER BY path
            """
        )
        paths = [r["path"] for r in rows]
        ok = any("CPTax" in p for p in paths) and any("CPDetail" in p for p in paths)
        return ok, f"grids={paths}"

    report.results.append(run_case(report.name, "count nodes", count_nodes))
    report.results.append(run_case(report.name, "count edges", count_edges))
    report.results.append(run_case(report.name, "edge types structural", edge_types))
    report.results.append(run_case(report.name, "needs_xml nodes", needs_xml_count))
    report.results.append(run_case(report.name, "fields_names quoting bug", fields_names_quoting_bug))
    report.results.append(run_case(report.name, "list_contains ma_kh", list_contains_ma_kh))
    report.results.append(run_case(report.name, "list_contains 'ma_kh' diagnostic", list_contains_quoted_ma_kh, "warn"))
    report.results.append(run_case(report.name, "search_fields API ma_kh", search_fields_api))
    report.results.append(run_case(report.name, "search_code TenVtFromDienGiai", search_code_api))
    report.results.append(run_case(report.name, "CPTran GRID edges Cypher", cptran_edges_cypher))
    report.results.append(run_case(report.name, "load_graph", load_graph))
    return report, graph_holder.get("graph")


# ============================================================
# B. QUERY ENGINE (reuse cache)
# ============================================================
def suite_queries() -> SuiteReport:
    from xml_fbograph.query.engine import xml_graph_query

    report = SuiteReport("B.query_engine")

    def q(label, qtype, target, ref=REF, severity="fail", check: Optional[Callable[[dict], tuple[bool, str]]] = None, **kwargs):
        def _fn():
            data = xml_graph_query(qtype, target, ref, **kwargs)
            size = len(json.dumps(data, ensure_ascii=False))
            if check:
                ok, detail = check(data)
                return ok, f"{detail} | {size}B"
            if "error" in data and len(data) <= 2:
                return False, f"error={data.get('error')}"
            return True, f"keys={list(data.keys())[:5]} | {size}B"

        report.results.append(run_case(report.name, label, _fn, severity))

    q("search ma_kh", "search", "ma_kh", check=lambda d: (
        len(d.get("field_matches", [])) + len(d.get("code_matches", [])) > 0,
        f"field={len(d.get('field_matches',[]))} code={len(d.get('code_matches',[]))}",
    ))
    q("search TenVtFromDienGiai code", "search", "TenVtFromDienGiai", match_type="code", compact=True, check=lambda d: (
        len(d.get("code_matches", [])) > 0,
        f"paths={[x.get('relative_path') for x in d.get('code_matches',[])]}",
    ))
    q("search f.request", "search", "f.request", match_type="code", severity="warn", check=lambda d: (
        len(d.get("code_matches", [])) > 0,
        f"code={len(d.get('code_matches',[]))}",
    ))
    q("search onChange$Voucher", "search", "onChange$Voucher", match_type="code", check=lambda d: (
        len(d.get("code_matches", [])) + len(d.get("field_matches", [])) > 0,
        f"code={len(d.get('code_matches',[]))} field={len(d.get('field_matches',[]))}",
    ))
    q("search synonym gia ban", "search", "gia ban", check=lambda d: (
        "gia2" in d.get("expanded_query", "") and (
            len(d.get("field_matches", [])) + len(d.get("code_matches", [])) > 0
        ),
        f"exp={d.get('expanded_query','')[:55]} field={len(d.get('field_matches',[]))} code={len(d.get('code_matches',[]))}",
    ))
    q("search synonym giay bao no", "search", "giay bao no", severity="warn", check=lambda d: (
        "CPTran" in d.get("expanded_query", "") and (
            len(d.get("file_matches", [])) + len(d.get("field_matches", [])) + len(d.get("code_matches", [])) > 0
        ),
        f"file={len(d.get('file_matches',[]))} field={len(d.get('field_matches',[]))} code={len(d.get('code_matches',[]))}",
    ))
    q("search fsd_addfields", "search", "fsd_addfields", severity="expected", check=lambda d: (
        len(d.get("code_matches", [])) > 0,
        f"code={len(d.get('code_matches',[]))}",
    ))
    q("search Customer file", "search", "Customer", match_type="file", check=lambda d: (
        any("customer" in x.get("relative_path", "").lower() for x in d.get("file_matches", [])),
        f"file={len(d.get('file_matches',[]))}",
    ))

    q("context CPTran", "context", "CPTran", compact=True, check=lambda d: (
        len(d.get("fields", [])) > 10 and len(d.get("grid_details", [])) >= 2 and len(d.get("needs_xml") or []) > 0,
        f"fields={len(d.get('fields',[]))} grids={len(d.get('grid_details',[]))} needs_xml={d.get('needs_xml')}",
    ))
    q("context CDTran", "context", "CDTran", compact=True, check=lambda d: (
        "node_id" in d and len(d.get("fields", [])) > 0,
        f"fields={len(d.get('fields',[]))} table={d.get('table')}",
    ))
    q("context CPTax f-only", "context", "CPTax", check=lambda d: (
        bool(d.get("is_f_only") or d.get("needs_xml")),
        f"needs_xml={d.get('needs_xml')} source={d.get('source_on_disk')}",
    ))
    q("context CPDetail", "context", "CPDetail", check=lambda d: (
        "node_id" in d,
        f"enc_note={bool(d.get('encrypted_note'))} fields={len(d.get('fields',[]))} readable={d.get('readable')}",
    ))
    q("navigate CPTran", "navigate", "CPTran", check=lambda d: (
        any(g.get("field_name") == "r30" for g in d.get("grid_details", [])) and len(d.get("needs_xml") or []) > 0,
        f"grids={[(g.get('field_name'), g.get('controller')) for g in d.get('grid_details',[])]} needs_xml={d.get('needs_xml')}",
    ))
    q("navigate CDTran", "navigate", "CDTran", check=lambda d: (
        len(d.get("grid_details", [])) >= 1,
        f"grids={len(d.get('grid_details',[]))}",
    ))
    q("blocks CPTran", "blocks", "CPTran", check=lambda d: (
        len(d.get("sql_blocks", [])) + len(d.get("js_blocks", [])) > 0,
        f"sql={len(d.get('sql_blocks',[]))} js={len(d.get('js_blocks',[]))}",
    ))
    q("blocks CPTax", "blocks", "CPTax", check=lambda d: (
        bool(d.get("needs_xml") or d.get("is_f_only") or d.get("encrypted_note")),
        f"needs_xml={d.get('needs_xml')} sql={len(d.get('sql_blocks',[]))}",
    ))
    q("dependencies CPTran", "dependencies", "CPTran", check=lambda d: (
        len(d.get("dependencies", [])) > 0 and not any(x.get("type") == "JS_FUNC_CALL" for x in d.get("dependencies", [])),
        f"n={len(d.get('dependencies',[]))} types={sorted({x.get('type') for x in d.get('dependencies',[])})}",
    ))
    q("dependents Customer", "dependents", "Customer", ref=REF_GRID, check=lambda d: (
        len(d.get("dependents", [])) > 0,
        f"n={len(d.get('dependents',[]))}",
    ))
    q("entity ListQuery note", "entity", "ListQuery", check=lambda d: (
        "note" in d,
        f"note={str(d.get('note',''))[:70]}",
    ))
    q("entity Invoice", "entity", "Invoice", severity="warn", check=lambda d: (
        len(d.get("declarations", [])) + len(d.get("usages", [])) > 0,
        f"decl={len(d.get('declarations',[]))} use={len(d.get('usages',[]))}",
    ))
    q("impact Include", "impact", "Include/XML/WhenVoucherInit.xml", severity="expected", check=lambda d: (
        d.get("impacted_count", 0) > 0,
        f"impacted={d.get('impacted_count')} err={d.get('error','')}",
    ))
    q("use_case CPTran", "use_case", "CPTran", check=lambda d: (
        bool(d.get("main_db_table")),
        f"table={d.get('main_db_table')} related={len(d.get('related_db_tables',[]))} note={str(d.get('sql_note',''))[:40]}",
    ))
    q("missing XYZFoo", "context", "XYZFooNotExist", severity="expected", check=lambda d: (
        "error" in d,
        f"error={d.get('error')}",
    ))
    return report


def suite_tax() -> SuiteReport:
    from xml_fbograph.query.engine import xml_graph_query

    report = SuiteReport("C.tax_flow")

    def map_cptran():
        d = xml_graph_query("navigate", "CPTran", REF)
        grids = {g.get("field_name"): g for g in d.get("grid_details", [])}
        ok = "d56" in grids and "r30" in grids
        return ok, f"grids={list(grids)} needs_xml={d.get('needs_xml')}"

    def cptax_needs():
        d = xml_graph_query("context", "CPTax", REF)
        ok = bool(d.get("needs_xml"))
        return ok, f"needs_xml={d.get('needs_xml')} source={d.get('source_on_disk')}"

    def handler():
        d = xml_graph_query("search", "TenVtFromDienGiai", REF, match_type="code", compact=True)
        paths = [x.get("relative_path", "") for x in d.get("code_matches", [])]
        ok = any("GLTax" in p or "CPDetail" in p for p in paths)
        return ok, f"paths={paths}"

    def cdtran():
        d = xml_graph_query("navigate", "CDTran", REF)
        return len(d.get("grid_details", [])) >= 1, f"grids={len(d.get('grid_details',[]))}"

    report.results.append(run_case(report.name, "map CPTran d56+r30", map_cptran))
    report.results.append(run_case(report.name, "CPTax needs_xml", cptax_needs))
    report.results.append(run_case(report.name, "handler TenVtFromDienGiai", handler))
    report.results.append(run_case(report.name, "map CDTran", cdtran))
    return report


def print_report(reports: list[SuiteReport]) -> int:
    total_fail = total_warn = total_expected = total_ok = 0
    total_time = 0.0
    for report in reports:
        print("\n" + "=" * 100)
        print(f"SUITE: {report.name} (n={len(report.results)})")
        print("-" * 100)
        for r in report.results:
            total_time += r.elapsed
            if r.ok:
                total_ok += 1
            elif r.severity == "fail":
                total_fail += 1
            elif r.severity == "warn":
                total_warn += 1
            else:
                total_expected += 1
            line = f"[{_flag(r)}] {r.elapsed:6.2f}s | {r.label:42} | {r.detail[:150]}"
            print(line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
        if report.failed:
            print(f"\n  FAILED ({len(report.failed)}):")
            for r in report.failed:
                print(f"    - {r.label}: {r.detail}".encode("ascii", errors="replace").decode("ascii"))
        if report.warnings:
            print(f"\n  WARNINGS ({len(report.warnings)}):")
            for r in report.warnings:
                print(f"    - {r.label}: {r.detail}".encode("ascii", errors="replace").decode("ascii"))

    print("\n" + "=" * 100)
    print(f"SUMMARY: ok={total_ok} fail={total_fail} warn={total_warn} expected={total_expected} time={total_time:.1f}s")
    print("=" * 100)
    return total_fail


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(f"Python: {sys.version}")
    print(f"ROOT: {ROOT}")
    try:
        import kuzu
        print(f"kuzu: {getattr(kuzu, '__version__', '?')}")
    except ImportError:
        print("ERROR: cần Python có kuzu (3.12). Ví dụ: C:\\Python312\\python.exe scripts\\test_kuzu_comprehensive.py")
        return 2

    kuzu_path = ensure_local_kuzu()
    print(f"KUZU: {kuzu_path} size={kuzu_path.stat().st_size}")

    store = ReadOnlyKuzuStore(kuzu_path)
    try:
        health, graph = suite_health(store)
        if graph is None:
            print("FATAL: load_graph failed")
            print_report([health])
            return 1
        prepare_engine_cache(store, graph)
        reports = [health, suite_queries(), suite_tax()]
        return 1 if print_report(reports) else 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
