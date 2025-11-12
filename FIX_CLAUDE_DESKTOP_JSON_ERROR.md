# Fix: Claude Desktop JSON Parsing Error

## Problem

Claude Desktop báo lỗi:
```
SyntaxError: Unexpected non-whitespace character after JSON at position 4 (line 1 column 5)
```

**Cursor work OK** nhưng **Claude Desktop bị lỗi**.

---

## Root Cause

**MCP Protocol Requirements:**
- **stdout** → PURE JSON-RPC messages ONLY
- **stderr** → Logs, debug messages

**Lỗi:** Server logging ra **stdout** thay vì **stderr**
→ Claude Desktop nhận được log text trước JSON
→ JSON parser fail

---

## Solution

### Fixed in this commit! ✅

**File**: `fastbusiness_mcp/utils/logger.py`

**Before** (❌ Wrong):
```python
ch = logging.StreamHandler(sys.stdout)  # ❌ Logs ra stdout
```

**After** (✅ Correct):
```python
ch = logging.StreamHandler(sys.stderr)  # ✅ Logs ra stderr
```

---

## Rebuild Steps

### Option 1: Rebuild onefile
```bash
cd E:\mcp_fbo
git pull origin claude/mcp-pull-fastbusiness-011CUkuccYZCQMezy1RoGUhj
pyinstaller fastbusiness_mcp.spec --clean
```

### Option 2: Rebuild onedir (Recommended)
```bash
cd E:\mcp_fbo
git pull origin claude/mcp-pull-fastbusiness-011CUkuccYZCQMezy1RoGUhj
build_onedir.bat
```

---

## Test After Rebuild

### Test 1: Check stdout/stderr
```bash
# Run server and check output
E:\mcp_fbo\dist\fastbusiness_mcp\fastbusiness_mcp.exe

# Should see:
# - JSON messages on screen (from stdout)
# - No log text before JSON
```

### Test 2: Claude Desktop Config

**File**: `%APPDATA%\Roaming\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "fastbusiness-mcp": {
      "command": "E:\\mcp_fbo\\dist\\fastbusiness_mcp\\fastbusiness_mcp.exe",
      "args": [],
      "cwd": "E:\\mcp_fbo\\dist\\fastbusiness_mcp",
      "env": {
        "FASTBUSINESS_VSCODE_DB_PATH": "E:\\mcp_fbo\\dist\\fastbusiness_mcp\\data\\fields_lmdb",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

**Important**:
- ✅ Use `args: []` (empty array)
- ✅ Add `PYTHONIOENCODING: "utf-8"` for encoding
- ✅ Use absolute paths

### Test 3: Restart Claude Desktop

1. Close Claude Desktop completely
2. Reopen
3. Check MCP server status
4. Should see: ✅ Connected

---

## Verify Fix

### Check Logs Location

**Claude Desktop logs**: `%APPDATA%\Roaming\Claude\logs\mcp*.log`

```bash
# View latest log
type "%APPDATA%\Roaming\Claude\logs\mcp-server-fastbusiness-mcp.log"
```

**Should see**:
- ✅ Server connected successfully
- ✅ No JSON parsing errors
- ✅ Tools listed correctly

---

## Why Cursor Works but Claude Desktop Doesn't?

| Feature | Cursor | Claude Desktop |
|---------|--------|----------------|
| **stdout handling** | Tolerant (strips logs) | Strict (pure JSON only) |
| **Error handling** | Permissive | Strict |
| **MCP compliance** | Loose | Full compliance |

→ Claude Desktop requires **strict MCP protocol compliance**

---

## Technical Explanation

### MCP Protocol (JSON-RPC over stdio)

```
stdout: {"jsonrpc":"2.0","id":0,...}     ← PURE JSON
        {"jsonrpc":"2.0","id":1,...}     ← PURE JSON

stderr: 2025-11-12 | INFO | Server started   ← Logs OK here
        2025-11-12 | DEBUG | Processing...   ← Logs OK here
```

**If logs go to stdout**:
```
stdout: 2025-11-12 | INFO | Server started   ← ❌ Breaks JSON parser!
        {"jsonrpc":"2.0","id":0,...}         ← Parser fails here
```

→ Claude Desktop tries to parse log line as JSON → Error!

---

## Common Mistakes

### ❌ Wrong:
```python
# Don't use print() without file=sys.stderr
print("Log message")  # ❌ Goes to stdout

# Don't use logging with stdout handler
logging.StreamHandler(sys.stdout)  # ❌ Wrong
```

### ✅ Correct:
```python
# Use logger (configured with stderr)
logger.info("Log message")  # ✅ Goes to stderr

# Or use print with stderr
print("Log message", file=sys.stderr)  # ✅ Goes to stderr

# Configure logging with stderr
logging.StreamHandler(sys.stderr)  # ✅ Correct
```

---

## Checklist

After rebuild, verify:

- [ ] Pull latest code with fix
- [ ] Rebuild .exe
- [ ] Test .exe runs without errors
- [ ] Configure Claude Desktop
- [ ] Restart Claude Desktop
- [ ] Check MCP server connects
- [ ] No JSON parsing errors in logs
- [ ] Tools list appears correctly

---

## Support

If still failing:

1. **Check config path**:
   - Claude Desktop: `%APPDATA%\Roaming\Claude\claude_desktop_config.json`
   - NOT in User folder

2. **Check logs**:
   ```bash
   type "%APPDATA%\Roaming\Claude\logs\mcp-server-fastbusiness-mcp.log"
   ```

3. **Check stderr output**:
   - All logs should be in Claude Desktop logs
   - Not mixed with JSON messages

4. **Rebuild clean**:
   ```bash
   rmdir /s /q build dist
   pyinstaller fastbusiness_mcp.spec --clean
   ```

---

## References

- MCP Protocol: https://modelcontextprotocol.io/
- JSON-RPC spec: https://www.jsonrpc.org/specification
- Python logging: https://docs.python.org/3/library/logging.html

---

## Fixed Files

✅ `fastbusiness_mcp/utils/logger.py` - Changed stdout → stderr
✅ All logging now goes to stderr
✅ stdout reserved for pure JSON-RPC only
✅ Claude Desktop compatible
