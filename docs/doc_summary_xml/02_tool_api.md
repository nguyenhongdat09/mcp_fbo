# 02 — Tool API: `read_local_file` + `summary_xml`

## 1. Đăng ký MCP (mở rộng tool hiện có)

**Không** thêm tool mới. Sửa `fastbusiness_mcp/mcp_app.py` — `read_local_file_tool`:

```python
from typing import Annotated, Literal
from pydantic import Field

from xml_fbograph.mcp_tools import mcp_read_local_file
from fastbusiness_mcp.tool_errors import format_execution_error

@server.tool(name="read_local_file")
def read_local_file_tool(
    file_path: Annotated[
        str,
        Field(description="Relative path (e.g., 'Dir/CPTran.xml') or absolute path"),
    ],
    reference_file: Annotated[
        str,
        Field(description="BẮT BUỘC đường dẫn ABSOLUTE tới 1 file XML trong project FBO..."),
    ],
    read_option: Annotated[
        Literal[1, 2, 3],
        Field(
            default=1,
            description=(
                "1: nội dung gốc (raw); "
                "2: flat sau resolve entities/includes; "
                "3: summary_xml JSON gọn (JS functions, SQL tables/procs, fields type/lookup) "
                "— ưu tiên khi chỉ cần bản đồ controller, tránh flat full."
            ),
        ),
    ] = 1,
) -> str:
    ...
```

Trong `xml_fbograph/mcp_tools.py` → `mcp_read_local_file`:

```python
def mcp_read_local_file(file_path: str, reference_file: str, read_option: int = 1) -> str:
    # ... resolve path + sandbox giống hiện tại ...
    if read_option == 3:
        from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
        from find_entity_by_xml.bridges.summary_xml_format import format_summary_xml_result
        result = summary_xml(str(p))
        return format_summary_xml_result(result)
    if read_option == 2:
        content = flat_xml(str(p))
        ...
    else:
        content = read_file_content(p)
    return content
```

Import bridge từ `find_entity_by_xml` (hoặc `xml_controller_summary` qua bridge) — **không** import `js_engine` / `tsql_engine` trực tiếp trong `mcp_app.py`.

## 2. Tham số input

| Tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
|---------|------|----------|----------|-------|
| `file_path` | `str` | ✅ | — | Relative (Controllers) hoặc absolute path file XML |
| `reference_file` | `str` | ✅ | — | Absolute path XML trong project — resolve root + sandbox |
| `read_option` | `1\|2\|3` | — | `1` | `1` raw, `2` flat, **`3` summary_xml** |

### Không thêm param v1

- Không `mode`, `keywords`, `max_depth` (khác summary_object)
- Không `include_encrypted` (luôn skip encrypted)

Phase 2 có thể thêm `max_fields`, `include_hidden_fields` — **không** bắt buộc v1.

## 3. Tool description (cập nhật cho Agent)

Ghép vào docstring hiện có của `read_local_file`:

```
Đọc file controller FBO từ ổ cứng.

read_option:
  1 — raw (mặc định)
  2 — flat (resolve ENTITY/includes)
  3 — summary_xml: JSON gọn (hàm JS, bảng/proc SQL, fields type+lookup)
      Dùng khi chỉ cần bản đồ chứng từ/danh mục — TRÁNH flat full.

QUY TRÌNH AGENT (tiết kiệm token):
1) read_local_file(..., read_option=3) — biết functions / tables / fields
2) read_local_file(..., read_option=2) — chỉ khi cần sửa đúng đoạn CDATA
3) get_xml_entities — chỉ khi cần ENTITY chưa flat / vị trí khai báo

CHÚ Ý: File không tồn tại → báo user, KHÔNG tự tạo file.
```

## 4. Response format (text cho MCP)

### `read_option=3` — formatter markdown + JSON

```markdown
[OK] read_local_file summary_xml
File: Dir\SVTran.xml
Parse JS: ok | partial | failed
Parse SQL: ok | partial | failed
Fields: 87

```json
{ ... }
```
```

Lỗi:

```markdown
[ERROR] read_local_file
Loi: File khong ton tai: ...
```

```markdown
[ERROR] read_local_file
Loi: Duong dan nam ngoai thu muc du an: ...
```

```markdown
[ERROR] read_local_file summary_xml
Loi khi flat XML: ...
```

### `read_option=1|2`

Giữ nguyên: trả **thuần text** nội dung file (không bọc markdown JSON).

## 5. Pipeline `read_option=3` chi tiết

1. Resolve `file_path` qua `ProjectPathHelper(reference_file)` (giống opt 1/2)
2. Sandbox: path phải nằm trong project root
3. File tồn tại; nếu không → error string hiện tại
4. `flat_xml(path)` — nếu fail → error (có thể kèm gợi ý thử opt 1)
5. `xml_controller_summary.analyze_flat_xml(flat_text, source_path=...)`
6. `format_summary_xml_result(dict)` → markdown string

**Không** gọi SQL Server. **Không** mở Kùzu.

## 6. Quan hệ với tool khác

| Nhu cầu | Tool |
|---------|------|
| Bản đồ JS/SQL/fields của 1 XML | **`read_local_file` opt 3** |
| Đọc/sửa đúng đoạn CDATA | `read_local_file` opt 2 |
| ENTITY list/path/content | `get_xml_entities` |
| Tìm file liên quan trong graph | `query_radar` |
| Schema bảng / body proc sâu | `query_database` / summary_object |

## 7. Lỗi chuẩn

| Code / tình huống | Behavior |
|-------------------|----------|
| `file_not_found` | Tool trả string lỗi (giống hiện tại) |
| `sandbox_violation` | String lỗi ngoài project |
| `flat_failed` | String lỗi flat |
| `unsupported_extension` | v1: vẫn cố flat nếu đọc được text; warning trong meta nếu không phải `.xml`/`.f` |
| `js_parse_failed` / `sql_parse_failed` | **OK** + JSON với `parse_status` + fallback regex |
| `empty_after_flat` | JSON `success: false` hoặc warning |

Dùng `format_execution_error("read_local_file", e)` cho exception không mong đợi.

## 8. Bảo mật & sandbox

- Giữ nguyên sandbox `startswith(project_root)`
- Không thực thi JS/SQL — chỉ parse tĩnh
- Không ghi file
- Encrypted: strip, không gửi nội dung mã hóa vào JSON

## 9. Timeout & kích thước

| Giới hạn | Giá trị v1 | Ghi chú |
|----------|------------|---------|
| Flat XML size | 5 MB | Vượt → error / truncate warning |
| Tổng request | 30s | Bridge wall-clock |
| Fields trả về | tất cả field trong flat | Hidden vẫn liệt kê (ngắn); phase 2 mới filter |
| JSON target | < 20 KB | Ưu tiên dedupe set tables/functions |

## 10. Formatter — tách JSON vs MCP text

| Hàm | Package | Output |
|-----|---------|--------|
| `result_to_dict(SummaryXmlResult)` | `xml_controller_summary/formatter.py` | `dict` JSON thuần |
| `format_summary_xml_result(dict)` | `find_entity_by_xml/bridges/summary_xml_format.py` | Markdown string cho MCP |

MCP **chỉ** gọi formatter bridge; không format markdown trong `xml_controller_summary` / `js_engine`.
