"""Verify ZTEST exists + cách lọc gridHeader ma_vt."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

MR = "ctl00_FastBusiness_MainReport"
CODE = "ZTEST232529"

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto("http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06", timeout=90000)
time.sleep(8)

# Inspect filter inputs
filt = p.evaluate("""() => {
  var inputs = document.querySelectorAll('#ctl00_FastBusiness_MainReport_gridHeader input');
  return Array.from(inputs).map(inp => ({
    id: inp.id, type: inp.type, value: inp.value, className: inp.className
  }));
}""")
print("=== filter inputs ===")
print(json.dumps(filt, ensure_ascii=False, indent=2))

# Try set filter via _setItemValue / setFilter if any
api = p.evaluate(f"""() => {{
  var mr = $find('{MR}');
  var methods = [];
  for (var k in mr) if (typeof mr[k]==='function' && /filter|Filter|search|Search|QBE/i.test(k)) methods.push(k);
  return methods;
}}""")
print("=== filter methods ===", json.dumps(api, ensure_ascii=False))

# Fill first text filter + Enter
res = p.evaluate(f"""(code) => {{
  var inputs = document.querySelectorAll('#ctl00_FastBusiness_MainReport_gridHeader input[type="text"]');
  if (!inputs.length) return {{ error: 'no filter input' }};
  var inp = inputs[0];
  inp.focus();
  inp.value = code;
  inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
  inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
  // Enter
  inp.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
  inp.dispatchEvent(new KeyboardEvent('keypress', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
  inp.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
  return {{ id: inp.id, value: inp.value }};
}}""", CODE)
print("=== set filter ===", json.dumps(res, ensure_ascii=False))
time.sleep(4)

grid = p.evaluate(f"""() => {{
  var mr = $find('{MR}');
  var rows = [];
  for (var r = 1; r <= Math.min(mr._rows.length, 5); r++) {{
    rows.push(mr._getItemValue(r, 1));
  }}
  return {{ row_count: mr._rows.length, first_codes: rows }};
}}""")
print("=== after Enter filter ===", json.dumps(grid, ensure_ascii=False, indent=2))

# Also try searching all pages for ZTEST via reading _rows after search with *
p.evaluate(f"""() => {{
  var mr = $find('{MR}');
  // clear and use contains
  var inputs = document.querySelectorAll('#ctl00_FastBusiness_MainReport_gridHeader input[type="text"]');
  if (inputs[0]) {{
    inputs[0].value = 'ZTEST';
    inputs[0].dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
  }}
}}""")
time.sleep(4)
grid2 = p.evaluate(f"""() => {{
  var mr = $find('{MR}');
  var rows = [];
  for (var r = 1; r <= Math.min(mr._rows.length, 20); r++) {{
    rows.push({{ ma: mr._getItemValue(r, 1), ten: mr._getItemValue(r, 2) }});
  }}
  return {{ row_count: mr._rows.length, rows: rows }};
}}""")
print("=== filter ZTEST ===", json.dumps(grid2, ensure_ascii=False, indent=2))
p.close()
