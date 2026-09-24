import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from browser_fbo import service as BS
from trace_profile import service as PS
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\Report\Config\MRTran.ent"

# đóng browser cũ trước cho chắc
BS.browser_fbo(action="close", config=cfg)

r = PS.profiler(file_path=FP, action="start", db_type="all", config=cfg)
tid = r.get("trace_id")
print("trace:", tid)

r = BS.browser_fbo(action="login", file_path=FP, user="ADMIN",
                   password="2222222222", config=cfg)
print("login:", r.get("success"), (r.get("result") or {}).get("login_as"),
      "| err:", r.get("error"))
if not r.get("success"):
    sys.exit("LOGIN FAIL")

r = BS.browser_fbo(action="menu", menu_text="Danh mục khách hàng", config=cfg)
print("menu:", r.get("result") or r.get("error"))
time.sleep(3)
r = BS.browser_fbo(action="command", command_name="Retrieve", config=cfg)
print("retrieve:", r.get("result") or r.get("error"))
time.sleep(3)

r = PS.profiler(file_path=FP, action="read", trace_id=tid, since_seq=-1,
                config=cfg, max_rows=500)
rows = r.get("rows") or []
print(f"\nread: {len(rows)} rows")
# chỉ quan tâm events của HAOHOA
hh = [x for x in rows if "HAOHOA" in str(x.get("DatabaseName") or "")]
print("HAOHOA events:", len(hh))
dbs = {}
for x in hh:
    d = x.get("DatabaseName") or "?"
    dbs[d] = dbs.get(d, 0) + 1
print("HAOHOA DatabaseName dist:", dbs)
for x in hh[:12]:
    print("  ", x.get("DatabaseName"), "|", x.get("EventName"), "|",
          str(x.get("TextData"))[:90].replace("\n", " "))

PS.profiler(file_path=FP, action="stop", trace_id=tid, config=cfg)
BS.browser_fbo(action="close", config=cfg)
print("DONE")
