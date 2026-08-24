"""Discover toolbar buttons + MainReport retrieve APIs after filter."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/rpt_bkctsstt.aspx?id=15.02.39"

def run_filter(p, tu, den, ma_vt):
    p.evaluate("""(args) => {
      var se = $find('ctl00_FastBusiness_MainReport_searchExtender');
      function fill(name, val) {
        var el = document.querySelector('[id*="searchExtender_form_' + name + '"]');
        if (el) { el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); }
      }
      fill('tu_ngay', args.tu);
      fill('den_ngay', args.den);
      se.setItemValue('ma_vt', args.ma_vt);
    }""", {"tu": tu, "den": den, "ma_vt": ma_vt})
    p.locator("#ctl00_FastBusiness_MainReport_searchExtender_updateDlgOk").click()
    time.sleep(4)

DISCOVER_JS = """
() => {
  var out = { buttons: [], mr_methods: [] };
  document.querySelectorAll('input, button, a, img, span, div').forEach(function(el) {
    var t = (el.value || el.title || el.alt || el.innerText || '').trim();
    if (!t || t.length > 30) return;
    if (t.indexOf('Tìm') >= 0 || t.indexOf('Làm tươi') >= 0 || t.indexOf('Refresh') >= 0 || t.indexOf('Nhận') >= 0) {
      out.buttons.push({ text: t.substring(0, 20), id: el.id, tag: el.tagName, className: (el.className||'').substring(0, 60), visible: el.offsetParent !== null });
    }
  });
  var mr = $find('ctl00_FastBusiness_MainReport');
  if (mr) {
    for (var k in mr) {
      if (typeof mr[k] === 'function' && /retrieve|search|find|load|refresh|execute|run|query/i.test(k)) {
        out.mr_methods.push(k);
      }
    }
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

    defaults = p.evaluate("""() => {
      var tu = document.querySelector('[id*="searchExtender_form_tu_ngay"]');
      var den = document.querySelector('[id*="searchExtender_form_den_ngay"]');
      return { tu: tu ? tu.value : '', den: den ? den.value : '' };
    }""")
    print("Defaults:", defaults)

    run_filter(p, defaults.get('tu') or '01/01/2025', defaults.get('den') or '31/12/2025', '001')
    print("\n=== Buttons after Nhận ===")
    print(json.dumps(p.evaluate(DISCOVER_JS), ensure_ascii=False, indent=2))

    # Try retrieveData / executeQuery etc
    try_retrieve = p.evaluate("""() => {
      var mr = $find('ctl00_FastBusiness_MainReport');
      var log = [];
      var fns = ['retrieve', 'retrieveData', 'execute', 'executeQuery', 'loadData', 'refresh', 'doSearch', 'search'];
      for (var fn of fns) {
        if (typeof mr[fn] === 'function') {
          try {
            mr[fn]();
            log.push({ fn: fn, ok: true });
          } catch (e) {
            log.push({ fn: fn, error: String(e) });
          }
        }
      }
      return log;
    }""")
    print("\n=== Try retrieve methods ===")
    print(json.dumps(try_retrieve, ensure_ascii=False, indent=2))
    time.sleep(8)

    final = p.evaluate("""() => {
      var mr = $find('ctl00_FastBusiness_MainReport');
      return {
        rows: mr && mr._rows ? mr._rows.length : 0,
        sample: mr && mr._rows && mr._rows[0] ? mr._rows[0] : null,
        filter: (document.body.innerText.match(/Vật tư:[^\\n]+/) || [])[0]
      };
    }""")
    print("\n=== After retrieve attempts ===")
    print(json.dumps(final, ensure_ascii=False, indent=2, default=str))

    p.close()

if __name__ == "__main__":
    main()
