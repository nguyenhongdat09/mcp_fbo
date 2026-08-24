"""Probe fill 1 dòng detail FormGridd81 (SVDetail) trên socthda."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"
FG = f"{DE}_FormGridd81"

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)
p.locator(f"#{MR}_ToolbarButton_New").click()
time.sleep(4)

# Tab Chi tiết
p.locator("#__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel1").click()
time.sleep(1)

# Thêm dòng
p.locator(f"#{FG}_ToolbarButton_Insert").click()
time.sleep(2)

probe = p.evaluate(f"""() => {{
  var g = $find('{FG}');
  var de = $find('{DE}');
  var out = {{
    grid_id: '{FG}',
    has_g: !!g,
    g_type: g ? g._type : null,
    g_rows: g && g._rows ? g._rows.length : null,
    g_activeRow: g ? g._activeRow : null,
    g_fields_sample: [],
    methods: {{}},
    cell_ids: [],
    ma_vt_dom: null
  }};

  if (g && g._fields) {{
    out.g_fields_sample = g._fields.slice(0, 12).map(function(f) {{
      return {{ Name: f.Name, AllowNulls: f.AllowNulls, ItemStyle: f.ItemStyle, ColIndex: f.ColIndex }};
    }});
    var ma_vt = g._fields.find(function(x) {{ return x.Name === 'ma_vt'; }});
    if (ma_vt) out.ma_vt_col = ma_vt.ColIndex;
  }}

  ['_getItemValue','setItemValue','getItemValue','_setItemValue','_getActiveRow','executeCommand','addRow','insertRow'].forEach(function(m) {{
    out.methods[m] = g && typeof g[m] === 'function';
  }});

  if (g && g._activeRow >= 0 && out.ma_vt_col) {{
    try {{ out.ma_vt_val = g._getItemValue(g._activeRow, out.ma_vt_col); }} catch(e) {{ out.ma_vt_err = String(e); }}
  }}

  // DOM cells row 1
  document.querySelectorAll('[id*="FormGridd81_gridCell_"]').forEach(function(el) {{
    var id = el.id;
    if (/gridCell_1\\./.test(id) || /gridCell_\\$%r\\.0/.test(id)) {{
      var inp = el.querySelector('input');
      out.cell_ids.push({{ id: id, has_input: !!inp, input_id: inp ? inp.id : null }});
    }}
  }});

  // Tìm input ma_vt trong grid
  var inp = document.querySelector('[id*="FormGridd81"][id*="ma_vt"]');
  if (inp) out.ma_vt_dom = {{ id: inp.id, tag: inp.tagName, value: inp.value }};

  // Lookup img trong grid row active
  document.querySelectorAll('[id*="FormGridd81"] img.CellImgLookup').forEach(function(img) {{
    if (!out.lookup_imgs) out.lookup_imgs = [];
    out.lookup_imgs.push(img.id || img.parentElement.id);
  }});

  return out;
}}""")
print(json.dumps(probe, ensure_ascii=False, indent=2))

# Thử click cell ma_vt col 0 (1-based?)
if probe.get("ma_vt_col"):
    col = probe["ma_vt_col"]
    for row in [1, probe.get("g_activeRow", 0)]:
        cid = f"{FG}_gridCell_{row}.{col}"
        try:
            loc = p.locator(f'[id="{cid}"]')
            if loc.count():
                loc.first.click()
                time.sleep(0.5)
                after = p.evaluate(f"""() => {{
                  var g = $find('{FG}');
                  return {{ row: g._activeRow, col: {col}, cell: '{cid}' }};
                }}""")
                print("\nclick cell:", json.dumps(after))
        except Exception as e:
            print("click err", e)

# Thử setItemValue ma_vt qua grid extender
set_res = p.evaluate(f"""() => {{
  var g = $find('{FG}');
  if (!g || !g.setItemValue) return {{ error: 'no setItemValue' }};
  try {{
    g.setItemValue('ma_vt', 'ZTEST');
    return {{ ok: true, val: g.getItemValue('ma_vt') }};
  }} catch(e) {{ return {{ error: String(e) }}; }}
}}""")
print("\nsetItemValue ma_vt:", json.dumps(set_res, ensure_ascii=False))

p.close()
