# MCP Impact — FBO Platform Migration (FastReport / No WebForm / API / Cross-platform SQL)

> **Bối cảnh:** FRD thông báo FBO sẽ chuyển toàn bộ sang nền tảng mới:
>
> 1. **Crystal Report → FastReport.Net** — thiết kế/xuất mẫu in bằng FastReport.
> 2. **Bỏ WebForm (.aspx)** — không còn ViewState/server controls; chuyển CSR + Web Components (JS ES6+).
> 3. **Bỏ AjaxControlToolkit** — tương tác bất đồng bộ bằng JS thuần ES6+.
> 4. **Bỏ ASMX Web Service / IHttpHandler** — thay bằng API chuẩn (JSON).
> 5. **SQL chạy đa hệ điều hành** — Stored Proc tương thích Linux (không chỉ Windows).
>
> Tài liệu này liệt kê **toàn bộ điểm chạm trong fastbusiness-mcp** cần rà soát khi bản
> mới ra mắt, kèm file:line tại thời điểm viết (2025). Chưa có chương trình thật nên
> nhiều chi tiết là "chưa biết" — mục 5 là checklist khảo sát khi có project bản mới.

## 1. Kết luận tổng

- **MCP KHÔNG phải viết lại.** Engine lõi (XML parser, T-SQL engine, DB layer,
  Jev routing) phụ thuộc **metadata XML + SQL** — 2 thứ FBO giữ nguyên.
- Thay đổi tập trung ở **"convention layer"**: danh sách file/thư mục/extension/attr
  theo quy ước FBO. Ước lượng ~10–15 chỗ sửa + template + skills/docs.
- **Yêu cầu quan trọng nhất: hỗ trợ SONG SONG 2 convention** (cũ + mới) vì user quản
  lý nhiều project nhiều đời FBO — project cũ vẫn Crystal/WebForm, project mới
  FastReport/CSR. Không được xóa convention cũ.

## 2. Bản đồ điểm chạm theo từng thay đổi

### 2.1 Crystal → FastReport.Net (mức độ: vừa)

Crystal hiện để lại 2 dấu vết trong code: thư mục `Templates/Rpt` (file `.rpt` mẫu
in + `.xsd` schema dataset) và attr `reportFile`/`templateFile` trong Report XML.

| Chỗ cần sửa | File | Hiện trạng |
|---|---|---|
| Candidate `.xsd` | `clone_things/type3_file_clone.py:113` | `Templates/Rpt/{ctrl}.xsd` — FastReport không dùng `.xsd`; giữ cho project cũ, thêm dir mới |
| Scan dir | `clone_things/type3_file_clone.py:143-161` (`SUITE_SCAN_DIRS`) | Có `Templates/Rpt` (153) + `Templates/Excel` (154); **thêm dir FastReport** khi biết tên (vd `Templates/Frx`?) |
| Template refs | `clone_things/type3_file_clone.py:226-235` (`RE_TEMPLATE_FILE` + `_TEMPLATE_FILE_DIRS`) | Regex `(templateFile|reportFile)`; **kiểm tra attr mới** nếu FastReport đổi tên attr |
| Deny `.xsd` | `type3_file_clone.py:1131-1138` + `suggest_edit/service.py:721` + `xml_fbograph/mcp_tools.py:812-814` + `search_files/service.py:179-180` + `mcp_app.py` nhiều chỗ | Lý do deny là "designer sinh lại schema" = đặc thù Crystal. **Giữ deny** (vô hại cho project cũ); nếu bản mới vẫn sinh `.xsd` cho mục đích khác thì xem lại |

**Điểm thuận lợi:** `.frx` (FastReport) là file XML text — **tự động đọc/sửa/search
được** bằng tool hiện có, không nằm trong deny list. Không cần viết parser mới.

### 2.2 Bỏ .aspx WebForm (mức độ: vừa-lớn, nhiều chỗ sửa nhất)

Đây là hạng mục MCP phụ thuộc sâu nhất — `.aspx` là **entry point** của mọi chức
năng và là cách suite-clone phát hiện trang chủ.

