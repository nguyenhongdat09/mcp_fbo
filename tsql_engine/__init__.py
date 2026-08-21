"""T-SQL ANTLR4 engine — parse only, no DB dependency."""

from tsql_engine.engine import TSqlEngine, ParseResult, parse

__all__ = ["TSqlEngine", "ParseResult", "parse"]
