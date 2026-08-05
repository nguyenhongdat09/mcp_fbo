# FSPEC / PROMPT — Fix lỗi Kùzu `parent database is closed` trên FBOGraph MCP

> **Cách dùng:** Copy toàn bộ nội dung từ mục «PROMPT GỬI GEMINI» trở xuống, dán cho Gemini (hoặc AI khác) kèm repo `E:\mcp_fbo` để nó investigate + fix.
>
> **Mục tiêu sản phẩm:** Agent Cursor gọi song song `search_nodes` / `get_related_nodes` / `query_radar` **không còn** nhận lỗi runtime Kùzu dạng `parent database is closed`; nếu connection/DB bị đóng giữa chừng thì MCP **tự reopen + retry 1 lần** rồi mới trả lỗi.

---

## PROMPT GỬI GEMINI

```
Bạn là Senior Python engineer làm việc trên repo FastBusiness MCP: E:\mcp_fbo
(package chính: fastbusiness_mcp/, xml_fbograph/).

# 1. Bối cảnh / Bug thật đã xảy ra

Agent Cursor (session SP228 BANYANFBO) gọi MCP FastBusiness FBOGraph tools:

Tools lỗi (cùng lúc, đầu session):
- get_related_nodes
- search_nodes
- query_radar

Error message (nguyên văn từ MCP response):
  Loi get_related_nodes: Runtime exception: The current operation is not allowed because the parent database is closed.
  Loi thuc thi Cypher: Runtime exception: The current operation is not allowed because the parent database is closed.
  Loi search_nodes: Runtime exception: The current operation is not allowed because the parent database is closed.

Cùng MCP, các tool KHÔNG dùng Kùzu vẫn OK ngay lúc đó:
- query_database (SQL Server)
- get_xml_entities (đọc XML)

Vài phút sau, Agent gọi LẠI đúng 3 tool FBOGraph (cùng reference_file UNC) → cả 3 OK, không cần rebuild index, không restart MCP thủ công rõ ràng từ phía user.

reference_file dùng:
  \\172.168.5.14\CustomerPro\FBO\BANYANFBO\SP228\App_Data\Controllers\Dir\SVTran.xml

Kết luận hiện trường:
- KHÔNG phải thiếu Kuzu DB / chưa index.
- KHÔNG phải reference_file sai (path absolute UNC đúng CustomerPro).
- Là lỗi TRANSIENT lifecycle connection/Database Kùzu trong process MCP: DB/Connection bị đóng trong khi Connection hoặc store cache vẫn còn được dùng.

# 2. Giả thuyết gốc (ưu tiên cao → thấp) — Agent Cursor ghi từ đọc code

## H2-A (CAO) — Reconnect handler KHÔNG nhận diện lỗi "parent database is closed"

File: xml_fbograph/storage/kuzu_index.py

Hàm `_is_connection_closed_error`:
  return "connection is closed" in msg or "connection closed" in msg

Error thật từ Kùzu:
  "The current operation is not allowed because the parent database is closed."

→ Chuỗi "parent database is closed" KHÔNG match 2 pattern trên.
→ Các chỗ catch + reopen (search_fields / execute_cypher / … gọi close_cached_database rồi _bind_live_connection(force_reopen=True)) KHÔNG kích hoạt.
→ Exception bubble thẳng ra MCP tool → Agent thấy lỗi.

Có file stress_test_reconnect.py cho thấy team đã biết race close/reopen, nhưng pattern detect còn hẹp.

FIX đề xuất:
- Mở rộng `_is_connection_closed_error` (đổi tên nếu cần thành `_is_kuzu_closed_error`) để bắt thêm:
  - "parent database is closed"
  - "database is closed"
  - "connection has been closed" (nếu có)
- Đảm bảo MỌI đường execute Cypher / query tool (query_radar, search_nodes, get_related_nodes, query_node_details) đều đi qua 1 wrapper execute có: try → nếu closed-error → close_cached_database + force_reopen + retry đúng 1 lần.
- Hiện một số method đã có retry, nhưng query_radar / đường execute_cypher raw có thể chưa đồng nhất — audit toàn bộ.

## H2-B (CAO) — Race khi gọi song song 3 tool FBOGraph

Hiện tượng: Agent gọi get_related_nodes + search_nodes + query_radar gần như CÙNG LÚC ở đầu session.

Luồng liên quan:
- mcp_tools.get_kuzu_store() → ensure_fresh_readonly_store() → có thể close_cached_database() khi mtime/cache miss
- close_cached_database() đóng conn + db rồi pop `_db_instances`
- Thread/request khác vẫn giữ KuzuIndexStore cũ với self.conn/self.db trỏ object đã close → query → "parent database is closed"
- Watcher (start_watcher_for_project được gọi trong get_kuzu_store) cũng có invalidate_project_cache() → close_cached_database

File liên quan:
- xml_fbograph/mcp_tools.py (get_kuzu_store, start_watcher_for_project)
- xml_fbograph/query/engine.py (ensure_fresh_readonly_store)
- xml_fbograph/storage/kuzu_index.py (close_cached_database, _bind_live_connection, _db_instances)
- xml_fbograph/service/watcher.py (invalidate_project_cache)

FIX đề xuất:
- Mọi reopen/close DB phải dưới cùng RLock theo db_path_key (đã có get_db_lock — audit xem close + execute có luôn cùng lock không; locked_execute trên conn có thể không bao phủ close vs execute cross-store).
- Sau close_cached_database, mọi store cache (engine._store_cache, mcp_tools._kuzu_stores) phải invalidate (đã có một phần trong invalidate_store_caches_for_db — kiểm tra không còn reference stale).
- Optional: serial hóa lần open đầu tiên per db_path (singleflight) để N request song song không cùng close/reopen.

## H2-C (TRUNG) — close DB trong lúc vẫn còn Connection sống

close_cached_database:
  cached["conn"].close()
  cached["db"].close()
  pop _db_instances

Nếu Connection.close() không đủ / thứ tự sai / object khác vẫn giữ Database → Kùzu báo parent database closed khi execute.

FIX: chuẩn hóa close order + không reuse Connection sau khi Database đã close; luôn tạo Database + Connection mới khi reopen.

## H2-D (TRUNG) — Watcher incremental write vs read-only MCP query

get_kuzu_store luôn start_watcher_for_project.
Watcher khi file change gọi invalidate + close DB để ghi incremental.
Query RO đang chạy / cache RO vừa lấy có thể đụng lock/conflict trên cùng Kuzu path (nhất là DB nằm trên UNC CustomerPro hoặc copy local cache).

Code đã WARN:
  "Recommend using a single MCP instance per machine for same KuzuDB to avoid lock conflicts."

FIX đề xuất:
- Khi đang có query RO, watcher không close đột ngột không đồng bộ; hoặc query path luôn ensure_fresh + retry on closed.
- Document / enforce 1 MCP instance per machine nếu chưa.

## H2-E (THẤP-TRUNG) — UNC path + local fbo_kuzu_cache copy

KuzuIndexStore có nhánh copy remote Kuzu về %TEMP%/fbo_kuzu_cache khi path remote.
Race copy/mtime giữa processes hoặc giữa open RO và watcher write có thể khiến reopen/close liên tục ở đầu session.

Không phải nguyên nhân chắc (vì retry sau vài phút OK với cùng UNC), nhưng nên kiểm tra log lúc lỗi có "Failed to copy remote Kuzu" / reopen mtime không.

## H2-F (THẤP) — maybe_cleanup_stale_kuzu mỗi request

get_kuzu_store và xml_graph_query gọi maybe_cleanup_stale_kuzu().
Cleanup stale theo retention — ít khả năng xóa project đang touch (vì touch_kuzu_access ngay trước đó), trừ bug decode/path key. Vẫn nên xác nhận cleanup KHÔNG bao giờ xóa/đóng DB đang active của request hiện tại.

# 3. Việc CẦN làm (acceptance)

1. Reproduce:
   - Viết/ mở rộng test (có thể dựa stress_test_reconnect.py) simulate:
     a) close_cached_database giữa chừng trong khi N thread execute_cypher
     b) raise/ giả lập exception message chứa "parent database is closed"
   - Kỳ vọng: tool/wrapper retry thành công, không trả lỗi ra ngoài trừ khi reopen cũng fail.

2. Fix `_is_connection_closed_error` (hoặc tương đương) nhận đủ lỗi closed của Kùzu, gồm "parent database is closed".

3. Audit mọi public MCP FBOGraph entry:
   - search_nodes
   - get_related_nodes
   - query_radar
   - query_node_details
   Đảm bảo cùng 1 execute wrapper có reopen+retry.

4. Giảm race parallel open/close (singleflight / giữ lock xuyên suốt close→rebind→execute).

5. Log rõ khi reopen vì closed-error (stderr [FBOGraph] Reopen after closed: ... ) để lần sau debug nhanh.

6. Không đổi contract MCP tools / không phá CustomerPro gate reference_file.

7. Chạy lại tests liên quan:
   - xml_fbograph/tests/test_watcher_advanced.py
   - xml_fbograph/tests/test_radar_schema.py
   - stress_test_reconnect.py (cập nhật nếu cần)
   - test mới cho parent-database-closed

# 4. Out of scope

- Không đụng query_database / get_xml_entities (không liên quan Kùzu).
- Không yêu cầu user rebuild toàn bộ Kuzu trừ khi chứng minh DB corrupt.
- Không đổi schema XmlFile/Rel.

# 5. File ưu tiên đọc/sửa

- xml_fbograph/storage/kuzu_index.py   (_is_connection_closed_error, close_cached_database, _bind_live_connection, execute_cypher wrappers)
- xml_fbograph/query/engine.py         (ensure_fresh_readonly_store)
- xml_fbograph/mcp_tools.py            (get_kuzu_store, tool handlers)
- xml_fbograph/service/watcher.py      (invalidate_project_cache)
- stress_test_reconnect.py
- xml_fbograph/save_disk/cleanup.py    (chỉ review an toàn với active DB)

Hãy: (1) xác nhận root cause bằng test reproduce, (2) implement fix tối thiểu + test, (3) tóm tắt diff và cách verify bằng 3 tool MCP song song.
```

---

## Ghi chú nội bộ (Agent Cursor — không bắt buộc gửi Gemini)

| Thời điểm | Hiện tượng |
|-----------|------------|
| Session SP228 ~2026-08-03 | 3 tool FBOGraph fail cùng lúc với `parent database is closed` |
| Cùng lúc | `query_database`, `get_xml_entities` OK |
| ~vài phút sau | Retry 3 tool FBOGraph → OK |

Đoán mạnh nhất khi đọc code: **H2-A + H2-B** (detect lỗi hẹp + race close/reopen khi parallel tools).
