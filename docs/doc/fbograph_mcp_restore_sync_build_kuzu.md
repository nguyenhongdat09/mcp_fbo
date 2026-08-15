# FSPEC / PROMPT — Khôi phục sync-build Kuzu trong MCP (bỏ ủy thác `build_cmd` cho Agent)

> **Cách dùng:** Copy toàn bộ nội dung từ mục «PROMPT GỬI GEMINI» trở xuống, dán cho Gemini (hoặc AI khác) kèm repo `mcp_fbo` để nó implement.
>
> **Mục tiêu sản phẩm:** Khi Agent gọi tool FBOGraph đang live — **chỉ `query_radar`** — mà project **chưa có Kuzu**, MCP **tự build Kuzu ngay trong process MCP**, xong rồi **chạy tiếp Cypher và trả kết quả thật**. Agent **không** được nhận JSON `status=building` + `build_cmd` rồi tự quyết định có chạy hay không.
>
> **Tool đã ẩn (CẤM bật lại trong task này):** `search_nodes`, `get_related_nodes`, `query_node_details`. Backup nằm ở `fastbusiness_mcp/backup_hidden_tools.py`. Không đăng ký lại `server.py`, không sửa schema/handler của chúng.

---

## 0. Tóm tắt 1 dòng (cho người gửi prompt)

| Trước đây (đúng, cần khôi phục) | Hiện tại (sai, phải bỏ) | Mong muốn |
|---|---|---|
| `query_radar` thiếu Kuzu → `build_and_save_graph(...)` **in-process** → mở store → trả kết quả Cypher | Thiếu Kuzu → ghi marker `.building` + trả JSON `build_cmd` bảo Agent `run_command` | Giống trước đây: MCP tự tạo Kuzu, Agent chỉ nhận kết quả `query_radar` |
| Agent không làm gì thêm | Agent hay **bỏ qua** không chạy cmd → Kuzu không bao giờ có | Không phụ thuộc Agent |

**Không revert** phần hard-guard `reference_file` (absolute path / reject relative / missing Controllers). Phần đó vẫn đúng.

---

## 1. Bối cảnh / vì sao phải sửa

### 1.1. Cách cũ (commit `fc9c25e`, trước khi có `kuzu_build_spawn.py`)

Trong `xml_fbograph/mcp_tools.py::_ensure_graph_built` và `xml_fbograph/query/engine.py::xml_graph_query`:

- Check `graph_dir / "kuzu"` đã sẵn sàng chưa (`exists` + size > 0 / dir không rỗng).
- Nếu **chưa có** → log stderr → gọi `build_and_save_graph(controllers_dir, graph_dir)` **ngay trong process MCP**.
- Invalidate cache store/graph trước khi build.
- Build xong → mở Kuzu read-only → chạy query → trả JSON kết quả cho Agent.

Ví dụ Agent gọi:

```text
query_radar(
  cypher_query="MATCH (a:XmlFile) WHERE a.relative_path ENDS WITH 'CPTran.xml' RETURN a.relative_path LIMIT 20",
  reference_file="E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml"
)
```

Nếu Kuzu chưa có: MCP **block** (có thể 15–30 phút với project ~6000 file), build xong, **trả luôn rows Cypher**. Agent không biết/không cần biết đã build.

`search_nodes` / `get_related_nodes` / `query_node_details` **đã bỏ khỏi MCP server** (ẩn, backup `fastbusiness_mcp/backup_hidden_tools.py`). Task này **không** bật lại, không test, không sửa schema của chúng.

### 1.2. Cách giữa (commit `0798b6e`) — spawn detached

Thêm `xml_fbograph/utils/kuzu_build_spawn.py`:

- Thiếu Kuzu → `subprocess.Popen` mở CMD mới (`CREATE_NEW_CONSOLE`) chạy `fastbusiness_mcp.exe build <project>` hoặc `py xml_fbograph/build_kuzu_projects.py <project>`.
- Raise `KuzuBuildingError` payload `status=building`, `spawned=True`, `pid=...`.
- Agent phải **gọi lại tool sau 15–30 phút**. MCP không đợi, không trả kết quả query.

### 1.3. Cách hiện tại (working tree) — ủy thác Agent chạy `build_cmd` ← **PHẢI BỎ**

`spawn_detached_kuzu_build` **không còn Popen**. Chỉ:

1. Ghi marker `.building` với `pid=0` + chuỗi `build_cmd`.
2. Trả JSON kiểu:

```json
{
  "status": "building",
  "message": "Kuzu chua co. BAN PHAI SỬ DỤNG TOOL run_command ĐỂ CHẠY LỆNH TRONG TRƯỜNG build_cmd BẰNG POWERSHELL NGAY BÂY GIỜ. Khong duoc bo qua buoc nay!",
  "project_root": "...",
  "graph_dir": "...",
  "build_cmd": "E:\\fastbusiness_mcp\\fastbusiness_mcp.exe build E:\\FBO\\SP2263",
  "pid": 0,
  "spawned": false
}
```

3. `ensure_mcp_kuzu_ready` raise `KuzuBuildingError(payload)`.
4. `mcp_tools._mcp_gate_error_json` serialize payload trả về Agent.

