# FSPEC / PROMPT — Fix sau review: sync-build Kuzu MCP (P0 marker treo + stdout MCP)

> **Cách dùng:** Copy mục «PROMPT GỬI GEMINI» gửi Gemini kèm repo `mcp_fbo`.
>
> **Bối cảnh:** Task khôi phục sync-build (`docs/doc/fbograph_mcp_restore_sync_build_kuzu.md`) đã làm xong. Review + unittest:
> - `py -m unittest xml_fbograph.tests.test_customerpro_kuzu_gate -v` → **17/17 OK** (mock, không bắt được bug runtime).
> - Logic chính (`ensure_mcp_kuzu_ready` → `_sync_build_kuzu_in_mcp` → `build_and_save_graph`) **đúng hướng**.
> - Còn **2 lỗi P0/P1** và vài P2 phải sửa trước khi dùng thật với `query_radar`.

---

## Kết quả review (ngắn)

| Mức | Vấn đề | Ảnh hưởng |
|---|---|---|
| **P0** | Marker `.building` legacy (`pid=0` hoặc pid chết) vẫn được coi “đang build” nếu age < 45 phút → `ensure_mcp_kuzu_ready` **poll chờ tới 45 phút** rồi mới sync-build | Sau upgrade, project từng trả `build_cmd` (marker pid=0 còn trên đĩa) → `query_radar` **treo** |
| **P1** | `build_and_save_graph` dùng `print()` → **stdout** (`[TIMING]`, `[FBOGraph] Parsing...`) | MCP stdio JSON-RPC bị phá khi cold-start `query_radar` |
| **P1** | Cùng process, request 2 thấy `pid == os.getpid()` → **bỏ wait**, gọi `_sync_build_kuzu_in_mcp` lần 2 | Double-build / lock Kuzu nếu 2 tool call chồng |
| **P2** | `.cursorrules` Agent habit vẫn bảo dùng `search_nodes` / `get_related_nodes` (tool đã ẩn) | Agent gọi tool không tồn tại |
| **P2** | Docstring module `kuzu_build_spawn.py` + comment `engine.py` vẫn viết “spawn detached / không sync-build”; `_write_building_marker` còn field `build_cmd` | Gây hiểu nhầm / leak marker |

**Không revert** sync-build. Chỉ vá các lỗ hổng trên.

---

## P0 — Marker stale treo 45 phút (chi tiết)

### Code hiện tại

`xml_fbograph/utils/kuzu_build_spawn.py` → `is_building_in_progress`:

```python
pid = int(data.get("pid") or 0)
started_at = float(data.get("started_at") or 0.0)
age = time.time() - started_at if started_at else BUILDING_MARKER_MAX_AGE_SEC + 1
if _pid_alive(pid) or age < BUILDING_MARKER_MAX_AGE_SEC:
    return data   # ← pid=0 (chết) + age < 45p vẫn “in progress”
```

`_pid_alive(0)` = False, nhưng `age < 45*60` vẫn True.

`ensure_mcp_kuzu_ready`:

```python
existing_marker = is_building_in_progress(graph_dir)
if existing_marker and existing_marker.get("pid") != os.getpid():
    # pid=0 != getpid() → vào nhánh WAIT
    while is_building_in_progress(graph_dir):
        time.sleep(2)
        ...
        if time.time() - start_wait > BUILDING_MARKER_MAX_AGE_SEC:
            break
```

### Vì sao xảy ra sau upgrade

Cách cũ (ủy thác Agent) ghi marker:

```json
{ "pid": 0, "started_at": ..., "build_cmd": "....exe build ..." }
```

Nhiều project CustomerPro **còn file** `C:/KuzuDB/<base64>/.fbograph/.building` pid=0. Lần `query_radar` đầu sau sync-build sẽ **sleep 2s × ~1350 lần ≈ 45 phút** rồi mới build.

### Hành vi bắt buộc sau fix