| Chỗ cần sửa | File | Hiện trạng |
|---|---|---|
| Candidate `Main/{ctrl}.aspx` | `clone_things/type3_file_clone.py:129` | Entry point chuẩn trùng tên ctrl |
| Detect aspx theo nội dung | `clone_things/type3_file_clone.py:279-312` (`_detect_suite_aspx`) | Scan `Main/*.aspx` tìm `Controller="<ctrl>"` — **cần pattern mới** khi biết entry point thay thế (`.html`? `.js` module? route?) |
| Warnings aspx | `clone_things/type3_file_clone.py:352-369` | `suite_aspx_detected` / `suite_aspx_missing` |
| PRESETS mail/ajax | `clone_things/type3_file_clone.py:25-39` | `AjaxWeb.aspx`, `AjaxWeb_Core.aspx`, `jAjax.js` — cầu nối ajax cũ, **chết** trên bản mới; giữ cho project cũ |
| Template type=4 | `template/*/manifest.yaml` (dst `Main/{new}.aspx`) + các file `main.aspx`/`main_voucher.aspx`/`main_approval.aspx` | **Mọi manifest ship 1 aspx entry point** — phải thay bằng file entry-point mới khi biết format |
| check_things | `check_things/file_resolver.py:30-35` | `.aspx` → skipped (v1 không port AnalystASPX) — cập nhật ext mới nếu cần resolve |
| JS extractor | `xml_fbograph/mcp_tools.py:475` (`_PLAIN_SCRIPT_EXTS`) + `xml_controller_summary/snippet.py:25-33` | Đã generic (`.aspx/.html/.htm/.cshtml`) — **chỉ cần thêm ext mới** (vd `.html` đã có sẵn) |
| search glob | `search_files/service.py:179` include_glob `*.{xml,aspx,js,html,config,ent,txt,sql}` | Thêm ext entry-point mới |
| tool_help | `tool_help/notices.py:126,140,179-180` + `tool_help/cards.py:52,295-296,549,593,791,880-889` | Text nhắc `aspx`, `Chart.ascx`, `Controller=` — cập nhật wording |

**Lưu ý:** JS nhúng trong Dir XML `<command>` (`f.request`, `g.request`,
`objectBehavior$...`) là API client của FBO — nếu runtime mới đổi API này thì
**skill `fbo-js-skill` + docs phải viết lại**, còn MCP tools vẫn đọc/trích được bình
thường (extractor không phụ thuộc tên API).

### 2.3 Bỏ AjaxControlToolkit (mức độ: gần như 0)

MCP không đụng toolkit. Chỉ ảnh hưởng gián tiếp qua `PRESETS` ở mục 2.2.

### 2.4 Bỏ ASMX/IHttpHandler → API JSON (mức độ: nhỏ — chủ yếu docs/skills)

- **MCP tự thân không gọi webservice FBO.** HTTP call duy nhất: Jev (TypeSafe) +
  `search_qlyc` (QLYC API) — đều ngoài FBO app (`jev/client.py`, `search_qlyc/client.py`).
- Ảnh hưởng nằm ở **skill docs**: `fbo-js-skill` mô tả `f.request`/`g.request` gọi
  endpoint — nếu endpoint đổi sang API chuẩn, cập nhật skill.
- `fbo-fastapi-test` skill **quan trọng hơn** sau migration (Fast đã có tầng API).
- Có thể cần tool mới gọi API FBO (vd test endpoint, lấy metadata runtime) — cân nhắc
  khi biết đặc tả API.

### 2.5 SQL đa hệ điều hành (mức độ: nhỏ / tùy chọn)

- `query_database` + `tsql_engine` (PARSEONLY) là T-SQL — SQL Server trên Linux vẫn
  cùng dialect, **không đổi**.
