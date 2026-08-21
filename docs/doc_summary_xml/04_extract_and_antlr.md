# 04 — Extract blocks & ANTLR (`js_engine` + `tsql_engine`)

> **Đọc kiến trúc:** [07_architecture_layers.md](./07_architecture_layers.md) — tách biệt / nhúng nhẹ.  
> **SQL engine:** reuse [`docs/doc/04_antlr4_parser.md`](../doc/04_antlr4_parser.md) + [`docs/doc/09_tsql_grammar.md`](../doc/09_tsql_grammar.md) — **không** fork grammar T-SQL.  
>
> **Phân lớp trong file này:**
>
> | Việc | Package |
> |------|---------|
> | `parse(js)` / `parse(sql)` | `js_engine` / `tsql_engine` (engine thuần) |
> | Extract tag + visitor + field map | `xml_controller_summary` (pure feature) |
> | `flat_xml(path)` | **Không** nằm đây — chỉ bridge gọi `facade` |
>
> Engine **không** biết Checking/field. Feature **không** `open()` file.
---

## 1. Tổng quan pipeline

```
flat_text (string)
  → strip_encrypted(flat_text)
  → extract_controller_blocks(flat_text)   # xml_controller_summary/extract.py
       → js_chunks[]   (script + Checking*)
       → sql_chunks[]  (command khác + action + query)
       → field_nodes[]
  → js_source = "\n;\n".join(js_chunks)
  → js_engine.parse(js_source) → JsVisitor → JsSummary
  → for each sql_chunk: tsql_engine.parse → SqlFragmentVisitor → merge sets
  → classify_fields(field_nodes) → FieldSummary[]
  → SummaryXmlResult
```

`*` Checking sau language sniff (xem §3.3).

---

## 2. Strip encrypted

Trước mọi extract, loại nội dung mã hóa (không decrypt):

```python
ENCRYPTED_RE = re.compile(
    r"<(encrypted|Encrypted)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

def strip_encrypted(text: str) -> tuple[str, int]:
    count = 0
    def _repl(_m):
        nonlocal count
        count += 1
        return "/* encrypted_skipped */"
    return ENCRYPTED_RE.sub(_repl, text), count
```

Đếm → `meta.skipped_encrypted_blocks`.  
Signal SQL: thêm `"encrypted_skipped"` nếu count > 0.

---

## 3. Extract blocks từ flat XML

### 3.1. Helper lấy CDATA trong `<text>`

Flat FBO thường:

```xml
<command event="Loading">
  <text><![CDATA[
    declare @x int
    ...
  ]]></text>
</command>
```

Pseudo:

```python
CDATA_IN_TEXT_RE = re.compile(
    r"<text>\s*<!\[CDATA\[(.*?)\]\]>\s*</text>",
    re.DOTALL | re.IGNORECASE,
)

def extract_cdata_from_inner(inner: str) -> str:
    m = CDATA_IN_TEXT_RE.search(inner)
    if m:
        return m.group(1).replace("]]]]><![CDATA[>", "]]>").strip()
    m2 = re.search(r"<!\[CDATA\[(.*?)\]\]>", inner, re.DOTALL)
    if m2:
        return m2.group(1).replace("]]]]><![CDATA[>", "]]>").strip()
    # plain text fallback
    return re.sub(r"<[^>]+>", "", inner).strip()
```

Reuse tinh thần [`find_entity_by_xml/facade.py`](../../find_entity_by_xml/facade.py) `extract_expanded_blocks` — **refactor** logic vào `xml_controller_summary/extract.py`.

**Caller hiện có (đã grep):** `xml_fbograph/parsers/xml_parser.py` gọi `extract_expanded_blocks` khi build Graph node.

→ **Bắt buộc giữ** hàm `extract_expanded_blocks` trên facade: bên trong **delegate** sang extract mới (hoặc gọi `analyze` subset), **không** xóa / không để hai bản regex lệch nhau.

### 3.2. Script → JS

```python
SCRIPT_RE = re.compile(
    r"<script\b[^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
)
```

Mỗi match → `JsChunk(source="script", line=..., content=cdata)`.

### 3.3. Command — phân JS vs SQL

```python
COMMAND_RE = re.compile(
    r'<command\b([^>]*)>(.*?)</command>',
    re.DOTALL | re.IGNORECASE,
)
EVENT_ATTR_RE = re.compile(r'\bevent\s*=\s*["\']([^"\']+)["\']', re.I)
```

