"""E2E socthda: Mới → master lookup → 1 dòng detail (dvt auto) → Lưu → verify browse."""
import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"
FG = f"{DE}_FormGridd81"
SVDETAIL_XML = r"\\172.168.5.14\CustomerPro\FBI\BINHDIENMK\SP2264\App_Data\Controllers\Grid\SVDetail.xml"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def ev(p, js, arg=None):
    return p.evaluate(js, arg) if arg is not None else p.evaluate(js)


def dismiss_msg(p):
    return ev(p, """() => {
      var btns = document.querySelectorAll('input[type="button"], button');
      for (var b of btns) {
        if ((b.value || b.innerText || '').trim() === 'Nhận') { b.click(); return { ok: true }; }
      }
      return { ok: false };
    }""")


def dismiss_master_lookup(p, field):
    prefix = f"{DE}_FormLookup{field}_Button_Lookup"
    ev(p, f"""() => {{
      var bg = document.getElementById('{prefix}_backgroundElement');
      if (bg) bg.click();
      try {{
        var ext = FastBusiness.AjaxControlExtender.AutoCompleteExtender.find('{prefix}');
        if (ext && ext.hide) ext.hide();
      }} catch(e) {{}}
    }}""")
    time.sleep(0.4)


def lookup_master(p, field, search=None):
    btn = f"{DE}_FormLookup{field}_Button_Lookup"
    qf = f"{DE}_FormLookup{field}_Button_Lookup_QuickFind"
    table = f"{DE}_FormLookup{field}_Button_Lookup_Table"
    ev(p, """(field) => {
      var inp = document.querySelector('[id*="dirExtender_form_' + field + '"]');
      var img = (inp.closest('td') || inp.parentElement).querySelector('img.CellImgLookup');
      img.click();
    }""", field)
    time.sleep(2)
    if search:
        ev(p, """(a) => {
          var qf = document.getElementById(a.qf);
          qf.value = a.term;
          qf.dispatchEvent(new Event('input', { bubbles: true }));
          FastBusiness.AjaxControlExtender.AutoCompleteExtender.find(a.btn).quickFind();
        }""", {"qf": qf, "btn": btn, "term": search})
        time.sleep(2.5)
    pick = ev(p, """(table) => {
      var t = document.getElementById(table);
      for (var tr of t.querySelectorAll('tr')) {
        var tds = tr.querySelectorAll('td');
        if (tds.length < 2) continue;
        var c1 = (tds[0].innerText || '').trim();
        if (!c1 || /Danh mục|Chọn:|Không có|Làm tươi|Đóng/.test(c1)) continue;
        var link = tds[0].querySelector('a') || tr.querySelector('a');
        if (link) { link.click(); return { picked: (link.innerText || '').trim() }; }
      }
      return { error: 'no row' };
    }""", table)
    time.sleep(1.5)
    dismiss_master_lookup(p, field)
    dismiss_msg(p)
    val = ev(p, f"() => $find('{DE}').getItemValue('{field}')")
    return {"pick": pick, "value": val}


def grid_col_map(p):
    return ev(p, f"""() => {{
      var g = $find('{FG}');
      var m = {{}};
      for (var i = 0; i < g._fields.length; i++) m[g._fields[i].Name] = i + 1;
      return m;
    }}""")


def dismiss_grid_lookup(p, row, col):
    bg = f"{FG}_GridLookup{row}.{col}_Button_Lookup_backgroundElement"
    ev(p, f"""() => {{
      var bg = document.getElementById('{bg}');
      if (bg) bg.click();
      try {{
        var ext = FastBusiness.AjaxControlExtender.AutoCompleteExtender.find('{FG}_GridLookup{row}.{col}_Button_Lookup');
        if (ext && ext.hide) ext.hide();
      }} catch(e) {{}}
    }}""")
    time.sleep(0.4)


