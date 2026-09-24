"""Conflict test: fastbusiness-mcp (dev) + @playwright/mcp (Microsoft) cùng lúc.

- Spawn CẢ HAI server qua stdio JSON-RPC đồng thời
- tools/list cả hai → check tool name overlap
- Combo thật: profiler start (FBO MCP) → playwright navigate+login → profiler read
"""

import json
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")

PW_CMD = ["node", r"C:\Users\Windows 10\AppData\Roaming\npm\node_modules\@playwright\mcp\cli.js"]
FBO_CMD = [sys.executable, "run_server.py"]
FBO_LOGIN = "http://172.168.5.14/HAOHOA/"


class Mcp:
    def __init__(self, name, cmd, cwd=None):
        self.name = name
        self.responses = {}
        self.lock = threading.Lock()
        self.rid = 0
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", bufsize=1, cwd=cwd)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if "id" in msg:
                with self.lock:
                    self.responses[msg["id"]] = msg

    def rpc(self, method, params=None, timeout=60):
        self.rid += 1
        rid = self.rid
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                if rid in self.responses:
                    return self.responses.pop(rid)
            time.sleep(0.05)
        return {"error": f"TIMEOUT {self.name}.{method}"}

    def call(self, tool, args, timeout=90):
        r = self.rpc("tools/call", {"name": tool, "arguments": args}, timeout)
        try:
            parts = r["result"]["content"]
            return "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
        except Exception:
            return f"<<BAD>> {json.dumps(r, default=str)[:400]}"

    def init(self):
        r = self.rpc("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "conflict-test", "version": "1"}})
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.proc.stdin.flush()
        return r

    def kill(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


PASS, FAIL = [], []
def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {extra if not cond else ''}")


print("=== spawn cả 2 server đồng thời ===")
pw = Mcp("playwright", PW_CMD)
fbo = Mcp("fbo", FBO_CMD, cwd=r"E:\PythonProject\mcp_fbo")

r_pw = pw.init()
r_fbo = fbo.init()
check("playwright init", "result" in r_pw, str(r_pw)[:150])
check("fbo init", "result" in r_fbo, str(r_fbo)[:150])
print("  playwright server:", json.dumps(r_pw.get("result", {}).get("serverInfo", {})))
print("  fbo server:", json.dumps(r_fbo.get("result", {}).get("serverInfo", {})))

pw_tools = {t["name"] for t in pw.rpc("tools/list")["result"]["tools"]}
fbo_tools = {t["name"] for t in fbo.rpc("tools/list")["result"]["tools"]}
overlap = pw_tools & fbo_tools
print(f"  playwright tools ({len(pw_tools)}): {sorted(pw_tools)[:8]}...")
print(f"  fbo tools ({len(fbo_tools)}): {sorted(fbo_tools)}")
check("không trùng tool name", not overlap, str(overlap))

print("\n=== combo: profiler start → playwright navigate+login → profiler read ===")
out = fbo.call("profiler", {"file_path": r"\\172.168.5.14\CustomerPro\FBI\HAOHOA\FBISP2421\Web.config",
                            "action": "start", "db_type": "all",
                            "login_name": "HAOHOA", "duration_minutes": 3})
print(out)
check("profiler start qua MCP", "STARTED" in out, out[:200])

out = pw.call("browser_navigate", {"url": FBO_LOGIN})
check("pw navigate FBO login", "Login" in out or "Fast" in out or "error" not in out.lower(), out[:200])
pw.call("browser_type", {"element": "username", "ref": "#LoginExtender_txtUserName",
                         "text": "admin", "submit": False})
pw.call("browser_press_key", {"key": "Tab"})
time.sleep(1.5)
pw.call("browser_select_option", {"element": "unit", "ref": "#LoginExtender_cboUnit", "values": ["0"]})
pw.call("browser_type", {"element": "password", "ref": "#LoginExtender_txtPassword",
                         "text": "2222222222", "submit": False})
out = pw.call("browser_click", {"element": "login button", "ref": "#LoginExtender_Ok"})
time.sleep(4)
snap = pw.call("browser_snapshot", {})
logged = "Main" in snap or "Trang" in snap or "Phải" in snap
if not logged:  # dialog 'Có' — force login
    pw.call("browser_click", {"element": "Có", "ref": "button.Button"})
    time.sleep(4)
    snap = pw.call("browser_snapshot", {})
    logged = "Main" in snap or "Phải" in snap
check("pw login FBO", logged, snap[:200])

out = fbo.call("profiler", {"file_path": ".", "action": "read", "wait_seconds": 8})
print(out[:1500])
check("profiler bắt được SQL app web", "rows mới" in out and "0 rows mới" not in out,
      out[:200])
check("thấy batch FBO", "BatchStarting" in out or "FastBusiness" in out)

out = fbo.call("profiler", {"file_path": ".", "action": "stop"})
check("profiler stop", "STOPPED" in out, out[:150])

# dọn browser
pw.call("browser_close", {})
pw.kill(); fbo.kill()

print("\n" + "=" * 50)
print(f"RESULT: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL); sys.exit(1)
print("NO CONFLICT — 2 MCP chạy mượt cùng nhau")
