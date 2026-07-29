"""
Deep YC smoke: BANYAN SP228 — 3 yêu cầu nghiệp vụ cũ vs khả năng đáp ứng của Kuzu
(sau extract_options.shared_include=0).

Chạy:
  python xml_fbograph/tests/test_banyanfbo_yc_deep.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from xml_fbograph.query.engine import xml_graph_query
from xml_fbograph.storage.kuzu_index import KuzuIndexStore

REF = r"\\172.168.5.14\CustomerPro\FBO\BANYANFBO\SP228\App_Data\Controllers\Dir\SVTran.xml"
DB_PATH = Path(
    r"C:\KuzuDB\XFwxNzIuMTY4LjUuMTRcQ3VzdG9tZXJQcm9cRkJPXEJBTllBTkZCT1xTUDIyOA==\.fbograph\kuzu"
)


def q(query_type: str, target: str, **kwargs):
    return xml_graph_query(query_type, target, REF, **kwargs)


class TestBanyanYcDeep(unittest.TestCase):
    """Kuzu co the DAN DUONG toi dung file/tab/field cho 3 YC; khong thay the doc XML/SQL."""

    @classmethod
    def setUpClass(cls):
        if not DB_PATH.exists():
            raise unittest.SkipTest(f"Missing DB {DB_PATH}")
        cls.store = KuzuIndexStore(DB_PATH, read_only=True)
        cls.conn = cls.store.conn

    def cypher(self, sql: str, params: dict | None = None):
        res = self.conn.execute(sql, params or {})
        rows = []
        while res.has_next():
            rows.append(res.get_next())
        return rows

    # -------- YC1: Dieu chinh HTTT / tab thanh toan SV + SS --------

    def test_yc1_map_controllers_by_title(self):
        rows = self.cypher(
            """
            MATCH (n:XmlFile)
            WHERE n.folder_type = 'Dir'
              AND (
                toLower(n.title_v) CONTAINS 'hóa đơn'
                OR toLower(n.title_v) CONTAINS 'cửa hàng'
                OR n.relative_path IN ['Dir\\\\SVTran.xml','Dir\\\\SSTran.xml']
              )
            RETURN n.relative_path, n.title_v
            """
        )
        paths = {r[0] for r in rows}
        self.assertIn("Dir\\SVTran.xml", paths)
        self.assertIn("Dir\\SSTran.xml", paths)

    def test_yc1_svtran_has_payment_tab(self):
        nav = q("navigate", "SVTran")
        grids = {g["field_name"]: g["controller"] for g in nav.get("grid_details", [])}
        self.assertEqual(grids.get("zcHDAdmtt"), "Grid\\SVPayment.xml")

    def test_yc1_sstran_has_payment_detail_tab(self):
        nav = q("navigate", "SSTran")
        controllers = {g["controller"] for g in nav.get("grid_details", [])}
        self.assertIn("Grid\\SSTTDetail.xml", controllers)

    def test_yc1_payment_fields_and_lookup(self):
        # SVPayment: ma_hinh_thuc -> zcdmhtttch; ma_bp
        rows = self.cypher(
            """
            MATCH (n:XmlFile)
            WHERE n.relative_path = 'Grid\\\\SVPayment.xml'
            RETURN list_contains(n.fields_names, 'ma_hinh_thuc'),
                   list_contains(n.fields_names, 'ma_bp'),
                   size(coalesce(n.js_text, ''))
            """
        )
        self.assertEqual(rows[0][0], True)
        self.assertEqual(rows[0][1], True)
        self.assertGreater(rows[0][2], 0)

        nav = q("navigate", "SVPayment")
        lookups = {(x["field_name"], x["controller"]) for x in nav.get("lookup_references", [])}
        self.assertIn(("ma_hinh_thuc", "Grid\\zcdmhtttch.xml"), lookups)
        self.assertIn(("ma_bp", "Grid\\Department.xml"), lookups)
        masters = {m["controller"] for m in nav.get("master_controllers", [])}
        self.assertIn("Dir\\SVTran.xml", masters)

        # SSTTDetail: ma_httt
        rows = self.cypher(
            """
            MATCH (n:XmlFile)
            WHERE n.relative_path = 'Grid\\\\SSTTDetail.xml'
            RETURN list_contains(n.fields_names, 'ma_httt')
            """
        )
        self.assertEqual(rows[0][0], True)

    def test_yc1_catalog_httt_exists(self):
        rows = self.cypher(
            """
            MATCH (n:XmlFile)
            WHERE n.relative_path = 'Dir\\\\zcdmhtttch.xml'
               OR toLower(coalesce(n.title_v, '')) CONTAINS 'hình thức thanh toán'
            RETURN n.relative_path, n.title_v
            """
        )
        self.assertTrue(any("zcdmhtttch" in r[0] for r in rows))

    def test_yc1_shared_include_not_required(self):
        n = self.cypher(
            "MATCH ()-[r:Rel {edge_type:'SHARED_INCLUDE'}]->() RETURN count(r)"
        )[0][0]
        self.assertEqual(n, 0)

    # -------- YC2: SRTran ke thua bo phan + hoan thanh toan --------

    def test_yc2_srtran_tabs(self):
        nav = q("navigate", "SRTran")
        grids = {g["field_name"]: g["controller"] for g in nav.get("grid_details", [])}
        self.assertEqual(grids.get("d76"), "Grid\\SRDetail.xml")
        self.assertEqual(grids.get("d76tt"), "Grid\\SRTTDetail.xml")

    def test_yc2_sr_detail_has_ma_bp_ma_kho(self):
        rows = self.cypher(
            """
            MATCH (n:XmlFile)
            WHERE n.relative_path = 'Grid\\\\SRDetail.xml'
            RETURN list_contains(n.fields_names, 'ma_bp'),
                   list_contains(n.fields_names, 'ma_kho')
            """
        )
        self.assertEqual(rows[0][0], True)
        self.assertEqual(rows[0][1], True)

    def test_yc2_srtt_has_ma_bp_and_ma_httt(self):
        rows = self.cypher(
            """
            MATCH (n:XmlFile)
            WHERE n.relative_path = 'Grid\\\\SRTTDetail.xml'
            RETURN list_contains(n.fields_names, 'ma_bp'),
                   list_contains(n.fields_names, 'ma_httt')
            """
        )
        self.assertEqual(rows[0][0], True)
        self.assertEqual(rows[0][1], True)

        nav = q("navigate", "SRTTDetail")
        lookups = {(x["field_name"], x["controller"]) for x in nav.get("lookup_references", [])}
        self.assertIn(("ma_bp", "Grid\\Department.xml"), lookups)
        self.assertIn(("ma_httt", "Grid\\zcdmhtttch.xml"), lookups)

    def test_yc2_ss_and_sv_are_discoverable_sources(self):
        # Agent can find SS (store invoice) + SV (sales invoice) as inheritance sources
        for name, title_part in (("SSTran", "cửa hàng"), ("SVTran", "hóa đơn")):
            nav = q("navigate", name)
            self.assertNotIn("error", nav)
            self.assertEqual(nav.get("folder_type"), "Dir")

    # -------- YC3: SOTran ma_kho -> ma_bp (+ SV/SR tuong tu) --------

    def test_yc3_sotran_detail_has_ma_kho_ma_bp(self):
        nav = q("navigate", "SOTran")
        grids = {g["controller"] for g in nav.get("grid_details", [])}
        self.assertIn("Grid\\SODetail.xml", grids)

        ctx = q("context", "SODetail")
        names = {f["name"] for f in ctx.get("fields", [])}
        self.assertIn("ma_bp", names)
        self.assertIn("ma_kho", names)
        # header Bo phan
        bp = next(f for f in ctx["fields"] if f["name"] == "ma_bp")
        self.assertIn("Bộ phận", bp.get("header_v") or "")

    def test_yc3_sodetail_lookups_site_and_department(self):
        nav = q("navigate", "SODetail")
        lookups = {(x["field_name"], x["controller"]) for x in nav.get("lookup_references", [])}
        self.assertIn(("ma_kho", "Grid\\Site.xml"), lookups)
        self.assertIn(("ma_bp", "Grid\\Department.xml"), lookups)
        masters = {m["controller"] for m in nav.get("master_controllers", [])}
        self.assertIn("Dir\\SOTran.xml", masters)

    def test_yc3_sv_and_sr_detail_also_have_ma_bp_ma_kho(self):
        rows = self.cypher(
            """
            MATCH (v:XmlFile)-[r:Rel]->(d:XmlFile)
            WHERE v.relative_path IN ['Dir\\\\SOTran.xml','Dir\\\\SVTran.xml','Dir\\\\SRTran.xml']
              AND r.edge_type = 'GRID_MASTER_DETAIL'
              AND d.relative_path IN ['Grid\\\\SODetail.xml','Grid\\\\SVDetail.xml','Grid\\\\SRDetail.xml']
            RETURN v.relative_path, d.relative_path,
                   list_contains(d.fields_names, 'ma_bp'),
                   list_contains(d.fields_names, 'ma_kho')
            ORDER BY v.relative_path
            """
        )
        by_pair = {(r[0], r[1]): (r[2], r[3]) for r in rows}
        expected = {
            ("Dir\\SOTran.xml", "Grid\\SODetail.xml"),
            ("Dir\\SVTran.xml", "Grid\\SVDetail.xml"),
            ("Dir\\SRTran.xml", "Grid\\SRDetail.xml"),
        }
        self.assertTrue(expected <= set(by_pair.keys()), f"Thieu pair: {expected - set(by_pair.keys())}")
        for pair in expected:
            has_ma_bp, has_ma_kho = by_pair[pair]
            self.assertTrue(has_ma_bp, f"{pair} thieu ma_bp")
            self.assertTrue(has_ma_kho, f"{pair} thieu ma_kho")

    def test_yc3_js_mentions_ma_bp_on_details(self):
        rows = self.cypher(
            """
            MATCH (n:XmlFile)
            WHERE n.relative_path IN [
              'Grid\\\\SODetail.xml','Grid\\\\SVDetail.xml','Grid\\\\SRDetail.xml'
            ]
            RETURN n.relative_path, n.js_text CONTAINS 'ma_bp', n.js_text CONTAINS 'ma_kho'
            """
        )
        by_path = {r[0]: (r[1], r[2]) for r in rows}
        for path in ("Grid\\SODetail.xml", "Grid\\SVDetail.xml", "Grid\\SRDetail.xml"):
            self.assertTrue(by_path[path][0], f"{path} js thieu ma_bp")
            self.assertTrue(by_path[path][1], f"{path} js thieu ma_kho")


def main():
    print(f"DB={DB_PATH} size_mb={DB_PATH.stat().st_size/1024/1024:.2f}")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestBanyanYcDeep)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("\n=== SUMMARY ===")
    print(
        f"Ran={result.testsRun} Fail={len(result.failures)} "
        f"Err={len(result.errors)} Skip={len(result.skipped)}"
    )
    if result.wasSuccessful():
        print("VERDICT: Kuzu DU de DAN DUONG 3 YC (map controller/tab/field/lookup).")
        print("NOTE: Rule chi tiet (quyen sua, xoa/sinh phieu hach toan, max ma_bp) can doc XML/SQL.")
    else:
        print("VERDICT: FAIL")
        for case, tb in result.failures + result.errors:
            print("---", case)
            print(tb)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
