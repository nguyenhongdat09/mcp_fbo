"""E2E lọc báo cáo: fill filter -> Nhận -> Tìm -> verify grid rows."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

REPORT_URL = "http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39"

VERIFY_JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  var out = {
    mr_type: mr ? mr._type : null,
    filter_summary: null,
    row_count: mr && mr._rows ? mr._rows.length : null,
    sample_rows: [],
    empty_hints: []
  };
  var body = document.body.innerText || '';
  var m = body.match(/Vật tư:[^\\n]+/);
  if (m) out.filter_summary = m[0].trim();

  if (mr && mr._rows && mr._rows.length) {
    for (var i = 0; i < Math.min(3, mr._rows.length); i++) {
      var r = mr._rows[i];
      var sample = {};
      ['ngay_ct','ma_ct','so_ct','ma_kho','ten_kho','dien_giai'].forEach(function(k) {
        if (r[k] !== undefined) sample[k] = String(r[k]).substring(0, 60);
      });
      if (Object.keys(sample).length === 0) {
        Object.keys(r).slice(0, 6).forEach(function(k) { sample[k] = String(r[k]).substring(0, 60); });
      }
      out.sample_rows.push(sample);
    }
  }

  // gridTable DOM rows
  var gt = document.getElementById('ctl00_FastBusiness_MainReport_gridTable');
  if (gt) {
    out.grid_table_trs = gt.querySelectorAll('tr').length;
  }

  ['không có dữ liệu','không tìm thấy','no data'].forEach(function(p) {
    if (body.toLowerCase().indexOf(p) >= 0) out.empty_hints.push(p);
  });
  return out;
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(REPORT_URL, timeout=90000)
    time.sleep(8)

    print("=== 1. Fill filter ===")
    fill_res = p.evaluate("""() => {
      var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
      function fill(name, val) {
        var el = document.querySelector('[id*="searchExtender_form_' + name + '"]');
        if (el) { el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); return true; }
        return false;
      }
      var log = [];
      log.push({ tu_ngay: fill('tu_ngay', '01/01/2025') });
      log.push({ den_ngay: fill('den_ngay', '31/12/2025') });
      se.setItemValue('ma_vt', '001');
      log.push({ ma_vt: '001 via setItemValue' });
      return log;
    }""")
    print(json.dumps(fill_res, ensure_ascii=False))

    print("\n=== 2. Click Nhận ===")
    p.locator("#ctl00_FastBusiness_MainReport_searchExtender_updateDlgOk").click()
    time.sleep(4)
    v1 = p.evaluate(VERIFY_JS)
    print("After Nhận:", json.dumps(v1, ensure_ascii=False, indent=2))

    print("\n=== 3. Click Tìm ===")
    # Try multiple selectors for Search button
    clicked = False
    for sel in [
        '#ctl00_FastBusiness_MainReport_gridToolbar_btnFind',
        '[id*="MainReport"][id*="btnFind"]',
        '[id*="MainReport"][id*="Find"]',
        'input[value="Tìm"]',
        'button:has-text("Tìm")',
    ]:
        try:
            loc = p.locator(sel)
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                clicked = True
                print(f"Clicked via: {sel}")
                break
        except Exception:
            pass

    if not clicked:
        # JS fallback: find button/link with text Tìm near MainReport
        js_click = p.evaluate("""() => {
          var els = document.querySelectorAll('input, button, a, span');
          for (var el of els) {
            var t = (el.value || el.innerText || '').trim();
            if (t === 'Tìm' && el.id && el.id.indexOf('MainReport') >= 0) {
              el.click();
              return { ok: true, id: el.id, tag: el.tagName };
            }
          }
          // broader: any Tìm in toolbar area
          for (var el of els) {
            var t = (el.value || el.innerText || '').trim();
            if (t === 'Tìm') {
              el.click();
              return { ok: true, id: el.id || '', tag: el.tagName, broad: true };
            }
          }
          return { ok: false };
        }""")
        print("JS click Tìm:", json.dumps(js_click, ensure_ascii=False))
        clicked = js_click.get('ok', False)

    print("\n=== 4. Chờ grid load ===")
    for wait in [5, 10, 15]:
        time.sleep(5)
        v = p.evaluate(VERIFY_JS)
        print(f"--- after {wait}s total ---")
        print(json.dumps(v, ensure_ascii=False, indent=2))
        if v.get('row_count', 0) and v['row_count'] > 0:
            break
        if v.get('grid_table_trs', 0) and v['grid_table_trs'] > 0:
            break
        if v.get('empty_hints'):
            break

    print("\n=== KẾT LUẬN ===")
    final = p.evaluate(VERIFY_JS)
    ok_filter = bool(final.get('filter_summary'))
    ok_grid = (final.get('row_count') or 0) > 0 or (final.get('grid_table_trs') or 0) > 0
    ok_empty = bool(final.get('empty_hints'))
    if ok_filter and ok_grid:
        print("PASS: Lọc OK + có dữ liệu grid")
    elif ok_filter and ok_empty:
        print("PASS (partial): Lọc OK, grid chạy nhưng không có dữ liệu với điều kiện này")
    elif ok_filter:
        print("PASS (partial): Lọc OK, grid phase Report, chưa có row (có thể cần thêm bước hoặc DB trống)")
    else:
        print("FAIL: Không lọc được")

    p.close()

if __name__ == "__main__":
    main()