`is_building_in_progress` **chỉ** return marker khi `pid > 0` **và** `_pid_alive(pid)`:

- `pid == 0` (legacy agent-delegate) → `clear_building_marker` ngay → return None → **sync-build ngay**.
- pid chết (MCP crash giữa chừng) → xóa marker → sync-build ngay.
- pid sống + khác `os.getpid()` → mới được wait/poll (process khác đang build thật).
- Bỏ điều kiện `age < BUILDING_MARKER_MAX_AGE_SEC` như lý do “còn sống”. Age chỉ dùng timeout khi **đang wait pid sống** (tránh wait vô hạn nếu `_pid_alive` false-positive trên Windows).

`ensure_mcp_kuzu_ready` wait loop:

- Chỉ vào wait nếu marker pid sống và `pid != os.getpid()`.
- Mỗi vòng: nếu pid chết hoặc marker mất → break, sync-build (nếu kuzu chưa ready).
- Timeout wait vẫn `BUILDING_MARKER_MAX_AGE_SEC`, nhưng **không** áp dụng cho pid=0.

### Test bắt buộc (P0)

Thêm trong `xml_fbograph/tests/test_customerpro_kuzu_gate.py`:

**`test_stale_pid0_marker_does_not_wait_sync_builds_immediately`**

1. Fixture Controllers + `reference_file` abs như các test gate khác.
2. Tạo `graph_dir / ".building"` JSON: `{"pid": 0, "started_at": time.time(), "build_cmd": "legacy.exe build X"}` (giả lập marker cũ).
3. Mock `build_and_save_graph` side_effect tạo dummy `graph_dir/kuzu/data.bin`.
4. Mock `time.sleep` (assert **không** bị gọi, hoặc call_count == 0) — nếu wait 45p test sẽ timeout.
5. `ensure_mcp_kuzu_ready(ref)` return `db_path` trong < vài giây.
6. `build_and_save_graph` gọi đúng 1 lần.
7. Marker `.building` bị xóa sau cùng.
8. Payload lỗi (nếu có) không chứa `build_cmd` hướng dẫn Agent.

**`test_dead_pid_marker_cleared_then_sync_build`** (khuyến nghị)

- Marker `pid=999999` (không sống) + `started_at` mới.
- Patch `_pid_alive` return False.
- Không wait; sync-build 1 lần; marker xóa.

---

## P1 — `print()` phá stdout MCP khi sync-build

### Code

`xml_fbograph/builder/graph_builder.py` → `GraphBuilder.build` / `build_and_save_graph` gọi `print(...)` nhiều chỗ:

- `[TIMING] walk+stat / parse / edges / kuzu write`
- `[FBOGraph] Parsing N new/changed files...`
- `[FBOGraph] extract_options.shared_include=...`

Thanh parse `\r[FBOGraph] Parse [...]` đã ghi **stderr** (OK). Các `print()` mặc định = **stdout**.

MCP server chạy stdio (`fastbusiness_mcp/server.py` → `stdio_server`). Mọi byte stdout xen vào JSON-RPC → Cursor/client parse fail, Agent thấy tool error dù Kuzu build xong.

`_sync_build_kuzu_in_mcp` hiện gọi:

```python
build_and_save_graph(helper.get_controllers_path(), graph_dir, project_label=project_root)
```

Không `progress`, không redirect stdout.

### Fix bắt buộc (chỉ trong MCP sync-build, đừng phá CLI)

Trong `_sync_build_kuzu_in_mcp`, bọc:

```python
import contextlib
with contextlib.redirect_stdout(sys.stderr):
    build_and_save_graph(
        helper.get_controllers_path(),
        graph_dir,
        project_label=project_root,
    )
```

Hoặc `progress` no-op ghi stderr — không bắt buộc nếu đã redirect stdout.

**Không** đổi hàng loạt `print` → `stderr` trong `graph_builder.py` trừ khi cần (CLI `fbograph` vẫn dùng stdout bình thường).

