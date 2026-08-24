"""Probe grid data sau lọc báo cáo — đọc qua MainReport component + DOM."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

REPORT_URL = "http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39"

PROBE_JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
  var out = {
    mr_type: mr ? mr._type : null,
    se_type: se ? se._type : null,
    filter_summary: null,
    row_count: null,
    sample_rows: [],
    grid_props: [],
    dom_tables: []
  };

  // Filter summary text on page
  var body = document.body.innerText || '';
  var m = body.match(/Vật tư:[^\\n]+/);
  if (m) out.filter_summary = m[0].trim();

  if (mr) {
    // Common FBO grid APIs
    var apis = ['getRowCount', 'getRows', 'getData', 'getRecordCount', '_rows', '_dataSource', 'getGridData'];
    for (var api of apis) {
      if (typeof mr[api] === 'function') {
        try {
          var v = mr[api]();
          out.grid_props.push({ api: api, type: typeof v, isArray: Array.isArray(v), len: Array.isArray(v) ? v.length : null, sample: Array.isArray(v) && v.length ? JSON.stringify(v[0]).substring(0, 200) : String(v).substring(0, 200) });
        } catch (e) {
          out.grid_props.push({ api: api, error: String(e) });
        }
      } else if (mr[api] !== undefined) {
        var val = mr[api];
        out.grid_props.push({ prop: api, type: typeof val, isArray: Array.isArray(val), len: Array.isArray(val) ? val.length : null });
      }
    }

    // _fields columns
    if (mr._fields) {
      out.columns = mr._fields.slice(0, 6).map(f => f.Name || f.HeaderText);
    }

    // Try getRows pattern
    if (typeof mr.getRows === 'function') {
      try {
        var rows = mr.getRows();
        out.row_count = rows ? rows.length : 0;
        if (rows && rows.length) {
          for (var i = 0; i < Math.min(3, rows.length); i++) {
            var r = rows[i];
            if (typeof r === 'object') {
              var keys = Object.keys(r).slice(0, 8);
              var sample = {};
              keys.forEach(k => sample[k] = String(r[k]).substring(0, 50));
              out.sample_rows.push(sample);
            } else {
              out.sample_rows.push(String(r).substring(0, 200));
            }
          }
        }
      } catch (e) { out.getRows_error = String(e); }
    }
  }

  // DOM: all MainReport tables
  document.querySelectorAll('table[id*="MainReport"]').forEach(function(t) {
    var trs = t.querySelectorAll('tr');
    var dataRows = [];
    trs.forEach(function(tr) {
      var tds = tr.querySelectorAll('td');
      if (tds.length >= 3) {
        var txt = Array.from(tds).map(x => (x.innerText||'').trim()).filter(x => x);
        if (txt.length >= 2) dataRows.push(txt.slice(0, 6));
      }
    });
    out.dom_tables.push({ id: t.id, tr_count: trs.length, data_rows: dataRows.slice(0, 5) });
  });

  // Empty / no data messages
  var emptyPatterns = ['không có dữ liệu', 'không tìm thấy', 'no data', 'Không có bản ghi'];
  out.empty_hints = emptyPatterns.filter(p => body.toLowerCase().indexOf(p.toLowerCase()) >= 0);

  return out;
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(REPORT_URL, timeout=90000)
    time.sleep(8)

    # fill + nhan
    p.evaluate("""() => {
      var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
      function fill(name, val) {
        var el = document.querySelector('[id*="searchExtender_form_' + name + '"]');
        if (el) { el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); }
      }
      fill('tu_ngay', '01/01/2025');
      fill('den_ngay', '31/12/2025');
      se.setItemValue('ma_vt', '001');
    }""")
    p.locator("#ctl00_FastBusiness_MainReport_searchExtender_updateDlgOk").click()
    time.sleep(10)

    result = p.evaluate(PROBE_JS)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    p.close()

if __name__ == "__main__":
    main()
