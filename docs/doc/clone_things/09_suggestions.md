# 09 — Suggestions (không bắt buộc v1)

Các ý dưới đây **không** block merge v1. Ghi để BA/product chọn phase sau.

## 1. `dry_run`

Param `dry_run=true`: chạy toàn bộ resolve + exists + deps, **không** ghi file / không mở editor. JSON vẫn trả `cloned` (would_clone), `skipped_exists`, `not_found_both`.

Dùng cho Agent ước lượng scope trước khi paste.

## 2. `CREATE OR ALTER` / idempotent script (type=0)

Option `script_style` cho **type=0**: `raw` (default, giữ source) | `create_or_alter`.

> **Đã lấy một phần cho type=1:** paste-for-edit dùng **`ALTER`** (không phải `CREATE OR ALTER`) — xem [11_type1_paste_for_edit.md](./11_type1_paste_for_edit.md). Suggestion này chỉ còn áp dụng nếu muốn thêm style cho nhánh clone type=0.

## 3. Topological sort (GO đã là v1)

- Sắp tables → views → functions → procedures trước khi ghi (GO giữa batch **đã bắt buộc** trong `03` / `08` — không còn optional).
- Phase sau chỉ còn việc **sắp thứ tự topo** cho dễ Execute một lần.

## 4. Diff source vs target

Nếu object **có ở cả hai** nhưng definition khác: thay vì chỉ `skipped_exists`, thêm `exists_but_different` (hash / modify_date so sánh). Hữu ích khi sync hotfix.

## 5. `db_type` / multi-DB

Param rõ `db_type_source` / `db_type_target` (`app`|`sys`) khi object nằm sys DB.

## 6. Clone type=2 — file XML / Controllers (đổi số — không dùng type=1)

> **Thu hồi:** Trước đây gợi ý `type=1` = copy XML Controllers. **`type=1` đã dành cho paste-for-edit** ([11](./11_type1_paste_for_edit.md)).

Phase sau: `type=2` (hoặc tên khác) copy file XML (và companion Grid/Filter) từ source tree sang target tree, kèm map path. Tách khỏi SQL pipeline.

## 7. Integration extension

Command palette “Clone SQL to Temp” gọi MCP hoặc HTTP local — mở tab bằng VS Code API chính chủ (ổn định hơn `os.startfile`).

## 8. Báo cáo Markdown

Thêm file `.md` cạnh `.sql` liệt kê cloned / skipped / missing — cho human review UR.

## 9. Mở rộng summary_xml

- Hỗ trợ Report/Lookup trong `read_option=3`
- Thêm `sql.functions[]` thật
→ `clone_things` XML seed sẽ đủ hơn mà không đổi tool API.

## 10. FK / index dependency cho table

Khi clone table, optionally enqueue FK referenced tables (cẩn thận chu kỳ danh mục lớn).

## 11. `include_infra=true`

Override exclude để clone cả `fsd_*` khi cần (hiếm).

## 12. Streaming progress

Với queue dài: log / partial JSON progress (MCP notifications nếu runtime hỗ trợ) — tránh Agent tưởng treo.

## 13. Bảo mật

Allowlist project roots trong config — chỉ cho clone giữa các path nằm trong list (tránh đọc nhầm Web.config ngoài ý muốn).

## 14. Force-deps khi root đã có ở target

v1: object đã có target → skip, không quét con. Phase sau: param `force_missing_deps=true` để vẫn summary deps trên source/target và chỉ clone phần còn thiếu.
