# Grammar T-SQL (ANTLR4) — bắt buộc cho `tsql_engine`

Thư mục này chứa **file grammar gốc** `.g4` — không phải tài liệu mô tả.

## File

| File | Nguồn | Kích thước ~ |
|------|--------|--------------|
| `TSqlLexer.g4` | [antlr/grammars-v4/sql/tsql](https://github.com/antlr/grammars-v4/tree/master/sql/tsql) | 71 KB |
| `TSqlParser.g4` | cùng upstream | 207 KB |
| `UPSTREAM_README.md` | README upstream | copy tham khảo |

## FastBusiness — không cần patch lexer v1

Token `ID` upstream **đã hỗ trợ `$`**:

```antlr
ID : ( [A-Z_#] | FullWidthLetter) ( [A-Z_#$@0-9] | FullWidthLetter)*;
```

→ Parse được `FastBusiness$Balance$BContract`, `r00$`, `#report`, `@Status`.

## Cập nhật grammar

```bat
cd E:\PythonProject\mcp_fbo\tsql_engine\tools
python download_grammar.py
generate.bat
```

Sau `generate.bat`, commit cả `grammar/` và `generated/`.

## Entry rule parse

`TSqlParser.tsql_file` — dùng cho full batch (proc có `CREATE PROCEDURE`).

Proc body từ `sys.sql_modules` (không có header CREATE) — preprocess + parse rule phù hợp (xem `docs/doc/09_tsql_grammar.md`).

License: MIT (xem header file `.g4`).
