"""Error handling and data structures for js_engine."""

from __future__ import annotations

from dataclasses import dataclass
from antlr4.error.ErrorListener import ErrorListener


@dataclass
class ParseError:
    line: int
    column: int
    message: str


class JsErrorListener(ErrorListener):
    """Collect syntax errors without writing to stderr."""

    def __init__(self, errors_list: list[ParseError]):
        super().__init__()
        self.errors = errors_list

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(
            ParseError(
                line=line or 0,
                column=column or 0,
                message=msg or "Syntax error in JavaScript source",
            )
        )