**Lỗi thực tế:** Agent Cursor/Gemini **có thể bỏ qua** không gọi `run_command`. Marker `.building` vẫn sống 45 phút → lần gọi sau vẫn chỉ nhắc lại `build_cmd`. Kuzu **không bao giờ được tạo**. Tool FBOGraph vô dụng.

User đã thử cách ủy thác Agent; **không chấp nhận**. Yêu cầu **trả lại cách cũ**: tạo Kuzu **ngay trong MCP**, rồi trả kết quả query.

---

## 2. Phạm vi tool (bắt buộc hiểu)

MCP FBOGraph **đang live** chỉ còn:

| Tool MCP | Entry | Gate Kuzu |
|---|---|---|
| **`query_radar`** (DUY NHẤT dùng Kuzu) | `fastbusiness_mcp/server.py` → `mcp_query_radar` → `get_kuzu_store` | `ensure_mcp_kuzu_ready` |
| `read_local_file` | `mcp_read_local_file` | **Không** gọi gate Kuzu — chỉ sandbox path |

**Đã ẩn / đã bỏ — CẤM đụng trong task này:**

| Tool | Trạng thái |
|---|---|
| `search_nodes` | Ẩn. Code wrapper còn trong `mcp_tools.py`, backup schema/handler ở `fastbusiness_mcp/backup_hidden_tools.py`. **Không** import lại `server.py`, **không** list_tools, **không** call_tool. |
| `get_related_nodes` | Như trên |
| `query_node_details` | Như trên |

`xml_graph_query` (`engine.py`) là hàm nội bộ cũ của 3 tool đã ẩn. **Không** bắt buộc sửa trừ comment/gate nếu `ensure_mcp_kuzu_ready` dùng chung. **Không** viết test/`Definition of Done` cho 3 tool đã ẩn.

**Không** sync-build khi gọi `read_local_file` / `query_database` / `get_xml_entities` / `search_qlyc`.

**Không** đụng CLI thủ công: `fbograph`, `xml_fbograph/build_kuzu_projects.py`, `fastbusiness_mcp.exe build|rebuild`.

---

## 3. File / module liên quan (đọc trước khi sửa)

Bắt buộc đọc hết trước khi code:

1. `xml_fbograph/utils/kuzu_build_spawn.py` — gate hiện tại (validate + ủy thác Agent).
   - `InvalidReferenceFileError`, `NotFastBusinessProjectError`, `KuzuBuildingError`
   - `_validate_and_resolve_reference_file`
   - `kuzu_db_ready`, `is_building_in_progress`, `_write_building_marker`, `clear_building_marker`
   - `spawn_detached_kuzu_build` ← **ngừng gọi từ gate**; có thể xóa hoặc để dead-code unused
   - `ensure_mcp_kuzu_ready` ← **sửa trọng tâm**
2. `xml_fbograph/mcp_tools.py`
   - `_ensure_graph_built`, `get_kuzu_store`, `_mcp_gate_error_json`
   - **`mcp_query_radar`** — tool Kuzu duy nhất đang live
   - `mcp_search_nodes` / `mcp_get_related_nodes` / `mcp_query_node_details`: **để yên** (tool đã ẩn, không wire lại `server.py`)
   - Commit cũ `fc9c25e` là reference implementation `_ensure_graph_built`
3. `fastbusiness_mcp/server.py`
   - Chỉ import/list/call: `query_radar`, `read_local_file` (+ SQL/XML/QLYC). **Không** thêm lại 3 tool đã ẩn.
4. `xml_fbograph/query/engine.py`
   - `xml_graph_query` vẫn gọi `ensure_mcp_kuzu_ready` (nội bộ, tool đã ẩn). Chỉ sửa comment/gate nếu cần đồng bộ; không phải surface MCP.
5. `xml_fbograph/builder/graph_builder.py`
   - `build_and_save_graph(controllers_dir, output_dir, progress=None, project_label="")` ← **hàm build in-process phải gọi**
6. `xml_fbograph/build_kuzu_projects.py`
   - `build_kuzu_for_project(..., overwrite=True)` **KHÔNG dùng** cho first-create trong MCP (nó `reset_graph_dir` xóa vật lý `.fbograph`). Chỉ dùng CLI rebuild.
7. `xml_fbograph/tests/test_customerpro_kuzu_gate.py`
   - `TestEnsureMcpKuzuGate.test_missing_kuzu_spawns_once_no_sync_build` ← **đổi hoàn toàn**
   - Giữ các test `invalid_reference_file` (missing / relative / missing_controllers)
8. `.cursorrules` — dòng “KHÔNG chạy build_cmd cho path lạ” cần sửa cho khớp hành vi mới. Nếu section tool list còn ghi `search_nodes` / `get_related_nodes` / `query_node_details`: có thể xóa 3 dòng đó cho khớp `server.py` (tùy chọn). **Không** thêm chúng lại.
9. `xml_fbograph/kuzu_build.txt` — tài liệu CLI; có thể thêm 1 dòng: MCP `query_radar` tự sync-build khi thiếu DB. Không bắt buộc rewrite cả file.
10. `fastbusiness_mcp/backup_hidden_tools.py` — **không sửa**, không copy ngược vào `server.py`.

Tham chiếu git (không checkout, chỉ đọc):

```text
git show fc9c25e:xml_fbograph/mcp_tools.py
git show fc9c25e:xml_fbograph/query/engine.py
```

