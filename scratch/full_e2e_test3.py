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
    print(f"== {kw.get('action')} ({time.time()-t:.1f}s) ok={r.get('success')} "
          f"err={str(r.get('error'))[:120]}")
    return r

r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
print("  login_as:", (r.get("result") or {}).get("login_as"))
if not r["success"]:
    sys.exit("LOGIN FAIL")

# mở màn Danh mục khách hàng bằng action menu (submenu Hệ thống)
r = bf(action="menu", menu_text="Danh mục khách hàng")
print("  menu:", r.get("result") or r.get("error"))
time.sleep(3)

r = bf(action="snapshot")
st = r.get("state") or {}
print("  screen:", st.get("screen"), "| url:", st.get("url"))
print("  components:", json.dumps(st.get("components"), ensure_ascii=False)[:400])
print("  toolbar:", st.get("toolbar"))
print("  grid:", st.get("grid"))
print("  dialogs:", json.dumps(st.get("dialogs"), ensure_ascii=False)[:300])

# grid actions trên list nếu có
r = bf(action="row_count")
print("  row_count:", r.get("result") or r.get("error"))
rc = ((r.get("result") or {}).get("row_count") or 0)
if rc > 0:
    r = bf(action="select_row", row=1)
    print("  select_row:", r.get("result") or r.get("error"))
    r = bf(action="grid_get", row=1, col="1")
    print("  grid_get:", r.get("result") or r.get("error"))

bf(action="close")
print("DONE")
