"""Probe grid chi tiết d81/SVDetail trên form HĐ sau Mới."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)
p.locator(f"#{MR}_ToolbarButton_New").click()
time.sleep(4)

probe = p.evaluate(f"""() => {{
  var de = $find('{DE}');
  var out = {{
    has_de: !!de,
    fields_d81: null,
    grid_ids: [],
    detail_extenders: [],
    grid_tables: [],
    g_exists: typeof g !== 'undefined',
    f_exists: typeof f !== 'undefined'
  }};

  if (de && de._fields) {{
    var d81 = de._fields.find(function(x) {{ return x.Name === 'd81'; }});
    if (d81) out.fields_d81 = {{
      Name: d81.Name, ItemStyle: d81.ItemStyle, ItemController: d81.ItemController,
      AllowNulls: d81.AllowNulls, CategoryIndex: d81.CategoryIndex
    }};
  }}

  // Tìm grid detail components
  Sys.Application.getComponents().forEach(function(c) {{
    var id = c.get_id ? c.get_id() : '';
    if (/SVDetail|FormGrid|d81|Detail|GridVoucher/i.test(id)) {{
      out.detail_extenders.push({{
        id: id,
        _type: c._type,
        fields: c._fields ? c._fields.length : 0,
        rows: c._rows ? c._rows.length : null
      }});
    }}
  }});

  document.querySelectorAll('[id*="d81"], [id*="SVDetail"], [id*="FormGrid"]').forEach(function(el) {{
    if (el.tagName === 'TABLE' || el.id.indexOf('grid') >= 0 || el.id.indexOf('Grid') >= 0)
      out.grid_ids.push({{ id: el.id, tag: el.tagName }});
  }});

  // Thử biến g trong dirExtender context
  try {{
    if (typeof g !== 'undefined' && g) {{
      out.g_id = g.get_id ? g.get_id() : 'g';
      out.g_fields = g._fields ? g._fields.slice(0,8).map(function(f){{ return f.Name; }}) : [];
      out.g_rows = g._rows ? g._rows.length : 0;
    }}
  }} catch(e) {{ out.g_err = String(e); }}

  // DOM grid trong form
  document.querySelectorAll('[id*="dirExtender"] table, [id*="dirExtender"] [id*="grid"]').forEach(function(el) {{
    if (el.id) out.grid_tables.push(el.id);
  }});

  return out;
}}""")
print(json.dumps(probe, ensure_ascii=False, indent=2))

# Thử tìm tab Chi tiết
tabs = p.evaluate("""() => {
  var tabs = [];
  document.querySelectorAll('[id*="dirExtender_Tabs"] a, [id*="dirExtender"] span').forEach(function(el) {
    var t = (el.innerText||'').trim();
    if (t && t.length < 30) tabs.push({ text: t, id: el.id, tag: el.tagName });
  });
  return tabs.slice(0, 20);
}""")
print("\n=== tabs ===")
print(json.dumps(tabs, ensure_ascii=False, indent=2))
p.close()