Đoạn `_ensure_graph_built` cũ (phải khôi phục logic này vào gate):

```python
def _ensure_graph_built(reference_file: str) -> Path:
    """Build graph neu kuzu chua co / rong. Tra ve db_path."""
    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    db_path = graph_dir / "kuzu"
    if _kuzu_db_ready(db_path):
        return db_path

    _safe_log(f"[FboFBOGraph MCP] Building graph for {helper.get_project_root()} ...")
    from xml_fbograph.builder.graph_builder import build_and_save_graph

    db_key = str(db_path)
    _kuzu_stores.pop(db_key, None)
    from xml_fbograph.query import engine as qe
    qe._store_cache.pop(str(graph_dir), None)
    qe._graph_cache.pop(str(graph_dir), None)

    build_and_save_graph(helper.get_controllers_path(), graph_dir)
    _safe_log("[FboFBOGraph MCP] Graph build finished.")
    return db_path
```

---

## 4. Thiết kế chi tiết (Gemini phải bám)

### 4.1. Nguyên tắc

1. **Một cửa vào duy nhất:** `ensure_mcp_kuzu_ready(reference_file) -> Path`.
   - Tool MCP Kuzu đang live **chỉ** `query_radar` → `get_kuzu_store` → gate này.
   - **Không** copy logic build vào `mcp_query_radar` (tránh lệch với `get_kuzu_store`). User nói “ngay ở hàm query_radar” nghĩa là **khi gọi query_radar thì MCP tự build rồi trả kết quả Cypher** — implement ở gate là đủ.
   - **Không** bật lại / không wire `mcp_search_nodes` / `mcp_get_related_nodes` / `mcp_query_node_details`.
2. **Thứ tự bắt buộc:**
   1. Validate `reference_file` (giữ nguyên `_validate_and_resolve_reference_file`).
   2. Nếu Kuzu ready → `clear_building_marker` → `return db_path`.
   3. Nếu chưa ready → **sync-build in-process** → nếu thành công → `return db_path`.
   4. Caller `get_kuzu_store` (dùng bởi `mcp_query_radar`) mở store RO và chạy Cypher như bình thường.
3. **Cấm** trả về Agent:
   - `status: "building"`
   - field `build_cmd`
   - message “BAN PHAI SỬ DỤNG TOOL run_command…”
4. **Cấm** `subprocess.Popen` / `CREATE_NEW_CONSOLE` / ủy thác `fastbusiness_mcp.exe build` từ MCP tool path.
5. **Giữ** `InvalidReferenceFileError` / reject relative / missing Controllers. Path sai **không** được build.

### 4.2. `ensure_mcp_kuzu_ready` — hành vi mới (pseudo)

```python
def ensure_mcp_kuzu_ready(reference_file: str) -> Path:
    """
    Gate MCP: validate reference_file + dam bao Kuzu ready.
    - invalid path -> InvalidReferenceFileError (KHONG build)
    - kuzu ready -> return db_path
    - thieu kuzu -> sync-build in-process (build_and_save_graph), roi return db_path
    - build fail -> exception ro, KHONG tra build_cmd
    """
    reference_file = _validate_and_resolve_reference_file(reference_file)

    helper = ProjectPathHelper(reference_file)
    graph_dir = helper.get_graph_dir()
    db_path = graph_dir / "kuzu"

    if kuzu_db_ready(db_path):
        clear_building_marker(graph_dir)
        return db_path

    _sync_build_kuzu_in_mcp(reference_file, graph_dir)

    if not kuzu_db_ready(db_path):
        raise KuzuBuildFailedError(...)  # hoac RuntimeError + payload ro
    clear_building_marker(graph_dir)
    return db_path
```

Đặt `_sync_build_kuzu_in_mcp` trong cùng file `kuzu_build_spawn.py` (đổi module docstring) **hoặc** `mcp_tools.py`. Ưu tiên **cùng file gate** để `engine.py` / `mcp_tools.py` không lệch nhau.

Nội dung `_sync_build_kuzu_in_mcp` (bắt buộc):

1. Log **stderr** (không stdout — tránh phá JSON-RPC MCP):
   `[FboFBOGraph MCP] Kuzu missing. Sync-building in-process for <project_root> ...`
2. Ghi marker `.building` với `pid=os.getpid()` (khóa chống 2 request MCP cùng lúc double-build). Không cần field `build_cmd`.
3. Invalidate cache trước build:
   - `xml_fbograph.query.engine._store_cache` / `_graph_cache` pop `str(graph_dir)`
   - `xml_fbograph.storage.kuzu_index._db_instances` pop key của `graph_dir / "kuzu"` (giống đoạn auto-sync trong `engine.py`)
   - nếu import được `mcp_tools._kuzu_stores` thì pop `str(db_path)`
4. Gọi:

```python
from xml_fbograph.builder.graph_builder import build_and_save_graph
build_and_save_graph(
    helper.get_controllers_path(),
    graph_dir,
    project_label=str(helper.get_project_root()),
)
```

