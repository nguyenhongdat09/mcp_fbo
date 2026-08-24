"""Probe _rowSelected / _setActiveCell / click gridCell trước Edit."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"
FILTER = f"{MR}_FilterPanelTextma_vt"

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)
p.locator(f"#{FILTER}").fill("ZTEST")
p.locator(f"#{FILTER}").press("Enter")
time.sleep(4)

# Inspect grid cells row 1
cells = p.evaluate(f"""() => {{
  var ids = [];
  document.querySelectorAll('[id*="gridCell_1."]').forEach(el => ids.push(el.id));
  var mr = $find('{MR}');
  return {{
    cell_ids: ids.slice(0, 8),
    rowSelected_src: mr._rowSelected ? mr._rowSelected.toString().substring(0, 400) : null,
    setActive_src: mr._setActiveCell ? mr._setActiveCell.toString().substring(0, 300) : null
  }};
}}""")
print(json.dumps(cells, ensure_ascii=False, indent=2))

# Strategy: Playwright click on ma_vt cell / link in row 1
# cells often id gridCell_1.1 for first data col (1-based row.col)
for sel in [
    f"#{MR}_gridCell_1\\.1",
    f"#{MR}_gridCell_1\\.1 a",
    f"#{MR}_gridTable tr:first-child td:nth-child(2)",
    f"#{MR}_gridTable tr:first-child td:nth-child(2) a",
]:
    try:
        loc = p.locator(sel)
        if loc.count() > 0:
            loc.first.click(timeout=3000)
            print("clicked", sel)
            time.sleep(0.5)
            break
    except Exception as ex:
        print("fail", sel, ex)

# Also try _setActiveCell / _rowSelected via JS
js_focus = p.evaluate(f"""() => {{
  var mr = $find('{MR}');
  var log = [];
  var cell = document.getElementById('{MR}_gridCell_1.1');
  function t(n, fn) {{
    try {{ fn(); log.push({{n:n, ok:true}}); }} catch(e) {{ log.push({{n:n, err:String(e).substring(0,100)}}); }}
  }}
  if (cell) {{
    t('cell.click', () => cell.click());
    t('_setActiveCell(cell)', () => mr._setActiveCell(cell));
    t('_rowSelected', () => mr._rowSelected(cell));
    t('_focus', () => mr._focus(cell));
  }}
  // current row after
  var cur = null;
  try {{ cur = mr._currentRow(); }} catch(e) {{ cur = String(e); }}
  return {{ log: log, currentRow: cur, active: mr._activeElement ? String(mr._activeElement()) : null }};
}}""")
print("js_focus:", json.dumps(js_focus, ensure_ascii=False, indent=2))
time.sleep(0.5)

# Click toolbar Sửa via DOM button instead of executeCommand
toolbar = p.evaluate(f"""() => {{
  var btns = [];
  document.querySelectorAll('[id*="ToolbarButton"], [id*="MainReport"] div, [id*="MainReport"] a').forEach(el => {{
    var t = (el.innerText||el.title||'').trim();
    if (t === 'Sửa' || (el.id && el.id.indexOf('Edit')>=0)) btns.push({{id: el.id, text: t.substring(0,20), tag: el.tagName}});
  }});
  return btns.slice(0, 10);
}}""")
print("toolbar Sửa:", json.dumps(toolbar, ensure_ascii=False, indent=2))

# Fire Edit after focus
p.evaluate(f"() => {{ $find('{MR}').executeCommand({{ commandName: 'Edit', commandArgument: '0' }}); }}")
time.sleep(3)
# Also try clicking Sửa button
try:
    p.locator(f"#{MR}_ToolbarButton_Edit").click(timeout=2000)
    time.sleep(2)
except Exception:
    pass

state = p.evaluate(f"""() => {{
  var de = $find('{MR}_dirExtender');
  var apps = Sys.Application.getComponents();
  var dirIds = [];
  for (var i=0;i<apps.length;i++) {{
    var id = apps[i].get_id ? apps[i].get_id() : '';
    if (id.indexOf('dirExtender')>=0) dirIds.push(id);
  }}
  return {{
    has_de: !!de,
    dirIds: dirIds,
    ma: de ? de.getItemValue('ma_vt') : null,
    ten: de ? de.getItemValue('ten_vt') : null,
    body_has_sua: (document.body.innerText||'').indexOf('Sửa vật tư')>=0 || (document.body.innerText||'').indexOf('Cập nhật')>=0
  }};
}}""")
print("state:", json.dumps(state, ensure_ascii=False, indent=2))
p.close()
