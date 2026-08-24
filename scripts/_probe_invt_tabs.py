"""Probe tab Tài khoản + ItemReference cho dvt/tk_vt."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"

JS = """
() => {
  var f = $find('ctl00_FastBusiness_MainReport_dirExtender');
  var names = ['dvt','loai_vt','tk_vt'];
  var meta = names.map(function(n) {
    var field = f._fields.find(function(x) { return x.Name === n; });
    if (!field) return { name: n, missing: true };
    return {
      Name: field.Name, ItemStyle: field.ItemStyle, AllowNulls: field.AllowNulls,
      Visible: field.Visible, CategoryIndex: field.CategoryIndex,
      ItemController: field.ItemController, ItemReference: field.ItemReference,
      ItemKeyFilter: field.ItemKeyFilter
    };
  });
  var tabs = [];
  document.querySelectorAll('[id*="dirExtender"] a, [id*="dirExtender"] span, .ajax__tab_tab').forEach(function(el) {
    var t = (el.innerText||'').trim();
    if (t && t.length < 30) tabs.push({ text: t, id: el.id, tag: el.tagName });
  });
  return { meta: meta, tabs: tabs.slice(0, 20) };
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(URL, timeout=90000)
    time.sleep(8)
    p.evaluate("""() => { $find('ctl00_FastBusiness_MainReport').executeCommand({ commandName: 'New', commandArgument: '0' }); }""")
    time.sleep(3)
    print(json.dumps(p.evaluate(JS), ensure_ascii=False, indent=2))
    p.close()

if __name__ == "__main__":
    main()
