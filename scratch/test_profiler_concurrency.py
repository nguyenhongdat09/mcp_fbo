"""Test bất đồng bộ/concurrency cho tool `profiler`:

A) Gọi qua MCP stdio thật (JSON-RPC vào run_server.py)
B) Nhiều thread cùng gọi profiler_tool (MCP dispatch song song)
C) 2 process riêng (2 MCP server) đua trên cùng registry file
D) profiler đua với tool khác (read_local_file)

Chạy: PYTHONPATH=. python -X utf8 scratch/test_profiler_concurrency.py
"""

import json
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import pyodbc

FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\Web.config"
DB = "HAOHOA_FBISP2421_A"
MARK = "ccy"

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {extra if not cond else ''}")


def fire(sql_text, app="AGENTTEST"):
    c = pyodbc.connect(
        "DRIVER={SQL Server Native Client 11.0};SERVER=172.168.5.14\\SQL2008;"
        f"DATABASE={DB};UID=HAOHOA;PWD=fsd;APP={app};", timeout=5)
    try:
        c.cursor().execute(sql_text)
    except Exception:
        pass
    c.close()


def reg_ok():
    try:
        json.loads(open(r"C:\Users\Windows 10\AppData\Local\Temp\fbo_mcp_trace_registry.json",
                        encoding="utf-8").read())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
print("=== A) MCP stdio THẬT — initialize → tools/list → tools/call profiler ===")
proc = subprocess.Popen(
    [sys.executable, "run_server.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    text=True, encoding="utf-8", errors="replace", bufsize=1,
)
responses = {}
_lock = threading.Lock()


def reader():
    for line in proc.stdout:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if "id" in msg:
            with _lock:
                responses[msg["id"]] = msg


threading.Thread(target=reader, daemon=True).start()
_req = 0


def rpc(method, params=None, timeout=60):
    global _req
    _req += 1
    rid = _req
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid,
                                 "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    t0 = time.time()
    while time.time() - t0 < timeout:
        with _lock:
            if rid in responses:
                return responses.pop(rid)
        time.sleep(0.05)
    return {"error": "TIMEOUT"}


def call(name, args, timeout=60):
    r = rpc("tools/call", {"name": name, "arguments": args}, timeout)
    try:
        return r["result"]["content"][0]["text"]
    except Exception:
        return f"<<BAD>> {json.dumps(r)[:300]}"


rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "ccy-test", "version": "1"}})
proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
proc.stdin.flush()

r = rpc("tools/list")
tools = [t["name"] for t in r.get("result", {}).get("tools", [])]
check("stdio tools/list có profiler", "profiler" in tools, str(tools))
schema = [t for t in r["result"]["tools"] if t["name"] == "profiler"][0]
props = schema["inputSchema"].get("properties", {})
check("schema có đủ params", all(k in props for k in
      ("action", "trace_id", "app_name", "errors_only", "wait_seconds")), str(props.keys()))

out = call("profiler", {"file_path": FP, "action": "start", "duration_minutes": 3})
print(out)
check("stdio start", "STARTED" in out, out[:200])
tid_mcp = int(out.split("#")[1].split(" ")[0])

fire(f"select '{MARK}_stdio'")
time.sleep(2)
out = call("profiler", {"file_path": ".", "action": "read"})
print(out)
check("stdio read bắt được batch", f"{MARK}_stdio" in out, out[:250])
out = call("profiler", {"file_path": ".", "action": "stop", "trace_id": tid_mcp})
check("stdio stop", "STOPPED" in out, out[:150])

# ---------------------------------------------------------------------------
print("\n=== B) Nhiều thread đua trong 1 process (MCP dispatch song song) ===")
from fastbusiness_mcp.mcp_app import profiler_tool, read_local_file_tool

# B1: 5 start đồng thời
with ThreadPoolExecutor(5) as ex:
    outs = list(ex.map(lambda i: profiler_tool(
        FP, action="start", duration_minutes=5, app_name="AGENTTEST"), range(5)))
tids = set()
for o in outs:
    if "STARTED" in o:
        tids.add(int(o.split("#")[1].split(" ")[0]))
check("5 start đồng thời → 5 trace_id khác nhau", len(tids) == 5, str(tids))
main_tid = sorted(tids)[0]
time.sleep(1)
for i in range(6):
    fire(f"select '{MARK}_thr{i}'")
time.sleep(2)

# B2: 8 read đồng thời trên cùng trace — không crash, không exception
def do_read(i):
    try:
        return profiler_tool(".", action="read", trace_id=main_tid, since_seq=0,
                             max_rows=100)
    except Exception as e:
        return f"<<EXC>> {e}"

