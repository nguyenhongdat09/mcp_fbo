"""Probe xóa dòng 2 trống trên FormGridd81."""
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

# Case A: không Insert
rows_a = p.evaluate(f"""() => {{
  var out = [];
  for (var r = 1; r <= 3; r++) {{
    out.push({{ r: r, inp: !!document.getElementById('{FG}_inputCell_' + r + '.1') }});
  }}
  return {{ case: 'no_insert', rows: out }};
}}""")
print(json.dumps(rows_a, indent=2))

p.locator(f"#{FG}_ToolbarButton_Insert").click()
time.sleep(2)
rows_b = p.evaluate(f"""() => {{
  var out = [];
  for (var r = 1; r <= 3; r++) {{
    out.push({{ r: r, inp: !!document.getElementById('{FG}_inputCell_' + r + '.1') }});
  }}
  return {{ case: 'after_insert', rows: out }};
}}""")
print(json.dumps(rows_b, indent=2))

# Thử xóa dòng 2: focus + Toolbar Remove
cell = f"{FG}_gridCell_2.1"
p.locator(f'[id="{cell}"]').click()
time.sleep(0.5)
before = p.evaluate(f"() => $find('{FG}')._activeRow")
p.locator(f"#{FG}_ToolbarButton_Remove").click()
time.sleep(1)
# confirm Có
p.evaluate("""() => {
  for (var b of document.querySelectorAll('input[type="button"], button')) {
    if ((b.value||b.innerText||'').trim() === 'Có') { b.click(); return true; }
  }
  return false;
}""")
time.sleep(1)
rows_c = p.evaluate(f"""() => {{
  var out = [];
  for (var r = 1; r <= 3; r++) {{
    out.push({{ r: r, inp: !!document.getElementById('{FG}_inputCell_' + r + '.1') }});
  }}
  return {{ case: 'after_remove_row2', active_before: {before}, rows: out }};
}}""")
print(json.dumps(rows_c, indent=2))
p.close()
