"""Probe _getItemValue trên grid danh mục (có data)."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

CATEGORY_URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"

PROBE_JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  if (!mr) return { error: 'no MainReport' };

  var out = {
    mr_type: mr._type,
    row_count: mr._rows ? mr._rows.length : null,
    field_names: mr._fields ? mr._fields.slice(0, 8).map(f => f.Name) : [],
    getItemValue_methods: [],
    sample_via_getItemValue: [],
    sample_via__getItemValue: [],
  };

  // Liệt kê method liên quan getItemValue
  for (var k in mr) {
    if (typeof mr[k] === 'function' && /getItemValue|getRow|getCell|getValue/i.test(k)) {
      out.getItemValue_methods.push(k);
    }
  }

  var n = mr._rows ? mr._rows.length : 0;
  if (n === 0) return out;

  // Thử _getItemValue(rowIndex, fieldName) và getItemValue
  var fields = mr._fields ? mr._fields.slice(0, 5).map(f => f.Name) : ['ma_vt', 'ten_vt'];
  for (var i = 0; i < Math.min(3, n); i++) {
    var row = {};
    for (var fn of fields) {
      try {
        if (typeof mr._getItemValue === 'function') {
          row[fn] = mr._getItemValue(i, fn);
        }
      } catch (e) { row['_err_' + fn] = String(e); }
    }
    out.sample_via__getItemValue.push({ rowIndex: i, data: row });
  }

  // Thử getItemValue(row, field) variants
  if (typeof mr.getItemValue === 'function') {
    try {
      var r0 = {};
      for (var fn2 of fields) {
        try { r0[fn2] = mr.getItemValue(fn2, 0); } catch (e1) {
          try { r0[fn2] = mr.getItemValue(0, fn2); } catch (e2) {
            r0[fn2] = 'err:' + String(e2);
          }
        }
      }
      out.sample_via_getItemValue.push(r0);
    } catch (e) { out.getItemValue_error = String(e); }
  }

  return out;
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(CATEGORY_URL, timeout=90000)
    time.sleep(8)
    # Click Tìm nếu cần load grid
    try:
        p.locator("#ctl00_FastBusiness_MainReport_ToolbarButton_Search").click(timeout=5000)
        time.sleep(5)
    except Exception:
        pass
    result = p.evaluate(PROBE_JS)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    p.close()

if __name__ == "__main__":
    main()
