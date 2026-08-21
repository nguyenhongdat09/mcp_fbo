"""ANTLR Visitor to summarize JavaScript functions, calls, and request actions."""

from __future__ import annotations

import re
from js_engine.generated.JavaScriptParser import JavaScriptParser
from js_engine.generated.JavaScriptParserVisitor import JavaScriptParserVisitor

_STRIP_QUOTES_RE = re.compile(r"^['\"]|['\"]$")


class JsSummaryVisitor(JavaScriptParserVisitor):
    """Visitor collecting function declarations and notable API calls."""

    def __init__(self):
        super().__init__()
        self.functions: set[str] = set()
        self.calls: set[str] = set()
        self.request_actions: set[str] = set()

    def visitFunctionDeclaration(self, ctx: JavaScriptParser.FunctionDeclarationContext):
        if ctx.identifier():
            func_name = ctx.identifier().getText()
            if func_name:
                self.functions.add(func_name)
        return self.visitChildren(ctx)

    def visitFunctionProperty(self, ctx: JavaScriptParser.FunctionPropertyContext):
        if ctx.propertyName():
            prop_name = ctx.propertyName().getText()
            if prop_name:
                self.functions.add(prop_name)
        return self.visitChildren(ctx)

    def visitArgumentsExpression(self, ctx: JavaScriptParser.ArgumentsExpressionContext):
        # singleExpression arguments
        callee_ctx = ctx.singleExpression()
        if callee_ctx:
            callee_text = callee_ctx.getText()

            # 1. Check for request calls (*.request or request)
            if callee_text.endswith(".request") or callee_text == "request":
                # Normalize call representation
                if "parentform" in callee_text.lower():
                    self.calls.add("o.parentForm.request")
                elif callee_text.startswith("f."):
                    self.calls.add("f.request")
                elif callee_text.startswith("this."):
                    self.calls.add("this.request")
                elif callee_text.startswith("sender."):
                    self.calls.add("sender.request")
                else:
                    self.calls.add("f.request")

                # Extract first argument for request_actions
                args_ctx = ctx.arguments()
                if args_ctx and args_ctx.argument():
                    first_arg = args_ctx.argument(0)
                    if first_arg:
                        arg_text = first_arg.getText()
                        cleaned_arg = _STRIP_QUOTES_RE.sub("", arg_text)
                        # Ensure it's a valid identifier/action name
                        if cleaned_arg and re.match(r"^[a-zA-Z0-9_$]+$", cleaned_arg):
                            self.request_actions.add(cleaned_arg)

            # 2. Check for executeExpression
            elif callee_text.endswith(".executeExpression") or callee_text == "executeExpression":
                self.calls.add("f.executeExpression")

            # 3. Check for $message.show
            elif "$message.show" in callee_text:
                self.calls.add("$message.show")

        return self.visitChildren(ctx)
