# Follow-up fix: residual sau review `summary_xml`

> **Mục đích:** Tài liệu ngắn để Gemini/Claude **sửa tiếp** các điểm residual còn lại sau khi đã đóng 8 mục trong [`summary_xml_implementation_review.md`](./summary_xml_implementation_review.md).  
> **Không** đụng lại kiến trúc tầng `js_engine` / `xml_controller_summary` / MCP trừ khi bắt buộc.  
> **Repo:** `E:\PythonProject\mcp_fbo\`

---

## 1. Bối cảnh (đã xong vs còn lại)

### Đã xác nhận xong (không làm lại)

- Delegate `extract_expanded_blocks` → `extract_controller_blocks`
- Views heuristic `^(v\d|zv)`, signal `checking_routed_to_sql`, cache bridge, normalize path, `.f`, fallback JS calls
- 12 unit/bridge tests + `verify_mcp_migration` pass

### Còn lại (làm trong PR này)

| ID | Mức | Vấn đề |
|----|-----|--------|
| **R1** | P1 | Facade không còn đưa `<clientScript>` vào `js_blocks` → FBOGraph có thể mất onchange ngắn |
| **R2** | P2 | Cache key thiếu `spec_version` |
| **R3** | P2 | Cache trả shallow copy — mutate nested có thể bẩn cache |
| **R4** | P3 | (Optional) Smoke UNC SVTran khi mount được share |
| **R5** | P3 | Ghi chú / test: tag `command:Event` vs `command` — Graph không break |

---

## 2. R1 — Khôi phục `clientScript` trên facade (cho Graph), không vào ANTLR summary

### Vấn đề

Trước refactor, `extract_expanded_blocks` lấy JS từ cả:

- `<script>`
- `<clientScript>` (thường `onchange="onChange$Voucher$Customer(this);"`)

Sau delegate, chỉ map `JsChunk` từ `extract_controller_blocks` → **chỉ** `script` + `command:Checking`.

`xml_controller_summary` **đúng** khi không đưa `clientScript` vào ANTLR concat (docs summary_xml).  
Nhưng **FBOGraph** (`xml_fbograph/parsers/xml_parser.py` → `graph_builder`) vẫn đọc `js_blocks` từ facade — mất `clientScript` là **regression Graph**.

### Yêu cầu

1. **Không** thêm `clientScript` vào `JsChunk` / `analyze_js_chunks` / summary JSON `js.functions` (trừ khi đã có qua script).
2. Chỉ bổ sung ở **facade** `extract_expanded_blocks` sau khi delegate:

```text
extracted = extract_controller_blocks(flat_text)
map js_chunks → js_blocks   # như hiện tại
map sql_chunks → sql_blocks # như hiện tại
+ quét thêm <clientScript> trên flat_text → append js_blocks
    { "content": cdata_or_inner, "line": N, "tag": "clientScript" }
```

3. Reuse helper extract CDATA đã có trong `xml_controller_summary.extract` nếu public được (vd. `extract_cdata_from_inner`, `CLIENT_SCRIPT_RE`) — **hoặc** regex mỏng trong facade; tránh copy-paste lệch CDATA rules.
4. Dedup: nếu cùng content+line đã có thì bỏ qua.

### Test bắt buộc

Thêm vào `tests/find_entity_by_xml/test_summary_xml_bridge.py` (hoặc file test facade riêng):

```xml
<field name="ma_kh">
  <clientScript><![CDATA[onchange="onChange$Voucher$Customer(this);"]]></clientScript>
</field>
<script><text><![CDATA[function init$Voucher$(f){}]]></text></script>
```

Assert:

- `extract_expanded_blocks`: có `tag == "clientScript"` và content chứa `onChange$Voucher$Customer`
- `summary_xml` / `analyze_flat_xml`: **không** bắt buộc có function từ chỉ clientScript; `onchange` field vẫn lấy qua `field_classifier` như hiện tại

### Acceptance R1

- [ ] Graph nhận lại `clientScript` trong `js_blocks`
- [ ] `read_option=3` JSON không phình vì ANTLR parse từng onchange
- [ ] Test mới pass; 12 test cũ không regress

---

## 3. R2 — Cache key gồm `spec_version`

### Vấn đề

[`summary_xml_bridge.py`](../../find_entity_by_xml/bridges/summary_xml_bridge.py) key hiện:

```python
(abspath.lower(), mtime_ns, size)
```

Đổi `spec_version` / shape JSON mà file không đổi mtime → Agent nhận cache schema cũ.

### Yêu cầu

```python
from xml_controller_summary.models import ...  # hoặc hằng SPEC_VERSION = "1.0"

