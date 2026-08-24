"""Thử row/col 0-based vs 1-based cho _getItemValue."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

JS = """
() => {
  var mr = $find('ctl00_FastBusiness_MainReport');
  var attempts = [];
  var combos = [[0,1],[1,1],[0,0],[1,0],[1,2],[2,1]];
  for (var combo of combos) {
    try {
      var v = mr._getItemValue(combo[0], combo[1]);
      attempts.push({ row: combo[0], col: combo[1], ok: true, value: String(v).substring(0, 60) });
    } catch (e) {
      attempts.push({ row: combo[0], col: combo[1], ok: false, error: String(e).substring(0, 100) });
    }
  }
  // Thử truyền cell DOM
  var gt = document.getElementById('ctl00_FastBusiness_MainReport_gridTable');
  var cell = gt && gt.querySelector('tr td');
  if (cell) {
    try {
      attempts.push({ via: 'cell_only', ok: true, value: String(mr._getItemValue(cell)).substring(0, 60) });
    } catch (e) {
      attempts.push({ via: 'cell_only', ok: false, error: String(e).substring(0, 100) });
    }
  }
  return { row_count: mr._rows.length, grid_trs: gt ? gt.querySelectorAll('tr').length : 0, attempts: attempts };
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
