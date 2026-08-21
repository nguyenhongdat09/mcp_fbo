"""ECMAScript / JavaScript ANTLR4 engine — parse only, no XML/MCP dependency."""

from js_engine.engine import JsEngine, ParseResult, parse
from js_engine.errors import ParseError

__all__ = ["JsEngine", "ParseResult", "ParseError", "parse"]
