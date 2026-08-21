"""TSqlEngine facade — parse T-SQL via ANTLR4 generated parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from tsql_engine.preprocess import preprocess_definition


@dataclass
class ParseError:
    line: int
    column: int
    message: str


@dataclass
class ParseResult:
    source: str
    tree: object | None
    errors: list[ParseError] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    status: Literal["ok", "partial", "failed"] = "failed"
    entry_rule: str = "tsql_file"


class TSqlEngine:
    """Parse T-SQL using generated ANTLR artifacts in tsql_engine/generated/."""

    def parse(self, source: str, entry_rule: str = "tsql_file") -> ParseResult:
        processed = preprocess_definition(source)
        lines = processed.splitlines()

        try:
            from antlr4 import CommonTokenStream, InputStream
            from antlr4.error.ErrorListener import ErrorListener
            from tsql_engine.generated.TSqlLexer import TSqlLexer
            from tsql_engine.generated.TSqlParser import TSqlParser
        except ImportError as exc:
            return ParseResult(
                source=processed,
                tree=None,
                lines=lines,
                status="failed",
                entry_rule=entry_rule,
                errors=[
                    ParseError(
                        line=0,
                        column=0,
                        message=(
                            "Chưa có generated parser. Chạy: "
                            "tsql_engine/tools/generate.bat (cần Java + antlr jar). "
                            f"Detail: {exc}"
                        ),
                    )
                ],
            )

        errors: list[ParseError] = []

        class _Collect(ErrorListener):
            def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
                errors.append(ParseError(line=line or 0, column=column or 0, message=msg or "syntax error"))

        lexer = TSqlLexer(InputStream(processed))
        lexer.removeErrorListeners()
        lexer.addErrorListener(_Collect())

        from antlr4.atn.PredictionMode import PredictionMode

        token_stream = CommonTokenStream(lexer)
        parser = TSqlParser(token_stream)
        parser.removeErrorListeners()
        # SLL prediction mode avoids exponential backtracking in pure-Python runtime
        parser._interp.predictionMode = PredictionMode.SLL

        rule_fn = getattr(parser, entry_rule, None)
        if rule_fn is None:
            return ParseResult(
                source=processed,
                tree=None,
                lines=lines,
                status="failed",
                entry_rule=entry_rule,
                errors=[ParseError(0, 0, f"Unknown entry rule: {entry_rule}")],
            )

        try:
            tree = rule_fn()
            status: Literal["ok", "partial", "failed"] = "ok" if not errors else "partial"
        except Exception as e:
            # If SLL mode fails, return partial tree rather than falling back to slow LL mode
            tree = None
            status = "partial"
            errors.append(ParseError(line=0, column=0, message=f"SLL parsing exception: {e}"))

        return ParseResult(
            source=processed,
            tree=tree,
            errors=errors,
            lines=lines,
            status=status,
            entry_rule=entry_rule,
        )


def parse(source: str, *, entry_rule: str = "tsql_file") -> ParseResult:
    return TSqlEngine().parse(source, entry_rule=entry_rule)
