"""E2E socthda: classify → đọc grid → focus+Xem → Mới+lookup ma_kh → Hủy."""
import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def ev(p, js, arg=None):
    return p.evaluate(js, arg) if arg is not None else p.evaluate(js)


def lookup_select(p, field, search=None, prefer=None):
    open_res = ev(p, """(field) => {
      var inp = document.querySelector('[id*="dirExtender_form_' + field + '"]');
      if (!inp) return { ok: false, error: 'no input' };
      var img = (inp.closest('td') || inp.parentElement).querySelector('img.CellImgLookup');
      if (!img) return { ok: false, error: 'no lookup' };
      img.click();
      return { ok: true };
    }""", field)
    time.sleep(2)
    if not open_res.get("ok"):
        return {"open": open_res}

    btn = f"{DE}_FormLookup{field}_Button_Lookup"
    qf = f"{DE}_FormLookup{field}_Button_Lookup_QuickFind"
    table = f"{DE}_FormLookup{field}_Button_Lookup_Table"

    filt = None
    if search:
        filt = ev(p, """(args) => {
          var qf = document.getElementById(args.qf);
          if (!qf) return { error: 'no qf' };
          qf.value = args.term;
          qf.dispatchEvent(new Event('input', { bubbles: true }));
          FastBusiness.AjaxControlExtender.AutoCompleteExtender.find(args.btn).quickFind();
          return { ok: true, term: args.term };
        }""", {"qf": qf, "btn": btn, "term": search})
        time.sleep(2.5)

    pick = ev(p, """(args) => {
      var skip = {'Đóng':1,'Làm tươi':1,'Chọn:':1,'Mã khách':1,'Tên khách':1,'Tài khoản':1,'Tên tài khoản':1};
      var t = document.getElementById(args.table);
      if (!t) return { error: 'no table' };
      var links = t.querySelectorAll('a');
      if (args.prefer) {
        for (var a of links) {
          var txt = (a.innerText||'').trim();
          if (txt === args.prefer) { a.click(); return { picked: txt, method: 'prefer' }; }
        }
      }
      for (var tr of t.querySelectorAll('tr')) {
        var tds = tr.querySelectorAll('td');
        if (tds.length < 2) continue;
        var c1 = (tds[0].innerText||'').trim();
        if (!c1 || skip[c1] || /Danh mục|Các bản ghi|Xem |Chọn:|Không có/.test(c1)) continue;
        var link = tds[0].querySelector('a') || tr.querySelector('a');
        if (!link) continue;
        var txt = (link.innerText||'').trim() || c1;
        if (skip[txt] || txt === 'Làm tươi') continue;
        link.click();
        return { picked: txt, desc: (tds[1].innerText||'').trim(), method: 'first_data_row' };
      }
      return { error: 'no row' };
    }""", {"table": table, "prefer": prefer})
    time.sleep(1.5)
    val = ev(p, f"() => $find('{DE}').getItemValue('{field}')")
    return {"open": open_res, "filter": filt, "pick": pick, "value": val}


