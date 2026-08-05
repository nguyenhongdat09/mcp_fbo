# FSPEC / PROMPT — Hard-guard `reference_file` cho FastBusiness MCP (chống lỗi path Agent)

> **Cách dùng:** Copy toàn bộ nội dung từ mục «PROMPT GỬI GEMINI» trở xuống, dán cho Gemini (hoặc AI khác) kèm repo `mcp_fbo` để nó implement.
>
> **Mục tiêu sản phẩm:** Agent Cursor gọi `search_nodes` / FBOGraph tools **không còn** tạo project Kuzu ảo, không còn báo `building` vì path tương đối / thiếu `reference_file`.

---

## PROMPT GỬI GEMINI

```
Bạn là Senior Python engineer làm việc trên repo FastBusiness MCP: E:\mcp_fbo
(package chính: fastbusiness_mcp/, xml_fbograph/).

# 1. Bối cảnh / Bug thật đã xảy ra

Agent Cursor gọi MCP tool search_nodes:

LẦN 1 — thiếu tham số:
→ Input validation error: 'reference_file' is a required property

LẦN 2 — truyền path TƯƠNG ĐỐI / ngắn, ví dụ:
  Filter/SVInvoiceFilter.xml
  hoặc App_Data/Controllers/Filter/SVInvoiceFilter.xml
Trong khi file thật của user là:
  E:\FBO\SP2263\App_Data\Controllers\Filter\SVInvoiceFilter.xml

MCP server chạy với cwd = E:\fastbusiness_mcp (hoặc tương đương).
Path.resolve() của path tương đối bị gắn vào cwd → thành:
  E:\fastbusiness_mcp\Filter\...
→ project_root = E:\fastbusiness_mcp\Filter  (folder KHÔNG tồn tại)
→ graph_dir = KuzuDB/<base64(E:\fastbusiness_mcp\Filter)>/.fbograph
→ kuzu chưa có → spawn_detached_kuzu_build ghi marker .building
→ trả JSON status=building + build_cmd:
  fastbusiness_mcp.exe build E:\fastbusiness_mcp\Filter

Trong khi Kuzu ĐÚNG của project đã có sẵn tại slot:
  base64(E:\FBO\SP2263) → đã có file kuzu.

Kết luận: KHÔNG phải mất DB. Là reference_file sai → resolve nhầm project → tạo slot ảo.

# 2. Mục tiêu implement (bắt buộc)

Sau khi sửa:
1) reference_file KHÔNG absolute → FAIL ngay với message rõ, KHÔNG Path.resolve theo cwd, KHÔNG tạo .building, KHÔNG trả build_cmd.
2) reference_file absolute nhưng không tìm được App_Data\Controllers hợp lệ trên đĩa → FAIL rõ, KHÔNG spawn build.
3) Chỉ khi project hợp lệ VÀ thiếu kuzu thật → mới được trả status=building + build_cmd như hiện tại.
4) Cập nhật mô tả schema MCP (reference_file) + .cursorrules để Agent biết phải truyền absolute path.
5) (Tuỳ chọn nhưng khuyến khích) Nếu nhận path tương đối: thử match vào các project đã đăng ký trong KuzuDB (discover_registered_projects); match đúng 1 file thì dùng project đó; 0 hoặc >1 → FAIL + liệt kê candidates. Không đoán bừa.

# 3. File / module liên quan (đọc trước khi sửa)

- xml_fbograph/utils/kuzu_build_spawn.py
  - ensure_mcp_kuzu_ready()
  - spawn_detached_kuzu_build()
  - kuzu_db_ready()
  - _raise_if_not_fbo_project()  ← hiện đang pass (no-op) — PHẢI implement hoặc thay bằng validate mới
  - NotFastBusinessProjectError, KuzuBuildingError

- xml_fbograph/utils/path_helper.py
  - ProjectPathHelper.get_project_root()
  - has_app_data_controllers / get_customerpro_project_path
  - discover_registered_projects()  ← đã có, dùng cho optional resolve
  - resolve_graph_dir / _encode_project_root / decode_project_root

- fastbusiness_mcp/server.py
  - Tool schemas: search_nodes, get_related_nodes, query_node_details, query_radar, read_local_file
  - property reference_file description hiện là "Any XML file path in the project to resolve paths" → QUÁ MƠ HỒ, Agent hay truyền relative

- .cursorrules (workspace root)
  - Thêm rule ngắn về reference_file absolute

- xml_fbograph/tests/test_customerpro_kuzu_gate.py
  - Bổ sung test case cho relative path / absolute rác / không Controllers

# 4. Thiết kế chi tiết (phải bám)

## 4.1. Hàm validate mới (đặt tên snake_case)

Ví dụ: validate_reference_file(reference_file: str) -> Path
hoặc mở rộng ensure_mcp_kuzu_ready / _raise_if_not_fbo_project.

Logic tối thiểu:

A) Chuỗi rỗng / None → error payload:
   error: "invalid_reference_file"
   reason: "missing"
   message: giải thích phải truyền absolute path + ví dụ E:\FBO\SP2263\App_Data\Controllers\Dir\XXTran.xml

B) Phát hiện path TƯƠNG ĐỐI:
   - Không match ổ đĩa Windows (^[A-Za-z]:[\\/]) 
   - Và không phải UNC (\\\\ hoặc //)
   → KHÔNG được Path(reference_file).resolve() theo cwd.
   → Optional (khuyến khích): thử resolve_relative_against_registered_projects(rel_path)
        * Dùng discover_registered_projects()
        * Với mỗi project_root: candidate = project_root / "App_Data" / "Controllers" / rel (chuẩn hoá bỏ prefix App_Data/Controllers nếu có)
        * Nếu đúng 1 candidate.is_file() → trả về absolute đó và tiếp tục
        * Nếu 0 hoặc >1 → error reason: "ambiguous_or_unresolved_relative" + list candidates / known projects
   → Nếu không làm optional: FAIL ngay reason: "relative_path_forbidden"

C) Path absolute:
   - Normalize separator / UNC (đã có _normalize_path_str)
   - Dùng ProjectPathHelper / has_app_data_controllers
   - Phải tồn tại App_Data\Controllers trên đĩa (is_dir)
   - Nếu không: error reason: "missing_controllers" — KHÔNG spawn build
   - (Khuyến nghị) Nếu bản thân file reference chưa tồn tại nhưng Controllers tồn tại → VẪN CHO PHÉP (vì reference_file chỉ để resolve project). Document rõ trong code comment.

D) Chỉ sau khi A–C pass:
   - graph_dir = helper.get_graph_dir()
   - db_path = graph_dir / "kuzu"
   - nếu kuzu_db_ready → clear_building_marker; return db_path
   - else → spawn_detached_kuzu_build như hiện tại (building)

## 4.2. Error payload chuẩn (JSON-serializable)

Khi invalid reference_file, raise exception kiểu NotFastBusinessProjectError
HOẶC exception mới InvalidReferenceFileError với payload:

{
  "error": "invalid_reference_file",
  "reason": "relative_path_forbidden" | "missing" | "missing_controllers" | "ambiguous_or_unresolved_relative",
  "message": "<tiếng Việt, rõ ràng, hướng dẫn Agent truyền absolute>",
  "reference_file": "<input gốc>",
  "hint": "Luôn truyền absolute path, ví dụ: E:\\\\FBO\\\\SP2263\\\\App_Data\\\\Controllers\\\\Filter\\\\SVInvoiceFilter.xml",
  "known_projects": ["E:\\\\FBO\\\\SP2263", ...]   // optional, từ discover_registered_projects
}

QUAN TRỌNG:
- status KHÔNG được là "building" trong các case invalid path.
- KHÔNG ghi file .building
- KHÔNG trả build_cmd

MCP call_tool layer (fastbusiness_mcp/server.py hoặc mcp_tools.py) phải bắt exception này và trả TextContent JSON payload (giống cách đang handle KuzuBuildingError / NotFastBusinessProjectError). Kiểm tra handler hiện tại và wire đúng.

## 4.3. Cập nhật Tool schema description

Mọi property tên reference_file trong fastbusiness_mcp/server.py (và chỗ schema trùng nếu có) đổi description thành nội dung mạnh, ví dụ:

"BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO để resolve Kuzu/project root.
Ví dụ đúng: E:\\FBO\\SP2263\\App_Data\\Controllers\\Dir\\SVTran.xml
hoặc UNC: \\\\server\\CustomerPro\\FBO\\...\\App_Data\\Controllers\\Dir\\SVTran.xml
CẤM path tương đối: Filter/x.xml, App_Data/Controllers/..., ./Dir/x.xml.
Thiếu hoặc relative sẽ bị reject; không dùng để build Kuzu."

Giữ required: ["..., reference_file"] như hiện tại. KHÔNG bỏ required.

## 4.4. Cập nhật .cursorrules

Thêm section ngắn (tiếng Việt), ví dụ:

## FBOGraph reference_file (BẮT BUỘC)
- Mọi tool: search_nodes, get_related_nodes, query_node_details, query_radar, read_local_file
  phải truyền reference_file = ABSOLUTE path XML trong project đang làm
  (vd E:\\FBO\\SP2263\\App_Data\\Controllers\\Filter\\SVInvoiceFilter.xml).
- CẤM relative / basename. Nếu user đang mở file trong IDE → lấy full path file đó.
- Nếu tool trả invalid_reference_file → sửa path rồi gọi lại, KHÔNG chạy build_cmd cho path lạ.

## 4.5. Cleanup slot ảo (script/note, không bắt buộc code)

Document trong PR/commit message: có thể xóa thủ công folder KuzuDB hash của
E:\fastbusiness_mcp\Filter nếu còn:
  E:\fastbusiness_mcp\KuzuDB\RTpcZmFzdGJ1c2luZXNzX21jcFxGaWx0ZXI=
Chỉ xóa slot ảo đó; KHÔNG đụng slot E:\FBO\SP2263.

# 5. Tests bắt buộc

Thêm/sửa trong xml_fbograph/tests/test_customerpro_kuzu_gate.py (hoặc file test mới):

1) reference_file = "Filter/SVInvoiceFilter.xml"
   → raise invalid_reference_file (relative), KHÔNG tạo .building dưới bất kỳ graph_dir nào gắn cwd giả.

2) reference_file absolute trỏ project không có App_Data/Controllers
   → missing_controllers, không building.

3) reference_file absolute đúng temp CustomerPro fixture đã có Controllers + đã có kuzu file giả
   → ensure_mcp_kuzu_ready return db_path, không building.

4) reference_file absolute đúng Controllers nhưng chưa có kuzu
   → KuzuBuildingError status=building (giữ behavior cũ).

5) (Nếu làm optional resolve) relative path + đúng 1 registered project chứa file đó
   → resolve thành absolute và ready/building đúng project đó.

Chạy test bằng venv project; không deploy DB/proc.

# 6. Ràng buộc / Không được làm

- KHÔNG đổi logic Cypher / schema Kuzu / builder graph trừ khi cần import validate.
- KHÔNG sync-build Kuzu trong process MCP (giữ detached / agent-run build_cmd như thiết kế hiện tại) — nhưng CHỈ khi path hợp lệ.
- KHÔNG hardcode d91$202501 / partition.
- KHÔNG commit / xóa nhầm KuzuDB của E:\FBO\SP2263.
- Biến local / param: snake_case.
- Comment tiếng Việt ngắn nơi validate quan trọng.

# 7. Definition of Done

- [ ] Relative reference_file không còn tạo E:\...\Filter slot / .building
- [ ] Missing reference_file vẫn fail schema (giữ required); nếu lọt xuống runtime cũng có message rõ
- [ ] Absolute đúng SP2263-like path dùng đúng graph_dir đã có kuzu
- [ ] Schema description + .cursorrules đã cập nhật
- [ ] Unit tests mới pass
- [ ] Tóm tắt thay đổi + ví dụ JSON error mới trong response cho user

Hãy đọc code hiện tại, implement đúng thiết kế trên, chạy test liên quan, rồi báo cáo diff các file đã sửa.
```

---

## Phụ lục (cho người gửi prompt) — tóm tắt 1 dòng

| Layer | Việc |
|-------|------|
| MCP gate | Reject relative / Controllers ảo trước khi `.building` |
| Tool schema | Description `reference_file` bắt absolute |
| `.cursorrules` | Agent luôn lấy full path file đang mở |
| Optional | Relative → match 1 project trong `discover_registered_projects` |
| Cleanup | Xóa slot hash `E:\fastbusiness_mcp\Filter` nếu còn |

## File bug thật để Gemini đối chiếu

- User file đúng: `E:\FBO\SP2263\App_Data\Controllers\Filter\SVInvoiceFilter.xml`
- Path agent sai: `Filter/SVInvoiceFilter.xml`
- Project resolve nhầm: `E:\fastbusiness_mcp\Filter`
- build_cmd sai: `E:\fastbusiness_mcp\fastbusiness_mcp.exe build E:\fastbusiness_mcp\Filter`