def scan_detail_rows(p, cm, max_row=5):
    ma_col = cm["ma_vt"]
    dvt_col = cm["dvt"]
    sl_col = cm["so_luong"]
    return ev(p, f"""() => {{
      var g = $find('{FG}');
      var rows = [];
      for (var r = 1; r <= {max_row}; r++) {{
        var has_inp = !!document.getElementById('{FG}_inputCell_' + r + '.{ma_col}');
        if (!has_inp) continue;
        var ma = '', dvt = '', sl = 0;
        try {{ ma = g._getItemValue(r, {ma_col}) || ''; }} catch(e) {{ ma = ''; }}
        try {{ dvt = g._getItemValue(r, {dvt_col}) || ''; }} catch(e) {{ dvt = ''; }}
        try {{ sl = g._getItemValue(r, {sl_col}); }} catch(e) {{ sl = 0; }}
        rows.push({{ row: r, ma_vt: ma, dvt: dvt, so_luong: sl }});
      }}
      return rows;
    }}""")


def lookup_grid_cell_generic(p, row, col, field_name=""):
    """Lookup AutoComplete trên cell grid — không filter, chọn dòng đầu."""
    cell = f"{FG}_gridCell_{row}.{col}"
    table = f"{FG}_GridLookup{row}.{col}_Button_Lookup_Table"
    loc = p.locator(f'[id="{cell}"]')
    loc.click(timeout=5000)
    time.sleep(0.3)
    loc.locator("img.CellImgLookup").click(timeout=5000)
    time.sleep(2)
    pick = ev(p, """(table) => {
      var t = document.getElementById(table);
      if (!t) return { error: 'no table' };
      for (var tr of t.querySelectorAll('tr')) {
        var tds = tr.querySelectorAll('td');
        if (tds.length < 2) continue;
        var c1 = (tds[0].innerText || '').trim();
        if (!c1 || /Danh mục|Chọn:|Không có|Làm tươi|Đóng|Tìm nhanh/.test(c1)) continue;
        var link = tds[0].querySelector('a') || tr.querySelector('a');
        if (link) { link.click(); return { picked: (link.innerText || '').trim() }; }
      }
      return { error: 'no row' };
    }""", table)
    time.sleep(1.5)
    dismiss_grid_lookup(p, row, col)
    dismiss_msg(p)
    val = ev(p, f"() => $find('{FG}')._getItemValue({row}, {col})")
    return {"field": field_name, "pick": pick, "value": val}


def read_fbo_popup(p):
    return ev(p, """() => {
      var body = document.body.innerText || '';
      var m = body.match(/Trường\\s+(.+?)\\s+chưa nhập[^\\n]*/i);
      return {
        raw: m ? m[0] : null,
        header: m ? m[1].trim() : null,
        has_nhan: body.indexOf('Nhận') >= 0
      };
    }""")


def resolve_field_by_header(p, header, scopes=("master", "detail")):
    return ev(p, f"""() => {{
      var header = {json.dumps(header)};
      function scan(comp, scope) {{
        if (!comp || !comp._fields) return null;
        for (var i = 0; i < comp._fields.length; i++) {{
          var f = comp._fields[i];
          var h = (f.HeaderText || f.Label || '').trim();
          if (h === header)
            return {{ name: f.Name, scope: scope, col: i + 1 }};
        }}
        return null;
      }}
      var de = $find('{DE}');
      var g = $find('{FG}');
      var o = null;
      if ({json.dumps("master" in scopes)}) o = scan(de, 'master');
      if (!o && {json.dumps("detail" in scopes)}) o = scan(g, 'detail');
      return o;
    }}""")


def fix_field(p, field_info, cm, row=1):
    if not field_info:
        return {"error": "no field_info"}
    name = field_info["name"]
    if field_info["scope"] == "master":
        res = lookup_master(p, name)
        verify = ev(p, f"() => $find('{DE}').getItemValue('{name}')")
        return {"action": "lookup_master", "field": name, "result": res, "verify": verify}
    col = cm.get(name) or field_info.get("col")
    if not col:
        return {"error": "no col", "field": name}
    if name == "so_luong":
        v = fill_grid_numeric(p, row, col, "1")
        return {"action": "fill_numeric", "field": name, "verify": v}
    res = lookup_grid_cell_generic(p, row, col, name)
    verify = ev(p, f"() => $find('{FG}')._getItemValue({row}, {col})")
    return {"action": "lookup_detail", "field": name, "result": res, "verify": verify}