5. Log stderr: `[FboFBOGraph MCP] Sync-build finished.`
6. `try/finally`: luôn `clear_building_marker(graph_dir)` khi ra khỏi hàm (kể cả fail), **trừ khi** quyết định giữ marker khi fail để lần sau retry — nếu giữ marker fail thì phải ghi `pid` chết + age ngắn; đơn giản hơn: **xóa marker khi fail** để lần gọi sau build lại.
7. **Không** gọi `reset_graph_dir` / `build_kuzu_for_project(overwrite=True)`. First-create dùng incremental writer của `build_and_save_graph` giống cách cũ.

### 4.3. Marker `.building` khi sync-build (khuyến nghị, không ủy thác Agent)

Mục đích marker giờ chỉ là **lock in-process / cross-request**, không phải giao việc cho Agent.

- Request A đang `build_and_save_graph` (marker pid = PID MCP, process sống).
- Request B vào `ensure_mcp_kuzu_ready` cùng `graph_dir`:
  - **Không** start build thứ 2.
  - **Poll** `kuzu_db_ready(db_path)` + `is_building_in_progress` mỗi 2–5 giây.
  - Timeout đề xuất: `BUILDING_MARKER_MAX_AGE_SEC` (45 phút) hoặc tối thiểu 30 phút.
  - Nếu ready → `return db_path`.
  - Nếu timeout / pid chết / marker hết hạn → xóa marker, **tự sync-build** (không trả `build_cmd`).
- Log stderr khi wait: `[FboFBOGraph MCP] Waiting for in-process Kuzu build pid=...`

Nếu thấy phức tạp: MVP chấp nhận **không poll**, chỉ lock bằng marker + nếu marker sống thì **đợi blocking** bằng sleep-loop. Vẫn **cấm** raise `KuzuBuildingError` kiểu `build_cmd` cho Agent.

### 4.4. `KuzuBuildingError` / `_mcp_gate_error_json`

- Payload `status=building` + `build_cmd` **không còn** là happy-path / expected response của tool.
- `_mcp_gate_error_json` **vẫn** bắt `InvalidReferenceFileError`, `NotFastBusinessProjectError`.
- `KuzuBuildingError`:
  - **Xóa** khỏi luồng thiếu Kuzu, **hoặc**
  - Đổi thành lỗi hiếm: “build đang chạy quá lâu / build failed” **không** kèm `build_cmd`.
- Nếu build in-process ném exception (IO, Kuzu lock, OOM): bắt, log stderr, trả JSON/text lỗi rõ (`error: "kuzu_build_failed"`, `message`, `project_root`, `graph_dir`). Agent đọc lỗi, **không** được bảo đi chạy PowerShell.

Gợi ý exception mới (snake_case file, PascalCase class):

```python
class KuzuBuildFailedError(Exception):
    def __init__(self, payload: dict):
        self.payload = payload
        super().__init__(payload.get("message", "Kuzu build failed"))
```

Wire vào `_mcp_gate_error_json` giống các gate error khác.

### 4.5. `mcp_tools.py` / `engine.py` — chỉnh comment + cache

- `_ensure_graph_built`: docstring đổi thành “thieu Kuzu -> sync-build in-process roi return db_path”. Vẫn delegate `ensure_mcp_kuzu_ready`.
- `get_kuzu_store`: docstring bỏ “spawn detached / khong sync-build”. Sau `ensure_mcp_kuzu_ready` return, mở RO store như hiện tại (`ensure_fresh_readonly_store` + `_bind_live_connection` + watcher + touch access).
- `xml_graph_query` (nội bộ, không phải MCP tool live): nếu còn gọi `ensure_mcp_kuzu_ready` thì chỉ sửa comment “spawn detached”; **không** dành effort test/DoD cho hàm này. Giữ nhánh `FBOGRAPH_AUTO_SYNC=1`.
- `mcp_query_radar`: **không** early-return JSON building. Sau build, `store.execute_cypher` chạy bình thường, return results.
- `mcp_search_nodes` / `mcp_get_related_nodes` / `mcp_query_node_details`: **không sửa** trừ khi refactor import/gate bắt buộc (tránh diff lớn). **Không** thêm vào `server.py`.

### 4.6. `spawn_detached_kuzu_build` / resolve exe

Sau khi `ensure_mcp_kuzu_ready` không còn gọi:

- Xóa hẳn `spawn_detached_kuzu_build`, `build_detached_command`, `resolve_fastbusiness_mcp_command`, `_mcp_json_candidates` **nếu không còn caller**.
- Hoặc để lại nhưng đánh dấu unused — **không** import từ MCP tools.
- Đổi module docstring `kuzu_build_spawn.py`: không còn “Spawn detached / không sync-build”. Có thể rename file sau (không bắt buộc trong PR này; YAGNI). Giữ tên file cũng được để ít đụng import.

Giữ: `kuzu_db_ready`, marker helpers, `InvalidReferenceFileError`, `_validate_and_resolve_reference_file`, `ensure_mcp_kuzu_ready`.

### 4.7. `.cursorrules`

Sửa section FBOGraph `reference_file`:

- Giữ: bắt buộc absolute path; cấm relative; `invalid_reference_file` → sửa path rồi gọi lại.
- **Xóa / thay** câu “KHÔNG chạy `build_cmd` cho path lạ”.
- Thêm 1 dòng: *Thiếu Kuzu thì MCP tự build in-process rồi trả kết quả; Agent không chạy cmd tạo Kuzu, không bỏ qua tool vì thấy message building.*

