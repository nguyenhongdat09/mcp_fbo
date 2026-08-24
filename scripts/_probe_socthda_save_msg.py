"""Probe message sau Lưu socthda — 1 dòng detail đúng."""
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

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)
p.locator(f"#{MR}_ToolbarButton_New").click()
time.sleep(4)

for field in ["ma_kh", "tk", "ma_tt"]:
    ev(p, """(field) => {
      var inp = document.querySelector('[id*="dirExtender_form_' + field + '"]');
      inp.closest('td').querySelector('img.CellImgLookup').click();
    }""", field)
    time.sleep(2)
    table = f"{DE}_FormLookup{field}_Button_Lookup_Table"
    ev(p, """(t) => {
      var table = document.getElementById(t);
      for (var tr of table.querySelectorAll('tr')) {
        var link = tr.querySelector('a');
        if (link && link.innerText.trim() && !/Danh mục|Chọn/.test(link.innerText)) { link.click(); break; }
      }
    }""", table)
    time.sleep(1.5)

p.locator("#__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel1").click()
time.sleep(1)

# ma_vt row 1
cell = f"{FG}_gridCell_1.1"
p.locator(f'[id="{cell}"]').click()
p.locator(f'[id="{cell}"] img.CellImgLookup').click()
time.sleep(2)
table = f"{FG}_GridLookup1.1_Button_Lookup_Table"
ev(p, """(t) => {
  var table = document.getElementById(t);
  for (var tr of table.querySelectorAll('tr')) {
    var link = tr.querySelector('a');
    if (link && link.innerText.trim() && !/Danh mục|Chọn/.test(link.innerText)) { link.click(); break; }
  }
}""", table)
time.sleep(2)

# so_luong — Playwright fill + Enter (tránh onchange lỗi context)
inp = f"{FG}_inputCell_1.18"
p.locator(f'[id="{inp}"]').click()
p.locator(f'[id="{inp}"]').fill("1")
p.locator(f'[id="{inp}"]').press("Tab")
time.sleep(1)

pre = ev(p, f"""() => {{
  var g = $find('{FG}');
  return {{ ma_vt: g._getItemValue(1,1), dvt: g._getItemValue(1,3), sl: g._getItemValue(1,18),
    so_ct: $find('{DE}').getItemValue('so_ct'), rows: [1,2].map(r => !!document.getElementById('{FG}_inputCell_'+r+'.1')) }};
}}""")
print("PRE SAVE:", json.dumps(pre, ensure_ascii=False, indent=2))

p.locator(f"#{DE}_updateDlgOk").click(force=True)
time.sleep(4)

post = ev(p, """() => {
  var texts = [];
  document.querySelectorAll('div, span, td').forEach(function(el) {
    var t = (el.innerText||'').trim();
    if (t && t.length > 5 && t.length < 300) texts.push(t);
  });
  var uniq = [];
  texts.forEach(function(t) { if (uniq.indexOf(t) < 0) uniq.push(t); });
  var btn = document.getElementById('""" + DE + """_updateDlgOk');
  return {
    dialog_open: !!(btn && btn.offsetParent),
    visible_dialogs: uniq.filter(function(t) {
      return /Fast Business|Trường|lỗi|thành công|bắt buộc|nhập|hợp lệ|Có|Nhận|Không/i.test(t);
    }).slice(0, 15)
  };
}""")
print("POST SAVE:", json.dumps(post, ensure_ascii=False, indent=2))
p.close()