cache_key = (
    os.path.abspath(file_path).lower(),
    st.st_mtime_ns,
    st.st_size,
    "summary_xml:1.0",  # đồng bộ SummaryXmlResult.spec_version
)
```

Khi bump spec trong models → **đổi cùng** chuỗi này (một constant shared, vd. `xml_controller_summary.models.SPEC_VERSION`).

### Test

- Gọi `summary_xml` 2 lần → hit cache (giữ assert hiện có)
- (Optional) mock/patch `SPEC_VERSION` khác → miss cache / kết quả mới

### Acceptance R2

- [ ] Key có spec
- [ ] Constant một chỗ, không magic string rải rác

---

## 4. R3 — Cache trả bản sao sâu (deep copy)

### Vấn đề

```python
return dict(_SUMMARY_CACHE[cache_key])  # shallow
```

Caller `result["js"]["functions"].append(...)` làm bẩn entry trong `_SUMMARY_CACHE`.

### Yêu cầu

Khi **đọc** và **ghi** cache dùng `copy.deepcopy`:

```python
import copy
...
return copy.deepcopy(_SUMMARY_CACHE[cache_key])
...
_SUMMARY_CACHE[cache_key] = copy.deepcopy(res_dict)
```

### Test

```python
r1 = summary_xml(path, use_cache=True)
r1["js"]["functions"].append("HACKED")
r2 = summary_xml(path, use_cache=True)
assert "HACKED" not in r2["js"]["functions"]
```

### Acceptance R3

- [ ] Mutate kết quả không ảnh hưởng lần gọi sau
- [ ] Test trên pass

---

## 5. R4 — (Optional) Smoke SVTran UNC

Chỉ chạy khi path tồn tại:

```python
@pytest.mark.integration
@pytest.mark.skipif(not Path(UNC).exists(), reason="share not mounted")
def test_svtran_unc_smoke():
    d = summary_xml(UNC)
    assert d["success"]
    assert "onChange$Voucher$Customer" in d["js"]["functions"]
    ma = next(f for f in d["fields"] if f["name"] == "ma_kh")
    assert ma["lookup"] == "Customer"
    assert d["file"].replace("/", "\\").endswith("Dir\\SVTran.xml") \
        or "SVTran.xml" in d["file"]
```

UNC tham chiếu docs:

`\\172.168.5.14\CustomerPro\HRM\LIKSIN\FBISP23\App_Data\Controllers\Dir\SVTran.xml`

Không fail CI khi không mount.

---

## 6. R5 — Tag format Graph-safe

### Hiện trạng

Facade map SQL tag thành `command:Loading`, `action:Customer` (không còn thuần `command` / `action`).

Graph hiện chủ yếu dùng `content` + `line` (đã verify nhanh). Vẫn cần:

1. Grep trong `xml_fbograph/` xem có chỗ `tag == "command"` / `tag == "script"` cứng không.
2. Nếu có — sửa so sánh thành `tag.startswith("command")` hoặc `tag in ("script",) or tag.startswith("command:")`.
3. Thêm assert trong test facade: `script` vẫn là tag script; Checking JS là `command:Checking`.

### Acceptance R5

- [ ] Không còn filter tag cứng bị break
- [ ] Test facade cover tag mới

---

## 7. Thứ tự làm (bắt buộc)

```
R1 (clientScript facade)  →  R2 (spec cache)  →  R3 (deepcopy)
  →  R5 (grep tag)  →  R4 optional smoke
```

Sau mỗi mục: chạy

```bash
pytest tests/js_engine tests/xml_controller_summary tests/find_entity_by_xml -q
python scripts/verify_mcp_migration.py
```

---

## 8. Cấm / không làm trong PR này

- Đưa `clientScript` vào ANTLR JS summary concat
- Fork lại extract regex song song trong facade (ngoài phần clientScript bổ sung)
- Đổi MCP tool API / `read_option`
- Sửa grammar `js_engine` / `tsql_engine` trừ khi test fail bắt buộc

---

## 9. Definition of Done

- [x] R1 + R2 + R3 + R5 xong + test mới
- [x] Toàn bộ test summary_xml liên quan xanh (13 passed, 1 skipped UNC)
- [x] `verify_mcp_migration` xanh (5 tools passed)
- [x] Ghi 3–5 dòng vào cuối file này (section **Changelog**) ngày sửa + commit/PR

---

## Changelog

| Ngày | Việc |
|---|---|
| 2026-08-21 | **R1:** Bổ sung trích xuất `<clientScript>` vào `js_blocks` trên facade `extract_expanded_blocks` phục vụ FBOGraph parser, không làm phình `summary_xml` ANTLR. |
| 2026-08-21 | **R2:** Thêm hằng số `SPEC_VERSION = "1.0"` vào `models.py` và đưa `f"summary_xml:{SPEC_VERSION}"` vào `cache_key` của `summary_xml_bridge.py`. |
| 2026-08-21 | **R3:** Dùng `copy.deepcopy` khi đọc và ghi cache trong `summary_xml_bridge.py` để chống dirty cache do mutation. |
| 2026-08-21 | **R4 & R5:** Thêm test kiểm thử format tag (`command:Checking`, `clientScript`), immunity mutate cache, và smoke test UNC SVTran (skipif). Toàn bộ 13 test pass. |

