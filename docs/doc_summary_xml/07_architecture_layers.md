# 07 — Kiến trúc lớp: tách biệt, reuse, nhúng nhẹ

> **Nguyên tắc vàng (bắt buộc Gemini tuân thủ):**
>
> 1. **Tách biệt** — mỗi package một trách nhiệm; logic không trộn lẫn giữa MCP / flat I/O / summary / ANTLR.
> 2. **Reuse có sẵn** — cái đã dùng lại được (`tsql_engine`, `flat_xml`) thì **nhúng nhẹ** (import API), không copy-paste, không fork grammar.
> 3. **Nhúng nhẹ chiều ngược** — feature khác (FBOGraph, formatter, test, tool mới) muốn dùng summary XML thì chỉ gọi **public API mỏng** của đúng lớp; **không** copy visitor / extract vào trong feature kia.
> 4. **Dependency một chiều xuống** — cấm import ngược.

Song song mẫu đã làm với `summary_object`: xem [`docs/doc/07_architecture_layers.md`](../doc/07_architecture_layers.md).

---

## 1. Sơ đồ tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│  fastbusiness_mcp/          (Lớp MCP — siêu mỏng)             │
│  mcp_app.py  →  read_local_file_tool (~gọi mcp_tools)         │
│  KHÔNG chứa extract / ANTLR / field map                       │
└───────────────────────────┬─────────────────────────────────┘
                            │ import
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  xml_fbograph/mcp_tools.py  (adapter MCP — mỏng)              │
│  mcp_read_local_file: sandbox + switch read_option            │
│  opt 3 → CHỈ gọi bridge (1–3 dòng logic)                      │
└───────────────┬─────────────────────────────┬─────────────────┘
                │ opt 1/2                      │ opt 3
                ▼                              ▼
┌───────────────────────────┐    ┌────────────────────────────────┐
│  flat_xml / read content  │    │  find_entity_by_xml/bridges/    │
│  (I/O đã có sẵn)          │    │  summary_xml_bridge  (~10 dòng) │
│                           │    │  = flat_xml + analyze + dict    │
└───────────────────────────┘    └───────────────┬────────────────┘
                                                 │ flat_text: str
                                                 ▼
                                 ┌────────────────────────────────┐
                                 │  xml_controller_summary/       │
                                 │  PURE: extract + visitor + JSON│
                                 │  KHÔNG open/file/DB/MCP        │
                                 └───────┬──────────────┬─────────┘
                                         │ nhúng nhẹ     │ nhúng nhẹ
                                         ▼              ▼
                                 ┌──────────────┐ ┌──────────────┐
                                 │  js_engine/  │ │ tsql_engine/ │
                                 │  ANTLR JS    │ │ ANTLR T-SQL  │
                                 │  (MỚI)       │ │ (REUSE sẵn)  │
                                 └──────────────┘ └──────────────┘
```

---

## 2. Ma trận “ai sở hữu logic gì”

| Logic | Đặt ở đâu | Ai được gọi |
|-------|-----------|-------------|
| Parse JS string → AST | `js_engine` | `xml_controller_summary` (+ tương lai: lint JS, Graph enrich) |
| Parse SQL string → AST | `tsql_engine` (**đã có**) | `sql_object_summary`, `xml_controller_summary`, … |
| Extract script/Checking/action/fields từ flat string | `xml_controller_summary/extract.py` | Chỉ package summary (+ test) |
| Visitor JS → functions / request_actions | `xml_controller_summary/visitors/` | Chỉ qua `analyze_flat_xml` |
| Visitor SQL fragment → tables/procs | `xml_controller_summary/visitors/` | Chỉ qua `analyze_flat_xml` |
| Expand ENTITY file → flat string | `find_entity_by_xml.facade.flat_xml` | Bridge, `read_option=2`, Graph builder… |
| `path` → flat → dict summary | `find_entity_by_xml.bridges.summary_xml_bridge` | MCP, script, test integration |
| Markdown MCP | `summary_xml_format` | Chỉ MCP adapter |
| Sandbox / `reference_file` | `xml_fbograph.mcp_tools` | Chỉ MCP |

**Cấm:** nhét extract Checking vào `mcp_tools.py`; nhét `flat_xml` vào `js_engine`; nhét markdown vào `xml_controller_summary`.

---

## 3. Package độc lập + Public API (ổn định)

### 3.1. `js_engine/` — engine ANTLR JS (dùng lại được)

**Trách nhiệm duy nhất:** `string JS` → `ParseResult` (tree + errors + status).

**Không được biết:** XML, field, Checking, MCP, path file.

```python
# js_engine/__init__.py
def parse(source: str, *, entry_rule: str = "program") -> ParseResult: ...
```

**Ai nhúng nhẹ sau này (không sửa engine):**

| Use case | Cách |
|----------|------|
| summary_xml | `xml_controller_summary` visitor |
| Lint JS FBO (`$` naming) | package `js_lint/` mới + visitor |
| Enrich FBOGraph `js_text` | import `js_engine.parse` trong enricher riêng |

→ **Không sửa** `js_engine` trừ grammar/lexer.

### 3.2. `tsql_engine/` — REUSE nguyên xi (đã có từ summary_object)

**Nhúng nhẹ:**

```python
from tsql_engine import parse
```

- **Không** copy `grammar/` sang chỗ khác.
- **Không** import `sql_object_summary` chỉ để lấy table list nếu kéo theo model DB — viết `SqlFragmentVisitor` mỏng trong `xml_controller_summary` trên cùng `tsql_engine`.
- Chỉ mở rộng preprocess/wrap fragment SQL XML nếu bắt buộc; ghi chú PR; không phá `summary_object`.

### 3.3. `xml_controller_summary/` — feature pure (dùng lại được bởi nhiều caller)

**Trách nhiệm:** flat **string** in → `SummaryXmlResult` / dict out.

**Public API (đây là cổng duy nhất cho feature khác):**

```python
# xml_controller_summary/__init__.py