Ví dụ:

```text
## FBOGraph reference_file (BẮT BUỘC)
- Tool live: query_radar, read_local_file
  phải truyền reference_file = ABSOLUTE path XML trong project đang làm
  (vd E:\FBO\SP2263\App_Data\Controllers\Filter\SVInvoiceFilter.xml).
- CẤM relative / basename. Nếu user đang mở file trong IDE → lấy full path file đó.
- Nếu tool trả invalid_reference_file → sửa path rồi gọi lại.
- query_radar thiếu Kuzu: MCP tự sync-build rồi trả kết quả Cypher. Agent KHÔNG tự chạy fbograph / fastbusiness_mcp.exe build.
```

Khi sửa `.cursorrules`, **không** thêm lại `search_nodes` / `get_related_nodes` / `query_node_details` vào danh sách tool live. Nếu section “MCP Tools Available” vẫn liệt kê 3 tool đã ẩn: có thể xóa 3 dòng đó cho khớp `server.py` (tùy chọn, không bắt buộc).

### 4.8. Timeout MCP client (trade-off, chấp nhận)

Sync-build project lớn có thể 15–30 phút. Cursor/MCP client có thể timeout stdio.

**Vẫn làm sync-build** theo yêu cầu user. Không “lách” bằng trả `build_cmd`.

Bắt buộc:

- Log tiến độ ra **stderr** (GraphBuilder đã có progress bar trên stdout khi CLI — trong MCP phải đảm bảo progress **không** viết stdout JSON-RPC). Kiểm tra `build_and_save_graph` / `progress` callback: nếu mặc định print stdout, truyền `progress` no-op hoặc wrapper ghi stderr.
- Docstring / comment ngắn: first-index chậm là cố ý.

Không bắt buộc trong task này: streaming MCP progress notification.

### 4.9. `read_local_file` + validate

`mcp_read_local_file` hiện **không** gọi `ensure_mcp_kuzu_ready`. Giữ vậy (không build Kuzu chỉ để đọc file).

Nếu `reference_file` relative: `ProjectPathHelper` vẫn có thể resolve sai. Ngoài phạm vi task này trừ khi đã gọi validate chung. Không mở rộng trừ khi sửa 1 dòng gọi `_validate_and_resolve_reference_file` — **không bắt buộc**.

---

## 5. Tests bắt buộc

File: `xml_fbograph/tests/test_customerpro_kuzu_gate.py` (hoặc test mới cùng folder).

**Giữ nguyên** (vẫn phải pass):

- `test_missing_reference_file` → `InvalidReferenceFileError` reason `missing`, không tạo `.building`, không gọi `build_and_save_graph`.
- `test_relative_reference_file` → reason `ambiguous_or_unresolved_relative` (hoặc `relative_path_forbidden` nếu đổi tên; đừng đổi nếu không cần).
- `test_absolute_but_missing_controllers` → reason `missing_controllers`, không build.

**Xóa** `test_missing_kuzu_spawns_once_no_sync_build`.

**Thêm:**

### 5.1. `test_missing_kuzu_sync_builds_then_returns_db_path`

- Fixture temp `CustomerPro/.../App_Data/Controllers/Dir/AITran.xml` + `FBOGRAPH_KUZU_BASE`.
- `mock.patch("xml_fbograph.builder.graph_builder.build_and_save_graph", side_effect=_fake_build)`  
  `_fake_build(controllers, graph_dir, **kwargs)` tạo `graph_dir / "kuzu"` file giả (size > 0) hoặc dir có 1 file dummy.
- `db_path = ensure_mcp_kuzu_ready(self.ref)`
- Assert `db_path == graph_dir / "kuzu"` và `kuzu_db_ready(db_path)`.
- Assert `build_and_save_graph` được gọi **đúng 1 lần**.
- Assert **không** raise `KuzuBuildingError`.
- Assert không tồn tại payload/file chứa `build_cmd` (marker nếu còn thì không có key `build_cmd`, hoặc marker đã xóa).

### 5.2. `test_kuzu_already_ready_skips_build`

- Tạo sẵn `graph_dir / "kuzu"` dummy ready.
- Mock `build_and_save_graph`.
- `ensure_mcp_kuzu_ready` return db_path, mock **không** được gọi.

### 5.3. `test_invalid_path_does_not_sync_build`

- Relative path + mock `build_and_save_graph`.
- Raise `InvalidReferenceFileError`, mock call_count == 0.

### 5.4. `test_sync_build_failure_returns_error_not_build_cmd` (khuyến nghị)

- Mock `build_and_save_graph` raise `RuntimeError("disk full")`.
- `ensure_mcp_kuzu_ready` raise `KuzuBuildFailedError` (hoặc exception đã chọn).
- `payload` không có `build_cmd`, không `status=building`.
- Marker `.building` không còn (finally clear).

### 5.5. Optional: `test_second_call_waits_instead_of_double_build`

- Mock build sleep ngắn + tạo kuzu.
- Thread 2 gọi `ensure_mcp_kuzu_ready` khi thread 1 đang build.
- `build_and_save_graph` call_count == 1.
- Cả 2 return cùng `db_path`.

Chạy:

```text
py -m unittest xml_fbograph.tests.test_customerpro_kuzu_gate -v
```

