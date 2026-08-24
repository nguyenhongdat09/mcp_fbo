"""Sau lookup ma_vt — xem field detail nào còn trống."""
import json, sys, time
sys.path.insert(0, r"e:\PythonProject\mcp_fbo")
from fastbusiness_mcp.chrome_debug.config_loader import load_chrome_debug_config
from fastbusiness_mcp.chrome_debug.session import ChromeSession

URL = "http://172.168.5.14/BinhDienMK/Main/socthda.aspx?id=09.10.06"
MR = "ctl00_FastBusiness_MainReport"
DE = f"{MR}_dirExtender"
FG = f"{DE}_FormGridd81"
CHECK = ["ma_vt","dvt","ma_kho","so_luong","tk_dt","tk_vt","tk_gv","ma_nx","gia_nt2","tien_nt2"]

cfg = load_chrome_debug_config()
s = ChromeSession.get_instance(); s.disconnect()
p = s.connect(cfg["cdp_url"]).contexts[0].new_page()
p.goto(URL, timeout=90000)
time.sleep(8)
p.locator(f"#{MR}_ToolbarButton_New").click()
time.sleep(4)
p.locator("#__tab_ctl00_FastBusiness_MainReport_dirExtender_Tabs_Panel1").click()
time.sleep(1)

p.locator(f'[id="{FG}_gridCell_1.1"]').click()
p.locator(f'[id="{FG}_gridCell_1.1"] img.CellImgLookup').click()
time.sleep(2)
t = f"{FG}_GridLookup1.1_Button_Lookup_Table"
p.evaluate("""(id) => {
  var table = document.getElementById(id);
  for (var tr of table.querySelectorAll('tr')) {
    var a = tr.querySelector('a');
    if (a && a.innerText.trim() && !/Danh mục|Chọn/.test(a.innerText)) { a.click(); break; }
  }
}""", t)
time.sleep(3)

res = p.evaluate(f"""() => {{
  var g = $find('{FG}');
  var cols = {{}};
  for (var i = 0; i < g._fields.length; i++) cols[g._fields[i].Name] = i + 1;
  var o = {{}}, empty = [];
  {json.dumps(CHECK)}.forEach(function(n) {{
    if (!cols[n]) return;
    var v = g._getItemValue(1, cols[n]);
    o[n] = v;
    if (v === null || v === undefined || String(v).trim() === '' || v === 0) empty.push(n);
  }});
  o.empty = empty;
  return o;
}}""")
print(json.dumps(res, ensure_ascii=False, indent=2))

# thử save và bắt message popup
p.locator(f'[id="{FG}_inputCell_1.18"]').fill("1")
p.locator(f'[id="{FG}_inputCell_1.18"]').press("Tab")
time.sleep(1)
p.locator(f"#{DE}_updateDlgOk").click(force=True)
time.sleep(6)
msg = p.evaluate("""() => {
  var out = [];
  document.querySelectorAll('div').forEach(function(d) {
    var t = (d.innerText||'').trim();
    if (/Fast Business|Trường|chưa|hợp lệ|bắt buộc|Nhận/i.test(t) && t.length < 300 && t.indexOf('\\n') >= 0)
      out.push(t);
  });
  return out.slice(0, 5);
}""")
print("MSG:", json.dumps(msg, ensure_ascii=False, indent=2))
p.close()
