"""Inspect _getItemValue source + thử với DOM row."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"

PROBE_JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  var out = {
    fn_source: mr._getItemValue ? mr._getItemValue.toString().substring(0, 800) : null,
    grid_tr_count: 0,
    attempts: [],
    extracted: []
  };

  var gt = document.getElementById('ctl00_FastBusiness_MainReport_gridTable');
  if (gt) {
    var trs = gt.querySelectorAll('tr');
    out.grid_tr_count = trs.length;

    for (var i = 0; i < Math.min(3, trs.length); i++) {
      var tr = trs[i];
      var rowData = {};
      mr._fields.slice(0, 6).forEach(function(f) {
        try {
          rowData[f.Name] = mr._getItemValue(tr, f.Name);
        } catch (e1) {
          try { rowData[f.Name] = mr._getItemValue(tr, f); } catch (e2) {
            rowData[f.Name] = String(e2).substring(0, 80);
          }
        }
      });
      out.extracted.push(rowData);
    }
  }

  // Thử map _rows index -> field name từ _fields order
  if (mr._rows && mr._rows[0] && Array.isArray(mr._rows[0])) {
    var arr = mr._rows[0];
    var mapped = {};
    mr._fields.forEach(function(f, idx) {
      mapped[f.Name] = arr[idx];
    });
    out.mapped_from_rows_array = mapped;
  }

  return out;
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(URL, timeout=90000)
    time.sleep(8)
    try:
        p.locator("#ctl00_FastBusiness_MainReport_ToolbarButton_Search").click(timeout=5000)
        time.sleep(5)
    except Exception:
        pass
    print(json.dumps(p.evaluate(PROBE_JS), ensure_ascii=False, indent=2))
    p.close()

if __name__ == "__main__":
    main()