def focus_row(p, row=1):
    cell = f"{MR}_gridCell_{row}.1"
    # socthda col 1 might be stt_rec hidden - try col with ma_kh
    # From probe: col0 stt_rec, col1 ma_dvcs, col2 ngay_ct, col3 so_ct, col4 ma_kh
    # Focus so_ct or ma_kh cell - try .4 for ma_kh (1-based fields index)
    for col in [4, 3, 2, 1]:
        cid = f"{MR}_gridCell_{row}.{col}"
        try:
            loc = p.locator(f'[id="{cid}"]')
            if loc.count() > 0:
                loc.first.click(timeout=3000)
                time.sleep(0.4)
                st = ev(p, f"""() => {{
                  var mr = $find('{MR}');
                  var sel = false;
                  try {{ sel = !!mr._rowSelected(); }} catch(e) {{}}
                  return {{ cell: '{cid}', selected: sel, active_row: mr._activeRow || null }};
                }}""")
                if st.get("selected"):
                    return st
        except Exception:
            continue
    return {"selected": False}


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    p.goto(URL, timeout=90000)
    time.sleep(8)

    classify = ev(p, f"""() => {{
      var mr = $find('{MR}');
      return {{
        page_kind: mr._type === 'Voucher' ? 'voucher' : mr._type,
        mr_type: mr._type,
        row_count: mr._rows ? mr._rows.length : 0,
        typeof_f: typeof f
      }};
    }}""")
    log("1. Classify", classify)

    # Read browse grid
    grid = ev(p, f"""() => {{
      var mr = $find('{MR}');
      var rows = [];
      for (var r = 1; r <= Math.min(3, mr._rows.length); r++) {{
        rows.push({{
          ngay_ct: mr._getItemValue(r, 3),
          so_ct: mr._getItemValue(r, 4),
          ma_kh: mr._getItemValue(r, 5),
          ten_kh: mr._getItemValue(r, 6),
          t_tt_nt: mr._getItemValue(r, 7)
        }});
      }}
      return {{ row_count: mr._rows.length, sample: rows }};
    }}""")
    log("2. Browse grid (_getItemValue)", grid)

    # Filter so_ct if panel exists
    filter_id = f"{MR}_FilterPanelTextso_ct"
    has_filt = ev(p, f"() => !!document.getElementById('{filter_id}')")
    if has_filt and grid.get("sample"):
        so = str(grid["sample"][0].get("so_ct") or "").strip()
        if so:
            p.locator(f"#{filter_id}").click()
            p.locator(f"#{filter_id}").fill(so)
            p.locator(f"#{filter_id}").press("Enter")
            time.sleep(4)
            g2 = ev(p, f"""() => {{
              var mr = $find('{MR}');
              return {{
                row_count: mr._rows.length,
                so_ct: mr._rows.length ? mr._getItemValue(1, 4) : null
              }};
            }}""")
            log("3. Filter so_ct", {"filter": so, "result": g2})
            # clear filter
            p.goto(URL, timeout=90000)
            time.sleep(8)

    # Focus + View
    foc = focus_row(p, 1)
    log("4. Focus dòng 1", foc)
    try:
        p.locator(f"#{MR}_ToolbarButton_View").click(timeout=5000)
        via = "ToolbarButton_View"
    except Exception:
        ev(p, f"() => {{ $find('{MR}').executeCommand({{ commandName: 'View', commandArgument: '0' }}); }}")
        via = "executeCommand View"
    time.sleep(3)
    view = ev(p, f"""() => {{
      var f = $find('{DE}');
      if (!f) return {{ error: 'no form', via: '{via}' }};
      return {{
        via: '{via}',
        de_type: f._type,
        ma_kh: f.getItemValue('ma_kh'),
        so_ct: f.getItemValue('so_ct'),
        ngay_ct: String(f.getItemValue('ngay_ct')||''),
        dien_giai: f.getItemValue('dien_giai')
      }};
    }}""")
    log("5. Xem chứng từ", view)

    # Close view
    try:
        p.locator(f"#{DE}_updateDlgClose").click(timeout=3000)
    except Exception:
        try:
            p.locator(f"#{DE}_updateDlgCancel").click(timeout=3000)
        except Exception:
            pass
    time.sleep(2)

    # New + lookup ma_kh (không Lưu — thiếu grid chi tiết d81)
    p.locator(f"#{MR}_ToolbarButton_New").click()
    time.sleep(3)
    log("6. Mới — lookup ma_kh", lookup_select(p, "ma_kh", search=None, prefer=None))

    # Lookup tk nếu còn trống
    tk_val = ev(p, f"() => $find('{DE}').getItemValue('tk')")
    if not tk_val:
        log("7. Lookup tk", lookup_select(p, "tk", search=None, prefer=None))
    else:
        log("7. tk đã có", tk_val)

    vals = ev(p, f"""() => {{
      var f = $find('{DE}');
      return {{
        ma_kh: f.getItemValue('ma_kh'),
        ten_kh: f.getItemValue('ten_kh'),
        tk: f.getItemValue('tk'),
        ma_gd: f.getItemValue('ma_gd'),
        ma_tt: f.getItemValue('ma_tt'),
        ma_nt: f.getItemValue('ma_nt'),
        so_ct: f.getItemValue('so_ct'),
        ngay_ct: String(f.getItemValue('ngay_ct')||''),
        dien_giai: f.getItemValue('dien_giai')
      }};
    }}""")
    log("8. Values sau lookup (chưa Lưu)", vals)

    # Hủy — không lưu phiếu thiếu chi tiết
    p.locator(f"#{DE}_updateDlgCancel").click(force=True)
    time.sleep(2)
    dismiss = ev(p, """() => {
      var btns = document.querySelectorAll('button, input[type="button"]');
      for (var b of btns) {
        var t = (b.value||b.innerText||'').trim();
        if (t === 'Có' || t === 'Nhận' || t === 'Yes') { b.click(); return t; }
      }
      return null;
    }""")
    log("9. Hủy form", {"confirm": dismiss})

    log("KẾT LUẬN", {
      "classify_voucher": classify.get("page_kind") == "voucher",
      "browse_grid_ok": (grid.get("row_count") or 0) > 0,
      "view_ok": not view.get("error") and bool(view.get("ma_kh") or view.get("so_ct")),
      "new_lookup_ma_kh": bool(vals.get("ma_kh")),
      "saved": False,
      "note": "Chưa Lưu — form cần grid chi tiết d81 (SVDetail); test dừng ở lookup master",
      "pass": (
        classify.get("page_kind") == "voucher"
        and (grid.get("row_count") or 0) > 0
        and bool(vals.get("ma_kh"))
      ),
    })

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
