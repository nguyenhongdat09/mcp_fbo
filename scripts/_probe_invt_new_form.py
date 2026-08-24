"""Probe form danh mục invt — Mới → fields dirExtender."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"

PROBE_AFTER_NEW_JS = """
() => {
  var out = { dirExtender: null, inputs: [], fields: [], buttons: [] };
  var de = null;
  var apps = Sys.Application.getComponents();
  for (var i = 0; i < apps.length; i++) {
    var c = apps[i];
    var id = c.get_id ? c.get_id() : '';
    if (id.indexOf('dirExtender') >= 0 && c._fields) {
      de = c;
      out.dirExtender = { id: id, _type: c._type, field_count: c._fields.length };
      out.fields = c._fields.slice(0, 15).map(function(f) {
        return { Name: f.Name, HeaderText: f.HeaderText || f.Label, Type: f.Type, AllowNulls: f.AllowNulls };
      });
    }
  }
  document.querySelectorAll('[id*="dirExtender"] input, [id*="dirExtender"] select, [id*="dirExtender"] textarea').forEach(function(el) {
    if (el.type === 'hidden') return;
    out.inputs.push({ id: el.id, name: el.name, type: el.type, value: (el.value||'').substring(0, 40), visible: el.offsetParent !== null });
  });
  document.querySelectorAll('input[value="Lưu"], input[value="Save"], button, a, input[type="button"], input[type="submit"]').forEach(function(el) {
    var t = (el.value || el.innerText || '').trim();
    if (/Lưu|Save|Hủy|Cancel|Đóng|Close/i.test(t)) {
      out.buttons.push({ text: t.substring(0, 20), id: el.id, tag: el.tagName });
    }
  });
  return out;
}
"""

def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance(); s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
    p.goto(URL, timeout=90000)
    time.sleep(8)

    # Click Mới
    clicked = p.evaluate("""() => {
      var mr = $find('ctl00_FastBusiness_MainReport');
      if (mr && typeof mr.executeCommand === 'function') {
        mr.executeCommand({ commandName: 'New', commandArgument: '0' });
        return { via: 'executeCommand New' };
      }
      return { error: 'no executeCommand' };
    }""")
    print("Click Mới:", json.dumps(clicked, ensure_ascii=False))
    time.sleep(4)

    probe = p.evaluate(PROBE_AFTER_NEW_JS)
    print(json.dumps(probe, ensure_ascii=False, indent=2))
    p.close()

if __name__ == "__main__":
    main()