def save_with_retry(p, cm, row=1, max_rounds=8):
    """Lưu → parse popup → Nhận → sửa field → Lưu lại. Không đóng form."""
    history = []
    for rnd in range(1, max_rounds + 1):
        p.locator(f"#{DE}_updateDlgOk").click(force=True)
        time.sleep(4)
        popup = read_fbo_popup(p)
        closed = ev(p, f"""() => {{
          var btn = document.getElementById('{DE}_updateDlgOk');
          return !(btn && btn.offsetParent !== null);
        }}""")
        if closed and not popup.get("raw"):
            return {"ok": True, "rounds": rnd, "history": history}
        if not popup.get("raw"):
            time.sleep(3)
            closed = ev(p, f"""() => {{
              var btn = document.getElementById('{DE}_updateDlgOk');
              return !(btn && btn.offsetParent !== null);
            }}""")
            if closed:
                return {"ok": True, "rounds": rnd, "history": history}
            history.append({"round": rnd, "error": "form_open_no_message"})
            break
        field_info = resolve_field_by_header(p, popup["header"])
        dismiss_msg(p)
        time.sleep(0.5)
        fix = fix_field(p, field_info, cm, row)
        history.append({"round": rnd, "popup": popup, "field_info": field_info, "fix": fix})
        log(f"save retry round {rnd}", history[-1])
    return {"ok": False, "history": history}


def lookup_grid_ma_vt(p, row, col):
    """Lookup ma_vt — KHÔNG đụng dvt sau khi chọn."""
    cell = f"{FG}_gridCell_{row}.{col}"
    table = f"{FG}_GridLookup{row}.{col}_Button_Lookup_Table"
    loc = p.locator(f'[id="{cell}"]')
    loc.click(timeout=5000)
    time.sleep(0.3)
    loc.locator("img.CellImgLookup").click(timeout=5000)
    time.sleep(2)
    pick = ev(p, """(table) => {
      var t = document.getElementById(table);
      if (!t) return { error: 'no table' };
      for (var tr of t.querySelectorAll('tr')) {
        var tds = tr.querySelectorAll('td');
        if (tds.length < 2) continue;
        var c1 = (tds[0].innerText || '').trim();
        if (!c1 || /Danh mục|Chọn:|Không có|Làm tươi|Đóng|Tìm nhanh/.test(c1)) continue;
        var link = tds[0].querySelector('a') || tr.querySelector('a');
        if (link) {
          var desc = (tds[1].innerText || '').trim();
          link.click();
          return { picked: (link.innerText || '').trim(), desc: desc };
        }
      }
      return { error: 'no row' };
    }""", table)
    time.sleep(2)
    dismiss_grid_lookup(p, row, col)
    dismiss_msg(p)
    ma = ev(p, f"() => $find('{FG}')._getItemValue({row}, {col})")
    dvt_col = ev(p, f"""() => {{
      var g = $find('{FG}');
      for (var i = 0; i < g._fields.length; i++)
        if (g._fields[i].Name === 'dvt') return i + 1;
      return 3;
    }}""")
    dvt = ev(p, f"() => $find('{FG}')._getItemValue({row}, {dvt_col})")
    return {"pick": pick, "ma_vt": ma, "dvt_auto": dvt}


def fill_grid_numeric(p, row, col, value):
    inp = f"{FG}_inputCell_{row}.{col}"
    loc = p.locator(f'[id="{inp}"]')
    loc.click(timeout=5000)
    loc.fill(str(value))
    loc.press("Tab")
    time.sleep(0.8)
    try:
        return ev(p, f"() => $find('{FG}')._getItemValue({row}, {col})")
    except Exception:
        return ev(p, f"""() => {{
          var el = document.getElementById('{inp}');
          return el ? el.value : null;
        }}""")