Với mỗi command:

| `event` | Mặc định bucket |
|---------|-----------------|
| `Checking` | **JS** (sau sniff) |
| khác (`Loading`, `Scattering`, `Inserting`, …) | **SQL** |

#### Language sniff cho Checking

```python
_SQL_HEAD = re.compile(
    r"^\s*(declare|select|if\s+exists|exec(?:ute)?|with)\b",
    re.I,
)
_JS_HINT = re.compile(
    r"(function\s+|var\s+f\s*=\s*this)",
    re.I,
)

def sniff_checking(content: str) -> Literal["js", "sql"]:
    head = content[:800]
    if _JS_HINT.search(head):
        return "js"
    if _SQL_HEAD.match(content):
        return "sql"
    return "js"  # default FBO Dir
```

Nếu route SQL → `meta.warnings += ["checking_routed_to_sql"]` và `sql.signals += ["checking_routed_to_sql"]`.

### 3.4. Action → SQL

```python
ACTION_RE = re.compile(
    r'<action\b([^>]*)>(.*?)</action>',
    re.DOTALL | re.IGNORECASE,
)
ID_ATTR_RE = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']', re.I)
```

→ `SqlChunk(kind="action", id=..., line=..., content=cdata)`.

### 3.5. Query → SQL (Filter/Report)

```python
QUERY_RE = re.compile(
    r"<query\b[^>]*>(.*?)</query>",
    re.DOTALL | re.IGNORECASE,
)
```

### 3.6. Fields

```python
FIELD_RE = re.compile(
    r"<field\b([^>]*)>(.*?)</field>",
    re.DOTALL | re.IGNORECASE,
)
```

Parse attributes từ group 1 (`name`, `type`, `hidden`, `allowNulls`, …).  
Trong inner: `<items ... controller="Customer" .../>`, `<clientScript>`.

**Không** recurse ENTITY — flat đã expand.

### 3.7. Preprocess SQL fragment FBO trước ANTLR

Trong CDATA command thường có:

- `#IF @@view = 0 #THEN` … `#END`
- `@@prime$partition$current`, `@@id`, `@@userName`
- HTML entities còn sót: `&lt;` `&gt;` `&amp;`

**v1 preprocess (bắt buộc):**

1. Unescape XML entities cơ bản: `&lt;`→`<`, `&gt;`→`>`, `&amp;`→`&`, `&quot;`→`"`.
2. Thay block `#IF ... #THEN` … `#END` bằng comment giữ nguyên nội dung bên trong **hoặc** strip directive giữ body (chọn **giữ body, xóa dòng `#IF/#THEN/#END`**) → signal `fbo_ifdef`.
3. **Không** xóa `@@identifier` — lexer T-SQL / preprocess phải cho phép `@` (đã có trong tsql).

Nếu parse fail vì `#IF`: `parse_status=partial`, vẫn chạy regex fallback trên raw chunk.

---

## 4. `js_engine/` — ANTLR ECMAScript

### 4.1. Trách nhiệm

Biến `string JS` → cây cú pháp + visitor extract:

- Function declarations / expressions có tên
- Call expressions đáng chú ý (`request`, `executeExpression`, `$message.show`, …)
- String arg đầu của `*.request(...)`

**Không:** biết XML, field, MCP, flat.

### 4.2. Grammar source