Không cần test MCP stdio thật. Comment ngắn tiếng Việt trên redirect: *tránh phá JSON-RPC MCP*.

---

## P1 — Cùng process double-build

### Code

```python
if existing_marker and existing_marker.get("pid") != os.getpid():
    # wait
...
_sync_build_kuzu_in_mcp(...)  # pid == self → không wait → build lần 2
```

Marker ghi `pid=os.getpid()`. Thread/request 2 trong **cùng MCP process** thấy pid trùng → bỏ wait → 2 `build_and_save_graph` song song → lock Kuzu / DB hỏng.

Stdio MCP thường tuần tự, nhưng `Server` là async — vẫn phải khóa.

### Fix

Thêm `threading.Lock` theo `graph_dir` (dict + lock tạo lock):

```python
# module-level
_sync_build_locks: dict[str, threading.Lock] = {}
_sync_build_locks_guard = threading.Lock()

def _graph_build_lock(graph_dir: Path) -> threading.Lock:
    key = str(graph_dir)
    with _sync_build_locks_guard:
        lock = _sync_build_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _sync_build_locks[key] = lock
        return lock
```

Trong `ensure_mcp_kuzu_ready`, sau validate + (optional) wait pid **process khác**:

```python
lock = _graph_build_lock(graph_dir)
with lock:
    if kuzu_db_ready(db_path):
        clear_building_marker(graph_dir)
        return db_path
    try:
        _sync_build_kuzu_in_mcp(reference_file, graph_dir)
    except Exception as e:
        ...
    if not kuzu_db_ready(db_path):
        raise KuzuBuildFailedError(...)
    clear_building_marker(graph_dir)
    return db_path
```

Double-check `kuzu_db_ready` **sau khi acquire lock** (thread kia có thể vừa build xong).

Test khuyến nghị: 2 thread cùng `ensure_mcp_kuzu_ready` + mock build sleep 0.2s rồi tạo kuzu → `build_and_save_graph.call_count == 1`.

---

## P2 — `.cursorrules` Agent habit còn tool đã ẩn

File `.cursorrules` section FBOGraph tools đã đúng (`query_radar`, `read_local_file`), nhưng **Agent habit** vẫn:

```text
- Chưa biết file → `search_nodes` → `get_related_nodes` navigate
- `search_nodes` query: **ưu tiên KHÔNG DẤU** ...
```

3 tool đó **đã ẩn**. Agent sẽ gọi tool không có trong `list_tools`.

Sửa habit thành dùng `query_radar` (Template Cypher trong rules), ví dụ:

```text
## Agent habit
- Chưa biết file → query_radar (Template 1 / 5 / 11), KHÔNG gọi search_nodes / get_related_nodes / query_node_details (đã ẩn).
- Entity Include → get_xml_entities; schema DB → query_database
- Thấy needs_xml / .f → đừng cố đọc XML mã hóa
- Keyword search qua query_radar: ưu tiên KHÔNG DẤU
  - giay bao no → CPTran | phieu chi → CDTran
  - dien giai → dien_giai | ten hang hoa → ten_vt | gia ban → gia2
```

Giữ nguyên block `reference_file` + “MCP tự sync-build” đã có.

---

## P2 — Dọn docstring / marker `build_cmd` / import chết

1. `xml_fbograph/utils/kuzu_build_spawn.py` dòng 1–3:
   - Đổi docstring: *Gate MCP: validate reference_file + sync-build Kuzu in-process khi thiếu DB. Không spawn detached, không trả build_cmd cho Agent.*
2. Xóa import không dùng: `subprocess`, `Tuple` (nếu không còn caller).
3. `_write_building_marker(graph_dir, pid, build_cmd="")`:
   - Bỏ param `build_cmd` và key JSON `build_cmd`. Marker chỉ còn `pid`, `started_at`.
4. `xml_fbograph/query/engine.py` ~dòng 215:
   - Comment vẫn `thieu Kuzu -> spawn detached (khong sync-build)` → đổi thành *gate ensure_mcp_kuzu_ready (thieu Kuzu -> sync-build in-process)*.
