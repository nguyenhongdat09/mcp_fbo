"""Test lookup dvt → chọn 'Khối' qua FormLookupdvt QuickFind."""
import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"
DE = "ctl00_FastBusiness_MainReport_dirExtender"
LOOKUP = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt"
QUICK_FIND = "ctl00_FastBusiness_MainReport_dirExtender_FormLookupdvt_Button_Lookup_QuickFind"
TARGET = "Khối"


def log(title, data):
    print(f"\n=== {title} ===")
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    p.goto(URL, timeout=90000)
    time.sleep(8)

    p.evaluate(f"() => {{ $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }}); }}")
    time.sleep(3)

    # Mở lookup dvt
    p.evaluate("""() => {
      var inp = document.querySelector('[id*="dirExtender_form_dvt"]');
      inp.closest('td').querySelector('img.CellImgLookup').click();
    }""")
    time.sleep(2)

    inspect = p.evaluate(f"""() => {{
      var lk = $find('{LOOKUP}');
      return {{
        found: !!lk,
        id: lk ? lk.get_id() : null,
        columns: lk && lk._fields ? lk._fields.map(f => f.Name) : []
      }};
    }}""")
    log("1. FormLookupdvt", inspect)

    # QuickFind "Khối"
    qf_res = p.evaluate(f"""(code) => {{
      var qf = document.getElementById('{QUICK_FIND}');
      if (!qf) return {{ error: 'no QuickFind' }};
      qf.focus();
      qf.value = code;
      qf.dispatchEvent(new Event('input', {{ bubbles: true }}));
      qf.dispatchEvent(new Event('change', {{ bubbles: true }}));
      qf.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
      qf.dispatchEvent(new KeyboardEvent('keypress', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
      qf.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
      // gọi API nếu có
      var lk = $find('{LOOKUP}');
      if (lk && typeof lk.quickFind === 'function') {{
        try {{ lk.quickFind(); }} catch (e) {{}}
      }}
      return {{ typed: code, qf_id: qf.id }};
    }}""", TARGET)
    log("2. QuickFind", qf_res)
    time.sleep(2.5)

    # Liệt kê mã hiện trong popup sau tìm
    codes = p.evaluate("""() => {
      var codes = [];
      document.querySelectorAll('[id*="FormLookupdvt"] a').forEach(function(a) {
        var t = (a.innerText || '').trim();
        if (t && t.length <= 30 && t !== 'Đóng' && t.indexOf('Trang') < 0 && t.indexOf('Trước') < 0 && t.indexOf('Tiếp') < 0)
          codes.push(t);
      });
      return [...new Set(codes)].slice(0, 15);
    }""")
    log("3. Mã trong popup sau QuickFind", codes)

    # Click "Khối"
    pick = p.evaluate("""(code) => {
      var links = document.querySelectorAll('[id*="FormLookupdvt"] a');
      for (var a of links) {
        if ((a.innerText || '').trim() === code) {
          a.click();
          return { picked: code, method: 'exact_link' };
        }
      }
      // fallback partial
      for (var a of links) {
        var t = (a.innerText || '').trim();
        if (t.indexOf(code) >= 0) {
          a.click();
          return { picked: t, method: 'partial' };
        }
      }
      return { picked: null, available: Array.from(links).map(a => (a.innerText||'').trim()).filter(Boolean).slice(0, 15) };
    }""", TARGET)
    log("4. Click chọn", pick)
    time.sleep(1.5)

    dvt = p.evaluate(f"() => $find('{DE}').getItemValue('dvt')")
    ten_dvt = p.evaluate(f"""() => {{
      try {{ return $find('{DE}').getItemValue('ten_dvt'); }} catch(e) {{ return null; }}
    }}""")
    log("5. Kết quả gán", {"dvt": dvt, "ten_dvt": ten_dvt, "pass": dvt == TARGET or (dvt and TARGET in str(dvt))})

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