Lấy từ [antlr/grammars-v4 JavaScript](https://github.com/antlr/grammars-v4/tree/master/javascript/javascript) (ECMAScript) **hoặc** bản `ecmascript` tương đương **ES5-friendly**.

```
js_engine/
  __init__.py
  engine.py
  preprocess.py
  errors.py
  grammar/
    JavaScriptLexer.g4      # tên theo upstream
    JavaScriptParser.g4
    README.md
  generated/                # commit sau generate
  tools/
    generate.bat            # reuse antlr-4.13.2-complete.jar (copy path hoặc dùng chung tsql_engine/tools)
  README.md
```

**Runtime dependency:** `antlr4-python3-runtime==4.13.2` (đã có từ summary_object).

### 4.3. Customization bắt buộc FBO

| Vấn đề FBO | Sửa |
|------------|-----|
| Identifier có `$` (`onChange$Voucher$Customer`) | Lexer: cho `$` trong Identifier (thường ES đã cho `$`; **verify** generate) |
| HTML entity trong string (`&lt;`) | preprocess unescape trước parse |
| `if !(...)` (syntax lỗi trong flat SVTran Checking) | Error listener → partial; không crash |
| Khối còn sót XML tag trong script | preprocess xóa `<encrypted…>` đã làm; strip tag lạ nếu cần |

### 4.4. Public API

```python
# js_engine/__init__.py
from js_engine.engine import JsEngine, ParseResult

def parse(source: str, *, entry_rule: str = "program") -> ParseResult:
    ...
```

```python
@dataclass
class ParseResult:
    source: str
    tree: Any | None
    errors: list[ParseError]
    lines: list[str]
    status: Literal["ok", "partial", "failed"]
```

### 4.5. Visitor (`xml_controller_summary/visitors/js_summary_visitor.py`)

Nằm **ngoài** `js_engine` (giống `sql_object_summary/visitors` vs `tsql_engine`).

Pseudo:

```python
class JsSummaryVisitor(JavaScriptParserVisitor):
    def __init__(self):
        self.functions: set[str] = set()
        self.calls: set[str] = set()
        self.request_actions: set[str] = set()

    def visitFunctionDeclaration(self, ctx):
        name = ctx.identifier().getText()  # giữ $
        self.functions.add(name)
        return self.visitChildren(ctx)

    def visitArgumentsExpression(self, ctx):  # hoặc CallExpression theo grammar
        # nếu callee text endswith .request hoặc == request
        # lấy StringLiteral arg[0] → request_actions
        # ghi calls dạng "f.request" / "o.parentForm.request"
        ...
```

**Calls whitelist — CHỐT CỨNG v1** (đồng bộ `03` §3.1):

| Ghi nhận | Không ghi (v1) |
|----------|----------------|
| `*.request` → `f.request` / `o.parentForm.request` | `setItemValue`, `getItemValue` |
| `*.executeExpression` → `f.executeExpression` | `$func.hideWait` |
| `$message.show` | mọi call khác |

Không có “optional” trong v1 — tránh ambiguity.

### 4.6. Fallback regex (khi ANTLR failed/partial)

Reuse / port từ [`xml_fbograph/rules/regex_rules.py`](../../xml_fbograph/rules/regex_rules.py):

```python
FUNCTIONS_RE = re.compile(r"\bfunction\s+([a-zA-Z0-9_$]+)\s*\(")
REQUEST_RE = re.compile(
    r"\brequest\s*\(\s*['\"]([a-zA-Z0-9_$]+)['\"]",
    re.I,
)
```

Merge vào sets; `parse_status = "partial"` nếu ANTLR lỗi nhưng regex có kết quả; `"failed"` nếu cả hai trống trong khi `line_count > 0`.

### 4.7. Nối nhiều chunk JS

```python
js_source = "\n;\n".join(c.content for c in js_chunks if c.content)
# optional banner comment:
# /* --- source: script --- */
```

Parse **một lần**. `sources` = list label chunk.

---

## 5. SQL — reuse `tsql_engine`

### 5.1. Không tạo `tsql_engine` mới

Gọi:

```python
from tsql_engine import parse
from xml_controller_summary.visitors.sql_fragment_visitor import SqlFragmentVisitor
```

### 5.2. Parse từng chunk vs nối một cục

**Chốt v1:** parse **từng** `SqlChunk` riêng, merge `tables`/`procs`/`signals`.

Lý do: mỗi command/action là batch độc lập; nối có thể làm parser confused giữa `RETURN` / thiếu GO.

`blocks[]` giữ metadata từng chunk kể cả khi content rỗng sau strip.

### 5.3. `SqlFragmentVisitor`

Subset của `sql_object_summary.visitors.summary_visitor.SummaryVisitor`:

- Collect table refs
- Collect EXEC targets
- Signals: `sp_executesql` / gán `@q =` → `dynamic_sql`; tên chứa `$partition$` hoặc `@@prime$partition$` → `partition`; `CURSOR` → `cursor`

**Không** cần: params catalog, call_graph, param_effects, result_set heuristic đầy đủ.

Có thể:

- **Option implement A (khuyến nghị):** copy-minimal visitor mới trong `xml_controller_summary` dùng chung `tsql_engine.parse`
- **Option B:** gọi `analyze_definition(chunk, object_name=f"xml:{event}")` rồi chỉ lấy `summary.tables_read`, `calls_direct`, `signals` — chấp nhận overhead

**Chốt docs cho Gemini: Option A** (visitor mỏng, không phụ thuộc DB models của summary_object). Được phép import `tsql_engine` only — **không** import `queryDatabase`.

### 5.4. Fallback regex SQL

Port [`xml_fbograph/parsers/sql_parser.py`](../../xml_fbograph/parsers/sql_parser.py) / `SQL_PATTERNS`:

- `exec|execute` → procs
- `from|join|into|update` → tables  
- Bỏ keyword giả; bỏ `#temp` khỏi tables

### 5.5. Entry rule cho SQL fragment — CHỐT

`tsql_engine.parse(source, entry_rule=...)` hiện tại:

- Default / đã dùng production: **`entry_rule="tsql_file"`**
- Rule khác chỉ chạy nếu tồn tại method cùng tên trên `TSqlParser` (`getattr`); không có `parse_procedure_body` riêng trên public API ổn định ngoài `tsql_file`

**Fragment trong XML** (Loading/action) **không** có `CREATE PROCEDURE` → parse thẳng `tsql_file` thường **partial/fail**.

**Chốt v1 (làm theo thứ tự):**

1. **Spike checklist B0.5:** thử `parse(chunk, entry_rule="tsql_file")` trên 2–3 fragment SVTran (Loading, TaxAccount). Nếu `status=ok|partial` và visitor lấy được table → dùng trực tiếp.
2. Nếu fail nặng → **wrap** rồi parse `tsql_file`:

```sql
CREATE PROCEDURE dbo.#xml_frag AS
BEGIN
{chunk_body}
END
```

3. Visitor bỏ qua tên proc giả `#xml_frag`; chỉ lấy tables/procs/signals từ body.
4. Vẫn giữ **fallback regex** khi wrap cũng lỗi (vd. `#IF` còn sót).

**Không** phụ thuộc entry rule `sql_clauses` / `batch` trừ khi spike chứng minh rule đó tồn tại trên `generated/TSqlParser.py`.

---

## 6. Field classifier

```python
def map_field_type(attrs: dict, items_style: str | None) -> str:
    t = (attrs.get("type") or "").strip()
    tl = t.lower()
    if items_style and items_style.lower() == "checkbox":
        return "checkbox"
    if tl in {"checkbox", "boolean"}:
        return "checkbox"
    if "date" in tl:  # DateTime, Date
        return "date"
    if tl in {"decimal", "int16", "int32", "int64", "byte", "double", "single", "numeric", "money"}:
        return "number"
    return "char"

def extract_lookup(items_attrs: dict) -> str | None:
    return items_attrs.get("controller") or None

def extract_onchange(client_script_inner: str) -> str | None:
    m = re.search(
        r"onchange\s*=\s*[\"']\s*([a-zA-Z0-9_$]+)\s*\(",
        client_script_inner,
        re.I,
    )
    return m.group(1) if m else None
```

Parse `hidden="true"` → bool; `allowNulls="false"` → False.

Thứ tự `fields[]`: theo thứ tự xuất hiện trong flat XML.

---

## 7. Controller meta từ path / root

```python
def folder_type_from_path(path: str) -> str | None:
    parts = Path(path).parts
    # .../Controllers/Dir/SVTran.xml
    for i, p in enumerate(parts):
        if p.lower() == "controllers" and i + 1 < len(parts):
            return parts[i + 1]  # Dir, Grid, Filter, ...
    return None
```

Optional: regex root tag attributes `table=`, `code=`, `id=` nếu có trên `<dir>` / controller root — không bắt buộc đủ.

---

## 8. Generate JS parser (build)

`js_engine/tools/generate.bat` — mirror `tsql_engine/tools/generate.bat`:

```bat
java -jar "%ANTLR_JAR%" -Dlanguage=Python3 -visitor -no-listener -o "%OUT_DIR%" "%GRAMMAR_DIR%\*.g4"
```

- Commit `generated/` vào git
- CI không cần Java nếu `generated/` đủ

---

## 9. Test đơn vị bắt buộc (không UNC)

Fixture string tối thiểu trong `tests/xml_controller_summary/`:

1. **JS only:** `function onChange$Voucher$Customer(o){o.parentForm.request('Customer','Customer',['ma_kh'],o);}`
2. **Checking JS** + **Loading SQL** trong một flat mini XML
3. **Field ma_kh** AutoComplete Customer + clientScript
4. **Encrypted** block bị skip
5. **Checking SQL sniff:** body bắt đầu `declare @x` → sql bucket

Assert sets tên, không assert timing.