5. `xml_fbograph/tests/test_customerpro_kuzu_gate.py` dòng 1:
   - Docstring vẫn `detached build (khong sync-build)` → đổi cho khớp sync-build.

---

## Không được làm

- Không revert sync-build / không trả lại `status=building` + `build_cmd` cho Agent.
- Không bật lại `search_nodes` / `get_related_nodes` / `query_node_details`.
- Không `reset_graph_dir` / `build_kuzu_for_project(overwrite=True)` trong MCP.
- Không đổi schema Cypher / `query_radar` LIMIT auto.
- Không hardcode partition `d91$202501`.
- Không commit/xóa KuzuDB production.
- Biến/param `snake_case`. Comment tiếng Việt ngắn chỗ wait/lock/redirect.

---

## Definition of Done

- [ ] Marker `pid=0` / pid chết → **không wait**, sync-build ngay; có unittest mock `time.sleep` không bị gọi.
- [ ] pid sống khác process → vẫn wait/poll (giữ an toàn 2 MCP).
- [ ] `_sync_build_kuzu_in_mcp` không in ra **stdout** (redirect stderr hoặc tương đương).
- [ ] Cùng process 2 request: 1 lock → 1 lần `build_and_save_graph` (lock hoặc test 2 thread).
- [ ] `.cursorrules` habit không còn bảo gọi 3 tool đã ẩn.
- [ ] Docstring module + `engine.py` comment không còn “spawn detached”.
- [ ] Marker JSON không còn field `build_cmd`.
- [ ] `py -m unittest xml_fbograph.tests.test_customerpro_kuzu_gate -v` pass (kể cả test P0 mới).

---

## PROMPT GỬI GEMINI

