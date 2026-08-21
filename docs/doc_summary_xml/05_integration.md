# 05 — Tích hợp: bridge mỏng vào `read_local_file`

> **Đọc trước:** [07_architecture_layers.md](./07_architecture_layers.md)  
> **Nguyên tắc nhúng nhẹ:**
>
> - ANTLR JS → `js_engine/`; T-SQL → **reuse** `tsql_engine/` (import API, không copy).
> - Mọi extract / visitor / field map → `xml_controller_summary/` (pure).
> - Bridge chỉ `flat_xml` + `analyze_flat_xml` + `result_to_dict` (~10 dòng).
> - MCP/`mcp_tools` chỉ sandbox + `read_option` switch + format markdown — **cấm** nhúng logic summary vào đây.
> - Feature khác (Graph, script) muốn dùng: gọi `summary_xml(path)` hoặc `analyze_flat_xml(flat)` — không copy code.
---

## 1. Cấu trúc file (phiên bản tách lớp)

```
E:\PythonProject\mcp_fbo\
  js_engine/                          # Lớp ANTLR JS — portable (MỚI)
    __init__.py                       # parse()
    engine.py
    preprocess.py
    errors.py
    grammar/ + generated/
    tools/generate.bat
    README.md

  tsql_engine/                        # REUSE — không sửa trừ khi cần wrap fragment

  xml_controller_summary/             # Lớp nghiệp vụ — pure (MỚI)
    __init__.py                       # analyze_flat_xml()
    models.py
    extract.py                        # blocks JS/SQL/fields
    analyze.py                        # orchestration pure
    field_classifier.py
    visitors/
      js_summary_visitor.py
      sql_fragment_visitor.py
    formatter.py                      # result_to_dict() — JSON thuần, không MCP markdown
    fallback_regex.py                 # JS/SQL regex khi ANTLR partial

  find_entity_by_xml/
    facade.py                         # flat_xml() — giữ nguyên public API
    bridges/
      __init__.py
      summary_xml_bridge.py           # summary_xml(path) orchestration I/O
      summary_xml_format.py           # format_summary_xml_result() — markdown MCP

  xml_fbograph/
    mcp_tools.py                      # mcp_read_local_file: nhánh read_option==3

  fastbusiness_mcp/
    mcp_app.py                        # Literal[1,2,3] + mô tả tool

  tests/
    js_engine/
    xml_controller_summary/
    find_entity_by_xml/               # optional bridge tests
```

---

## 2. `find_entity_by_xml/bridges/summary_xml_bridge.py`

```python
def summary_xml(file_path: str, *, use_cache: bool = True) -> dict:
    """
    1) flat_xml(file_path)
    2) xml_controller_summary.analyze_flat_xml(flat, source_path=file_path)
    3) result_to_dict(...)
    """
```

**Trách nhiệm bridge (nhúng nhẹ — không trộn logic):**

- Gọi `flat_xml` (I/O + entity expand) — **reuse** facade có sẵn
- Gọi `analyze_flat_xml` + `result_to_dict` — **nhúng** feature pure
- Optional LRU cache key = `(abspath, mtime, size)` — TTL không bắt buộc v1
- **Không** chứa visitor ANTLR / regex extract / field classifier
- **Không** format markdown (để `summary_xml_format.py`)
- **Không** import `js_engine` / `tsql_engine` trực tiếp
```python
def summary_xml(file_path: str, *, use_cache: bool = True) -> dict:
    from find_entity_by_xml.facade import flat_xml
    from xml_controller_summary import analyze_flat_xml
    from xml_controller_summary.formatter import result_to_dict

    flat = flat_xml(file_path)
    model = analyze_flat_xml(flat, source_path=file_path)
    return result_to_dict(model)
```

---

## 3. `summary_xml_format.py`

Mirror tinh thần `queryDatabase/bridges/summary_format.py`:

```python
def format_summary_xml_result(result: dict) -> str:
    if not result.get("success", True) and result.get("meta", {}).get("warnings"):
        # vẫn in JSON nếu có cấu trúc
        pass
    file = result.get("file", "?")
    js_st = result.get("js", {}).get("parse_status", "?")
    sql_st = result.get("sql", {}).get("parse_status", "?")
    n_fields = len(result.get("fields") or [])
    body = json.dumps(result, ensure_ascii=False, indent=2)
    return (
        f"[OK] read_local_file summary_xml\n"
        f"File: {file}\n"
        f"Parse JS: {js_st}\n"
        f"Parse SQL: {sql_st}\n"
        f"Fields: {n_fields}\n\n"
        f"```json\n{body}\n```\n"
    )
```

