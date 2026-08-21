# 09 — Grammar T-SQL (ANTLR4) — có sẵn trong repo

> **Quan trọng:** ANTLR4 **bắt buộc** có file `.g4`. Grammar **đã được đặt** trong repo — không chỉ mô tả.

---

## 1. Vị trí file (commit vào git)

```
E:\PythonProject\mcp_fbo\tsql_engine\grammar\
  TSqlLexer.g4          ← 71 KB — lexer token
  TSqlParser.g4         ← 207 KB — parser rules
  UPSTREAM_README.md    ← README từ upstream
  README.md             ← ghi chú FBO / cập nhật
```

**Nguồn:** [github.com/antlr/grammars-v4/tree/master/sql/tsql](https://github.com/antlr/grammars-v4/tree/master/sql/tsql)  
**License:** MIT (header trong file `.g4`)

### Tải lại / cập nhật upstream

```bat
cd E:\PythonProject\mcp_fbo\tsql_engine\tools
python download_grammar.py
```

Script: `tsql_engine/tools/download_grammar.py`

---

## 2. Generate Python parser

ANTLR4 **không chạy runtime** — cần generate **một lần** (hoặc commit sẵn `generated/`):

```bat
REM 1. Tải jar (một lần)
REM    https://www.antlr.org/download/antlr-4.13.2-complete.jar
REM    → tsql_engine\tools\antlr-4.13.2-complete.jar

cd E:\PythonProject\mcp_fbo\tsql_engine\tools
generate.bat
```

Output → `tsql_engine/generated/`:

- `TSqlLexer.py`
- `TSqlParser.py`
- `TSqlParserVisitor.py`
- `TSqlParserListener.py` (nếu có)

**Commit `generated/`** vào git để máy deploy không cần Java.

---

## 3. Dependency Python

```txt
antlr4-python3-runtime==4.13.2
```

Pin **cùng version** với jar 4.13.2.

---

## 4. Entry rules quan trọng

| Rule | Dùng khi |
|------|----------|
| `tsql_file` | Full script có `CREATE PROCEDURE` / batch |
| `batch` | Một batch sau preprocess (bỏ `GO`) |
| `sql_clauses` | Chỉ phần body / DML |

Proc lấy từ `sys.sql_modules.definition` thường **đủ** `CREATE PROC ...` → parse `tsql_file`.

Nếu chỉ có body (hiếm) → thử `batch` hoặc bọc tạm `CREATE PROC #wrapper AS` + body (fallback doc only).

---

## 5. FastBusiness — token `$` (không patch v1)

Upstream lexer **đã hỗ trợ**:

```antlr
ID : ( [A-Z_#] | FullWidthLetter) ( [A-Z_#$@0-9] | FullWidthLetter)*;
LOCAL_ID : '@' ([A-Z_$@#0-9] | FullWidthLetter)*;
TEMP_ID : '#' ([A-Z_$@#0-9] | FullWidthLetter)*;
```

Ví dụ parse được:

- `FastBusiness$Partition$Execute`
- `FastBusiness$Balance$BContract`
- `dmku`, `r00$`, `#report`, `@Status`

**Không fork grammar v1** trừ khi gặp lỗi parse thực tế trên proc FBO.

---

## 6. Preprocess trước parse

`tsql_engine/preprocess.py`:

- Xóa dòng `GO` (batch separator SSMS)
- Giữ comment (lexer channel HIDDEN)
- Normalize `\r\n`

---

## 7. API engine

```python
from tsql_engine import parse, TSqlEngine, ParseResult

result = parse(definition_text, entry_rule="tsql_file")
# result.tree → ANTLR ParseTree
# result.status → ok | partial | failed
# result.errors → list ParseError
```

Visitor nghiệp vụ (`SummaryVisitor`) **không** nằm trong `tsql_engine` — xem `sql_object_summary/visitors/`.

---

## 8. Quy trình implement (Gemini)

```
1. Verify grammar/ có 2 file .g4
2. generate.bat → generated/
3. pytest tests/tsql_engine/test_parse_basic.py
4. sql_object_summary SummaryVisitor extends TSqlParserVisitor
5. queryDatabase bridge — KHÔNG sửa grammar
```

---

## 9. Checklist grammar

- [ ] `TSqlLexer.g4` + `TSqlParser.g4` tồn tại trong repo
- [ ] `generated/*.py` đã generate và commit
- [ ] `antlr4-python3-runtime==4.13.2` trong requirements.txt
- [ ] Test parse: `EXEC FastBusiness$Partition$Execute`, `#temp`, `@var`
- [ ] Test fixture proc FBO (đoạn ngắn từ `rs_rptInterestDetailedByLoanContract`)

---

## 10. Lỗi thường gặp

| Lỗi | Cách xử lý |
|-----|------------|
| `ImportError: generated.TSqlLexer` | Chưa chạy `generate.bat` |
| `java not found` | Cài JRE; hoặc dùng `generated/` đã commit |
| Parse `partial` trên proc dài | Bình thường v1 — fallback regex ở `sql_object_summary` |
| Grammar quá nặm | Không rút gọn grammar v1 — dùng upstream full |