Dùng interpreter venv/project (Python 3.12 nếu test Kuzu thật; unit test này mock nên 3.x đều được). Không deploy DB/proc.

Khuyến nghị thêm test mỏng `mcp_query_radar` với mock `get_kuzu_store` / `ensure_mcp_kuzu_ready` + `execute_cypher`: sau “thiếu kuzu” vẫn trả list rows, không JSON building. **Không** viết test MCP cho `search_nodes` / `get_related_nodes` / `query_node_details`.

---

## 6. Ràng buộc / Không được làm

- KHÔNG đổi schema Cypher, `XmlFile`/`Rel`, synonym FBO, `query_radar` LIMIT auto.
- KHÔNG đổi `build_and_save_graph` logic parse/edge trừ khi cần chặn stdout progress trong MCP.
- KHÔNG hardcode partition `d91$202501`.
- KHÔNG `reset_graph_dir` khi first-create từ MCP.
- KHÔNG commit / xóa nhầm folder KuzuDB production (`C:/KuzuDB`, `E:\FBO\SP2263`, UNC CustomerPro).
- KHÔNG sửa `query_database` / HDDT / SQL proc.
- Biến local / param: `snake_case`.
- Comment tiếng Việt ngắn ở gate sync-build.
- KHÔNG tạo tool MCP mới (`build_kuzu`, `ensure_kuzu`, …). Gate ẩn trong `query_radar`.
- KHÔNG bật lại `search_nodes` / `get_related_nodes` / `query_node_details` (đã ẩn; backup `backup_hidden_tools.py`).
- KHÔNG yêu cầu Agent gọi `fbograph init` / `run_command`.

---

## 7. Definition of Done

- [ ] Gọi **`query_radar`** khi chưa có Kuzu → MCP sync-build in-process → trả **kết quả Cypher**, không JSON `building`/`build_cmd`.
- [ ] Kuzu đã có → không build lại, `query_radar` như hiện tại.
- [ ] `reference_file` relative / thiếu / không Controllers → vẫn `invalid_reference_file`, không build.
- [ ] `spawn_detached_kuzu_build` không còn nằm trên đường đi `query_radar`.
- [ ] `_mcp_gate_error_json` không còn lộ `build_cmd` cho case thiếu Kuzu.
- [ ] `.cursorrules` không còn bảo Agent chạy `build_cmd`.
- [ ] `fastbusiness_mcp/server.py` **không** đăng ký lại 3 tool đã ẩn.
- [ ] Unit tests gate mới pass; test spawn-once cũ đã xóa/đổi.
- [ ] CLI `fbograph` / `build_kuzu_projects.py` vẫn build/rebuild thủ công như cũ.
- [ ] Báo cáo diff + ví dụ: trước (JSON building) vs sau (rows Cypher).

---

## PROMPT GỬI GEMINI

