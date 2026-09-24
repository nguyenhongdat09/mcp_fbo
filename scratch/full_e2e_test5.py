import sys, json, time
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from trace_profile import service as PS
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"

def bf(**kw):
    kw.setdefault("config", cfg)
    t = time.time()
    r = BS.browser_fbo(**kw)
    print(f"== bf.{kw.get('action')} ({time.time()-t:.1f}s) ok={r.get('success')} "
          f"err={str(r.get('error'))[:100]}")
    return r

def pf(**kw):
    kw.setdefault("config", cfg)
    kw.setdefault("file_path", FP)
    t = time.time()
    r = PS.profiler(**kw)
    print(f"== pf.{kw.get('action')} ({time.time()-t:.1f}s) ok={r.get('success')} "
          f"err={str(r.get('error'))[:100]}")
    return r

# 1. profiler start
r = pf(action="start")
tid = (r.get("result") or {}).get("trace_id") or r.get("trace_id")
print("  trace_id:", tid)
if not r.get("success"):
    sys.exit("PROFILER START FAIL")

# 2. browser login + mở danh mục — SQL auth + load danh mục phải bắt được
r = bf(action="login", file_path=FP, user="ADMIN", password="2222222222")
print("  login_as:", (r.get("result") or {}).get("login_as"))
r = bf(action="menu", menu_text="Danh mục khách hàng")
print("  menu:", r.get("result") or r.get("error"))
time.sleep(2)
r = bf(action="command", command_name="Retrieve")
print("  retrieve:", r.get("result") or r.get("error"))
time.sleep(2)

# 3. read trace — classify on
r = pf(action="read", classify=True)
res = r.get("result") or {}
rows = res.get("rows") or res.get("events") or []
print(f"  rows: {len(rows)}")
biz = [x for x in rows if (x.get("tag") or x.get("jev_tag")) == "business"]
print(f"  business-tagged: {len(biz)}")
for x in rows[:3]:
    print("   ", str(x)[:160])

# 4. stop + close
r = pf(action="stop")
print("  stop:", r.get("result") or r.get("error"))
bf(action="close")
print("DONE")
