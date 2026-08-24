"""E2E invt: lookup click chọn mã trong popup (dvt/loai_vt/tk_vt) → Lưu → lọc → Sửa."""
import json
import sys
import time
from datetime import datetime

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"
DE = "ctl00_FastBusiness_MainReport_dirExtender"
SUFFIX = datetime.now().strftime("%H%M%S")
MA_VT = f"ZTEST{SUFFIX}"
TEN_VT = f"VT test Chrome CDP {SUFFIX}"
TEN_VT_EDIT = f"VT test EDIT {SUFFIX}"

HELPER_JS = """
() => {
  window.__fbo = {
    dismissMessage: function() {
      var btns = document.querySelectorAll('input[type="button"], button');
      for (var b of btns) {
        if ((b.value || '').trim() === 'Nhận') { b.click(); return { ok: true }; }
      }
      return { ok: false };
    },
    clickTab: function(text) {
      var as = document.querySelectorAll('[id*="dirExtender_Tabs"] a');
      for (var a of as) {
        if ((a.innerText||'').trim() === text) { a.click(); return true; }
      }
      return false;
    },
    fillText: function(name, val) {
      var f = $find('""" + DE + """');
      f.setItemValue(name, val);
      return f.getItemValue(name);
    },
    getVal: function(name) {
      return $find('""" + DE + """').getItemValue(name);
    },
    lookupOpen: function(fieldName) {
      var inp = document.querySelector('[id*="dirExtender_form_' + fieldName + '"]');
      if (!inp) return { ok: false, err: 'no input' };
      var img = (inp.closest('td') || inp.parentElement).querySelector('img.CellImgLookup');
      if (!img) return { ok: false, err: 'no lookup img' };
      img.click();
      return { ok: true, field: fieldName };
    },
    lookupPickInPopup: function(code) {
      // Chỉ tìm trong popup lookup dirExtender (modal trên cùng)
      var popups = document.querySelectorAll('[id*="FormLookup"], [id*="dirExtender"][id*="Lookup"]');
      var root = null;
      for (var i = popups.length - 1; i >= 0; i--) {
        var el = popups[i];
        if (el.offsetParent !== null || el.style.display !== 'none') { root = el; break; }
      }
      // Fallback: vùng có title Danh mục
      if (!root) {
        var divs = document.querySelectorAll('div');
        for (var d of divs) {
          var t = d.innerText || '';
          if (t.indexOf('Danh mục') >= 0 && t.indexOf('Tìm nhanh') >= 0 && d.offsetHeight > 100) {
            root = d; break;
          }
        }
      }
      var scope = root || document.body;
      var links = scope.querySelectorAll('a');
      for (var a of links) {
        var txt = (a.innerText || '').trim();
        if (txt === code) { a.click(); return { picked: code, scope: root ? root.id : 'body' }; }
      }
      // td first column
      var rows = scope.querySelectorAll('tr');
      for (var tr of rows) {
        var td = tr.querySelector('td');
        if (td && (td.innerText||'').trim() === code) {
          var link = td.querySelector('a') || td;
          link.click();
          return { picked: code, via: 'td' };
        }
      }
      return { picked: null, code: code };
    },
    lookupClose: function() {
      var btns = document.querySelectorAll('input, button, a');
      for (var b of btns) {
        var t = (b.value || b.innerText || '').trim();
        if (t === 'Đóng' && b.id && b.id.indexOf('Lookup') >= 0) { b.click(); return true; }
      }
      for (var b of btns) {
        if ((b.innerText||'').trim() === 'Đóng' && b.title === 'Close') { b.click(); return true; }
      }
      return false;
    },
    isLookupOpen: function() {
      return !!document.querySelector('.ModalBackground[id*="Lookup"]');
    },
    readGrid: function(n) {
      var mr = $find('""" + MR + """');
      if (!mr._rows || !mr._rows.length) return { row_count: 0, rows: [] };
      n = n || 10;
      var rows = [];
      for (var r = 1; r <= Math.min(mr._rows.length, n); r++) {
        var o = {};
        for (var c = 0; c < Math.min(6, mr._fields.length); c++) {
          o[mr._fields[c].Name] = mr._getItemValue(r, c + 1);
        }
        rows.push(o);
      }
      return { row_count: mr._rows.length, rows: rows };
    },
    filterMaVt: function(code) {
      var inp = document.querySelector('#ctl00_FastBusiness_MainReport_gridHeader input[type="text"]');
      if (inp) {
        inp.value = code;
        inp.dispatchEvent(new Event('change', { bubbles: true }));
      }
      $find('""" + MR + """').search();
    },
    selectRow: function(code) {
      var mr = $find('""" + MR + """');
      for (var r = 1; r <= mr._rows.length; r++) {
        if (String(mr._getItemValue(r, 1)).trim() === code) {
          var tr = document.getElementById('ctl00_FastBusiness_MainReport_gridTable').querySelectorAll('tr')[r-1];
          if (tr) tr.click();
          return r;
        }
      }
      return null;
    }
  };
  return true;
}
"""


