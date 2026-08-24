"""Probe lookup ma_vt trong FormGridd81 row 1."""
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
p.locator("#__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel1").click()
time.sleep(1)
p.locator(f"#{FG}_ToolbarButton_Insert").click()
time.sleep(2)

# Map field -> col (1-based from _fields order + 1 for row# col?)
col_map = p.evaluate(f"""() => {{
  var g = $find('{FG}');
  var map = {{}};
  if (!g || !g._fields) return map;
  for (var i = 0; i < g._fields.length; i++) {{
    var f = g._fields[i];
    map[f.Name] = i + 1;  // test 1-based
  }}
  return map;
}}""")
print("col_map sample:", {k: col_map[k] for k in list(col_map)[:8]})
print("ma_vt col:", col_map.get("ma_vt"), "dvt:", col_map.get("dvt"), "so_luong:", col_map.get("so_luong"))

row = 1
ma_col = col_map.get("ma_vt", 1)
cell = f"{FG}_gridCell_{row}.{ma_col}"
p.locator(f'[id="{cell}"]').click()
time.sleep(0.5)

# Lookup img trong cell
open_res = p.evaluate(f"""() => {{
  var cell = document.getElementById('{cell}');
  if (!cell) return {{ error: 'no cell' }};
  var img = cell.querySelector('img.CellImgLookup');
  if (!img) {{
    // thử sibling trong row
    var row = cell.parentElement;
    img = row ? row.querySelector('img.CellImgLookup') : null;
  }}
  if (!img) return {{ error: 'no img', cell_html: cell.innerHTML.slice(0,200) }};
  img.click();
  return {{ ok: true, img_id: img.id }};
}}""")
print("open lookup:", json.dumps(open_res, ensure_ascii=False))
time.sleep(2)

# Tìm popup lookup table
pop = p.evaluate("""() => {
  var tables = [];
  document.querySelectorAll('[id*="Lookup"][id*="Table"], [id*="lookup"][id*="Table"]').forEach(function(t) {
    if (t.offsetParent !== null || t.style.display !== 'none')
      tables.push({ id: t.id, rows: t.querySelectorAll('tr').length });
  });
  document.querySelectorAll('[id*="QuickFind"]').forEach(function(q) {
    if (q.offsetParent !== null) tables.push({ qf: q.id, val: q.value });
  });
  return tables.slice(0, 15);
}""")
print("popup:", json.dumps(pop, ensure_ascii=False, indent=2))

# Thử _setItemValue
set_res = p.evaluate(f"""() => {{
  var g = $find('{FG}');
  var row = 1, col = {ma_col};
  try {{
    g._setItemValue(row, col, 'ZTEST');
    return {{ val: g._getItemValue(row, col) }};
  }} catch(e) {{ return {{ error: String(e) }}; }}
}}""")
print("_setItemValue:", json.dumps(set_res, ensure_ascii=False))

p.close()
