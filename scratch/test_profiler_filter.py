"""Live test: app_name filter — chỉ bắt session có ApplicationName khớp."""

import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from trace_profile import profiler
from trace_profile.formatter import format_profiler_result

FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\Web.config"
MARKER = "mcp_filter_marker"

r = profiler(FP, action="start", app_name="TEST01", duration_minutes=5)
print(format_profiler_result(r))
assert r["success"], r
tid = r["trace_id"]

import pyodbc

def fire(app):
    c = pyodbc.connect(
        "DRIVER={SQL Server Native Client 11.0};SERVER=172.168.5.14\\SQL2008;"
        f"DATABASE=HAOHOA_FBISP2421_A;UID=HAOHOA;PWD=fsd;APP={app};",
        timeout=5,
    )
    c.cursor().execute(f"select '{MARKER}_{app}'")
    c.close()

fire("OTHER_APP")   # không khớp filter → không bắt
fire("TEST01")      # khớp → bắt
time.sleep(2)

r = profiler(FP, action="read", trace_id=tid, since_seq=0)
print(format_profiler_result(r))
texts = " ".join(str(x.get("TextData") or "") for x in r.get("rows") or [])
assert f"{MARKER}_TEST01" in texts, "TEST01 batch not captured"
assert f"{MARKER}_OTHER_APP" not in texts, "OTHER_APP leaked through filter!"
print("APP FILTER OK — OTHER_APP bị loại, TEST01 bắt được")

# errors_only trên trace không filter
r = profiler(FP, action="read", trace_id=tid, since_seq=0, errors_only=True)
err_events = {x.get("EventName") for x in r.get("rows") or []}
assert err_events <= {"Attention", "Audit Login Failed", "Exception", "User Error Message"}, err_events
print("errors_only OK:", err_events)

print(format_profiler_result(profiler(FP, action="stop", trace_id=tid)))
print("FILTER TEST PASSED")
