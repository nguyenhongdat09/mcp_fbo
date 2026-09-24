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
          f"ok={r.get('success')} err={str(r.get('error'))[:120]}")
    return r

r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
if not r["success"]:
    sys.exit("LOGIN FAIL: " + str(r.get("error")))

r = bf(action="menu", menu_text="Danh mục khách hàng")
print("  menu:", r.get("result") or r.get("error"))
time.sleep(2)

# New → dialog mở → cancel → verify đóng
bf(action="command", command_name="New")
time.sleep(1.5)
r = bf(action="snapshot")
st = r.get("state") or {}
print("  sau New:", st.get("screen"), "| dialogs:",
      len(st.get("dialogs") or []))

r = bf(action="set_field", field="ma_kh", value="TEST_CANCEL_01")
print("  set_field:", r.get("result") or r.get("error"))

r = bf(action="cancel")
print("  cancel:", r.get("result") or r.get("error"))
time.sleep(1.5)
r = bf(action="snapshot")
st = r.get("state") or {}
dlgs = st.get("dialogs") or []
print("  sau cancel:", st.get("screen"), "| dialogs:", len(dlgs),
      "| grid rows:", (st.get("grid") or {}).get("row_count"))
# cancel mà không confirm → nếu dialog còn là FAIL
if dlgs:
    print("  !! dialog còn — thử confirm yes")
    bf(action="confirm", answer="yes", required=False)

bf(action="close")
print("DONE")
