"""Profiler isolated e2e: start -> traffic -> read -> stop."""
import sys, time, json
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
from trace_profile.service import profiler as PROF
from fastbusiness_mcp.mcp_app import get_config

cfg = get_config()
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\App_Data\Controllers\x.ent"

def pf(**kw):
    t0 = time.time()
    r = PROF(file_path=FP, config=cfg.get("profiler"),
             classify_key=(cfg.get("api_key") or {}).get("Jev", ""),
             classify_config=cfg.get("jev"), **kw)
    print(f"== {kw.get('action')} ({time.time()-t0:.1f}s) ok={r.get('success')} err={str(r.get('error'))[:120]}")
    return r

r = pf(action="start", db_type="all", events="standard", exclude_self=False)
tid = r.get("trace_id")
print("  trace:", tid, "| path:", r.get("path"), "| filters:", r.get("filters"), "| warns:", r.get("warnings"))

# Tạo traffic SQL thật trên đúng server — query_database qua MCP-equivalent path
# (dùng query trực tiếp qua module nội bộ để chắc chắn traffic tới server)
from fastbusiness_mcp import mcp_app
r2 = mcp_app.query_database(file_path=FP, query="SELECT TOP 3 ma_kh, ten_kh FROM dmkh", query_type=1)
print("== query_database ok:", "dmkh" in str(r2).lower() or "ma_kh" in str(r2).lower())

time.sleep(3)
r = pf(action="read", trace_id=tid or 0, since_seq=0, max_rows=50)
rows = r.get("rows") or []
print("  rows:", len(rows), "| new:", r.get("new_rows"), "| warns:", r.get("warnings"))
for e in rows[:12]:
    print("   -", e.get("EventName"), "|", str(e.get("TextData"))[:80])

# read với classify
r = pf(action="read", trace_id=tid or 0, since_seq=0, max_rows=20, classify=True)
rows = r.get("rows") or []
print("  classified rows:", len(rows))
for e in rows[:8]:
    print("   -", e.get("EventName"), "| tag:", e.get("tag"), e.get("tag_conf"), "|", str(e.get("TextData"))[:60])

r = pf(action="stop", trace_id=tid or 0)
print("  stopped:", r.get("success"))
print("DONE")
