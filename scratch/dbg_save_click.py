import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from browser_fbo import session as S
from fastbusiness_mcp.mcp_app import get_config
from trace_profile.connection import resolve_profiler_connection, run_sql

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"
TEST_MA = "ZZ_TEST_MCP2"
conn = resolve_profiler_connection(FP, "app", cfg)

def db_row():
    res = run_sql(conn["parsed"],
        f"SELECT ma_kh FROM dmkh WHERE ma_kh='{TEST_MA}'")
    return (res.get("result_sets") or [{}])[0].get("rows", [])

run_sql(conn["parsed"], f"DELETE FROM dmkh WHERE ma_kh='{TEST_MA}'")
r = BS.browser_fbo(action="login", file_path=FP, user="ADMIN",
                   password="2222222222", config=cfg)
print("login:", r["success"])
BS.browser_fbo(action="menu", menu_text="Danh mục khách hàng", config=cfg)
time.sleep(2)
BS.browser_fbo(action="command", command_name="New", config=cfg)
time.sleep(1.5)
page = S.current_page()

# chỉ fill ma_kh + ten_kh (tránh ma_so_thue kích ajax taxcode)
BS.browser_fbo(action="set_field", field="ma_kh", value=TEST_MA, config=cfg)
BS.browser_fbo(action="set_field", field="ten_kh", value="KH TEST 2", config=cfg)
time.sleep(0.5)

# dump giá trị field trước save + trạng thái required
pre = page.evaluate("""() => {
  const out = {};
  for (const el of document.querySelectorAll('[id*="_form_"]')) {
    if (el.offsetWidth || el.offsetHeight)
      out[el.id.replace(/^.*_form_/, '')] = String(el.value||'').slice(0,40);
  }
  return out;
}""")
print("fields truoc save:", json.dumps(pre, ensure_ascii=False)[:800])

# click nút Lưu THẬT bằng locator (không JS click)
loc = page.locator('[id$="_updateDlgOk"]')
print("updateDlgOk count:", loc.count(), "visible:", loc.first.is_visible())
loc.first.click()
time.sleep(3)

# sau click: dump mọi text message/error đang hiện
post = page.evaluate("""() => {
  const vis = el => !!(el.offsetWidth || el.offsetHeight
    || el.getClientRects().length);
  const res = {msgs: [], errors: [], dlg_visible: null};
  for (const el of document.querySelectorAll(
      '[id*=Message],[id*=Error],[id*=error],[id*=Valid],[id*=Notify],'
      + '.MessageBox,.validation,[id*=Attention]')) {
    if (vis(el)) {
      const t = (el.innerText||'').trim();
      if (t) res.msgs.push(el.id + ' :: ' + t.slice(0,150));
    }
  }
  const ok = document.querySelector('[id$="_updateDlgOk"]');
  res.dlg_visible = ok ? !!(ok.offsetWidth||ok.offsetHeight) : null;
  return res;
}""")
print(json.dumps(post, ensure_ascii=False, indent=1)[:2000])
print("DB:", db_row())
BS.browser_fbo(action="close", config=cfg)
