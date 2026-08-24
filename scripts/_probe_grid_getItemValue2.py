"""Probe chữ ký _getItemValue / _getRow trên grid."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"

PROBE_JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  var out = { row_count: mr._rows.length, attempts: [] };

  function tryCall(label, fn) {
    try {
      var v = fn();
      out.attempts.push({ label: label, ok: true, result: typeof v === 'object' ? JSON.stringify(v).substring(0, 300) : String(v).substring(0, 200) });
    } catch (e) {
      out.attempts.push({ label: label, ok: false, error: String(e) });
    }
  }

  var row0 = mr._rows[0];
  out.row0_keys = row0 ? Object.keys(row0).slice(0, 15) : [];
  out.row0_sample = row0 ? JSON.stringify(row0).substring(0, 400) : null;

  // _getRow variants
  tryCall('_getRow(0)', () => mr._getRow(0));
  tryCall('_getRow(row0)', () => mr._getRow(row0));

  // _getItemValue variants
  tryCall('_getItemValue(row0, ma_vt)', () => mr._getItemValue(row0, 'ma_vt'));
  tryCall('_getItemValue(0, ma_vt)', () => mr._getItemValue(0, 'ma_vt'));
  tryCall('_getItemValue(ma_vt, 0)', () => mr._getItemValue('ma_vt', 0));
  tryCall('_getItemValue(row0, fieldObj)', () => {
    var f = mr._fields.find(x => x.Name === 'ma_vt');
    return mr._getItemValue(row0, f);
  });

  // Dump all rows via correct pattern if found
  var rows = [];
  for (var i = 0; i < Math.min(3, mr._rows.length); i++) {
    var r = mr._rows[i];
    var rowData = {};
    mr._fields.slice(0, 6).forEach(function(f) {
      try { rowData[f.Name] = mr._getItemValue(r, f.Name); } catch (e1) {
        try { rowData[f.Name] = mr._getItemValue(r, f); } catch (e2) {
          rowData[f.Name] = row0 && row0[f.Name] !== undefined ? row0[f.Name] : null;
        }
      }
    });
    rows.push(rowData);
  }
  out.extracted_rows = rows;

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