def analyze_flat_xml(
    flat_text: str,
    *,
    source_path: str = "",
) -> SummaryXmlResult:
    """Pure: không đọc disk, không MCP."""

def result_to_dict(result: SummaryXmlResult) -> dict:
    """JSON-ready dict theo spec 03 — không markdown."""
```

**Ai được nhúng nhẹ `analyze_flat_xml`:**

| Caller | Cách nhúng |
|--------|------------|
| `summary_xml_bridge` | flat_xml → analyze → dict (MCP path) |
| Unit test | fixture string → analyze |
| FBOGraph enrich (phase 2) | đã có flat_text trong builder → analyze → gắn meta node — **không** copy extract |
| Script batch scan controllers | loop path → bridge hoặc flat+analyze |
| Tool MCP khác sau này | import bridge hoặc `analyze_flat_xml` nếu đã có flat |

**Không được** export / bắt caller import sâu:

- `visitors.js_summary_visitor` (internal)
- `extract.COMMAND_RE` (internal)
- `fallback_regex` (internal)

### 3.4. Bridge — lớp I/O mỏng (file path → dict)

```python
# find_entity_by_xml/bridges/summary_xml_bridge.py

def summary_xml(file_path: str, *, use_cache: bool = True) -> dict:
    flat = flat_xml(file_path)           # REUSE facade
    model = analyze_flat_xml(flat, source_path=file_path)
    return result_to_dict(model)
```

- **~10–20 dòng.** Không ANTLR. Không field map. Không markdown.
- MCP và script “cần path” → gọi `summary_xml(path)`.
- Caller “đã có flat string” → **bỏ qua bridge**, gọi thẳng `analyze_flat_xml` (tránh flat 2 lần).

### 3.5. MCP — chỉ switch + format

```python
# trong mcp_read_local_file — ĐÚNG
if read_option == 3:
    return format_summary_xml_result(summary_xml(str(p)))

# SAI — cấm
if read_option == 3:
    flat = flat_xml(...)
    # regex extract Checking tại đây...
    # gọi JsLexer...
```

---

## 4. Quy tắc dependency (bắt buộc)

```
fastbusiness_mcp
    → xml_fbograph.mcp_tools          # mỏng

xml_fbograph.mcp_tools
    → find_entity_by_xml.bridges      # chỉ opt 3
    → find_entity_by_xml.facade       # opt 2 flat
    → xml_fbograph.parsers (read)     # opt 1

find_entity_by_xml.bridges
    → facade.flat_xml                 # REUSE I/O
    → xml_controller_summary          # nhúng nhẹ feature

xml_controller_summary
    → js_engine                       # nhúng nhẹ engine
    → tsql_engine                     # nhúng nhẹ engine (REUSE)

