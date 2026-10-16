"""Unit tests cho query_database mode='lookup' (function_lookup)."""
from __future__ import annotations

import query_database.function_lookup as fl
from query_database import query_database

_W = {"wmenu_id", "wmenu_id0", "menu_id", "bar", "bar2", "link",
      "parameter", "sysid", "type"}
_C = {"menu_id", "sysid", "syscode", "bar", "bar2", "type", "exe"}
_MENU_COLS = ["src", "wmenu_id", "menu_id", "title", "title_e", "controller",
              "ma_ct", "type", "page", "parameter", "parent_title", "grand_title"]


def _rs(columns, rows):
    return {"success": True, "result_sets": [{"columns": columns, "rows": rows}]}


def _patch(monkeypatch, tmp_path, *, sys_cols, menu_rows, dmct_rows=()):
    calls = []
    monkeypatch.setattr(
        fl, "get_connection_config",
        lambda fp, db: {"success": True, "parsed": {"db": db},
                        "project_root": str(tmp_path)},
    )

    def fake_exec(parsed, sql, max_rows=0, params=None):
        calls.append((parsed["db"], sql, params))
        if "sys.columns" in sql:
            cols = sys_cols if parsed["db"] == "sys" else {"dmct": {"ma_ct", "ten_ct"}}
            rows = [[t, c] for t, cs in cols.items() for c in sorted(cs)]
            return _rs(["t", "c"], rows)
        if "FROM dmct" in sql:
            return _rs(["ma_ct", "ten_ct"], [list(r) for r in dmct_rows])
        return {"success": True,
                "result_sets": [{"columns": _MENU_COLS, "rows": menu_rows}]}

    monkeypatch.setattr(fl, "execute_query", fake_exec)
    return calls


def _menu(controller, title, menu_id, wmenu_id="11.20.06", ma_ct=None,
          parent="Bán hàng", typ="V", page="x.aspx"):
    return ["wcommand", wmenu_id, menu_id, title, title, controller, ma_ct,
            typ, page, None, parent, None]


def test_lookup_requires_keyword():
    res = fl.lookup_function("x", "  ")
    assert res["success"] is False
    assert res["error_code"] == "keyword_required"


def test_lookup_ranks_exact_and_attaches_files(monkeypatch, tmp_path):
    ctrl_dir = tmp_path / "App_Data" / "Controllers"
    (ctrl_dir / "Dir").mkdir(parents=True)
    (ctrl_dir / "Grid").mkdir(parents=True)
    (ctrl_dir / "Dir" / "DDVTran.xml").write_text("<x/>", encoding="utf-8")
    (ctrl_dir / "Grid" / "DDVTran.f").write_bytes(b"enc")
    _patch(monkeypatch, tmp_path,
           sys_cols={"wcommand": _W, "command": _C},
           menu_rows=[
               _menu("InputInvoice", "Hóa đơn đầu vào", "09.35.10",
                     page="qlhddv.aspx"),
               _menu("DDVTran", "Hợp đồng dịch vụ (C)", "88.01.CZ", ma_ct="DDV"),
           ],
           dmct_rows=[("DDV", "Hợp đồng dịch vụ")])

    res = fl.lookup_function("x", "DDV")
    assert res["success"] is True
    first = res["functions"][0]
    assert first["controller"] == "DDVTran"
    assert first["type"] == "voucher"
    assert first["menu_paths"] == ["Bán hàng > Hợp đồng dịch vụ (C)"]
    assert first["files"] == ["Dir/DDVTran.xml"]
    assert first["encrypted_only"] == ["Grid/DDVTran.f"]
    assert res["vouchers"] == [{"ma_ct": "DDV", "ten_ct": "Hợp đồng dịch vụ"}]


def test_lookup_merges_menus_and_skips_separators(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path,
           sys_cols={"wcommand": _W, "command": _C},
           menu_rows=[
               _menu("Contract", "Danh mục hợp đồng", "04.07.15", "07.70.28",
                     parent="Phải thu", typ="D"),
               _menu("Contract", "Danh mục hợp đồng", "04.07.15", "09.55.09",
                     parent="Phải trả", typ="D"),
               _menu("ContractPaymentProgress", "-", "99.96.92", page="."),
           ])
    res = fl.lookup_function("x", "Contract")
    assert res["function_count"] == 1
    f = res["functions"][0]
    assert f["type"] == "category"
    assert f["menu_paths"] == ["Phải thu > Danh mục hợp đồng",
                               "Phải trả > Danh mục hợp đồng"]


def test_menu_sql_skips_missing_columns():
    """Bản FBO thiếu cột → SQL dùng NULL, không tham chiếu cột không tồn tại."""
    sql, params = fl._menu_sql({"wmenu_id", "menu_id", "bar", "sysid"}, set(), "abc")
    assert "w.link" not in sql and "w.bar2" not in sql
    assert "JOIN command" not in sql
    assert "wcommand p" not in sql  # không có wmenu_id0 → bỏ breadcrumb
    assert sql.count("?") == len(params)


def test_menu_sql_escapes_like_wildcards():
    sql, params = fl._menu_sql(_W, _C, "rpt_a%")
    assert "%rpt[_]a[%]%" in params
    assert "rpt_a%" in params  # so khớp chính xác giữ nguyên


def test_lookup_empty_gives_disk_hint(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, sys_cols={"wcommand": _W, "command": _C},
           menu_rows=[])
    res = fl.lookup_function("x", "zzz")
    assert res["functions"] == []
    assert any("search_files" in h for h in res["hints"])


def test_query_database_dispatches_lookup(monkeypatch):
    seen = {}

    def fake_lookup(fp, kw, max_results=20):
        seen.update(fp=fp, kw=kw, n=max_results)
        return {"success": True, "mode": "lookup"}

    monkeypatch.setattr(fl, "lookup_function", fake_lookup)
    res = query_database(file_path="p", query="DDV", mode="lookup", max_results=7)
    assert res["mode"] == "lookup"
    assert seen == {"fp": "p", "kw": "DDV", "n": 7}
    query_database(file_path="p", query="DDV", mode="lookup")  # default 50 → cap 20
    assert seen["n"] == 20
