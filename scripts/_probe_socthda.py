"""Probe chứng từ socthda — classify + toolbar + New form fields."""
import json
import sys
import time

sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"

PROBE_JS = """
() => {
  function findMainReportId() {
    var apps = Sys.Application.getComponents();
    for (var i = 0; i < apps.length; i++) {
      var id = apps[i].get_id ? apps[i].get_id() : '';
      if (/MainReport$/.test(id) && !/searchExtender|dirExtender|FormLookup|DropShadow|ToolbarButton/.test(id))
        return id;
    }
    return null;
  }
  var mrId = findMainReportId();
  var mr = mrId ? $find(mrId) : null;
  var de = mrId ? $find(mrId + '_dirExtender') : null;
  var out = {
    url: location.href,
    title: document.title,
    mr_id: mrId,
    mr_type: mr ? mr._type : null,
    page_kind: null,
    grid_fields: [],
    toolbar: [],
    typeof_f: typeof f,
    typeof_g: typeof g
  };
  if (mr && mr._type === 'Voucher') out.page_kind = 'voucher';
  else if (mr && mr._type === '') out.page_kind = 'category';
  else if (mr && mr._type === 'Report') out.page_kind = 'report';

  if (mr && mr._fields) {
    out.grid_fields = mr._fields.slice(0, 12).map(function(f) {
      return { Name: f.Name, HeaderText: f.HeaderText || f.Label, Type: f.Type };
    });
    out.row_count = mr._rows ? mr._rows.length : 0;
  }

  document.querySelectorAll('[id*="ToolbarButton"]').forEach(function(el) {
    var t = (el.innerText || el.title || '').trim();
    if (t) out.toolbar.push({ id: el.id, text: t.substring(0, 30) });
  });

  out.has_dirExtender = !!de;
  return out;
}
"""

AFTER_NEW_JS = """
() => {
  function findMainReportId() {
    var apps = Sys.Application.getComponents();
    for (var i = 0; i < apps.length; i++) {
      var id = apps[i].get_id ? apps[i].get_id() : '';
      if (/MainReport$/.test(id) && !/searchExtender|dirExtender|FormLookup|DropShadow|ToolbarButton/.test(id))
        return id;
    }
    return null;
  }
  var mrId = findMainReportId();
  var de = $find(mrId + '_dirExtender');
  if (!de || !de._fields) return { error: 'no dirExtender after New', mrId: mrId };

  var required = [];
  var autocomplete = [];
  de._fields.forEach(function(f) {
    var info = {
      Name: f.Name,
      HeaderText: f.HeaderText || f.Label || '',
      Type: f.Type,
      AllowNulls: f.AllowNulls,
      ItemStyle: f.ItemStyle,
      ItemController: f.ItemController,
      CategoryIndex: f.CategoryIndex,
      Visible: f.Visible
    };
    if (f.AllowNulls === false) required.push(info);
    if (f.ItemStyle === 'AutoComplete' || f.ItemStyle === 'Lookup') autocomplete.push(info);
  });

  var buttons = [];
  document.querySelectorAll('[id*="dirExtender"] button, [id*="dirExtender"] input[type="button"]').forEach(function(el) {
    var t = (el.value || el.innerText || '').trim();
    if (t) buttons.push({ id: el.id, text: t });
  });

  return {
    mrId: mrId,
    de_type: de._type,
    field_count: de._fields.length,
    required: required.slice(0, 25),
    autocomplete: autocomplete.slice(0, 25),
    buttons: buttons.slice(0, 10),
    sample_inputs: Array.from(document.querySelectorAll('[id*="dirExtender_form_"]'))
      .filter(function(el) { return el.offsetParent !== null && el.type !== 'hidden'; })
      .slice(0, 15)
      .map(function(el) { return { id: el.id, type: el.type, value: (el.value||'').substring(0,40) }; })
  };
}
"""


def main():
    cfg = load_chrome_debug_config()
    s = ChromeSession.get_instance()
    s.disconnect()
    p = s.connect(cfg["cdp_url"]).contexts[0].new_page()

    print("=== 1. Mở socthda ===")
    p.goto(URL, timeout=90000)
    time.sleep(8)
    probe = p.evaluate(PROBE_JS)
    print(json.dumps(probe, ensure_ascii=False, indent=2))

    mr_id = probe.get("mr_id")
    if not mr_id:
        print("FAIL: no MainReport")
        p.close()
        return

    print("\n=== 2. Click Mới ===")
    try:
        p.locator(f"#{mr_id}_ToolbarButton_New").click(timeout=5000)
        via = "toolbar_New"
    except Exception:
        p.evaluate(f"() => {{ $find('{mr_id}').executeCommand({{ commandName: 'New', commandArgument: '0' }}); }}")
        via = "executeCommand New"
    print("via:", via)
    time.sleep(4)

    after = p.evaluate(AFTER_NEW_JS)
    print(json.dumps(after, ensure_ascii=False, indent=2))

    p.close()
    s.disconnect()


if __name__ == "__main__":
    main()
