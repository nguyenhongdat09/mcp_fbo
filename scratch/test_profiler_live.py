"""Live test profiler trên 172.168.5.14\\SQL2008 — reproduce FSD Profiler screenshot."""

import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from trace_profile import profiler
from trace_profile.formatter import format_profiler_result

FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\Web.config"
MARKER = "mcp_trace_marker_x9"


def show(r):
    print(format_profiler_result(r))
    print("-" * 70)
    return r


# 1. start
r = show(profiler(FP, action="start", duration_minutes=10))
assert r["success"], r
tid = r["trace_id"]

# 2. bắn lỗi divide by zero bằng user app (giống screenshot) + 1 batch marker
import pyodbc

conn = pyodbc.connect(
    "DRIVER={SQL Server Native Client 11.0};SERVER=172.168.5.14\\SQL2008;"
    "DATABASE=HAOHOA_FBISP2421_A;UID=HAOHOA;PWD=fsd;APP=TEST01;",
    timeout=5,
)
cur = conn.cursor()
cur.execute(f"declare @stt_rec char(13) select @stt_rec='{MARKER}'")
try:
    cur.execute("select 1/0")
except Exception as e:
    print("fired expected:", str(e)[:70])
cur.execute(f"select '{MARKER}_done'")
conn.close()
time.sleep(2)

# 3. read
r = show(profiler(FP, action="read", trace_id=tid))
texts = [row.get("TextData") or "" for row in r.get("rows") or []]
names = [row.get("EventName") for row in r.get("rows") or []]
print("captured events:", names)
assert any(MARKER in t for t in texts), "marker batch not captured!"
assert any("BatchStarting" in (n or "") for n in names)
assert any("Error" in (n or "") for n in names), "error event not captured!"

# 3b. detail mode — đúng event Divide by zero
err_row = next((x for x in r["rows"] if "Divide" in (x.get("TextData") or "")), None)
assert err_row, "no Divide row captured"
r2 = show(profiler(FP, action="read", trace_id=tid, read_mode="detail", seq=err_row["EventSequence"]))
assert "Divide" in (r2["rows"][0].get("TextData") or "")

# 4. stop
r = show(profiler(FP, action="stop", trace_id=tid))
assert r["success"]

# 5. list — trace đã close không còn trong sys.traces
r = show(profiler(FP, action="list"))

# 6. clean (idempotent)
r = show(profiler(FP, action="clean"))

print("ALL LIVE TESTS PASSED")
