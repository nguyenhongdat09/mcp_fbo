# Fix get_xml_entities mode=list — chỉ trả `kind=general`

## Bối cảnh

Tool `get_xml_entities` đã có `mode=list` liệt kê ENTITY trong DOCTYPE.

Trên file lớn (vd. `Dir/SVTran.xml`) hiện trả ~1101 entity (~211KB), trong đó:

| kind | Số lượng (SVTran) | Dùng với `mode=content`? |
|------|-------------------|---------------------------|
| `general` | ~587 | Có (`&Name;`) |
| `parameter` | ~514 | Không (chỉ `%Name;` trong DTD / include `.ent`) |

Agent Cursor dùng `list` để **biết tên entity rồi gọi `content`/`path`**. Parameter entity (`Invoice`, `DownPayment`…) không phải use-case đó → nhiễu.

## Yêu cầu sửa

### 1. Mặc định `mode=list` chỉ trả `kind=general`

- Lọc bỏ toàn bộ `kind=parameter` (`<!ENTITY % ...>`).
- Vẫn giữ schema từng item như hiện tại:
  - `name`, `kind`, `is_external`, `system_path`, `value_preview`, `line`
- Với mặc định mới, mọi item trả về đều có `"kind": "general"`.

### 2. (Khuyến nghị) Thêm filter tùy chọn — không bắt buộc nếu muốn làm tối giản

Thêm param tùy chọn, ví dụ:

- `kind_filter`: `"general"` (default) | `"parameter"` | `"all"`

Hoặc tên tương đương trong codebase hiện có.

Hành vi:

| kind_filter | Kết quả |
|-------------|---------|
| `general` (default) | Chỉ general entity |
| `parameter` | Chỉ parameter entity |
| `all` | Cả hai (hành vi cũ) |

Nếu **không** thêm param: chỉ cần hard-filter mặc định = `general` là đủ.

### 3. Không đổi `mode=content` / `mode=path`

- API cũ giữ nguyên.
- Không bắt buộc sửa xử lý `content` cho parameter entity trong ticket này.

### 4. (Cùng đợt nếu tiện) Chỉ list ENTITY khai báo trực tiếp trong DOCTYPE file

Ưu tiên phụ nhưng rất hữu ích: **không expand** `%Invoice;`, `%Profile;`, không đọc/merge entity từ file `SYSTEM` `.ent`.

Kỳ vọng sau khi lọc local + general: `SVTran` còn khoảng vài chục–~100 item, không còn hàng nghìn.

Nếu tách PR: làm **filter general trước**, local-only sau cũng được.

## Ví dụ kỳ vọng

### Gọi

```json
{
  "file_path": "\\\\172.168.5.14\\CustomerPro\\FBI\\CNNB_FBI\\FBISP229\\App_Data\\Controllers\\Dir\\SVTran.xml",
  "mode": "list"
}
```

### Có trong kết quả (general)

```json
{
  "name": "DetailTable",
  "kind": "general",
  "is_external": false,
  "system_path": null,
  "value_preview": "d81$$partition$current",
  "line": 88
}
```

```json
{
  "name": "g",
  "kind": "general",
  "is_external": false,
  "system_path": null,
  "value_preview": "SVDownPayment",
  "line": 100
}
```

### Không còn trong kết quả mặc định (parameter)

```json
{
  "name": "DownPayment",
  "kind": "parameter",
  "is_external": true,
  "system_path": "..\\Include\\DownPayment.ent",
  "value_preview": null,
  "line": 1
}
```

```json
{
  "name": "Invoice",
  "kind": "parameter",
  "is_external": true,
  "system_path": "..\\Include\\Invoice.ent",
  "value_preview": null,
  "line": 1
}
```

## Prompt triển khai (gửi Gemini)

```
Dự án MCP FBO tại E:\mcp_fbo. Đọc E:\mcp_fbo\docs\doc_fix\get_xml_entities_list_filter_general.md trước khi sửa.

Sửa tool get_xml_entities, mode=list:

1. Mặc định chỉ trả entity kind="general". Lọc bỏ kind="parameter".
2. (Khuyến nghị) Thêm param tùy chọn kind_filter: general|parameter|all — default=general. Không thêm param cũng được nếu hard-filter general.
3. Không đổi mode=content và mode=path.
4. Cập nhật description tool: mode=list mặc định chỉ liệt kê general entity (dùng với &Name; / content).
5. Test với Dir/SVTran.xml: kết quả list không còn DownPayment, Invoice (parameter); vẫn còn DetailTable, Tag, g (general).
6. Không refactor ngoài phạm vi này.

Optional cùng đợt: list chỉ lấy ENTITY khai báo trực tiếp trong DOCTYPE file, không expand %Include; / không merge từ file SYSTEM .ent.
```

## Acceptance

- [ ] `mode=list` mặc định không trả `DownPayment` / `Invoice` trên `SVTran.xml`
- [ ] Vẫn trả `DetailTable`, `Tag`, và các general entity khác
- [ ] `mode=content` với `DetailTable` vẫn OK
- [ ] Description tool đã cập nhật
- [ ] (Nếu có) `kind_filter=all` khôi phục được hành vi cũ