```
Bạn là Senior Python engineer làm việc trên repo FastBusiness MCP: E:\PythonProject\mcp_fbo
(package chính: fastbusiness_mcp/, xml_fbograph/).

Đọc trước toàn bộ file:
  E:\PythonProject\mcp_fbo\docs\doc\fbograph_mcp_restore_sync_build_kuzu.md
và bám đúng thiết kế trong đó. Không sáng tác hướng “Agent tự chạy cmd”.

# 1. Mục tiêu

Khôi phục hành vi CŨ cho tool MCP Kuzu ĐANG LIVE — CHỈ query_radar.

search_nodes, get_related_nodes, query_node_details ĐÃ BỎ / ĐÃ ẨN
(backup: fastbusiness_mcp/backup_hidden_tools.py). CẤM bật lại, CẤM import/list/call trong fastbusiness_mcp/server.py, CẤM sửa schema/handler của chúng trong task này.

Khi Agent gọi query_radar mà project chưa có Kuzu DB, MCP phải TỰ build Kuzu NGAY TRONG PROCESS MCP (in-process, sync), rồi TIẾP TỤC chạy Cypher và TRẢ KẾT QUẢ THẬT cho Agent.

Hiện tại (SAI): ensure_mcp_kuzu_ready → spawn_detached_kuzu_build chỉ ghi marker .building + trả JSON status=building + build_cmd bảo Agent dùng run_command. Agent hay bỏ qua → Kuzu không bao giờ được tạo. Phải bỏ cách này.

Ví dụ đúng sau khi sửa:
  Agent gọi query_radar(cypher_query=..., reference_file=<ABS XML trong project>)
  → nếu chưa có C:/KuzuDB/<base64(project)>/.fbograph/kuzu
  → MCP gọi build_and_save_graph(controllers_dir, graph_dir) in-process
  → xong thì execute_cypher như bình thường
  → Agent nhận rows Cypher, KHÔNG nhận build_cmd.

# 2. Giữ nguyên (đừng revert)

- Hard-guard reference_file trong xml_fbograph/utils/kuzu_build_spawn.py:
  InvalidReferenceFileError, _validate_and_resolve_reference_file
  (absolute bắt buộc, relative reject, missing Controllers reject).
- Tool schema description reference_file absolute trong fastbusiness_mcp/server.py.
- CLI: xml_fbograph/build_kuzu_projects.py, fbograph, fastbusiness_mcp.exe build|rebuild.
- Không sync-build khi gọi read_local_file / query_database / get_xml_entities / search_qlyc.
- search_nodes / get_related_nodes / query_node_details vẫn ẨN. Không copy backup_hidden_tools.py vào server.py.

# 3. Sửa trọng tâm

File chính: xml_fbograph/utils/kuzu_build_spawn.py
  Hàm ensure_mcp_kuzu_ready(reference_file) -> Path

Luồng mới:
  1) reference_file = _validate_and_resolve_reference_file(...)  # giữ
  2) helper = ProjectPathHelper(...); graph_dir = helper.get_graph_dir(); db_path = graph_dir / "kuzu"
  3) nếu kuzu_db_ready(db_path): clear_building_marker; return db_path
  4) nếu chưa ready: sync-build IN-PROCESS:
       - log stderr: "[FboFBOGraph MCP] Kuzu missing. Sync-building in-process for <project_root> ..."
       - ghi marker .building với pid=os.getpid() (lock, KHÔNG kèm build_cmd cho Agent)
       - invalidate cache: engine._store_cache, engine._graph_cache, kuzu_index._db_instances, mcp_tools._kuzu_stores (nếu import được)
       - from xml_fbograph.builder.graph_builder import build_and_save_graph
         build_and_save_graph(helper.get_controllers_path(), graph_dir, project_label=str(helper.get_project_root()))
       - KHÔNG gọi build_kuzu_for_project(overwrite=True) / reset_graph_dir
       - progress/print không được phá stdout MCP (stdio JSON-RPC). Dùng stderr hoặc progress no-op.
       - finally: clear_building_marker
       - nếu sau build vẫn chưa kuzu_db_ready → raise lỗi kuzu_build_failed (payload không có build_cmd)
       - return db_path
  5) Nếu marker .building đang sống (pid MCP khác/cùng process đang build): ĐỢI (poll 2–5s) đến khi kuzu ready hoặc hết hạn marker; KHÔNG start build thứ 2; KHÔNG trả JSON building cho Agent. Timeout ~30–45 phút rồi tự build hoặc báo kuzu_build_failed.

Xóa khỏi đường đi MCP:
  - spawn_detached_kuzu_build
  - message "BAN PHAI SỬ DỤNG TOOL run_command ... build_cmd"
  - subprocess.Popen / CREATE_NEW_CONSOLE để build Kuzu từ tool
Có thể xóa luôn các helper chỉ phục vụ detached spawn (build_detached_command, resolve_fastbusiness_mcp_command, _mcp_json_candidates) nếu không còn caller.

# 4. Các file khác phải cập nhật

- xml_fbograph/mcp_tools.py
  * Docstring _ensure_graph_built / get_kuzu_store: thieu Kuzu -> sync-build in-process.
  * _mcp_gate_error_json: vẫn bắt InvalidReferenceFileError, NotFastBusinessProjectError.
    KuzuBuildingError status=building+build_cmd KHÔNG còn happy path.
    Nếu build fail: bắt KuzuBuildFailedError (hoặc tên tương đương) trả JSON error rõ, không build_cmd.
  * mcp_query_radar: sau get_kuzu_store phải chạy Cypher và trả results như cũ — không early return building.
  * mcp_search_nodes / mcp_get_related_nodes / mcp_query_node_details: ĐỂ YÊN, không wire lại server.py.

- fastbusiness_mcp/server.py
  * Chỉ giữ query_radar + read_local_file (FBOGraph). KHÔNG thêm lại 3 tool đã ẩn.
  * backup_hidden_tools.py: không sửa.

- xml_fbograph/query/engine.py
  * xml_graph_query là nội bộ (tool đã ẩn). Chỉ sửa comment/gate nếu ensure_mcp_kuzu_ready đổi chữ ký hành vi. Không test DoD cho xml_graph_query.
  * Giữ nhánh FBOGRAPH_AUTO_SYNC=1 incremental.

- .cursorrules
  * Bỏ câu bảo Agent chạy build_cmd.
  * Thêm: query_radar thiếu Kuzu thì MCP tự sync-build rồi trả Cypher; Agent không tự chạy fbograph / exe build.
  * Không liệt kê lại search_nodes / get_related_nodes / query_node_details như tool live.

- xml_fbograph/tests/test_customerpro_kuzu_gate.py
  * XÓA test_missing_kuzu_spawns_once_no_sync_build.
  * GIỮ test invalid reference_file (missing / relative / missing_controllers) — mock build_and_save_graph không được gọi.
  * THÊM test_missing_kuzu_sync_builds_then_returns_db_path:
      mock build_and_save_graph side_effect tạo dummy kuzu ready;
      ensure_mcp_kuzu_ready trả db_path; gọi build đúng 1 lần; không raise KuzuBuildingError; không build_cmd.
  * THÊM test_kuzu_already_ready_skips_build.
  * THÊM test_sync_build_failure_returns_error_not_build_cmd (mock raise; payload không có build_cmd; marker bị xóa).
  * Optional: 2 thread cùng ensure_mcp_kuzu_ready → chỉ 1 lần build_and_save_graph.

Chạy:
  py -m unittest xml_fbograph.tests.test_customerpro_kuzu_gate -v

# 5. Reference code cũ (đọc bằng git, đừng checkout nhầm)

  git show fc9c25e:xml_fbograph/mcp_tools.py
  git show fc9c25e:xml_fbograph/query/engine.py

Đoạn _ensure_graph_built cũ gọi build_and_save_graph in-process — khôi phục LOGIC đó vào ensure_mcp_kuzu_ready (sau bước validate reference_file hiện đại).

# 6. Cấm

- Không tạo MCP tool mới.
- Không bật lại search_nodes / get_related_nodes / query_node_details.
- Không ủy thác Agent / PowerShell / run_command.
- Không đổi Cypher schema, synonym, LIMIT auto của query_radar.
- Không hardcode d91$202501.
- Không xóa KuzuDB production.
- Không sync-build cho read_local_file.
- Biến/param snake_case. Comment tiếng Việt ngắn ở gate.

# 7. Definition of Done

- query_radar khi chưa có kuzu → MCP tự build → trả kết quả Cypher (không JSON building/build_cmd).
- server.py không đăng ký lại search_nodes / get_related_nodes / query_node_details.
- Path sai vẫn invalid_reference_file, không build.
- CLI fbograph/build_kuzu_projects không bị phá.
- Test gate pass.
- Báo cáo diff + ví dụ JSON trước/sau (query_radar).

Hãy đọc code hiện tại, implement đúng thiết kế, chạy unittest liên quan, rồi báo cáo các file đã sửa.
```

