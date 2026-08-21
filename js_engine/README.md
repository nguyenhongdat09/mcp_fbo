# `js_engine` — Pure ANTLR4 ECMAScript / JavaScript Engine

Engine phân tích cú pháp JavaScript độc lập dùng ANTLR4.

## Trách nhiệm
- Biến chuỗi `JavaScript source: str` thành cây cú pháp AST (`ParseResult`).
- Tuyệt đối **không** phụ thuộc vào XML, FBO metadata, SQL, hay MCP server.
- Hỗ trợ cú pháp ES5/ES6+ và đặc thù FBO (identifier chứa `$`: `onChange$Voucher$Customer`, `$message.show`).

## Cách sử dụng

```python
from js_engine import parse

result = parse("function onChange$Voucher$Customer(o) { f.request('Customer'); }")
if result.status == "ok":
    # Duyệt result.tree qua JavaScriptParserVisitor tùy ý
    pass
```

## Tạo lại Parser
Chạy `tools/generate.bat` khi sửa grammar trong `grammar/`.
Cần Java 11+ (hoặc JDK tự động tải ở `%USERPROFILE%\\.jdk\\`).
