"""Probe: focus/select row trước Edit — tìm API đúng."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/invt.aspx?id=15.70.06"
MR = "ctl00_FastBusiness_MainReport"
FILTER = "ctl00_FastBusiness_MainReport_FilterPanelTextma_vt"

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)

p.locator(f"#{FILTER}").click()
p.locator(f"#{FILTER}").fill("ZTEST")
p.locator(f"#{FILTER}").press("Enter")
time.sleep(4)

# List row-related methods
methods = p.evaluate(f"""() => {{
  var mr = $find('{MR}');
  var m = [];
  for (var k in mr) if (typeof mr[k]==='function' && /select|focus|row|current|active|mark/i.test(k)) m.push(k);
  return m;
}}""")
print("methods:", json.dumps(methods, ensure_ascii=False))

# Try several focus strategies on row 1
attempts = p.evaluate(f"""() => {{
  var mr = $find('{MR}');
  var gt = document.getElementById('{MR}_gridTable');
  var tr = gt.querySelectorAll('tr')[0];
  var log = [];
  function t(name, fn) {{
    try {{ var v = fn(); log.push({{ name: name, ok: true, result: v === undefined ? null : String(v).substring(0,80) }}); }}
    catch(e) {{ log.push({{ name: name, ok: false, error: String(e).substring(0,120) }}); }}
  }}
  t('tr.click', () => {{ tr.click(); }});
  t('tr.firstCell.click', () => {{ var td = tr.querySelector('td'); if(td) td.click(); }});
  t('tr.firstLink.click', () => {{ var a = tr.querySelector('a'); if(a) a.click(); }});
  t('markSelectedRow(0)', () => mr.markSelectedRow(0));
  t('markSelectedRow(1)', () => mr.markSelectedRow(1));
  t('toggleSelectedRow(0)', () => mr.toggleSelectedRow(0));
  t('set_firstRowSelected', () => mr.set_firstRowSelected && mr.set_firstRowSelected(true));
  // focus first input/cell
  t('focus cell input', () => {{
    var inp = tr.querySelector('input, td');
    if (inp && inp.focus) inp.focus();
  }});
  return {{
    log: log,
    tr_html: tr ? tr.innerHTML.substring(0, 200) : null,
    selected: typeof mr._selectedRow !== 'undefined' ? mr._selectedRow : 'n/a',
    current: typeof mr._currentRow !== 'undefined' ? mr._currentRow : 'n/a'
  }};
}}""")
print(json.dumps(attempts, ensure_ascii=False, indent=2))

# After focus, try Edit
p.evaluate(f"() => {{ $find('{MR}').executeCommand({{ commandName: 'Edit', commandArgument: '0' }}); }}")
time.sleep(3)
state = p.evaluate(f"""() => {{
  var de = $find('{MR}_dirExtender');
  var btn = document.getElementById('{MR}_dirExtender_updateDlgOk');
  return {{
    has_dirExtender: !!de,
    fields: de && de._fields ? de._fields.length : 0,
    ma_vt: de ? de.getItemValue('ma_vt') : null,
    ten_vt: de ? de.getItemValue('ten_vt') : null,
    save_visible: !!(btn && btn.offsetParent !== null)
  }};
}}""")
print("after Edit:", json.dumps(state, ensure_ascii=False, indent=2))
p.close()
