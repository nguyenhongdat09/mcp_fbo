"""Check required master fields + save result."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"
FG = f"{DE}_FormGridd81"
REQ = ["ma_kh","tk","ma_gd","ma_tt","so_ct","so_seri","ngay_lct","ngay_ct","ma_nt","tk_thue_no"]

def ev(p, js, arg=None):
    return p.evaluate(js, arg) if arg is not None else p.evaluate(js)

def dismiss(p):
    return ev(p, """() => {
      for (var b of document.querySelectorAll('input[type="button"], button')) {
        var t = (b.value||b.innerText||'').trim();
        if (t === 'Nhận' || t === 'Có') { b.click(); return t; }
      }
      return null;
    }""")

def lookup_master(p, field):
    ev(p, """(f) => {
      var inp = document.querySelector('[id*="dirExtender_form_' + f + '"]');
      inp.closest('td').querySelector('img.CellImgLookup').click();
    }""", field)
    time.sleep(2)
    t = f"{DE}_FormLookup{field}_Button_Lookup_Table"
    ev(p, """(id) => {
      var table = document.getElementById(id);
      for (var tr of table.querySelectorAll('tr')) {
        var a = tr.querySelector('a');
        if (a && a.innerText.trim() && !/Danh mục|Chọn|Đóng/.test(a.innerText)) { a.click(); return; }
      }
    }""", t)
    time.sleep(1.5)
    dismiss(p)

def lookup_ma_vt(p):
    p.locator(f'[id="{FG}_gridCell_1.1"]').click()
    p.locator(f'[id="{FG}_gridCell_1.1"] img.CellImgLookup').click()
    time.sleep(2)
    t = f"{FG}_GridLookup1.1_Button_Lookup_Table"
    ev(p, """(id) => {
      var table = document.getElementById(id);
      for (var tr of table.querySelectorAll('tr')) {
        var a = tr.querySelector('a');
        if (a && a.innerText.trim() && !/Danh mục|Chọn|Đóng/.test(a.innerText)) { a.click(); return; }
      }
    }""", t)
    time.sleep(2)
    ev(p, f"""() => {{
      var bg = document.getElementById('{FG}_GridLookup1.1_Button_Lookup_backgroundElement');
      if (bg) bg.click();
    }}""")

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)
p.locator(f"#{MR}_ToolbarButton_New").click()
time.sleep(4)

for f in ["ma_kh", "tk", "ma_tt"]:
    lookup_master(p, f)

p.locator("#__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel1").click()
time.sleep(1)
lookup_ma_vt(p)
p.locator(f'[id="{FG}_inputCell_1.18"]').click()
p.locator(f'[id="{FG}_inputCell_1.18"]').fill("1")
p.locator(f'[id="{FG}_inputCell_1.18"]').press("Tab")
time.sleep(1)

pre = ev(p, f"""() => {{
  var de = $find('{DE}');
  var g = $find('{FG}');
  var o = {{ master: {{}}, detail: {{}} }};
  {json.dumps(REQ)}.forEach(function(n) {{ o.master[n] = de.getItemValue(n); }});
  o.detail = {{ ma_vt: g._getItemValue(1,1), dvt: g._getItemValue(1,3), so_luong: g._getItemValue(1,18) }};
  o.master_empty = {json.dumps(REQ)}.filter(function(n) {{ var v = o.master[n]; return v === null || v === undefined || String(v).trim() === ''; }});
  return o;
}}""")
print("PRE:", json.dumps(pre, ensure_ascii=False, indent=2))

p.locator(f"#{DE}_updateDlgOk").click(force=True)
time.sleep(6)
for i in range(3):
    d = dismiss(p)
    if d: print("dismiss:", d)
    time.sleep(1)

post = ev(p, """() => {
  var modal = document.querySelector('[id*="dirExtender"][class*="Modal"], [id*="dirExtender_formTable"]');
  var btn = document.getElementById('""" + DE + """_updateDlgOk');
  var body = document.body.innerText || '';
  var msgs = [];
  document.querySelectorAll('div').forEach(function(d) {
    var t = (d.innerText||'').trim();
    if (/Trường|chưa nhập|không hợp lệ|thành công|lỗi|bắt buộc/i.test(t) && t.length < 250) msgs.push(t);
  });
  return {
    updateDlgOk_visible: !!(btn && btn.offsetParent),
    msgs: msgs.slice(0, 8),
    body_snip: body.substring(0, 500)
  };
}""")
print("POST:", json.dumps(post, ensure_ascii=False, indent=2))
p.close()