def ev(p, js, arg=None):
    return p.evaluate(js, arg) if arg is not None else p.evaluate(js)


def lookup_select(p, field, code, tab=None):
    if tab:
        ev(p, "(t) => window.__fbo.clickTab(t)", tab)
        time.sleep(1)
    ev(p, "(f) => window.__fbo.lookupOpen(f)", field)
    time.sleep(2)
    pick = ev(p, "(c) => window.__fbo.lookupPickInPopup(c)", code)
    time.sleep(1.5)
    val = ev(p, "(f) => window.__fbo.getVal(f)", field)
    # đóng popup nếu còn
    if ev(p, "() => window.__fbo.isLookupOpen()"):
        ev(p, "() => window.__fbo.lookupClose()")
        time.sleep(1)
    return {"field": field, "code": code, "pick": pick, "value_after": val}


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    log("0", {"ma_vt": MA_VT, "ten_vt": TEN_VT})
    p.goto(URL, timeout=90000)
    time.sleep(8)
    ev(p, HELPER_JS)

    ev(p, f"() => {{ $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }}); }}")
    time.sleep(3)

    log("1 ma_vt/ten_vt", {
        "ma_vt": ev(p, "(a) => window.__fbo.fillText('ma_vt', a)", MA_VT),
        "ten_vt": ev(p, "(a) => window.__fbo.fillText('ten_vt', a)", TEN_VT),
    })

    # Lookup từng field — click mã trong popup
    r_dvt = lookup_select(p, "dvt", "Cái", "Thông tin chính")
    log("2 lookup dvt → Cái", r_dvt)

    r_loai = lookup_select(p, "loai_vt", "08", "Thông tin chính")
    log("3 lookup loai_vt → 08", r_loai)

    r_tk = lookup_select(p, "tk_vt", "51", "Tài khoản")
    log("4 lookup tk_vt → 51 (tab Tài khoản)", r_tk)

    log("5 verify fields", {
        "dvt": ev(p, "() => window.__fbo.getVal('dvt')"),
        "loai_vt": ev(p, "() => window.__fbo.getVal('loai_vt')"),
        "tk_vt": ev(p, "() => window.__fbo.getVal('tk_vt')"),
    })

    # Lưu
    ev(p, "() => window.__fbo.lookupClose()")
    time.sleep(0.5)
    p.locator("#ctl00_FastBusiness_MainReport_dirExtender_updateDlgOk").click(force=True)
    time.sleep(4)
    dismiss = ev(p, "() => window.__fbo.dismissMessage()")
    log("6 Lưu", dismiss)
    time.sleep(3)

    status = ev(p, """() => {
      var open = !!document.querySelector('[id*="dirExtender_updateDlgOk"]');
      var body = document.body.innerText;
      return {
        dialog_still: open && document.getElementById('ctl00_FastBusiness_MainReport_dirExtender_updateDlgOk').offsetParent !== null,
        error: /chưa nhập|không hợp lệ|trùng|lỗi/i.test(body)
      };
    }""")
    log("7 sau Lưu", status)

    if status.get("dialog_still"):
        ev(p, "() => window.__fbo.dismissMessage()")
        log("FAIL", "Form vẫn mở — lookup chưa đủ")
        p.close()
        return

    ev(p, f"() => {{ $find('{MR}').search(); }}")
    time.sleep(3)
    ev(p, "(m) => window.__fbo.filterMaVt(m)", MA_VT)
    time.sleep(5)
    grid = ev(p, "() => window.__fbo.readGrid(10)")
    log("8 lọc grid", grid)

    found = any(r.get("ma_vt","").strip() == MA_VT for r in grid.get("rows",[]))
    if not found:
        log("KẾT LUẬN", {"pass": False, "reason": "không thấy sau lọc"})
        p.close()
        return

    ev(p, "(m) => window.__fbo.selectRow(m)", MA_VT)
    time.sleep(1)
    ev(p, f"() => {{ $find('{MR}').executeCommand({{ commandName: 'Edit', commandArgument: '0' }}); }}")
    time.sleep(3)
    new_name = ev(p, "(v) => window.__fbo.fillText('ten_vt', v)", TEN_VT_EDIT)
    log("9 Sửa", {"ten_vt": new_name})
    p.locator("#ctl00_FastBusiness_MainReport_dirExtender_updateDlgOk").click(force=True)
    time.sleep(5)
    ev(p, "() => window.__fbo.dismissMessage()")

    ev(p, "(m) => window.__fbo.filterMaVt(m)", MA_VT)
    time.sleep(4)
    final = ev(p, "() => window.__fbo.readGrid(5)")
    edited = any(r.get("ten_vt","").strip() == TEN_VT_EDIT for r in final.get("rows",[]))
    log("10 sau Sửa", final)
    log("KẾT LUẬN", {"pass": found and edited, "ma_vt": MA_VT, "created": found, "edited": edited})

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
