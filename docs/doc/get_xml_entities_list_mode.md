# get_xml_entities — mode `list` / `get_all_entity`

## Mục tiêu

Mở rộng tool MCP `get_xml_entities` (không tạo tool mới) để agent **liệt kê toàn bộ ENTITY trong DOCTYPE** của file XML trước khi gọi `content` / `path`.

Tránh đoán sai tên entity (vd. `Commands`, `Tables`…) → NOT FOUND → đọc full file không cần thiết.

## API đề xuất

Giữ nguyên:

- `file_path` (bắt buộc)
- `entities` (array) — dùng cho `mode=content|path`
- `mode`: `content` | `path` | **`list`**

Hoặc flag tương đương: `get_all_entity=true` (khi bật thì bỏ qua / không bắt buộc `entities`).

### Khi `mode=list` (hoặc `get_all_entity=true`)

- Input: chỉ cần `file_path`
- `entities` không bắt buộc
- Parse DOCTYPE của file XML (`.xml`; `.f` theo convention hiện có của tool)
- **Không** resolve / đọc nội dung file `SYSTEM`
- **Không** trả toàn bộ nội dung XML

### Output JSON (mỗi entity)

| Field | Mô tả |
|-------|--------|
| `name` | Tên entity, vd. `XMLWhenVoucherInit`, `DetailTable` |
| `kind` | `general` hoặc `parameter` (`<!ENTITY % ...>`) |
| `is_external` | `true` nếu có `SYSTEM` / `PUBLIC` |
| `system_path` | Đường dẫn SYSTEM nếu có, ngược lại `null` |
| `value_preview` | Entity inline: value rút gọn ≤ 120 ký tự; entity SYSTEM: `null` |
| `line` | Số dòng khai báo trong file (nếu lấy được) |

## Hành vi / ràng buộc

1. Giữ nguyên `mode=content` và `mode=path` — không phá API cũ.
2. File không tồn tại → báo lỗi rõ, **không** tạo file mới.
3. Cập nhật description tool + docs cho agent:
   - Chưa biết tên entity → gọi `list` / `get_all_entity` trước
   - Đã biết tên → `content` / `path` như cũ
4. Implement + test/docs tối thiểu; không refactor ngoài phạm vi.

## Ví dụ gọi (agent)

```text
get_xml_entities(file_path="Dir/SVTran.xml", mode="list")
get_xml_entities(file_path="Dir/SVTran.xml", entities=["Invoice","DetailTable"], mode="content")
get_xml_entities(file_path="Dir/SVTran.xml", entities=["XMLWhenVoucherInit"], mode="path")
```

## Prompt triển khai (gửi Gemini / agent code)

```
Dự án MCP FBO tại E:\mcp_fbo. Đọc docs trong E:\mcp_fbo\docs\doc trước khi sửa.

Mở rộng tool get_xml_entities (không tạo tool mới).

Thêm option/mode: get_all_entity (hoặc mode="list").

Mục đích: agent không đoán tên ENTITY — gọi 1 lần lấy danh sách ENTITY trong DOCTYPE của file XML, rồi mới gọi lại get_xml_entities(mode=content|path) với đúng tên.

Yêu cầu hành vi:
1. Input: file_path (bắt buộc). Khi get_all_entity/list: entities không bắt buộc (có thể bỏ qua hoặc ignore).
2. Parse DOCTYPE của file XML (hỗ trợ .xml; nếu .f thì theo convention hiện có của tool).
3. Trả về danh sách gọn, ưu tiên JSON, mỗi entity gồm:
   - name (vd: XMLWhenVoucherInit, DetailTable)
   - kind: "general" | "parameter" (parameter = <!ENTITY % ...>)
   - is_external: true nếu có SYSTEM/PUBLIC
   - system_path: đường dẫn SYSTEM nếu có (vd: ..\Include\Invoice.ent), không thì null
   - value_preview: với entity inline (không SYSTEM), trả value rút gọn ≤120 ký tự; entity SYSTEM thì null hoặc để trống
   - line (số dòng khai báo trong file, nếu lấy được)
4. Không resolve/đọc nội dung file SYSTEM trong mode list.
5. Không trả toàn bộ nội dung XML file.
6. Giữ nguyên mode content và path hiện có; không phá API cũ.
7. File không tồn tại: báo lỗi rõ, không tạo file mới.
8. Cập nhật description tool + docs cho agent: khi chưa biết tên entity → gọi get_all_entity trước; khi đã biết tên → mode content/path như cũ.

Ví dụ gọi sau này (agent):
- get_xml_entities(file_path=Dir/SVTran.xml, mode=list)  // hoặc get_all_entity=true
- get_xml_entities(file_path=Dir/SVTran.xml, entities=["Invoice","DetailTable"], mode=content)

Implement + cập nhật test/docs tối thiểu trong dự án. Không refactor rộng ngoài phạm vi này.
```

## Ghi chú UX cho Cursor agent

Ưu tiên `mode=list` (cùng enum với `content`/`path`) hơn flag riêng — gọi ngắn, schema rõ.