- Nâng cấp tùy chọn khi có yêu cầu: rule check **non-portable** trong
  `check_things`/proc analysis — `xp_cmdshell`, `sp_OA*`, OLE automation, đường dẫn
  Windows (`C:\`, `\\`), CLR assembly, `xp_regread`, cross-server query, codepage
  phụ thuộc collation. Chưa có spec → để sau.

## 3. Phần KHÔNG cần động vào

- `xml_controller_summary` / `suggest_edit` / `check_things` / `compare_things`
  (`kind=xml`) — chỉ đọc XML metadata, format không đổi.
- `clone_things` type=1/2 (SQL object clone), type=3 core copy engine, `paste_sql`,
  `query_database`, `db_check_syntax` — tầng DB/file chung.
- `xml_fbograph` — chỉ còn resolve project (`path_helper`/`any_path`) và `read_local_file`; phần graph/Kuzu đã gỡ.
- `tool_help` routing core + Jev — độc lập platform.
- Deny `.f` mã hóa — chắc chắn vẫn tồn tại (định dạng nội bộ FBO).

## 4. Những gì CHƯA BIẾT — phải đợi bản mới

Đừng code đoán các mục này; sai convention = phải viết lại:

1. **Thư mục + extension mẫu FastReport**: `Templates/Frx`? `Templates/FastReport`?
   `.frx`/`.fpx`? Còn sinh `.xsd` không?
2. **Attr trong Report XML** có đổi không (`reportFile=` → tên mới?).
3. **Entry point thay thế `.aspx`**: file `.html`? `.js` module? Route trong config?
   Cách link controller (`Controller="..."` hay attr/JSON khác)?
4. **Đồ thị/nút chart**: `Chart.ascx` chết theo WebForm — component thay thế?
5. **API client JS mới**: `f.request`/`g.request` giữ hay đổi signature?
6. **Có giữ tương thích ngược không**: FBO có thể ship song song `.aspx` trong thời
   gian chuyển — scan code phải chịu được "thiếu entry point" mà không báo lỗi giả.

## 5. Checklist khảo sát khi có project bản mới

Khi nhận được 1 project chạy bản mới, làm theo thứ tự:

1. `compare_things kind='folder'` giữa project cũ + mới trên `App_Data/Controllers`
   và `Main/` để thấy dir/file nào mới/biến mất.
2. Tìm file mẫu report mới → ghi lại **dir + ext** → thêm vào `SUITE_SCAN_DIRS`,
   `get_suite_candidates`, `_TEMPLATE_FILE_DIRS`.
3. Mở `Report/{ctrl}.xml` bản mới → kiểm tra attr `reportFile`/`templateFile` còn
   hay đổi tên → cập nhật `RE_TEMPLATE_FILE`.
4. Tìm entry point (mở `Main/` hoặc tương đương) → ghi **pattern file + cách bind
   controller** → viết `_detect_suite_entry` thay `_detect_suite_aspx`.
5. Kiểm tra `.xsd` còn được sinh không → quyết định giữ/bỏ deny.
6. Chạy `clone_things` type=6 dry-run trên 1 báo cáo bản mới → xem suite bắt đủ file
   chưa (warnings `suite_*`).
7. Soi 1 Dir XML bản mới → JS API (`f.request`...) giữ hay đổi → cập nhật skills.
8. Cập nhật `template/*/manifest.yaml` + file `main.*` entry-point.
9. Cập nhật `search_files` include_glob, `_PLAIN_SCRIPT_EXTS`, `file_resolver` ext.
10. Cập nhật `tool_help` cards/notices wording + skills mirror ×4 + docs.
11. Thêm test fixture mô phỏng layout mới trong `tests/clone_things/` (tmp_path
    giống test type6 hiện có).

## 6. Chuẩn bị có thể làm NGAY (không cần đợi bản mới)

- **Gom convention thành profile per-project**: `SUITE_SCAN_DIRS`,
  `get_suite_candidates`, ext globs, deny list hiện hardcode ~15 chỗ → tách thành
  cấu trúc `{suite_dirs, candidates_fn, entry_exts, deny_exts}` chọn theo project
  (detect version bằng marker file: `Templates/Frx` tồn tại? `Main/*.aspx` còn?).
  Khi bản mới ra chỉ cần **thêm 1 profile** thay vì săn code.
- Giữ nguyên convention cũ trong profile "v1" — project cũ không ảnh hưởng.
- Việc này nhỏ, an toàn, test được ngay; nhưng nếu chưa muốn thì cứ để doc này,
  khi có bản mới làm một thể.

## 7. Bảng tổng hợp mức độ ảnh hưởng

| Thay đổi FBO | Vùng MCP ảnh hưởng | Mức độ | Ghi chú |
|---|---|---|---|
| Crystal → FastReport | type3 suite (dir/attr/deny) | Vừa | `.frx` đọc được ngay, chỉ cần thêm dir |
| Bỏ WebForm/.aspx | type3 candidates + detect, type4 templates, file_resolver, globs, tool_help text | Vừa-lớn | Nhiều chỗ nhưng toàn pattern file |
| Bỏ AjaxControlToolkit | — | ~0 | — |
| ASMX/handler → API | skills docs; có thể tool mới | Nhỏ | `fbo-fastapi-test` quan trọng hơn |
| SQL đa nền tảng | `check_things` rule mới (tùy chọn) | Nhỏ | T-SQL không đổi |