---

## 4. Sửa `mcp_read_local_file`

File: [`xml_fbograph/mcp_tools.py`](../../xml_fbograph/mcp_tools.py)

```python
def mcp_read_local_file(file_path: str, reference_file: str, read_option: int = 1) -> str:
    try:
        helper = ProjectPathHelper(reference_file)
        project_root = helper.get_project_root()
        # ... resolve p, sandbox, exists — GIỮ NGUYÊN ...

        if read_option == 3:
            from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml
            from find_entity_by_xml.bridges.summary_xml_format import format_summary_xml_result
            try:
                result = summary_xml(str(p))
                return format_summary_xml_result(result)
            except Exception as e:
                return f"Loi khi summary XML: {str(e)}"

        from xml_fbograph.parsers.xml_parser import read_file_content
        from find_entity_by_xml.facade import flat_xml

        if read_option == 2:
            ...
        else:
            ...
    except Exception as e:
        return f"Loi doc file: {str(e)}"
```

**Validation:** `mcp_app.py` dùng `Literal[1, 2, 3]` — giá trị khác bị Pydantic reject (đã có pattern test `read_option=99`).

---

## 5. `xml_controller_summary/analyze.py`

```python
def analyze_flat_xml(flat_text: str, *, source_path: str = "") -> SummaryXmlResult:
    text, enc_count = strip_encrypted(flat_text)
    chunks = extract_controller_blocks(text)
    js_summary = analyze_js(chunks.js_chunks)
    sql_summary = analyze_sql(chunks.sql_chunks)
    fields = classify_fields(chunks.fields)
    controller = build_controller_meta(source_path, text)
    ...
```

Pure: **cấm** `open()`, `pyodbc`, `Path.read_text` trong package này (nhận string vào).

---

## 6. Cache (optional v1)

| Key | Value |
|-----|-------|
| `(realpath.lower(), mtime_ns, size, "summary_xml:1.0")` | `dict` result |

- Thread-safe `functools.lru_cache` không đủ (mtime) → dict + lock như summary_object bridge
- `use_cache=False` cho test
- Invalidate khi mtime đổi

**Không bắt buộc** để merge PR — checklist đánh dấu optional.

---

## 7. Tương thích ngược

| Hành vi cũ | Yêu cầu |
|------------|---------|
| `read_option=1` | Byte-identical behavior (cùng hàm đọc) |
| `read_option=2` | Cùng `flat_xml` |
| Tool name | Vẫn `read_local_file` |
| Sandbox / reference_file | Không đổi |

Cập nhật test: [`scripts/verify_mcp_migration.py`](../../scripts/verify_mcp_migration.py) — `read_option` invalid vẫn reject; thêm case `3` nếu có fixture.

---

## 8. PyInstaller / packaging

Nếu `fastbusiness_mcp.spec` dùng hiddenimports:

```
js_engine
js_engine.generated
xml_controller_summary
find_entity_by_xml.bridges.summary_xml_bridge
```

Mirror cách đã làm cho `tsql_engine` / `sql_object_summary`.

---

## 9. Docs vận hành (phase E — Gemini làm khi code)

- Root `README.md` — dòng `read_local_file`: ghi thêm opt 3
- `.cursorrules` — Agent: ưu tiên `read_option=3` trước flat khi chỉ cần bản đồ
- Không đổi 14 Cypher templates

---

## 10. Integration test gợi ý

```python
def test_summary_xml_fixture_ma_kh():
    flat = Path("tests/xml_controller_summary/fixtures/mini_svtran_flat.xml").read_text(encoding="utf-8-sig")
    result = analyze_flat_xml(flat, source_path="Dir/SVTran.xml")
    d = result_to_dict(result)
    assert "onChange$Voucher$Customer" in d["js"]["functions"]
    ma_kh = next(f for f in d["fields"] if f["name"] == "ma_kh")
    assert ma_kh["lookup"] == "Customer"
    assert ma_kh["onchange"] == "onChange$Voucher$Customer"
```

Optional live (skip nếu UNC không mount):

```python
@pytest.mark.integration
def test_svtran_unc():
    path = r"\\172.168.5.14\CustomerPro\HRM\LIKSIN\FBISP23\App_Data\Controllers\Dir\SVTran.xml"
    ...
```
