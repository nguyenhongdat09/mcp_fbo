# tsql_engine — ANTLR4 T-SQL parser (portable)

Engine parse T-SQL **không phụ thuộc** `queryDatabase` / MCP.

## Cấu trúc

```
tsql_engine/
  grammar/           ← TSqlLexer.g4, TSqlParser.g4 (CÓ SẴN trong repo)
  generated/         ← output ANTLR (chạy generate.bat, rồi commit)
  tools/
    download_grammar.py
    generate.bat
  engine.py          ← parse()
  preprocess.py
```

## Setup lần đầu

1. Grammar đã nằm sẵn trong `grammar/` (tải từ antlr/grammars-v4).
2. Tải [antlr-4.13.2-complete.jar](https://www.antlr.org/download/antlr-4.13.2-complete.jar) → `tools/`
3. Chạy:

```bat
cd tsql_engine\tools
generate.bat
```

4. `pip install antlr4-python3-runtime==4.13.2`

## Dùng

```python
from tsql_engine import parse

result = parse("CREATE PROC dbo.p AS BEGIN SELECT 1 END")
print(result.status, len(result.errors))
```

## Tài liệu

- `docs/doc/09_tsql_grammar.md` — chi tiết grammar, entry rules, FBO
- `docs/doc/04_antlr4_parser.md` — visitor / summary feature
