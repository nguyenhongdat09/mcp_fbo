"""Minimal save debug — copy flow main test."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"
FG = f"{DE}_FormGridd81"

def ev(p, js, arg=None):
    return p.evaluate(js, arg) if arg is not None else p.evaluate(js)

def dismiss_lookup(field):
    return f"""() => {{
      var bg = document.getElementById('{DE}_FormLookup{field}_Button_Lookup_backgroundElement');
      if (bg) bg.click();
    }}"""

def lookup_master(p, field):
    ev(p, """(f) => {
      document.querySelector('[id*="dirExtender_form_' + f + '"]').closest('td').querySelector('img.CellImgLookup').click();
    }""", field)
    time.sleep(2)
    ev(p, """(t) => {
      var table = document.getElementById('""" + DE + """_FormLookup' + t + '_Button_Lookup_Table');
      for (var tr of table.querySelectorAll('tr')) {
        var a = tr.querySelector('a');
        if (a && a.innerText.trim() && !/Danh mục|Chọn|Đóng/.test(a.innerText)) { a.click(); return; }
      }
    }""", field)
    time.sleep(1)
    ev(p, dismiss_lookup(field))

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)
ev(p, f"() => $find('{MR}').executeCommand({{ commandName: 'New', commandArgument: '0' }})")
time.sleep(4)
for f in ["ma_kh", "tk", "ma_tt"]:
    lookup_master(p, f)

p.locator("#__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel1").click()
time.sleep(1)
p.locator(f'[id="{FG}_gridCell_1.1"]').click()
p.locator(f'[id="{FG}_gridCell_1.1"] img.CellImgLookup').click()
time.sleep(2)
ev(p, f"""() => {{
  var t = document.getElementById('{FG}_GridLookup1.1_Button_Lookup_Table');
  for (var tr of t.querySelectorAll('tr')) {{
    var a = tr.querySelector('a');
    if (a && a.innerText.trim() && !/Danh mục|Chọn/.test(a.innerText)) {{ a.click(); return; }}
  }}
}}""")
time.sleep(2)
ev(p, f"() => document.getElementById('{FG}_GridLookup1.1_Button_Lookup_backgroundElement').click()")
time.sleep(1)
p.locator(f'[id="{FG}_inputCell_1.18"]').fill("1")
p.locator(f'[id="{FG}_inputCell_1.18"]').press("Tab")
time.sleep(1)

pre = ev(p, f"""() => {{
  var g = $find('{FG}');
  return {{ ma_vt: g._getItemValue(1,1), dvt: g._getItemValue(1,3), sl: g._getItemValue(1,18), ma_kho: g._getItemValue(1,10),
    ma_kh: $find('{DE}').getItemValue('ma_kh'), so_ct: $find('{DE}').getItemValue('so_ct') }};
}}""")
print("PRE", json.dumps(pre, ensure_ascii=False))

p.locator(f"#{DE}_updateDlgOk").click(force=True)
for wait in [3, 5, 8, 12]:
    time.sleep(wait if wait == 3 else wait - (3 if wait==5 else 5 if wait==8 else 8))
    post = ev(p, """() => {
      var btn = document.getElementById('""" + DE + """_updateDlgOk');
      var body = document.body.innerText || '';
      var fb = body.match(/Fast Business Online[\\s\\S]{0,250}/);
      return {
        wait: """ + str(wait) + """,
        dlg: !!(btn && btn.offsetParent),
        fb: fb ? fb[0] : null,
        nhận: body.indexOf('Nhận') >= 0
      };
    }""")
    print(json.dumps(post, ensure_ascii=False))
    if not post.get("dlg") and not post.get("fb"):
        break
    ev(p, "() => { for (var b of document.querySelectorAll('input[type=button],button')) if ((b.value||'').trim()==='Nhận') b.click(); }")
p.close()
