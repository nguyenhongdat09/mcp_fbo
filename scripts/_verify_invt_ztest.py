"""Verify ZTEST records + test applyFilter / Enter sau reload."""
import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def filter_ma_vt(p, code):
    return p.evaluate(
        """(code) => {
      var mr = $find('ctl00_FastBusiness_MainReport');
      var inp = document.getElementById('ctl00_FastBusiness_MainReport_FilterPanelTextma_vt');
      if (!inp) return { error: 'no filter input' };
      inp.focus();
      inp.value = code;
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      inp.dispatchEvent(new Event('change', { bubbles: true }));
      // Enter như user thao tác
      var evDown = new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true });
      inp.dispatchEvent(evDown);
      inp.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', keyCode: 13, which: 13, bubbles: true }));
      inp.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', keyCode: 13, which: 13, bubbles: true }));
      // fallback API
      try { if (typeof mr.applyFilter === 'function') mr.applyFilter(); } catch (e) {}
      try { if (typeof mr.search === 'function') mr.search(); } catch (e) {}
      return { ok: true, value: inp.value };
    }""",
        code,
    )


def read_grid(p, n=10):
    return p.evaluate(
        """(n) => {
      var mr = $find('ctl00_FastBusiness_MainReport');
      if (!mr._rows || !mr._rows.length) return { row_count: 0, rows: [] };
      var rows = [];
      for (var r = 1; r <= Math.min(mr._rows.length, n); r++) {
        rows.push({
          ma_vt: mr._getItemValue(r, 1),
          ten_vt: mr._getItemValue(r, 2),
          dvt: mr._getItemValue(r, 3)
        });
      }
      return { row_count: mr._rows.length, rows: rows };
    }""",
        n,
    )


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(URL, timeout=90000)
    time.sleep(8)

    # Verify các mã đã tạo trước
    for code in ["ZTEST232722", "ZTEST232529", "ZTEST"]:
        fr = filter_ma_vt(p, code)
        time.sleep(3)
        grid = read_grid(p, 10)
        log(f"Lọc '{code}'", {"filter": fr, "grid": grid})

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
