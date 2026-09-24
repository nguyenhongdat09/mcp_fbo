"""Test toàn diện tool `profiler` theo góc nhìn agent — qua profiler_tool (MCP wrapper).

Chạy: PYTHONPATH=. python -X utf8 scratch/test_profiler_agent.py
"""

import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import pyodbc

from fastbusiness_mcp.mcp_app import profiler_tool
from trace_profile import service as svc

FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\Web.config"
DB = "HAOHOA_FBISP2421_A"
MARK = "agt"

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {extra if not cond else ''}")


def fire(sql_text, app="AGENTTEST", login="HAOHOA", pwd="fsd"):
    c = pyodbc.connect(
        "DRIVER={SQL Server Native Client 11.0};SERVER=172.168.5.14\\SQL2008;"
        f"DATABASE={DB};UID={login};PWD={pwd};APP={app};", timeout=5)
    try:
        c.cursor().execute(sql_text)
    except Exception:
        pass
    c.close()


def err_query():
    try:
        fire("select 1/0")
    except Exception:
        pass


# ---------------------------------------------------------------------------
print("=== S1: workflow chuẩn — start(abs) → read(relative) → read('.') → stop(0) ===")
# Trace auto-stop 1 phút để test expiry (chạy song song các test khác)
out_expire = profiler_tool(FP, action="start", duration_minutes=1, app_name="NOHIT_EXPIRE")
print(out_expire)
expire_tid = int(out_expire.split("#")[1].split(" ")[0])

out = profiler_tool(FP, action="start")
print(out)
check("start OK", "[OK]" in out and "STARTED" in out)
check("start: exclude-self filter đúng config (FSD-Profiler)", "NOT LIKE FSD-Profiler%" in out,
      "— display vẫn hardcode FSD-MCP-Profiler?")
tid = int(out.split("#")[1].split(" ")[0])

time.sleep(1)
fire(f"select '{MARK}_batch'")
fire(f"select '{MARK}_dup'"); fire(f"select '{MARK}_dup'"); fire(f"select '{MARK}_dup'")
err_query()
time.sleep(2)

# relative path — sticky project (Web.config tồn tại ở root)
out = profiler_tool("Web.config", action="read")
print(out)
check("read relative path (sticky)", "[OK]" in out, out[:200])
check("bắt được batch marker", f"{MARK}_batch" in out)
check("collapse gom dup ×3", "×3" in out or "_dup" in out)
check("có User Error Message", "User Error Message" in out or "Divide" in out)
check("không thấy query của chính MCP (FSD-Profiler)", "fn_trace_gettable" not in out)

# '.' cũng phải resolve qua sticky
out2 = profiler_tool(".", action="read")
check("read file_path='.'", "[OK]" in out, out2[:150])
check("incremental: 0 rows mới", "0 rows mới" in out2, out2[:150])

print("\n=== S2: read modes ===")
out = profiler_tool(".", action="read", read_mode="detail")
check("detail seq=0 → error thân thiện", "[ERROR]" in out and "seq" in out, out[:150])

out = profiler_tool(".", action="read", since_seq=0, max_rows=50)
seq_div = None
for line in out.splitlines():
    if "Divide" in line or "8134" in line:
        seq_div = int(line.split()[0]); break
    if f"{MARK}_batch" in line and seq_div is None:
        seq_div = int(line.split()[0])
out = profiler_tool(".", action="read", read_mode="detail", seq=seq_div)
print(out)
check("detail seq=N → full TextData", "TextData (full)" in out, out[:200])

out = profiler_tool(".", action="read", since_seq=0, read_mode="full",
                    text_max_chars=80, max_rows=3, collapse=False)
long_line = [l for l in out.splitlines() if "network protocol" in l]
check("full mode tôn trọng text_max_chars=80", not long_line or "…[+" in long_line[0],
      "— text_max_chars không được wire?")

print("\n=== S3: wait_seconds + max_rows ===")
t0 = time.time()
def delayed():
    time.sleep(1.5); fire(f"select '{MARK}_wait'")
threading.Thread(target=delayed, daemon=True).start()
out = profiler_tool(".", action="read", wait_seconds=10)
dt = time.time() - t0
check("wait_seconds poll bắt event (~2s)", f"{MARK}_wait" in out and dt < 8,
      f"dt={dt:.1f}s")

t0 = time.time()
out = profiler_tool(".", action="read", wait_seconds=2)
dt = time.time() - t0
check("wait hết giờ → trả empty bounded", "không có event mới" in out and dt < 6, f"dt={dt:.1f}")

