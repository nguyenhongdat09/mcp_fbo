# 04 — ANTLR4 Parser (`tsql_engine/`)

> **Package:** `tsql_engine/` — engine thuần, **không** phụ thuộc `queryDatabase` / MCP.  
> **Visitor nghiệp vụ** (summary, signals…) nằm `sql_object_summary/visitors/`.  
> **Đọc kiến trúc:** [07_architecture_layers.md](./07_architecture_layers.md)

## 1. Tổng quan pipeline

```
definition (string)
    → tsql_engine.preprocess
    → TSqlEngine.parse(source)
    → ParseResult { tree, errors, lines, status }
    → (caller) SummaryVisitor trong sql_object_summary
    → SummaryModel → JSON
```

## 2. Grammar source

### Khuyến nghị

Grammar **đã copy sẵn** từ [antlr/grammars-v4 `sql/tsql`](https://github.com/antlr/grammars-v4/tree/master/sql/tsql):

```
tsql_engine/grammar/          ← COMMIT vào git (đã có)
  TSqlLexer.g4
  TSqlParser.g4
  README.md
tsql_engine/generated/        ← sau generate.bat, COMMIT vào git
tsql_engine/tools/
  download_grammar.py         ← tải lại upstream
  generate.bat
```

Xem **`docs/doc/09_tsql_grammar.md`** — hướng dẫn đầy đủ.

### Customization bắt buộc cho FBO

| Vấn đề FBO | Sửa grammar / lexer |
|------------|---------------------|
| Tên có `$` (`FastBusiness$Balance$BContract`) | `IDENTIFIER: [a-zA-Z_@#$][a-zA-Z0-9_@#$]*` hoặc fragment |
| `#temp`, `@var` | Đã có trong T-SQL grammar — verify |
| `GO` batch separator | Preprocessor xóa dòng `^\s*GO\s*$` |
| Proc body không có `CREATE` wrapper khi lấy từ module | Entry rule riêng `procedure_body` |

### Subset v1 (giảm scope)

**Cần parse:**

- `CREATE PROCEDURE` / `ALTER PROCEDURE` header
- `CREATE FUNCTION`
- DML: SELECT, INSERT, UPDATE, DELETE, MERGE
- EXEC / EXECUTE
- DECLARE (variable, cursor, table)
- IF / WHILE / BEGIN / END / TRY / CATCH
- Expression cơ bản (để detect function call)

**Có thể bỏ qua lỗi:**

- DDL ngoài proc (`CREATE INDEX` trong proc hiếm)
- `OPENJSON`, graph clauses, nội dung string phức tạp — skip subtree

## 3. Generate parser (build script)

### Vị trí ANTLR jar (commit vào repo)

```
tsql_engine/
  tools/
    antlr-4.13.2-complete.jar   ← download 1 lần, commit vào git
    generate.bat
  grammar/
    TSqlLexer.g4
    TSqlParser.g4
  generated/                    ← output generate, commit vào git
```

- **Runtime / CI test:** không cần Java — chỉ dùng `generated/` đã commit.
- **Regenerate grammar:** cần Java + jar tại `tsql_engine/tools/antlr-4.13.2-complete.jar`.
- Download: [ANTLR 4.13.2 complete jar](https://www.antlr.org/download/antlr-4.13.2-complete.jar) → đặt đúng path trên.

Tạo `tsql_engine/tools/generate.bat`:

```bat
@echo off
set SCRIPT_DIR=%~dp0
set GRAMMAR_DIR=%SCRIPT_DIR%..\grammar
set OUT_DIR=%SCRIPT_DIR%..\generated
set ANTLR_JAR=%SCRIPT_DIR%antlr-4.13.2-complete.jar

if not exist "%ANTLR_JAR%" (
  echo Missing %ANTLR_JAR% - download antlr-4.13.2-complete.jar
  exit /b 1
)

java -jar "%ANTLR_JAR%" ^
  -Dlanguage=Python3 ^
  -visitor ^
  -no-listener ^
  -o "%OUT_DIR%" ^
  "%GRAMMAR_DIR%\TSqlLexer.g4" ^
  "%GRAMMAR_DIR%\TSqlParser.g4"
```

Hoặc dùng `antlr4-tools` pip package (dev-only).

**Commit** cả `generated/` và `tools/antlr-4.13.2-complete.jar` vào repo (tránh bắt buộc download lúc build).

## 4. Preprocessor (`tsql_engine/preprocess.py`)

```python
def preprocess_definition(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip().upper() == "GO":
            continue
        lines.append(line)
    return "\n".join(lines)
```

Optional: map `line_number → original_line` để snippet trả đúng số dòng file.

## 5. Error handling

```python
from antlr4.error.ErrorListener import ErrorListener

class CollectErrorListener(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append({"line": line, "column": column, "message": msg})
```

- Nếu `errors` empty → `parse_status: ok`
- Nếu có errors nhưng visitor vẫn extract được calls/tables → `partial`
- Nếu không extract được → `failed` + fallback regex

**Quan trọng:** Không raise exception cứng — luôn cố trả partial summary.

## 6. Visitor design

**`SummaryVisitor`** đặt tại `sql_object_summary/visitors/summary_visitor.py` — import tree từ `tsql_engine`, **không** đặt visitor nghiệp vụ trong `tsql_engine/`.

```python
from tsql_engine import parse
from tsql_engine.generated.TSqlParserVisitor import TSqlParserVisitor

# sql_object_summary/visitors/summary_visitor.py
class SummaryVisitor(TSqlParserVisitor):
    ...
```

### Extract table name rules

| Cú pháp | Phân loại |
|---------|-----------|
| `dbo.dmku` | tables_read |
| `dmku` | tables_read (default schema dbo) |
| `#report` | temp_tables |
| `@t TABLE` | temp_tables (table variable) |
| `r00$`, `d91$` | tables_read + `uses_partition` signal |
| Alias sau FROM | **Không** coi alias là table |

Normalize tên:

```python
def normalize_table(raw: str) -> str:
    # bỏ [], "
    # lowercase optional (FBO thường lowercase dmku)
    return name.strip("[]").lower()
```

### Extract procedure calls

Match:

- `EXEC dbo.proc @a, @b`
- `EXECUTE FastBusiness$Partition$Execute ...`
- `INSERT #x EXEC proc` (nested)
- `SELECT ... FROM fn_xxx(...)` → function call

```python
def normalize_object(name_parts: list[str]) -> str:
    if len(name_parts) == 1:
        return f"dbo.{name_parts[0]}"
    return ".".join(name_parts)
```

## 7. Signals detector

```python
@dataclass
class Signals:
    uses_partition_execute: bool = False
    uses_balance_helper: bool = False
    has_cursor: bool = False
    has_while: bool = False
    has_dynamic_sql: bool = False
    has_try_catch: bool = False
    options_keys: list[str] = field(default_factory=list)
    uses_pivot_pattern: bool = False
```

| Signal | Cách detect |
|--------|-------------|
| `uses_partition_execute` | call name contains `Partition$Execute` |
| `uses_balance_helper` | call contains `Balance$` |
| `has_dynamic_sql` | `sp_executesql` hoặc `@var = N'SELECT` |
| `options_keys` | regex `options WHERE name = '([^']+)'` trên AST text |
| `uses_pivot_pattern` | temp `#pivot` hoặc identifier `xpivot`, `xsearch`, `npivot` |

## 8. Param effects (2-tier detector)

### Tầng 1: Generic Detector (AST-based)
Duyệt AST qua visitor để phát hiện mọi `@param` tham gia vào:
- Rẽ nhánh điều kiện: nằm trong biểu thức `IF ...`, `CASE WHEN ...` (`role: "branching"`)
- Lọc dữ liệu: nằm trong mệnh đề `WHERE ...`, `HAVING ...` (`role: "filter"`)
- Điều khiển vòng lặp: nằm trong `WHILE ...` (`role: "loop_bound"`)

```python
@dataclass
class ParamEffect:
    param: str
    role: Literal["branching", "filter", "loop_bound", "calculation"]
    effect: str
    confidence: Literal["low", "medium", "high"] = "medium"
    evidence_lines: list[int] = field(default_factory=list)
```

### Tầng 2: Specific Rule Matcher (FBO patterns)
Áp dụng rule chuyên biệt cho các tham số phổ biến của FastBusiness:

```python
PARAM_EFFECT_RULES = [
    {
        "param": r"@Status",
        "patterns": [
            r"@Status\s*=\s*'1'",
            r"DATEADD\s*\(\s*day\s*,\s*1",
        ],
        "role": "branching",
        "effect": "May shift period start date when Status=1",
        "confidence": "medium",
    },
    {
        "param": r"@mau_bc",
        "patterns": [r"@mau_bc\s*=\s*'\d+'"],
        "role": "branching",
        "effect": "Controls dynamic report layout / column structure",
        "confidence": "high",
    },
]
```

Kết hợp cả 2 tầng: Generic detector đảm bảo không bỏ sót tham số nào ảnh hưởng luồng thực thi, còn Specific rules bổ sung ý nghĩa nghiệp vụ chính xác.

## 9. Snippet extractor (`sql_object_summary/snippet.py`)

### Thuật toán keyword

```python
def extract_by_keywords(lines: list[str], keywords: list[str], context: int = 15) -> list[Snippet]:
    blocks = []
    matched_lines = [i for i, line in enumerate(lines) if any(k.lower() in line.lower() for k in keywords)]
    for i in matched_lines:
        start = expand_to_block_start(lines, i)  # lùi tới BEGIN/comment zone
        end = expand_to_block_end(lines, i)      # tiến tới END
        start = max(0, start - context)
        end = min(len(lines) - 1, end + context)
        blocks.append((start, end))
    return merge_overlapping(blocks)
```

### expand_to_block — stack `BEGIN/END`

Duyệt từ dòng match, đếm depth BEGIN/END để lấy cả vòng lặp.

### Zone detector

Scan comment FBO:

```sql
-- =============================================================================
-- KEY & JOIN
-- =============================================================================
```

Map comment chứa `KEY`, `JOIN`, `DATA`, `PROCESSING`, `RS1`, `PIVOT` → zones.

## 10. Fallback regex (`tsql_engine/fallback.py` hoặc `sql_object_summary/fallback.py`)

Regex fallback có thể nằm `sql_object_summary` (phụ thuộc nghiệp vụ). Engine **không bắt buộc** fallback.

Khi ANTLR fail hoàn toàn:

```python
RE_EXEC = re.compile(r"\bEXEC(?:UTE)?\s+(?:dbo\.)?([a-zA-Z0-9_$#]+)", re.I)
RE_FROM = re.compile(r"\bFROM\s+(?:dbo\.)?(#?[a-zA-Z0-9_$]+)", re.I)
RE_TEMP = re.compile(r"#([a-zA-Z0-9_]+)")
```

Đánh dấu `parse_status: partial`, `parser_used: fallback_regex`.

## 11. Performance

| Proc size | Target |
|-----------|--------|
| < 500 dòng | < 100ms parse |
| 500–2000 dòng | < 500ms |

- Cache parse AST (optional) trong `tsql_engine` — key: `sha256(source)`; **không** cache Summary JSON tại layer này
- Đệ quy call graph: batch fetch definitions 1 query (trong `object_catalog/fetcher.py`)

```sql
-- Batch: mỗi name đã sanitize; v1 dùng OR / IN tĩnh (≤ max_objects 30)
-- Phase 2: table-valued parameter hoặc execute_query(..., params=...)
SELECT o.name, SCHEMA_NAME(o.schema_id) AS schema_name, m.definition
FROM sys.objects o
JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE (SCHEMA_NAME(o.schema_id) = @schema1 AND o.name = @name1)
   OR (SCHEMA_NAME(o.schema_id) = @schema2 AND o.name = @name2)
-- ... tối đa max_objects cặp
```

## 12. Tests unit

```
tests/tsql_engine/test_parse_basic.py      # engine only
tests/sql_object_summary/test_analyze_proc.py  # visitor + fixture .sql
```

Fixture SQL strings (không cần DB):

```python
SIMPLE_EXEC = """
CREATE PROC dbo.p AS
BEGIN
  EXEC FastBusiness$Partition$Execute @t='r00$'
  SELECT * FROM dmku a JOIN ctdmku b ON ...
END
"""

def test_extract_calls_and_tables():
    model = parse_summary(SIMPLE_EXEC)
    assert "FastBusiness$Partition$Execute" in model.calls
    assert "dmku" in model.tables_read
    assert model.signals.uses_partition_execute
```

Thêm fixture từ file SQL thật (copy đoạn ngắn, không commit full proc nếu license concern).

## 13. Known limitations (document trong code)

1. Dynamic SQL trong string → chỉ signal, không parse nội dung
2. Proc gọi proc qua biến `@cmd` → không resolve
3. Linked server / OPENQUERY → bỏ qua v1
4. Encrypted object → error sớm
5. View parse được nhưng không đệ quy view v1

## 14. requirements.txt

Thêm:

```txt
antlr4-python3-runtime==4.13.2
```

Pin version khớp generated code.
