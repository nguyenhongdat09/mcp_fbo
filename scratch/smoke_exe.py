import json, subprocess, sys, threading, queue

exe = r"E:\PythonProject\mcp_fbo\dist\fastbusiness_mcp\fastbusiness_mcp.exe"
proc = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, cwd=r"E:\PythonProject\mcp_fbo",
                        text=True, bufsize=1)

q = queue.Queue()
def reader():
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("{"):
            q.put(json.loads(line))
threading.Thread(target=reader, daemon=True).start()

def send(obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()

def recv(timeout=60):
    return q.get(timeout=timeout)

send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2024-11-05",
                 "capabilities": {},
                 "clientInfo": {"name": "smoke", "version": "0"}}})
resp = recv()
print("initialize:", "OK" if resp and resp.get("result") else resp)

send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
resp = recv()
tools = [t["name"] for t in (resp or {}).get("result", {}).get("tools", [])]
print("tools count:", len(tools))
for n in ("browser_fbo", "profiler"):
    print(f"  {n}:", "OK" if n in tools else "MISSING!")

send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "browser_fbo",
                 "arguments": {"action": "status"}}})
resp = recv(120)
content = (resp or {}).get("result", {}).get("content", [])
txt = content[0]["text"] if content else json.dumps(resp)[:400]
print("browser_fbo status:", txt[:400])

proc.terminate()
try:
    proc.wait(timeout=10)
except Exception:
    proc.kill()