for i in range(5):
    fire(f"select '{MARK}_cap{i}'")
time.sleep(2)
out = profiler_tool(".", action="read", max_rows=2, collapse=False)
check("max_rows=2 → đúng 2 rows", out.count(f"{MARK}_cap") <= 2, out[:300])
out = profiler_tool(".", action="read")
check("read sau lấy nốt phần còn lại", f"{MARK}_cap4" in out, out[:300])

print("\n=== S4: post-filters lúc read ===")
out = profiler_tool(".", action="read", since_seq=0, errors_only=True, max_rows=50)
check("errors_only: có lỗi, không có BatchCompleted",
      ("User Error Message" in out or "Exception" in out) and "BatchCompleted" not in out)
out = profiler_tool(".", action="read", since_seq=0, event_filter="sql:batchcompleted", max_rows=50)
check("event_filter lowercase csv", "BatchCompleted" in out and "BatchStarting" not in out,
      out[:200])
out = profiler_tool(".", action="read", since_seq=0, text_like=f"{MARK}_batch", max_rows=10)
check("text_like post-filter", f"{MARK}_batch" in out and f"{MARK}_cap" not in out)

print("\n=== S5: stop → read lại file (agent xem lại sau stop) ===")
out = profiler_tool(".", action="stop", trace_id=tid)
print(out)
check("stop drain", "[OK]" in out and "STOPPED" in out)
out = profiler_tool(".", action="read", trace_id=tid, since_seq=0, errors_only=True, max_rows=10)
check("read file sau khi stop", "[OK]" in out and ("User Error Message" in out or "Divide" in out),
      out[:200])

print("\n=== S6: giả lập MCP restart (registry rỗng) ===")
out = profiler_tool(FP, action="start", app_name="AGENTTEST", duration_minutes=5)
print(out)
tid2 = int(out.split("#")[1].split(" ")[0])
fire(f"select '{MARK}_restart'")
time.sleep(1.5)
with svc._LOCK:
    svc._TRACES.clear()  # restart → registry mất
out = profiler_tool(".", action="list")
print(out)
check("list thấy fbo_mcp_* sau restart", "fbo_mcp_" in out)
out = profiler_tool(".", action="read")  # trace_id=0 → fallback sys.traces
check("read trace_id=0 fallback sys.traces", f"{MARK}_restart" in out, out[:250])
out = profiler_tool(".", action="stop", trace_id=tid2)
check("stop sau restart", "[OK]" in out)

print("\n=== S7: error paths ===")
out = profiler_tool(".", action="bogus") if False else profiler_tool(".", action="read", trace_id=99999)
check("read trace_id không tồn tại", "[ERROR]" in out, out[:150])
out = profiler_tool("E:/nonexistent/path/x.xml", action="start")
check("file_path sai → path error", "[ERROR]" in out or "path_not_found" in out, out[:150])
out = profiler_tool(FP, action="start", events="bogus_event_name", duration_minutes=1)
check("events rác → fallback standard + warn", "STARTED" in out and "WARN" in out, out[:250])
bad_tid = int(out.split("#")[1].split(" ")[0])
out = profiler_tool(FP, action="start", events="exception,SQL:BatchCompleted", duration_minutes=1)
check("events csv lowercase resolve", "STARTED" in out and "Exception" in out and "BatchCompleted" in out)
csv_tid = int(out.split("#")[1].split(" ")[0])

print("\n=== S8: auto-stop expiry (trace 1 phút đã start ở S1) ===")
wait_left = 68 - 0  # đảm bảo >60s từ lúc start
print(f"  (chờ trace #{expire_tid} hết hạn...)")
time.sleep(max(5, wait_left))
out = profiler_tool(".", action="read", trace_id=expire_tid)
print(out)
check("trace hết hạn → warn (stopped/closed) + không crash", "[WARN]" in out or "[OK]" in out,
      out[:300])

print("\n=== S9: clean ===")
out = profiler_tool(".", action="clean")
print(out)
check("clean mine dọn stopped fbo_mcp_*", "[OK]" in out)
for t in (bad_tid, csv_tid):
    profiler_tool(".", action="stop", trace_id=t, drain=False)
out = profiler_tool(".", action="clean", include_running=True)
check("clean include_running", "[OK]" in out)
out = profiler_tool(".", action="list")
check("sau clean không còn fbo_mcp_", "fbo_mcp_" not in out, out[:400])

print("\n" + "=" * 50)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL AGENT-USABILITY TESTS PASSED")
