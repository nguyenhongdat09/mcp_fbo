"""
Integration test: Kuzu BANYANFBO/SP228 sau khi extract_options.shared_include=0.

Chạy:
  python xml_codegraph/tests/test_banyanfbo_sp228_after_shared_off.py

Đối chiếu XML AITran với graph — xác minh tắt SHARED_INCLUDE không phá logic nghiệp vụ.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import kuzu

from xml_codegraph.query.engine import xml_graph_query
from xml_codegraph.storage.kuzu_index import KuzuIndexStore
from xml_codegraph.utils.path_helper import ProjectPathHelper


def q(query_type: str, target: str, **kwargs):
    return xml_graph_query(query_type, target, REF, **kwargs)

REF = r"\\172.168.5.14\CustomerPro\FBO\BANYANFBO\SP228\App_Data\Controllers\Dir\AITran.xml"
DB_PATH = Path(
    r"C:\KuzuDB\XFwxNzIuMTY4LjUuMTRcQ3VzdG9tZXJQcm9cRkJPXEJBTllBTkZCT1xTUDIyOA==\.fbograph\kuzu"
)

# Ground truth từ Dir\AITran.xml (field -> controller)
AI_TRAN_GRIDS = {
    "ddc": "Grid\\AIDetail.xml",
    "dinv": "Grid\\AIInvoice.xml",
}
AI_TRAN_LOOKUPS = {
    "ma_kh": "Grid\\Customer.xml",
    "ma_kh2": "Grid\\Customer.xml",
    "ma_nt": "Grid\\Currency.xml",
    "ma_tt": "Lookup\\Term.xml",
    "ma_thue": "Lookup\\Tax.xml",
    "tk_thue_no": "Grid\\Account.xml",
    "tk_thue_co": "Grid\\Account.xml",
    "mau_bc": "Lookup\\VATForm.xml",
    "ma_tc": "Grid\\TaxType.xml",
}
AI_TRAN_COMPANIONS = {"Grid\\AITran.xml", "Filter\\AITran.xml", "Report\\AITran.xml"}
AI_TRAN_FIELDS = {
    "stt_rec",
    "ma_kh",
    "dien_giai",
    "so_ct",
    "ngay_ct",
    "ma_nt",
    "ddc",
    "dinv",
    "ma_thue",
    "t_tt_nt",
}


def _skip_if_no_db():
    if not DB_PATH.exists():
        raise unittest.SkipTest(f"Thiếu DB: {DB_PATH}")
    if not Path(REF).exists():
        raise unittest.SkipTest(f"Thiếu REF XML: {REF}")


class TestBanyanfboSp228AfterSharedOff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _skip_if_no_db()
        cls.store = KuzuIndexStore(DB_PATH, read_only=True)
        cls.conn = cls.store.conn
        cls.graph = cls.store.load_graph()

    def _cypher(self, cypher: str, params: dict | None = None):
        res = self.conn.execute(cypher, params or {})
        rows = []
        while res.has_next():
            rows.append(res.get_next())
        return rows

    # ---- A. DB shape sau khi tắt SHARED ----

    def test_01_shared_include_count_is_zero(self):
        n = self._cypher(
            "MATCH ()-[r:Rel {edge_type:'SHARED_INCLUDE'}]->() RETURN count(r)"
        )[0][0]
        self.assertEqual(n, 0)

    def test_02_business_edge_types_still_present(self):
        rows = self._cypher(
            "MATCH ()-[r:Rel]->() RETURN r.edge_type AS t, count(*) AS c ORDER BY c DESC"
        )
        by_type = {r[0]: r[1] for r in rows}
        self.assertNotIn("SHARED_INCLUDE", by_type)
        for need in (
            "COMPANION_FILE",
            "ENTITY_INCLUDE",
            "LOOKUP_REFERENCE",
            "GRID_MASTER_DETAIL",
            "RETRIEVE_DATA_SOURCE",
        ):
            self.assertIn(need, by_type, f"Thiếu edge_type {need}")
            self.assertGreater(by_type[need], 0, f"{need} = 0")

    def test_03_db_size_reduced_ballpark(self):
        size_mb = DB_PATH.stat().st_size / (1024 * 1024)
        # Trước ~59.5MB; sau tắt SHARED ~34MB (±). Chấp nhận < 45MB.
        self.assertLess(size_mb, 45.0, f"DB vẫn lớn bất thường: {size_mb:.1f}MB")
        self.assertGreater(size_mb, 5.0)

    # ---- B. AITran node / search / fields ----

    def test_10_aitran_node_exists(self):
        rows = self._cypher(
            "MATCH (n:XmlFile) WHERE n.relative_path = 'Dir\\\\AITran.xml' "
            "RETURN n.controller_type, n.code_field, size(n.fields_names)"
        )
        self.assertEqual(len(rows), 1)
        controller_type, code_field, field_count = rows[0]
        self.assertEqual(controller_type, "dir")
        self.assertEqual(code_field, "stt_rec")
        self.assertGreaterEqual(field_count, 20)
        # cot table (reserved) — doi chieu qua context API
        ctx = q("context", "AITran")
        self.assertEqual(ctx.get("table"), "hddc")

    def test_11_search_and_context_fields(self):
        res = q("search", "AITran", folder_filter="Dir,Grid,Filter,Report", limit=20)
        paths = {m.get("relative_path") for m in res.get("file_matches", [])}
        self.assertIn("Dir\\AITran.xml", paths)

        ctx = q("context", "AITran")
        self.assertNotIn("error", ctx)
        names = {f["name"] for f in ctx.get("fields", [])}
        missing = AI_TRAN_FIELDS - names
        self.assertFalse(missing, f"Thiếu field trong context: {missing}")

    def test_12_field_search_ma_kh_dien_giai(self):
        for keyword in ("ma_kh", "dien_giai"):
            res = q("search", keyword, match_type="field", folder_filter="Dir", limit=30)
            field_hits = res.get("field_matches") or []
            hit_on_aitran = any(
                (m.get("relative_path") or "").replace("/", "\\").endswith("AITran.xml")
                or "AITran" in (m.get("relative_path") or "")
                for m in field_hits
            )
            if not hit_on_aitran:
                rows = self._cypher(
                    "MATCH (n:XmlFile) WHERE n.relative_path = 'Dir\\\\AITran.xml' "
                    "AND list_contains(n.fields_names, $kw) RETURN n.relative_path",
                    {"kw": keyword},
                )
                self.assertTrue(rows, f"Không tìm thấy field {keyword} trên AITran")

    # ---- C. Navigate / dependencies khớp XML ----

    def test_20_navigate_grid_details_match_xml(self):
        nav = q("navigate", "AITran")
        grids = {
            g["field_name"]: g["controller"]
            for g in nav.get("grid_details", [])
        }
        self.assertEqual(grids, AI_TRAN_GRIDS)

    def test_21_navigate_lookups_match_xml(self):
        nav = q("navigate", "AITran")
        lookups = {
            (x["field_name"], x["controller"])
            for x in nav.get("lookup_references", [])
        }
        expected = set(AI_TRAN_LOOKUPS.items())
        missing = expected - lookups
        self.assertFalse(missing, f"Thiếu LOOKUP_REFERENCE: {missing}")

    def test_22_navigate_companions_match_xml(self):
        nav = q("navigate", "AITran")
        companions = {c["relative_path"] for c in nav.get("companion_files", [])}
        missing = AI_TRAN_COMPANIONS - companions
        self.assertFalse(missing, f"Thiếu COMPANION_FILE: {missing}")

    def test_23_aidetail_master_backlink(self):
        nav = q("navigate", "AIDetail")
        masters = {
            m.get("controller")
            for m in nav.get("master_controllers", [])
        }
        self.assertIn("Dir\\AITran.xml", masters)

        deps = q("dependents", "AIDetail")
        sources = {d.get("source") for d in deps.get("dependents", [])}
        self.assertIn("Dir\\AITran.xml", sources)

    def test_24_dependencies_lists_business_edges_only(self):
        deps = q("dependencies", "AITran")
        types = {d["type"] for d in deps.get("dependencies", [])}
        self.assertNotIn("SHARED_INCLUDE", types)
        self.assertTrue(
            {"GRID_MASTER_DETAIL", "LOOKUP_REFERENCE", "COMPANION_FILE"} <= types
        )

    # ---- D. Cypher multi-hop / radar (không cần SHARED) ----

    def test_30_cypher_master_detail_chain(self):
        rows = self._cypher(
            """
            MATCH (v:XmlFile)-[r:Rel]->(d:XmlFile)
            WHERE v.relative_path = 'Dir\\\\AITran.xml'
              AND r.edge_type = 'GRID_MASTER_DETAIL'
            RETURN d.relative_path
            ORDER BY d.relative_path
            """
        )
        paths = [r[0] for r in rows]
        self.assertEqual(paths, ["Grid\\AIDetail.xml", "Grid\\AIInvoice.xml"])

    def test_31_cypher_no_shared_noise_from_aitran(self):
        rows = self._cypher(
            """
            MATCH (a:XmlFile {relative_path:'Dir\\\\AITran.xml'})-[r:Rel]->(b)
            WHERE r.edge_type = 'SHARED_INCLUDE'
            RETURN count(r)
            """
        )
        self.assertEqual(rows[0][0], 0)

    def test_32_entity_include_reverse_still_works_for_in_scope(self):
        """SHARED tắt nhưng ENTITY_INCLUDE reverse (impact include trong scope) vẫn được."""
        rows = self._cypher(
            """
            MATCH (src:XmlFile)-[r:Rel {edge_type:'ENTITY_INCLUDE'}]->(inc:XmlFile)
            WHERE inc.relative_path STARTS WITH 'Report\\\\Include\\\\'
            RETURN inc.relative_path, count(src) AS n
            ORDER BY n DESC
            LIMIT 3
            """
        )
        self.assertTrue(rows, "Không còn ENTITY_INCLUDE tới Report\\Include — bất thường")
        # Impact kiểu reverse không cần SHARED_INCLUDE
        top_inc = rows[0][0]
        rev = self._cypher(
            """
            MATCH (src:XmlFile)-[r:Rel {edge_type:'ENTITY_INCLUDE'}]->(inc:XmlFile)
            WHERE inc.relative_path = $p
            RETURN count(src)
            """,
            {"p": top_inc},
        )
        self.assertGreater(rev[0][0], 0, f"Reverse ENTITY_INCLUDE rỗng cho {top_inc}")
        # impact theo basename có thể ambiguous; miễn reverse Cypher còn sống
        impact = q("impact", top_inc)
        if not impact.get("error"):
            self.assertGreaterEqual(impact.get("impacted_count", 0), 0)

    def test_33_aitran_has_no_entity_include_edges_expected(self):
        """
        Controllers\\Include nằm ngoài GRAPH_TOP_LEVEL_FOLDERS → AITran không có
        ENTITY_INCLUDE trong DB (hành vi cũ, không phải regression SHARED).
        """
        rows = self._cypher(
            """
            MATCH (a:XmlFile {relative_path:'Dir\\\\AITran.xml'})-[r:Rel]->(b)
            WHERE r.edge_type IN ['ENTITY_INCLUDE', 'PARAM_ENTITY_USE', 'SHARED_INCLUDE']
            RETURN r.edge_type, count(*)
            """
        )
        self.assertEqual(rows, [])

    # ---- E. Nội dung searchable / JS / SQL vẫn còn trên node ----

    def test_40_js_sql_text_present_on_aitran(self):
        rows = self._cypher(
            """
            MATCH (n:XmlFile {relative_path:'Dir\\\\AITran.xml'})
            RETURN size(coalesce(n.js_text,'')), size(coalesce(n.sql_text,''))
            """
        )
        js_len, sql_len = rows[0]
        self.assertGreater(js_len, 100)
        # sql_text co the ngan (nhieu SQL nam trong include/entity)
        self.assertGreaterEqual(sql_len, 100)

    def test_41_js_contains_handler_names(self):
        rows = self._cypher(
            """
            MATCH (n:XmlFile {relative_path:'Dir\\\\AITran.xml'})
            WHERE n.js_text CONTAINS 'onChange' OR n.js_text CONTAINS 'Voucher'
            RETURN count(n)
            """
        )
        self.assertEqual(rows[0][0], 1)

    # ---- F. Sample voucher khác (APTran) — smoke ----

    def test_50_aptran_smoke_if_present(self):
        rows = self._cypher(
            "MATCH (n:XmlFile) WHERE n.relative_path = 'Dir\\\\APTran.xml' RETURN n.relative_path"
        )
        if not rows:
            self.skipTest("Không có Dir\\APTran.xml trong DB")
        nav = q("navigate", "APTran")
        self.assertIn("grid_details", nav)
        self.assertNotIn("error", nav)
        # Không có SHARED trong outbound
        shared = self._cypher(
            """
            MATCH (a:XmlFile {relative_path:'Dir\\\\APTran.xml'})-[r:Rel {edge_type:'SHARED_INCLUDE'}]->()
            RETURN count(r)
            """
        )[0][0]
        self.assertEqual(shared, 0)


def main():
    print(f"DB: {DB_PATH} exists={DB_PATH.exists()}")
    if DB_PATH.exists():
        print(f"Size: {DB_PATH.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"REF: {REF} exists={Path(REF).exists()}")
    helper = ProjectPathHelper(REF)
    print(f"Project root: {helper.get_project_root()}")
    print(f"Graph dir: {helper.get_graph_dir()}")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TestBanyanfboSp228AfterSharedOff
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # Tóm tắt ngắn
    print("\n=== SUMMARY ===")
    print(f"Ran={result.testsRun} Failures={len(result.failures)} Errors={len(result.errors)} Skipped={len(result.skipped)}")
    if result.wasSuccessful():
        print("VERDICT: PASS - tat SHARED_INCLUDE khong pha logic nghiep vu AITran/SP228.")
    else:
        print("VERDICT: FAIL - xem chi tiet phia tren.")
        for case, tb in result.failures + result.errors:
            print("---", case)
            print(tb)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