with ThreadPoolExecutor(8) as ex:
    outs = list(ex.map(do_read, range(8)))
check("8 read đồng thời: tất cả [OK] không exception",
      all(o.startswith("[OK]") for o in outs),
      str([o[:80] for o in outs if not o.startswith("[OK]")])[:300])
check("các read đều thấy marker", all(f"{MARK}_thr" in o for o in outs))

# B3: read đua với stop (race) — không crash dù ai thắng
results = {}
def race_read():
    results["read"] = profiler_tool(".", action="read", trace_id=main_tid)
def race_stop():
    results["stop"] = profiler_tool(".", action="stop", trace_id=main_tid)
t1 = threading.Thread(target=race_read)
t2 = threading.Thread(target=race_stop)
t1.start(); t2.start(); t1.join(); t2.join()
check("read+stop race không exception",
      all(not v.startswith("<<") for v in results.values()),
      str({k: v[:80] for k, v in results.items()}))

# B4: 3 wait_seconds đồng thời + fire giữa chừng
def waiter(i):
    return profiler_tool(".", action="read", trace_id=sorted(tids)[1],
                         wait_seconds=8)
def late_fire():
    time.sleep(2); fire(f"select '{MARK}_waitall'")
with ThreadPoolExecutor(3) as ex:
    threading.Thread(target=late_fire, daemon=True).start()
    outs = list(ex.map(waiter, range(3)))
check("3 waiter cùng poll — đều trả về bounded", all(o.startswith("[OK]") for o in outs))
print(f"    waiter results: {[o.splitlines()[0][:60] for o in outs]}")

# B5: clean đồng thời 2 thread
with ThreadPoolExecutor(2) as ex:
    outs = list(ex.map(lambda i: profiler_tool(
        ".", action="clean", include_running=True), range(2)))
check("2 clean đồng thời không exception", all("[OK]" in o for o in outs))

check("registry json vẫn valid sau storm", reg_ok())

# ---------------------------------------------------------------------------
print("\n=== C) 2 process riêng đua (2 MCP server cùng lúc) ===")
CHILD = r'''
import sys, time, json
sys.path.insert(0, ".")
sys.path.insert(0, r"E:\PythonProject\mcp_fbo")
import pyodbc
from trace_profile import profiler
from trace_profile import service as svc
FP = r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\Web.config"
tag = sys.argv[1]
r = profiler(FP, action="start", duration_minutes=3, app_name="AGENTTEST")
assert r["success"], r
tid = r["trace_id"]
c = pyodbc.connect("DRIVER={SQL Server Native Client 11.0};SERVER=172.168.5.14\\SQL2008;"
    f"DATABASE=HAOHOA_FBISP2421_A;UID=HAOHOA;PWD=fsd;APP=AGENTTEST;", timeout=5)
c.cursor().execute(f"select 'ccy_{tag}'")
c.close()
# hammer save registry đua với process kia
for i in range(40):
    svc._save_registry()
    time.sleep(0.01)
time.sleep(2)
r = profiler(FP, action="read", trace_id=tid, since_seq=0)
ok = f"ccy_{tag}" in json.dumps(r, default=str)
r2 = profiler(FP, action="stop", trace_id=tid)
print(f"CHILD {tag}: captured={ok} stopped={r2.get('success')}")
'''
procs = [subprocess.Popen([sys.executable, "-X", "utf8", "-c", CHILD, f"proc{i}"],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace",
                          cwd=r"E:\PythonProject\mcp_fbo")
         for i in range(2)]
outs = [p.communicate(timeout=120)[0] for p in procs]
for i, o in enumerate(outs):
    print("   ", o.strip()[:200])
    check(f"process {i}: capture + stop độc lập", "captured=True" in o and "stopped=True" in o,
          o[:200])
check("registry json valid sau 2-process storm", reg_ok())

# ---------------------------------------------------------------------------
print("\n=== D) profiler đua với tool khác (read_local_file) ===")
def other_tool(i):
    try:
        return read_local_file_tool(FP, read_option=1)
    except Exception as e:
        return f"<<EXC>> {e}"

with ThreadPoolExecutor(4) as ex:
    outs = list(ex.map(lambda i: (profiler_tool(".", action="list"),
                                  other_tool(i)), range(4)))
ok = all("[OK]" in a and not b.startswith("<<EXC>>") for a, b in outs)
check("profiler+read_local_file đồng thời không crash", ok,
      str(outs[0][1])[:150] if outs else "")

# dọn nốt + dừng server stdio
profiler_tool(".", action="clean", include_running=True)
try:
    proc.terminate()
except Exception:
    pass

print("\n" + "=" * 50)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
print("ALL CONCURRENCY TESTS PASSED")
