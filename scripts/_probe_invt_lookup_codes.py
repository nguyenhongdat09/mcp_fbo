"""Probe mã trong lookup dvt / loai_vt."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

def open_lookup(p, field):
    return p.evaluate("""(field) => {
      var inp = document.querySelector('[id*="dirExtender_form_' + field + '"]');
      var td = inp.closest('td');
      td.querySelector('img.CellImgLookup').click();
      return { ok: true };
    }""", field)

def list_codes(p):
    time.sleep(2)
    return p.evaluate("""() => {
      var codes = [];
      document.querySelectorAll('a, td').forEach(function(el) {
        var t = (el.innerText||'').trim();
        if (t && t.length <= 15 && /^[A-Za-z0-9\\-\\.]+$/.test(t)) codes.push(t);
      });
      return [...new Set(codes)].slice(0, 20);
    }""")

def close_lookup(p):
    p.evaluate("""() => {
      var btns = document.querySelectorAll('input, button, a');
      for (var b of btns) {
        var t = (b.value || b.innerText || '').trim();
        if (t === 'Đóng' || t === 'Close') { b.click(); return true; }
      }
      // click modal background to close?
      var bg = document.querySelector('.ModalBackground');
      if (bg) { bg.click(); return 'bg'; }
      return false;
    }""")
    time.sleep(1)

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto("http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06", timeout=90000)
    time.sleep(8)
    p.evaluate("() => { $find('ctl00_FastBusiness_MainReport').executeCommand({ commandName: 'New', commandArgument: '0' }); }")
    time.sleep(3)

    for field in ["dvt", "loai_vt"]:
        open_lookup(p, field)
        codes = list_codes(p)
        print(f"\n{field} lookup codes:", json.dumps(codes, ensure_ascii=False))
        close_lookup(p)

    p.close()

if __name__ == "__main__":
    main()
