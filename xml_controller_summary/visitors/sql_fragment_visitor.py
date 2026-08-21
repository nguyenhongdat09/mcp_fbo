"""ANTLR Visitor to extract tables, procedures, views, and signals from T-SQL fragments."""

from __future__ import annotations

import re
from tsql_engine.generated.TSqlParserVisitor import TSqlParserVisitor
from tsql_engine.generated.TSqlParser import TSqlParser

_NOISE_TOKENS = {
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "t1", "t2", "d1", "d2", "h1", "h2", "src", "dst", "tbl", "tab", "cte",
    "xml_frag", "#xml_frag", "dbo.#xml_frag",
}

_VIEW_HEURISTIC_RE = re.compile(r"^(v\d|zv)", re.IGNORECASE)



class SqlFragmentVisitor(TSqlParserVisitor):
    """Walks the T-SQL AST to collect table references, procs, and signals."""

    def __init__(self, raw_source: str = ""):
        super().__init__()
        self.raw_source = raw_source
        self.tables_dict: dict[str, str] = {}  # lower -> original casing
        self.procs_dict: dict[str, str] = {}   # lower -> original casing
        self.signals: set[str] = set()

        # Check for cursor / dynamic_sql in text
        if re.search(r"\bcursor\b", raw_source, re.IGNORECASE):
            self.signals.add("cursor")
        if re.search(r"\bsp_executesql\b", raw_source, re.IGNORECASE) or re.search(r"\bexec\s*\(\s*@", raw_source, re.IGNORECASE):
            self.signals.add("dynamic_sql")
        if "$partition$" in raw_source.lower() or "@@prime$partition" in raw_source.lower():
            self.signals.add("partition")

    def _clean_identifier(self, raw: str) -> str:
        clean = re.sub(r"[\[\]\"]", "", raw.strip())
        # Strip dbo. prefix if default
        if clean.lower().startswith("dbo."):
            clean = clean[4:]
        return clean

    def _add_table(self, raw_name: str):
        if not raw_name:
            return
        clean = self._clean_identifier(raw_name)
        if not clean or clean.startswith("#") or clean.startswith("@"):
            return
        lower = clean.lower()
        if lower in _NOISE_TOKENS:
            return

        if lower not in self.tables_dict:
            self.tables_dict[lower] = clean

        if "$partition$" in lower or "partition" in lower:
            self.signals.add("partition")

    def _add_proc(self, raw_name: str):
        if not raw_name:
            return
        clean = self._clean_identifier(raw_name)
        if not clean or clean.startswith("#") or clean.startswith("@"):
            return
        lower = clean.lower()
        if lower in _NOISE_TOKENS:
            return

        if lower not in self.procs_dict:
            self.procs_dict[lower] = clean

        if "sp_executesql" in lower:
            self.signals.add("dynamic_sql")

    def visitTable_source_item(self, ctx: TSqlParser.Table_source_itemContext):
        try:
            if ctx.full_table_name():
                self._add_table(ctx.full_table_name().getText())
        except Exception:
            pass
        return self.visitChildren(ctx)

    def visitInsert_statement(self, ctx: TSqlParser.Insert_statementContext):
        try:
            if ctx.ddl_object():
                self._add_table(ctx.ddl_object().getText())
        except Exception:
            pass
        return self.visitChildren(ctx)

    def visitUpdate_statement(self, ctx: TSqlParser.Update_statementContext):
        try:
            if ctx.ddl_object():
                self._add_table(ctx.ddl_object().getText())
        except Exception:
            pass
        return self.visitChildren(ctx)

    def visitDelete_statement(self, ctx: TSqlParser.Delete_statementContext):
        try:
            if ctx.delete_statement_from() and ctx.delete_statement_from().table_sources():
                # Let children visit table_sources
                pass
            elif ctx.ddl_object():
                self._add_table(ctx.ddl_object().getText())
        except Exception:
            pass
        return self.visitChildren(ctx)

    def visitExecute_statement(self, ctx: TSqlParser.Execute_statementContext):
        try:
            if ctx.execute_body():
                body = ctx.execute_body()
                if body.func_proc_name_server_database_schema():
                    proc_name = body.func_proc_name_server_database_schema().getText()
                    self._add_proc(proc_name)
                elif body.execute_var_string():
                    self.signals.add("dynamic_sql")
        except Exception:
            pass
        return self.visitChildren(ctx)

    def get_tables(self) -> list[str]:
        return list(self.tables_dict.values())

    def get_procs(self) -> list[str]:
        return list(self.procs_dict.values())

    def get_views(self) -> list[str]:
        """Views are a heuristic subset of tables."""
        return [t for t in self.tables_dict.values() if _VIEW_HEURISTIC_RE.match(t)]

    def get_signals(self) -> list[str]:
        return sorted(self.signals)