```
Bạn là Senior Python engineer trên repo FastBusiness MCP: E:\PythonProject\mcp_fbo

Đọc:
  E:\PythonProject\mcp_fbo\docs\doc_fix\fbograph_mcp_sync_build_review_fixes.md
  (tham khảo thêm docs/doc/fbograph_mcp_restore_sync_build_kuzu.md nếu cần ngữ cảnh)

Task trước (sync-build in-process cho query_radar) ĐÃ LÀM. Unittest cũ 17/17 pass.
Review tìm ra bug thật. Sửa đúng file dưới, KHÔNG revert sync-build, KHÔNG bật lại search_nodes/get_related_nodes/query_node_details.

# P0 — Marker .building legacy treo query_radar tới 45 phút

File: xml_fbograph/utils/kuzu_build_spawn.py

is_building_in_progress hiện:
  if _pid_alive(pid) or age < BUILDING_MARKER_MAX_AGE_SEC: return data

pid=0 (cách cũ ủy thác Agent ghi marker spawned=False) → _pid_alive False nhưng age < 45p → vẫn “in progress”.
ensure_mcp_kuzu_ready thấy pid != getpid() → while sleep(2) tới 45 phút rồi mới build.

SAI. Sau upgrade, nhiều project còn C:/KuzuDB/<hash>/.fbograph/.building pid=0 → query_radar TREO.

Fix is_building_in_progress:
  - Chỉ return marker khi pid > 0 VÀ _pid_alive(pid) == True.
  - pid==0 hoặc pid chết → clear_building_marker ngay, return None.
  - Bỏ “age < 45p coi như còn sống”.

ensure_mcp_kuzu_ready wait:
  - Chỉ wait khi marker pid sống VÀ pid != os.getpid() (process khác đang build).
  - Trong loop: pid chết / marker mất → break, nếu kuzu chưa ready thì sync-build ngay (không đợi hết 45p).
  - Timeout BUILDING_MARKER_MAX_AGE_SEC chỉ khi đang wait pid sống.

Test BẮT BUỘC trong xml_fbograph/tests/test_customerpro_kuzu_gate.py:

test_stale_pid0_marker_does_not_wait_sync_builds_immediately
  - Tạo graph_dir/.building JSON pid=0, started_at=now, build_cmd="legacy.exe build X"
  - mock build_and_save_graph tạo dummy kuzu ready
  - mock time.sleep → assert không gọi (call_count==0)
  - ensure_mcp_kuzu_ready(ref) return db_path nhanh, build 1 lần, marker bị xóa

test_dead_pid_marker_cleared_then_sync_build (khuyến nghị)
  - marker pid=999999, patch _pid_alive False → sync-build ngay, không wait

# P1 — print() phá stdout MCP

build_and_save_graph / GraphBuilder dùng print() → stdout.
MCP stdio_server: stdout = JSON-RPC. Cold-start query_radar sẽ vỡ protocol.

Trong _sync_build_kuzu_in_mcp, bọc:
  import contextlib
  with contextlib.redirect_stdout(sys.stderr):
      build_and_save_graph(...)

Không refactor hàng loạt print trong graph_builder (CLI fbograph vẫn stdout).
Comment tiếng Việt ngắn: tránh phá JSON-RPC MCP.

# P1 — Cùng process double-build

Hiện: if marker.pid != os.getpid() mới wait.
Cùng MCP process, request 2 thấy pid==self → không wait → _sync_build_kuzu_in_mcp lần 2.

Thêm threading.Lock theo graph_dir (dict + guard).
ensure_mcp_kuzu_ready: sau validate (+ wait process khác nếu có), with lock:
  if kuzu_db_ready: clear marker; return db_path
  try: _sync_build_kuzu_in_mcp(...)
  except: raise KuzuBuildFailedError (không build_cmd)
  if not ready: raise KuzuBuildFailedError
  clear marker; return db_path

Test khuyến nghị: 2 thread ensure_mcp_kuzu_ready, mock build sleep 0.2s rồi tạo kuzu → call_count == 1.

# P2 — .cursorrules

Section Agent habit vẫn: "Chưa biết file → search_nodes → get_related_nodes".
3 tool ĐÃ ẨN. Đổi habit: dùng query_radar + template Cypher; cấm gọi search_nodes/get_related_nodes/query_node_details.
Giữ block reference_file + MCP tự sync-build.

# P2 — dọn rác

- kuzu_build_spawn.py module docstring vẫn “Spawn detached / không sync-build” → đổi thành gate validate + sync-build in-process, không build_cmd.
- Xóa import chết: subprocess, Tuple (nếu unused).
- _write_building_marker: bỏ param/field build_cmd; marker chỉ pid + started_at.
- engine.py ~dòng 215 comment “spawn detached” → “ensure_mcp_kuzu_ready sync-build in-process”.
- test_customerpro_kuzu_gate.py docstring dòng 1: bỏ “detached build”.

# Cấm

- Không trả lại JSON status=building / build_cmd cho Agent.
- Không bật lại 3 tool ẩn.
- Không overwrite/reset_graph_dir trong MCP.
- Không hardcode d91$202501.
- snake_case. Comment tiếng Việt ngắn.

# Chạy test

py -m unittest xml_fbograph.tests.test_customerpro_kuzu_gate -v

Phải pass test cũ + test P0 mới.

Báo cáo diff + xác nhận: marker pid=0 không còn wait; stdout MCP không bị print TIMING.
```

---

## Phụ lục — File cần sửa

| File | Việc |
|---|---|
| `xml_fbograph/utils/kuzu_build_spawn.py` | P0 marker, P1 lock + redirect stdout, P2 docstring/import/`build_cmd` |
| `xml_fbograph/tests/test_customerpro_kuzu_gate.py` | Test P0 (+ optional 2-thread); sửa docstring |
| `xml_fbograph/query/engine.py` | Comment gate |
| `.cursorrules` | Agent habit |

Không sửa `fastbusiness_mcp/backup_hidden_tools.py` / không wire 3 tool ẩn vào `server.py`.
