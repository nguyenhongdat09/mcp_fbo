import sys, json, time
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"

def bf(**kw):
    kw.setdefault("config", cfg)
    t = time.time()
    r = BS.browser_fbo(**kw)
    print(f"== {kw.get('action')} {kw.get('command_name','')} ({time.time()-t:.1f}s) "
          f"ok={r.get('success')} err={str(r.get('error'))[:150]}")
    return r

r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
if not r["success"]:
    sys.exit("LOGIN FAIL: " + str(r.get("error")))

# mở lại danh mục khách hàng
r = bf(action="menu", menu_text="Danh mục khách hàng")
print("  menu:", r.get("result") or r.get("error"))
time.sleep(2)

# command New → form thêm mới
r = bf(action="command", command_name="New")
print("  New:", r.get("result") or r.get("error"))
time.sleep(2)
r = bf(action="snapshot")
st = r.get("state") or {}
print("  screen:", st.get("screen"), "| url:", st.get("url"))
print("  form_fields:", json.dumps(
    [f["name"] for f in (st.get("form_fields") or [])], ensure_ascii=False)[:500])
print("  dialogs:", json.dumps(st.get("dialogs"), ensure_ascii=False)[:400])

# set_field ma_kh nếu form mở
names = [f["name"] for f in (st.get("form_fields") or [])]
if "ma_kh" in names:
    r = bf(action="set_field", field="ma_kh", value="TEST_E2E_001")
    print("  set_field ma_kh:", r.get("result") or r.get("error"))
    r = bf(action="set_field", field="ten_kh", value="Test E2E KH")
    print("  set_field ten_kh:", r.get("result") or r.get("error"))
    # KHÔNG save — Cancel/đóng form
    for c in ("Cancel", "Close", "Back"):
        r = bf(action="command", command_name=c)
        if r.get("success"):
            print("  cancelled via", c); break
    time.sleep(1)
    r = bf(action="confirm", answer="yes", required=False)
    print("  confirm:", r.get("result") or r.get("error"))
    r = bf(action="message", dismiss=True)
    print("  message:", r.get("result"))
else:
    print("  !! form không có ma_kh — state:", json.dumps(st, ensure_ascii=False)[:800])

r = bf(action="snapshot")
print("  back to:", (r.get("state") or {}).get("screen"), "|", (r.get("state") or {}).get("url"))
bf(action="close")
print("DONE")
