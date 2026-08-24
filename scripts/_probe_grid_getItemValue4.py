"""Verify _getItemValue(rowIndex, colIndex) — colIndex 1-based."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  var rows = [];
  for (var i = 0; i < 3; i++) {
    var row = {};
    for (var c = 0; c < mr._fields.length; c++) {
      row[mr._fields[c].Name] = mr._getItemValue(i, c + 1);
    }
    rows.push(row);
  }
  return { method: '_getItemValue(rowIndex, colIndex_1based)', rows: rows };
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto("http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06", timeout=90000)
    time.sleep(8)
    try:
        p.locator("#ctl00_FastBusiness_MainReport_ToolbarButton_Search").click(timeout=5000)
        time.sleep(5)
    except Exception:
        pass
    print(json.dumps(p.evaluate(JS), ensure_ascii=False, indent=2))
    p.close()

if __name__ == "__main__":
    main()