---

## Phụ lục A — Sơ đồ luồng

### Hiện tại (bỏ)

```text
Agent → query_radar(reference_file abs)
     → get_kuzu_store
     → ensure_mcp_kuzu_ready
     → validate OK
     → kuzu CHƯA có
     → spawn_detached_kuzu_build
           ghi .building + build_cmd (KHÔNG Popen)
     → raise KuzuBuildingError
     → _mcp_gate_error_json → Agent nhận JSON building
     → Agent có thể BỎ QUA run_command
     → Kuzu không bao giờ có
```

### Mong muốn (cách cũ + giữ validate)

```text
Agent → query_radar(reference_file abs)
     → get_kuzu_store
     → ensure_mcp_kuzu_ready
     → validate OK (relative/sai path → InvalidReferenceFileError, DỪNG, không build)
     → kuzu CHƯA có
     → build_and_save_graph(controllers, graph_dir)   # IN-PROCESS, block đến xong
     → return db_path
     → ensure_fresh_readonly_store + execute_cypher
     → Agent nhận KẾT QUẢ query
```

### Kuzu đã có

```text
ensure_mcp_kuzu_ready → kuzu_db_ready True → return db_path → query như bình thường
(không build, không marker)
```

---

## Phụ lục B — Chỗ code hiện tại cần thay (định vị)

`xml_fbograph/utils/kuzu_build_spawn.py` khoảng cuối file:

```python
def ensure_mcp_kuzu_ready(reference_file: str) -> Path:
    ...
    if kuzu_db_ready(db_path):
        clear_building_marker(graph_dir)
        return db_path

    payload = spawn_detached_kuzu_build(reference_file, graph_dir)
    raise KuzuBuildingError(payload)   # ← XÓA nhánh này, thay bằng sync-build + return db_path
```

`xml_fbograph/utils/kuzu_build_spawn.py` `spawn_detached_kuzu_build`: message `BAN PHAI SỬ DỤNG TOOL run_command...` + `"spawned": False` — toàn bộ hàm ra khỏi MCP path.

`xml_fbograph/tests/test_customerpro_kuzu_gate.py` `test_missing_kuzu_spawns_once_no_sync_build` đang assert `KuzuBuildingError` + `spawned is False` — test này **mô tả đúng bug hiện tại**, phải thay bằng test sync-build.

---

## Phụ lục C — File bug / kỳ vọng để Gemini đối chiếu

| | |
|---|---|
| Project mẫu | `E:\FBO\SP2263` hoặc UNC `\\172.168.5.14\CustomerPro\...` |
| `reference_file` đúng | `E:\FBO\SP2263\App_Data\Controllers\Dir\SVTran.xml` |
| Slot Kuzu | `C:/KuzuDB/<base64(project_root)>/.fbograph/kuzu` (`fbograph.kuzu_db_base` trong `config.yaml`) |
| Trước sửa (thiếu kuzu) | JSON `status=building`, `build_cmd=...exe build ...`, Agent phải tự chạy |
| Sau sửa (thiếu kuzu) | MCP block + log stderr đang build → trả JSON rows Cypher của `query_radar` |
| `reference_file` sai `Filter/SVInvoiceFilter.xml` | Vẫn `invalid_reference_file`, **không** build, **không** tạo slot ảo cwd |

---

## Phụ lục D — Câu hỏi không mở lại trong task này

- Có làm background build + MCP progress notification không? **Không.** User muốn sync + trả kết quả.
- Có giữ spawn detached “mở CMD cho user nhìn” không? **Không.** Cách đó vẫn bắt Agent retry; user đã từ chối ủy thác.
- Có xóa physical `.fbograph` trước first-create không? **Không** (tránh `overwrite=True`). CLI rebuild vẫn xóa như cũ.
- Có bật lại `search_nodes` / `get_related_nodes` / `query_node_details` không? **Không.** Đã ẩn có chủ đích; backup `backup_hidden_tools.py` để yên.