def remove_detail_row(p, row, ma_col):
    """Focus dòng → toolbar Xóa dòng → confirm Có."""
    cell = f"{FG}_gridCell_{row}.{ma_col}"
    p.locator(f'[id="{cell}"]').click(timeout=5000)
    time.sleep(0.4)
    p.locator(f"#{FG}_ToolbarButton_Remove").click(timeout=5000)
    time.sleep(0.8)
    ev(p, """() => {
      for (var b of document.querySelectorAll('input[type="button"], button')) {
        if ((b.value || b.innerText || '').trim() === 'Có') { b.click(); return { ok: true }; }
      }
      return { ok: false };
    }""")
    time.sleep(1)


def remove_empty_detail_rows(p, cm):
    """Xóa mọi dòng không có ma_vt (vd dòng 2 trống do Insert thừa)."""
    removed = []
    for _ in range(4):
        rows = scan_detail_rows(p, cm)
        empty = [r["row"] for r in rows if not (r.get("ma_vt") or "").strip()]
        if not empty:
            break
        for r in sorted(empty, reverse=True):
            remove_detail_row(p, r, cm["ma_vt"])
            removed.append(r)
        time.sleep(0.5)
    return removed


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    log("reference", {"detail_xml": SVDETAIL_XML, "grid": "d81/SVDetail"})

    p.goto(URL, timeout=90000)
    time.sleep(8)
    ev(p, f"() => $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }})")
    time.sleep(4)

    log("master ma_kh", lookup_master(p, "ma_kh"))
    log("master tk", lookup_master(p, "tk"))
    log("master ma_tt", lookup_master(p, "ma_tt"))

    # tk_thue_no nếu trống
    tk_thue = ev(p, f"() => $find('{DE}').getItemValue('tk_thue_no')")
    if not (tk_thue or "").strip():
        log("master tk_thue_no", lookup_master(p, "tk_thue_no"))

    req = ["ma_kh", "tk", "ma_gd", "ma_tt", "so_ct", "so_seri", "ngay_lct", "ngay_ct", "ma_nt", "tk_thue_no"]
    master_vals = ev(p, f"""() => {{
      var de = $find('{DE}');
      var o = {{}};
      {json.dumps(req)}.forEach(function(n) {{ o[n] = de.getItemValue(n); }});
      o.empty = {json.dumps(req)}.filter(function(n) {{
        var v = o[n]; return v === null || v === undefined || String(v).trim() === '';
      }});
      return o;
    }}""")
    log("master required", master_vals)

    so_ct = master_vals.get("so_ct")
    ma_kh = master_vals.get("ma_kh")

    p.locator("#__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel1").click()
    time.sleep(1)

    cm = grid_col_map(p)
    log("cols", {k: cm[k] for k in ["ma_vt", "dvt", "so_luong", "ma_kho"] if k in cm})

    # Form Mới đã có sẵn dòng 1 — KHÔNG bấm Insert (Insert tạo thêm dòng 2 trống)
    log("rows default (no insert)", scan_detail_rows(p, cm))

    row = 1
    r_ma = lookup_grid_ma_vt(p, row, cm["ma_vt"])
    log("detail ma_vt lookup", r_ma)

    if not r_ma.get("ma_vt"):
        log("FAIL", {"reason": "ma_vt trống sau lookup"})
        p.close()
        return

    # dvt: CHỈ dùng giá trị auto sau ma_vt — KHÔNG mở lookup, KHÔNG lọc Khối
    dvt = r_ma.get("dvt_auto") or ev(p, f"() => $find('{FG}')._getItemValue(1, {cm['dvt']})")
    log("detail dvt (auto only)", dvt)
    if not dvt:
        log("FAIL", {"reason": "dvt không auto-fill sau ma_vt — cần chọn dvt hiện có, không lọc Khối"})
        p.close()
        return

    sl = fill_grid_numeric(p, row, cm["so_luong"], "1")
    log("detail so_luong", sl)

    # Xóa dòng trống thừa (nếu có dòng 2+ không có ma_vt)
    removed = remove_empty_detail_rows(p, cm)
    if removed:
        log("removed empty rows", removed)

    rows_final = scan_detail_rows(p, cm)
    log("detail rows before save", rows_final)

    detail_req = ["ma_vt", "dvt", "ma_kho", "so_luong", "tk_dt", "tk_vt", "tk_gv", "ma_nx"]
    detail_check = ev(p, f"""() => {{
      var g = $find('{FG}');
      var o = {{}}, empty = [];
      {json.dumps(detail_req)}.forEach(function(n) {{
        var col = null;
        for (var i = 0; i < g._fields.length; i++)
          if (g._fields[i].Name === n) {{ col = i + 1; break; }}
        if (!col) return;
        var v = g._getItemValue(1, col);
        o[n] = v;
        if (v === null || v === undefined || String(v).trim() === '' || (n !== 'so_luong' && v === 0))
          empty.push(n);
      }});
      o.empty = empty;
      return o;
    }}""")
    log("detail required check", detail_check)

    if detail_check.get("empty"):
        for field in list(detail_check["empty"]):
            if field == "so_luong":
                fill_grid_numeric(p, row, cm["so_luong"], "1")
                continue
            col = cm.get(field)
            if not col:
                continue
            # AutoComplete bắt buộc còn trống → lookup chọn dòng đầu (không lọc Khối)
            log(f"detail lookup {field}", lookup_grid_cell_generic(p, row, col, field))
        detail_check = ev(p, f"""() => {{
          var g = $find('{FG}');
          var o = {{}}, empty = [];
          {json.dumps(detail_req)}.forEach(function(n) {{
            var col = null;
            for (var i = 0; i < g._fields.length; i++)
              if (g._fields[i].Name === n) {{ col = i + 1; break; }}
            if (!col) return;
            var v = g._getItemValue(1, col);
            o[n] = v;
            if (v === null || v === undefined || String(v).trim() === '' || (n !== 'so_luong' && v === 0))
              empty.push(n);
          }});
          o.empty = empty;
          return o;
        }}""")
        log("detail required after fill", detail_check)
        if detail_check.get("empty"):
            log("FAIL", {"reason": "detail còn thiếu required", "empty": detail_check["empty"]})
            p.close()
            return

    filled = [r for r in rows_final if (r.get("ma_vt") or "").strip()]
    empty = [r for r in rows_final if not (r.get("ma_vt") or "").strip()]
    if len(filled) != 1 or empty:
        log("FAIL", {"reason": "phải đúng 1 dòng có ma_vt, không có dòng trống", "filled": filled, "empty": empty})
        p.close()
        return

    save_res = save_with_retry(p, cm, row=1)
    log("save_with_retry", save_res)

    if not save_res.get("ok"):
        log("KẾT LUẬN", {"pass": False, "reason": "Lưu thất bại sau retry", "save": save_res})
        p.close()
        return

    # Verify trên browse grid theo so_ct
    p.goto(URL, timeout=90000)
    time.sleep(8)

    if so_ct:
        filt = p.locator(f"#{MR}_FilterPanelTextso_ct")
        if filt.count():
            filt.click()
            filt.fill(str(so_ct))
            filt.press("Enter")
            time.sleep(5)

    verify = ev(p, f"""() => {{
      var mr = $find('{MR}');
      if (!mr._rows || !mr._rows.length) return {{ found: false, row_count: 0 }};
      var target = '{so_ct or ''}';
      for (var r = 1; r <= mr._rows.length; r++) {{
        var s = String(mr._getItemValue(r, 3) || '').trim();
        var kh = String(mr._getItemValue(r, 4) || '').trim();
        if (!target || s === target || kh === '{ma_kh or ''}') {{
          return {{
            found: true,
            row: r,
            so_ct: s,
            ma_kh: kh,
            ngay_ct: mr._getItemValue(r, 2),
            t_tt_nt: mr._getItemValue(r, 5)
          }};
        }}
      }}
      return {{ found: false, row_count: mr._rows.length, first_so_ct: mr._getItemValue(1, 3) }};
    }}""")
    log("verify browse", verify)

    passed = verify.get("found") and str(verify.get("so_ct", "")).strip() == str(so_ct or "").strip()
    log("KẾT LUẬN", {
        "pass": passed,
        "so_ct": so_ct,
        "ma_kh": ma_kh,
        "detail_line": filled[0] if filled else None,
        "note": "dvt auto; không Insert; save_with_retry parse popup → fix → Lưu lại"
    })
    p.close()


if __name__ == "__main__":
    main()
