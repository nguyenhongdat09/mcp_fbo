"""JsEngine facade — parse ECMAScript/JavaScript via ANTLR4 generated parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from js_engine.errors import ParseError, JsErrorListener
from js_engine.preprocess import preprocess_js


@dataclass
class ParseResult:
    source: str
    tree: object | None
    errors: list[ParseError] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    status: Literal["ok", "partial", "failed"] = "failed"
    entry_rule: str = "program"


class JsEngine:
    """Parse JavaScript source using generated ANTLR artifacts in js_engine/generated/."""

    def parse(self, source: str, entry_rule: str = "program") -> ParseResult:
        processed = preprocess_js(source)
        lines = processed.splitlines()

        if not processed.strip():
            return ParseResult(
                source=processed,
                tree=None,
                errors=[],
                lines=lines,
                status="ok",
                entry_rule=entry_rule,
            )

        try:
            from antlr4 import CommonTokenStream, InputStream
            from antlr4.atn.PredictionMode import PredictionMode
            from js_engine.generated.JavaScriptLexer import JavaScriptLexer
            from js_engine.generated.JavaScriptParser import JavaScriptParser
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
                            "Chưa có generated JS parser. Chạy: "
                            "js_engine/tools/generate.bat. "
                            f"Detail: {exc}"
                        ),
                    )
                ],
            )

        errors: list[ParseError] = []
        error_listener = JsErrorListener(errors)

        try:
            input_stream = InputStream(processed)
            lexer = JavaScriptLexer(input_stream)
            lexer.removeErrorListeners()
            lexer.addErrorListener(error_listener)

            token_stream = CommonTokenStream(lexer)
            parser = JavaScriptParser(token_stream)
            parser.removeErrorListeners()
            parser.addErrorListener(error_listener)
            # Use SLL prediction mode for fast parsing; fallback to LL if needed
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
            except Exception as sll_exc:
                # Fallback to LL if SLL threw
                try:
                    token_stream.seek(0)
                    parser.reset()
                    parser._interp.predictionMode = PredictionMode.LL
                    tree = rule_fn()
                    status = "ok" if not errors else "partial"
                except Exception as ll_exc:
                    tree = None
                    status = "failed"
                    errors.append(ParseError(line=0, column=0, message=f"Parsing exception: {ll_exc}"))
        except Exception as general_exc:
            return ParseResult(
                source=processed,
                tree=None,
                lines=lines,
                status="failed",
                entry_rule=entry_rule,
                errors=[ParseError(0, 0, f"JS parsing initialization failed: {general_exc}")],
            )

        return ParseResult(
            source=processed,
            tree=tree,
            errors=errors,
            lines=lines,
            status=status,
            entry_rule=entry_rule,
        )


def parse(source: str, *, entry_rule: str = "program") -> ParseResult:
    return JsEngine().parse(source, entry_rule=entry_rule)