js_engine      → stdlib + antlr4 only
tsql_engine    → stdlib + antlr4 only
```

### Cấm tuyệt đối (anti-pattern)

| Sai | Vì sao |
|-----|--------|
| `js_engine` import XML / MCP | Phá tái sử dụng engine |
| `tsql_engine` import `xml_controller_summary` | Import ngược |
| `xml_controller_summary` gọi `flat_xml` / `open()` | Pure bị bẩn; Graph/test khó reuse |
| `mcp_app` import `js_engine` / visitor | Logic trộn vào MCP |
| Copy `SqlFragmentVisitor` vào `xml_fbograph/builder` | Nhân đôi logic — phải gọi `analyze_flat_xml` |
| `xml_controller_summary` import `sql_object_summary` kéo theo catalog/DB | Trộn feature SQL Server với XML |
| Fork `TSqlLexer.g4` vào `js_engine` hoặc ngược lại | Không phải reuse |

---

## 5. Reuse có sẵn vs viết mới

| Thành phần | Quyết định |
|------------|------------|
| `tsql_engine` | **REUSE** — nhúng `parse()` |
| `flat_xml` / `XmlEntityExpander` | **REUSE** — chỉ ở bridge / opt 2 |
| `sql_object_summary.analyze_definition` | **Không bắt buộc** — tránh kéo DB models; viết visitor fragment riêng trên `tsql_engine` |
| `xml_fbograph/parsers/js_parser.py` | Chỉ **fallback regex** trong `xml_controller_summary/fallback_regex` (port pattern), primary = ANTLR |
| `extract_expanded_blocks` trong facade | **Chuyển logic** vào `xml_controller_summary/extract.py`; facade cũ có thể delegate mỏng để không phá caller cũ |
| Grammar JS | **MỚI** trong `js_engine/grammar` |

---

## 6. Hợp đồng “feature khác muốn gọi”

### 6.1. Đã có đường dẫn file

```python
from find_entity_by_xml.bridges.summary_xml_bridge import summary_xml

data = summary_xml(r"E:\...\Dir\SVTran.xml")
functions = data["js"]["functions"]
```

### 6.2. Đã có flat XML string (vd. Graph builder vừa flat)

```python
from xml_controller_summary import analyze_flat_xml, result_to_dict

result = analyze_flat_xml(flat_text, source_path=relative_path)
data = result_to_dict(result)
```

### 6.3. Chỉ cần parse JS thuần (không XML)

```python
from js_engine import parse

pr = parse(js_source)
# tự viết visitor ở package của bạn — hoặc sau này dùng helper shared
```

### 6.4. Chỉ cần parse SQL thuần

```python
from tsql_engine import parse
# giống summary_object / fragment visitor
```

→ Ba cấp API: **engine** (thấp) / **analyze_flat_xml** (feature) / **summary_xml(path)** (I/O). Caller chọn đúng cấp — **không** nhảy vào internal.

---

## 7. So với `summary_object` (cùng triết lý)

| | summary_object | summary_xml |
|--|----------------|-------------|
| Engine tái sử dụng | `tsql_engine` | `js_engine` + `tsql_engine` |
| Pure feature | `sql_object_summary` | `xml_controller_summary` |
| Bridge mỏng | `queryDatabase/bridges/` | `find_entity_by_xml/bridges/` |
| MCP | nhúng nhẹ bridge | nhúng nhẹ bridge (`read_option=3`) |
| Feature khác reuse | `analyze_definition(str)` | `analyze_flat_xml(str)` |

---

## 8. Versioning & ổn định API

- JSON: `spec_version: "1.0"` (xem `03_json_schema.md`)
- Public Python API ổn định: `parse` (engines), `analyze_flat_xml`, `result_to_dict`, `summary_xml`
- Đổi breaking → bump spec + ghi changelog ngắn trong README thư mục này
- Cache key (nếu có) gồm `spec_version`

---

## 9. Checklist review kiến trúc (PR)

- [ ] Không có logic extract/ANTLR/field trong `mcp_app.py` hoặc `mcp_tools.py` ngoài gọi bridge
- [ ] `xml_controller_summary` không `open` / `flat_xml` / pyodbc / MCP
- [ ] `js_engine` không import package FBO khác
- [ ] SQL dùng `tsql_engine` — không fork grammar
- [ ] FBOGraph / tool khác nếu cần summary → gọi `analyze_flat_xml` hoặc `summary_xml`, không copy visitor
- [ ] Facade `extract_expanded_blocks` (nếu giữ) chỉ delegate, không giữ bản logic thứ hai lệch nhau
- [ ] Test tách tầng: `tests/js_engine` (không XML), `tests/xml_controller_summary` (string flat), bridge (temp file)
- [ ] `read_option` 1 và 2 không regress
