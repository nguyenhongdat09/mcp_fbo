"""E2E test lọc báo cáo rpt_bkctsstt — fill filter + Nhận + verify grid."""

import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

REPORT_URL = "http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39"

# Probe cách fill từng field
PROBE_INPUTS_JS = """
() => {
  var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
  if (!se || !se._fields) return { error: 'no searchExtender fields' };
  var names = ['tu_ngay', 'den_ngay', 'ma_vt'];
  var out = [];
  for (var n of names) {
    var sel = [
      '[id*="searchExtender"][id*="' + n + '"]',
      '[id*="dirExtender_form_' + n + '"]',
      '[id*="_' + n + '"]',
      'input[name="' + n + '"]'
    ];
    for (var s of sel) {
      var el = document.querySelector(s);
      if (el) {
        out.push({ name: n, selector: s, id: el.id, tag: el.tagName, type: el.type, value: el.value });
        break;
      }
    }
    if (!out.find(x => x.name === n)) out.push({ name: n, found: false });
  }
  return { fields: se._fields.map(f => ({ name: f.Name, allowNulls: f.AllowNulls, type: f.Type })), inputs: out };
}
"""

FILL_AND_NHAN_JS = """
(args) => {
  var tu = args.tu_ngay;
  var den = args.den_ngay;
  var ma_vt = args.ma_vt;
  var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
  var log = [];

  function fillDom(name, val) {
    var el = document.querySelector('[id*="searchExtender"][id*="' + name + '"]')
      || document.querySelector('[id*="' + name + '"]');
    if (!el) return { name: name, ok: false, error: 'dom not found' };
    el.focus();
    el.value = val;
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
    if (el.onchange) try { el.onchange(); } catch (e) {}
    return { name: name, ok: true, via: 'dom', id: el.id, value: el.value };
  }

  function fillSetItem(name, val) {
    try {
      if (se && typeof se.setItemValue === 'function') {
        se.setItemValue(name, val);
        var v = se.getItemValue ? se.getItemValue(name) : null;
        return { name: name, ok: true, via: 'setItemValue', value: v };
      }
    } catch (e) {
      return { name: name, ok: false, via: 'setItemValue', error: String(e) };
    }
    return { name: name, ok: false, error: 'no setItemValue' };
  }

  // DateTime: thử nhiều format
  for (var fmt of [tu, den]) {
    /* placeholder */
  }

  // tu_ngay, den_ngay — DOM trước (FBO thường dd/MM/yyyy)
  log.push(fillDom('tu_ngay', tu));
  log.push(fillDom('den_ngay', den));

  // ma_vt — setItemValue rồi fallback DOM
  var mv = fillSetItem('ma_vt', ma_vt);
  if (!mv.ok) mv = fillDom('ma_vt', ma_vt);
  log.push(mv);

  return { fill_log: log, se_type: se ? se._type : null };
}
"""

VERIFY_GRID_JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  if (!mr) return { error: 'no MainReport' };

  var result = {
    mr_type: mr._type,
    field_count: mr._fields ? mr._fields.length : 0,
    column_headers: mr._fields ? mr._fields.slice(0, 8).map(f => f.HeaderText || f.Name) : [],
  };

  // Đếm dòng grid trong DOM (pattern FBO grid)
  var rows = document.querySelectorAll(
    'table[id*="MainReport"] tr.GridRow, table[id*="MainReport"] tr[class*="Grid"], ' +
    '.GridRow, tr[id*="GridRow"], div[id*="MainReport"] table tr'
  );
  result.dom_row_candidates = rows.length;

  // Text báo lỗi / validation
  var alerts = [];
  document.querySelectorAll('.Error, .error, [class*="Error"], .MessageBox, #message').forEach(function (el) {
    var t = (el.innerText || '').trim();
    if (t && t.length < 300) alerts.push(t);
  });
  result.alerts = alerts.slice(0, 5);

  // Modal filter còn mở không
  result.filter_dialog_visible = !!document.querySelector('[id*="updateDlg"]:not([style*="display: none"])');

  return result;
}
"""


def main():
    cfg = load_chrome_debug_config()
    session = ChromeSession.get_instance()
    session.disconnect()
    page = session.connect(cfg["cdp_url"]).contexts[0].new_page()

    print("=== 1. Mở báo cáo ===")
    page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(8)

    probe = page.evaluate(PROBE_INPUTS_JS)
    print(json.dumps(probe, ensure_ascii=False, indent=2))

    # Lấy format ngày từ input hiện tại nếu có
    sample_dates = page.evaluate(
        """() => {
      var tu = document.querySelector('[id*="tu_ngay"]');
      var den = document.querySelector('[id*="den_ngay"]');
      return { tu_default: tu ? tu.value : '', den_default: den ? den.value : '' };
    }"""
    )
    print("Default dates on form:", sample_dates)

    # Dùng ngày default nếu có, không thì thử dd/MM/yyyy
    tu_ngay = sample_dates.get("tu_default") or "01/01/2025"
    den_ngay = sample_dates.get("den_default") or "31/12/2025"
    ma_vt = "001"

    print(f"\n=== 2. Fill filter: tu_ngay={tu_ngay}, den_ngay={den_ngay}, ma_vt={ma_vt} ===")
    fill_res = page.evaluate(
        FILL_AND_NHAN_JS,
        {"tu_ngay": tu_ngay, "den_ngay": den_ngay, "ma_vt": ma_vt},
    )
    print(json.dumps(fill_res, ensure_ascii=False, indent=2))

    print("\n=== 3. Click Nhận ===")
    nhan_sel = "#ctl00_FastBusiness_MainReport_searchExtender_updateDlgOk"
    try:
        page.locator(nhan_sel).click(timeout=8000)
        print("Clicked Nhận OK")
    except Exception as ex:
        print("Click Nhận failed:", ex)
        # fallback text
        try:
            page.get_by_role("button", name="Nhận").click(timeout=5000)
            print("Clicked Nhận via role")
        except Exception as ex2:
            print("Fallback failed:", ex2)

    print("\n=== 4. Chờ grid load ===")
    for wait in [3, 5, 8]:
        time.sleep(3 if wait == 3 else 5)
        grid = page.evaluate(VERIFY_GRID_JS)
        print(f"--- after {wait}s ---")
        print(json.dumps(grid, ensure_ascii=False, indent=2))
        if grid.get("mr_type") == "Report" and grid.get("field_count", 0) > 0:
            if grid.get("dom_row_candidates", 0) > 0 or not grid.get("filter_dialog_visible"):
                break

    # Thử đọc vài cell grid
    cells = page.evaluate(
        """() => {
      var trs = document.querySelectorAll('tr.GridRow, tr[class*="GridItem"], table tr');
      var rows = [];
      for (var i = 0; i < trs.length && rows.length < 5; i++) {
        var cells = trs[i].querySelectorAll('td');
        if (cells.length >= 3) {
          var texts = Array.from(cells).slice(0, 5).map(c => (c.innerText||'').trim().substring(0, 40));
          if (texts.some(t => t)) rows.push(texts);
        }
      }
      return rows.slice(0, 3);
    }"""
    )
    print("\n=== 5. Sample grid rows ===")
    print(json.dumps(cells, ensure_ascii=False, indent=2))

    page.close()
    session.disconnect()


if __name__ == "__main__":
    main()
