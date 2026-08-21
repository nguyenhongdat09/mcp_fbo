"""ANTLR4 Visitor to extract parameters, table dependencies, calls, and signals from T-SQL AST."""

from __future__ import annotations

import re
from typing import Any

from tsql_engine.generated.TSqlParserVisitor import TSqlParserVisitor
from tsql_engine.generated.TSqlParser import TSqlParser
from sql_object_summary.models import (
    ObjectSummary,
    ParamInfo,
    DirectCall,
    ResultSetHint,
    Signals,
)
from sql_object_summary.classifier import classify_object
from sql_object_summary.keyword_builder import build_keywords_suggested

SQL_TABLE_NOISE_TOKENS = {
    # 1. Common table aliases & temporary query labels
    "a", "b", "c", "d", "e", "f", "g", "gl", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "aa", "bb", "cc", "dd", "tmp", "temp", "cur", "g1", "g2", "t1", "t2",
    "d1", "d2", "h1", "h2", "src", "dst", "tbl", "tab", "cte", "sub", "main",
    "dt", "hdr", "det", "mst", "item", "row", "val", "res", "result", "fact",
    "data", "rpt", "rep", "report", "detail", "master", "head", "calc", "re", "sl",

    # 2. SQL Keywords & Clauses
    "set", "select", "where", "from", "join", "inner", "outer", "left", "right",
    "full", "cross", "apply", "on", "into", "values", "exec", "execute", "begin",
    "end", "declare", "return", "with", "as", "order", "group", "by", "having",
    "union", "all", "case", "when", "then", "else", "and", "or", "not", "is",
    "null", "like", "in", "exists", "between", "distinct", "top", "offset",
    "fetch", "next", "rows", "only", "table", "cursor", "open", "close",
    "deallocate", "insert", "update", "delete", "truncate", "drop", "create",
    "alter", "proc", "procedure", "function", "view", "index", "trigger",
    "transaction", "commit", "rollback", "save", "nolock", "holdlock", "readuncommitted",

    # 3. SQL Data Types
    "nvarchar", "varchar", "char", "nchar", "text", "ntext", "int", "bigint",
    "smallint", "tinyint", "bit", "decimal", "numeric", "float", "real", "money",
    "smallmoney", "datetime", "smalldatetime", "date", "time", "datetime2",
    "datetimeoffset", "timestamp", "uniqueidentifier", "xml", "image", "binary",
    "varbinary", "sysname", "sql_variant", "geometry", "geography", "hierarchyid",

    # 4. System Catalog & Metadata
    "information_schema", "sys", "sysobjects", "syscolumns", "sysindexes",
}


class SummaryVisitor(TSqlParserVisitor):
    """Walks the T-SQL AST to build an ObjectSummary model."""

    def __init__(
        self,
        raw_lines: list[str] | None = None,
        options: Any = None,
        object_name: str | None = None,
    ):
        super().__init__()
        self.raw_lines = raw_lines or []
        self.options = options
        self.object_name = object_name or ""
        self.full_text = "\n".join(self.raw_lines)

        cte_matches = re.findall(r"(?i)(?:;?\s*WITH|,)\s*([a-zA-Z_][\w]*)\s+AS\s*\(", self.full_text)
        self.cte_names_set: set[str] = {c.lower() for c in cte_matches}

        self.params: list[ParamInfo] = []
        self.calls_direct_set: set[str] = set()
        self.tables_read_set: set[str] = set()
        self.tables_write_set: set[str] = set()
        self.temp_tables_set: set[str] = set()
        self.variables_count: dict[str, int] = {}
        self.result_sets: list[ResultSetHint] = []
        self.signals = Signals()
        self.zones_detected_set: set[str] = set()

    def _normalize_name(self, raw: str) -> str:
        """Strip brackets, quotes, and whitespace."""
        clean = re.sub(r"[\[\]\"]", "", raw.strip())
        return clean

    def _normalize_table_name(self, raw_table: str) -> str | None:
        """Normalize table name, stripping temp tables, aliases, numbers, and partition suffixes."""
        name = self._normalize_name(raw_table)
        if not name:
            return None

        # Check for temp table or table variable
        if name.startswith("#") or name.startswith("@"):
            self.temp_tables_set.add(name)
            return None

        # Strip schema if default dbo (keep for partitioned tables / sys tables)
        if "." in name:
            schema, table_name = name.split(".", 1)
            clean_name = f"{schema.lower()}.{table_name.lower()}" if schema.lower() != "dbo" else table_name.lower()
        else:
            clean_name = name.lower()

        # Pure numeric tokens are literals / indexes / TOP N, not table names
        if clean_name.isdigit():
            return None

        # Dynamic CTE aliases defined in WITH clause are not physical tables
        if clean_name in self.cte_names_set:
            return None

        # Collapse partition suffixes: r00$000000 -> r00$, d91$000000 -> d91$, a89$000000 -> a89$, m89$000000 -> m89$
        partition_match = re.match(r"^([ardcm]\d\d\$)\d+$", clean_name)
        if partition_match:
            clean_name = partition_match.group(1)

        # Filter known table aliases, SQL keywords, and data types
        if clean_name in SQL_TABLE_NOISE_TOKENS:
            return None

        # Signal check for partition tables (r00$, d91$, a89$, m89$, c00$, etc.)
        if "$" in clean_name and (clean_name.startswith("r") or clean_name.startswith("d") or clean_name.startswith("c") or clean_name.startswith("a") or clean_name.startswith("m")):
            self.signals.uses_partition_execute = True

        return clean_name

    def _add_table(self, raw_table: str, is_write: bool = False) -> None:
        clean_name = self._normalize_table_name(raw_table)
        if not clean_name:
            return

        if is_write:
            self.tables_write_set.add(clean_name)
        else:
            self.tables_read_set.add(clean_name)

    def _add_call(self, raw_proc: str) -> None:
        name = self._normalize_name(raw_proc)
        if not name:
            return

        # Normalize schema prefix
        if "." not in name:
            full_name = f"dbo.{name}"
        else:
            full_name = name

        self.calls_direct_set.add(full_name)

        if "Partition$Execute" in full_name:
            self.signals.uses_partition_execute = True
        if "Balance$" in full_name:
            self.signals.uses_balance_helper = True

    # -------------------------------------------------------------------------
    # Procedure / Function Parameter Extraction
    # -------------------------------------------------------------------------

    def visitProcedure_param(self, ctx: TSqlParser.Procedure_paramContext):
        try:
            param_name = ctx.LOCAL_ID().getText() if ctx.LOCAL_ID() else ""
            data_type = ctx.data_type().getText() if ctx.data_type() else ""

            default_val = None
            if hasattr(ctx, "procedure_param_default_value"):
                fn = getattr(ctx, "procedure_param_default_value")
                if callable(fn):
                    node = fn()
                    if node:
                        default_val = node.getText().lstrip("=").strip()

            is_out = bool(ctx.OUT() or ctx.OUTPUT())

            if param_name:
                self.params.append(
                    ParamInfo(
                        name=param_name,
                        type=data_type.upper(),
                        default=default_val if default_val else None,
                        is_output=is_out,
                    )
                )
                self.zones_detected_set.add("params")
        except Exception:
            pass
        return self.visitChildren(ctx)

    # -------------------------------------------------------------------------
    # Call / Execute Extraction
    # -------------------------------------------------------------------------

    def visitExecute_statement(self, ctx: TSqlParser.Execute_statementContext):
        try:
            if ctx.execute_body():
                body = ctx.execute_body()
                if body.func_proc_name_server_database_schema():
                    proc_name = body.func_proc_name_server_database_schema().getText()
                    self._add_call(proc_name)
                    if "sp_executesql" in proc_name.lower():
                        self.signals.has_dynamic_sql = True
        except Exception:
            pass
        return self.visitChildren(ctx)

    # -------------------------------------------------------------------------
    # CTE & Common Table Expressions (ANTLR4 Native AST)
    # -------------------------------------------------------------------------

    def visitCommon_table_expression(self, ctx: TSqlParser.Common_table_expressionContext):
        try:
            if ctx.id_():
                cte_name = self._normalize_name(ctx.id_().getText()).lower()
                self.cte_names_set.add(cte_name)
        except Exception:
            pass
        return self.visitChildren(ctx)

    # -------------------------------------------------------------------------
    # DML & Table Extraction
    # -------------------------------------------------------------------------

    def visitTable_source_item(self, ctx: TSqlParser.Table_source_itemContext):
        try:
            if ctx.full_table_name():
                t_name = ctx.full_table_name().getText()
                self._add_table(t_name, is_write=False)
        except Exception:
            pass
        return self.visitChildren(ctx)

    def visitInsert_statement(self, ctx: TSqlParser.Insert_statementContext):
        try:
            if ctx.ddl_object():
                t_name = ctx.ddl_object().getText()
                self._add_table(t_name, is_write=True)
        except Exception:
            pass
        return self.visitChildren(ctx)

    def visitUpdate_statement(self, ctx: TSqlParser.Update_statementContext):
        try:
            if ctx.ddl_object():
                t_name = ctx.ddl_object().getText()
                self._add_table(t_name, is_write=True)
        except Exception:
            pass
        return self.visitChildren(ctx)

    def visitDelete_statement(self, ctx: TSqlParser.Delete_statementContext):
        try:
            if ctx.delete_statement_from():
                t_name = ctx.delete_statement_from().getText()
                self._add_table(t_name, is_write=True)
        except Exception:
            pass
        return self.visitChildren(ctx)

    # -------------------------------------------------------------------------
    # Signals Detection (Cursor, While, Try Catch, Options, Pivot)
    # -------------------------------------------------------------------------

    def visitDeclare_cursor(self, ctx: TSqlParser.Declare_cursorContext):
        self.signals.has_cursor = True
        self.zones_detected_set.add("cursor")
        return self.visitChildren(ctx)

    def visitWhile_statement(self, ctx: TSqlParser.While_statementContext):
        self.signals.has_while = True
        self.zones_detected_set.add("processing")
        return self.visitChildren(ctx)

    def visitTry_catch_statement(self, ctx: TSqlParser.Try_catch_statementContext):
        self.signals.has_try_catch = True
        return self.visitChildren(ctx)

    # -------------------------------------------------------------------------
    # Result Set Extraction (Filtered: No variable assignments, no INTO)
    # -------------------------------------------------------------------------

    def visitSelect_statement_standalone(self, ctx: TSqlParser.Select_statement_standaloneContext):
        try:
            # 0. Skip if inside cursor declaration or subquery
            curr_parent = ctx.parentCtx
            while curr_parent is not None:
                parent_name = type(curr_parent).__name__
                if "Cursor" in parent_name or "Declare_cursor" in parent_name:
                    return self.visitChildren(ctx)
                curr_parent = getattr(curr_parent, "parentCtx", None)

            full_txt = ctx.getText()
            # 1. Skip if contains INTO #temp or INTO @table
            if re.search(r"\bINTO\s+[#@\[a-zA-Z0-9_]", full_txt, re.IGNORECASE) or "INTO#" in full_txt.upper():
                return self.visitChildren(ctx)

            select_stmt = ctx.select_statement()
            if not select_stmt or not select_stmt.query_expression():
                return self.visitChildren(ctx)

            query_expr = select_stmt.query_expression()
            query_spec = query_expr.query_specification()
            if not query_spec or not query_spec.select_list():
                return self.visitChildren(ctx)

            elems = query_spec.select_list().select_list_elem()
            if not elems:
                return self.visitChildren(ctx)

            # 2. Check if this is a variable assignment (e.g. SELECT @round = val)
            is_variable_assign = False
            for elem_ctx in elems:
                elem_txt = elem_ctx.getText().strip()
                if elem_txt.startswith("@") and ("=" in elem_txt or "+=" in elem_txt):
                    is_variable_assign = True
                    break

            if is_variable_assign:
                return self.visitChildren(ctx)

            # 3. Extract real clean column identifiers
            cols: list[str] = []
            for elem_ctx in elems:
                col_text = elem_ctx.getText().strip()
                clean_col = ""
                if " AS " in col_text.upper():
                    clean_col = col_text.split("AS")[-1].strip(" []\"'")
                elif "." in col_text:
                    clean_col = col_text.split(".")[-1].strip(" []\"'")
                else:
                    clean_col = col_text.strip(" []\"'")

                # Validate clean_col is a valid column identifier
                if clean_col and re.match(r"^[a-zA-Z0-9_#$]+$", clean_col) and not clean_col.startswith("@"):
                    if clean_col.lower() not in [c.lower() for c in cols]:
                        cols.append(clean_col)

            # Only add if valid column identifiers are returned
            if cols:
                ordinal = len(self.result_sets) + 1
                if ordinal <= 5:
                    if "@stt_rec" in self.full_text.lower():
                        rs_hint = "master" if ordinal == 1 else ("detail" if ordinal == 2 else f"RS{ordinal}")
                    else:
                        rs_hint = "listing" if ordinal == 1 else f"RS{ordinal}"

                    self.result_sets.append(
                        ResultSetHint(
                            ordinal=ordinal,
                            hint=rs_hint,
                            confidence="medium" if len(cols) >= 2 else "low",
                            columns_hint=cols[:30],
                        )
                    )
                    self.zones_detected_set.add("result_set")
        except Exception:
            pass
        return self.visitChildren(ctx)

    def _compute_snippet_index(self) -> dict[str, list[int]]:
        """Compute 1-indexed [start_line, end_line] ranges for detected zones."""
        index: dict[str, list[int]] = {}
        total_lines = len(self.raw_lines)
        if total_lines == 0:
            return index

        # 1. Header & Params zone (from start to AS/BEGIN)
        header_start = 1
        header_end = min(40, total_lines)
        for i, line in enumerate(self.raw_lines, start=1):
            if re.match(r"^\s*(AS|BEGIN)\b", line, re.IGNORECASE):
                header_end = i
                break
        index["header"] = [header_start, header_end]
        if self.params:
            index["params"] = [header_start, header_end]

        # 2. Key filter zone (-- KEY, -- JOIN, Partition$Execute)
        key_lines: list[int] = []
        for i, line in enumerate(self.raw_lines, start=1):
            if re.search(r"(--\s*(KEY|JOIN)|Partition\$Execute|Balance\$)", line, re.IGNORECASE):
                key_lines.append(i)
        if key_lines:
            index["key_filter"] = [max(1, min(key_lines) - 2), min(total_lines, max(key_lines) + 20)]

        # 3. Cursor zone (DECLARE ... CURSOR -> DEALLOCATE / CLOSE)
        cursor_lines: list[int] = []
        for i, line in enumerate(self.raw_lines, start=1):
            if re.search(r"\b(DECLARE\s+\w+\s+CURSOR|OPEN\s+\w+|FETCH\s+NEXT|DEALLOCATE\s+\w+)\b", line, re.IGNORECASE):
                cursor_lines.append(i)
        if cursor_lines:
            index["cursor"] = [max(1, min(cursor_lines) - 2), min(total_lines, max(cursor_lines) + 15)]

        # 4. Processing zone (WHILE loops / calculation blocks)
        proc_lines: list[int] = []
        for i, line in enumerate(self.raw_lines, start=1):
            if re.search(r"\b(WHILE\b|DATEADD|ROUND\b|\bUPDATE\s+#|\bINSERT\s+INTO\s+#)", line, re.IGNORECASE):
                proc_lines.append(i)
        if proc_lines:
            index["processing"] = [max(1, min(proc_lines) - 2), min(total_lines, max(proc_lines) + 20)]

        # 5. Pivot zone
        pivot_lines: list[int] = []
        for i, line in enumerate(self.raw_lines, start=1):
            if re.search(r"(#pivot|xpivot|xsearch)", line, re.IGNORECASE):
                pivot_lines.append(i)
        if pivot_lines:
            index["pivot"] = [max(1, min(pivot_lines) - 5), min(total_lines, max(pivot_lines) + 20)]

        # 6. Result Set zone (final SELECT statements)
        rs_lines: list[int] = []
        for i, line in enumerate(self.raw_lines, start=1):
            if re.search(r"^\s*SELECT\b", line, re.IGNORECASE) and not re.search(r"(@\w+\s*=|INTO\s+#)", line, re.IGNORECASE):
                rs_lines.append(i)
        if rs_lines:
            index["result_set"] = [max(1, rs_lines[-1] - 5), min(total_lines, rs_lines[-1] + 15)]

        return index

    def _compute_logic_hints(self) -> dict[str, Any]:
        """Compute domain-specific hints and keywords for the Agent."""
        txt_lower = self.full_text.lower()
        hints: dict[str, Any] = {}

        # 1. Interest calculation domain
        interest_related = bool(
            "tl_th" in txt_lower
            or "tl_qh" in txt_lower
            or "m_kieu_ls" in txt_lower
            or "m_ngay_ls_nam" in txt_lower
            or "lai_suat" in txt_lower
            or "dmku" in txt_lower
        )

        # 2. Financial Statement / Budget Form template domain (BCTC/NS)
        bctc_form_related = bool(
            "bcnsky" in txt_lower
            or "glns" in txt_lower
            or "dmctns" in txt_lower
            or "checkformula" in txt_lower
            or "jobcalcxstruct" in txt_lower
            or ("@form" in txt_lower and "@mau_bc" in txt_lower)
        )

        # 3. Inventory / Lot summary domain
        stock_related = bool(
            "balance$lot" in txt_lower
            or "m_instock_split" in txt_lower
            or ("dmvt" in txt_lower and "dmlo" in txt_lower)
        )

        obj_bare = self.object_name.split(".")[-1].lower()
        obj_clean = obj_bare.replace("$", "").replace("_", "")

        # 4. Input Invoice domain (HDDV / II) - MUST be checked before general EInvoice
        input_invoice_related = bool(
            "inputinvoice" in obj_clean
            or "fastbusiness$inputinvoice$" in txt_lower
            or ("einvoice" not in obj_clean and ("importxml" in txt_lower or "iiinsert" in txt_lower))
        )

        # 5. E-Invoice issuance domain (HDDT) - excludes InputInvoice
        einvoice_related = bool(
            not input_invoice_related
            and (
                "einvoice" in obj_clean
                or "$einvoice$" in obj_bare
                or "fastbusiness$einvoice$" in txt_lower
            )
        )

        # 6. Voucher Approval domain (APV / Approval)
        approval_related = bool(
            "$apv$" in obj_bare
            or "approval" in obj_clean
            or "approve" in obj_clean
            or "$apv$" in txt_lower
        )

        # 7. Discount / Rebate domain
        discount_related = bool(
            "discount" in obj_clean
            or "discount$" in txt_lower
        )

        # 8. Voucher Lifecycle hook domain (After/Before Update/Insert/Delete)
        voucher_lifecycle_related = bool(
            any(p in obj_clean for p in ["afterupdate", "beforeupdate", "afterinsert", "beforeinsert", "afterdelete", "beforedelete"])
            or any(p in txt_lower for p in ["afterupdate$", "beforeupdate$", "afterinsert$", "beforeinsert$"])
        )

        # 9. Inventory / GL Post procedure domain (fs_Post*) - excludes Discount and Lifecycle
        post_related = bool(
            not discount_related
            and not voucher_lifecycle_related
            and (
                obj_bare.startswith("fs_post")
                or re.search(r"(^|\$)post(\$|_|$)", obj_bare)
                or re.search(r"\bfs_post", txt_lower)
            )
        )

        # 10. Balance helper domain (Account/Customer/Item balance helpers)
        balance_related = bool(
            "balance$" in obj_bare
            or "$balance$" in obj_bare
            or "fastbusiness$balance$" in txt_lower
            or "balance$" in txt_lower
        )

        is_rs_object = obj_bare.startswith("rs_")
        is_zc_object = obj_bare.startswith("zc_")
        is_infra_object = obj_bare.startswith("fastbusiness$") or obj_bare.startswith("fs_") or is_rs_object

        # 11. Custom domain (zc_*, #$*, zcd*, customize logic) - FastBusiness$/fs_/rs_ are standard FBO infra/reports
        is_custom = bool(
            is_zc_object
            or (not is_infra_object and ("zcdm" in txt_lower or "#$" in txt_lower or "@keypo" in txt_lower))
        )

        has_real_write = bool(self.tables_write_set)

        custom_is_action = bool(
            is_custom
            and (
                any(obj_bare.startswith(p) for p in [
                    "zc_post", "zc_insert", "zc_update", "zc_delete", "zc_del",
                    "zc_save", "zc_check", "zc_import", "zc_convert", "zc_create", "zc_auto"
                ])
                or has_real_write
                or re.search(r"@action\b", txt_lower)
            )
        )

        output_select_count = len(re.findall(
            r"(?im)^\s*SELECT\b(?![^\n]*@\w+\s*=)(?![^\n]*\bINTO\b)",
            self.full_text,
        ))

        custom_is_report = bool(
            is_custom
            and not custom_is_action
            and (
                any(obj_bare.startswith(p) for p in ["zc_bc", "zc_rpt", "zc_list", "zc_view", "zc_dx", "zc_in"])
                or "#report" in txt_lower
                or "@datefrom" in txt_lower
                or "@ngay_tu" in txt_lower
                or "@tu_ngay" in txt_lower
                or (
                    "@stt_rec" in txt_lower
                    and not has_real_write
                    and output_select_count >= 1
                )
            )
        )
        custom_listing_related = is_custom

        # 12. Standard report generic domain (rs_*, #report with Partition/sp_executesql/date filters)
        report_generic = bool(
            obj_bare.startswith("rs_rpt")
            or (
                obj_bare.startswith("rs_")
                and (
                    "#report" in txt_lower
                    or "partition$execute" in txt_lower
                    or "sp_executesql" in txt_lower
                    or "@datefrom" in txt_lower
                    or "@thang_tu" in txt_lower
                    or "@ngay_tu" in txt_lower
                    or re.search(r"\bEXEC\s*\(\s*@q", txt_lower)
                )
            )
            or (
                "#report" in txt_lower
                and (
                    "partition$execute" in txt_lower
                    or "sp_executesql" in txt_lower
                    or re.search(r"\bEXEC\s*\(\s*@q", txt_lower)
                )
            )
        )

        domain_flag = None
        if interest_related:
            domain_flag = "interest_related"
            hints["interest_related"] = True
            hints["note"] = "Interest formula lives in cursor/WHILE; use mode=snippet with keywords_suggested"
        elif bctc_form_related:
            domain_flag = "bctc_form_related"
            hints["bctc_form_related"] = True
            hints["note"] = "Form/template report (bcnsky/glns); formula in CheckFormula + JobCalcXStruct; use mode=snippet with keywords_suggested or zones=['processing','result_set']"
        elif input_invoice_related:
            domain_flag = "input_invoice_related"
            hints["input_invoice_related"] = True
            hints["note"] = "Input invoice (HDDV/II); import/map XML or create voucher from inbound invoice"
        elif einvoice_related:
            domain_flag = "einvoice_related"
            hints["einvoice_related"] = True
            hints["note"] = "E-invoice issuance (HDDT); publish/process outbound electronic invoice"
        elif approval_related:
            domain_flag = "approval_related"
            hints["approval_related"] = True
            hints["note"] = "Voucher approval flow (APV/Approval); inspect status/role/process approve"
        elif discount_related:
            domain_flag = "discount_related"
            hints["discount_related"] = True
            hints["note"] = "Discount/rebate calculation or posting; inspect period allocation rules"
        elif post_related:
            domain_flag = "post_related"
            hints["post_related"] = True
            hints["note"] = "Inventory/GL post procedure (fs_Post*); inspect tables_write, site/item qty updates"
        elif voucher_lifecycle_related:
            domain_flag = "voucher_lifecycle_related"
            hints["voucher_lifecycle_related"] = True
            hints["note"] = "Voucher lifecycle hook (After/Before Update); updates source tracking/qty after retrieve or save; snippet @stt_rec, sl_*, link tables"
        elif balance_related:
            domain_flag = "balance_related"
            hints["balance_related"] = True
            hints["note"] = "Balance helper (tồn/dư Account/Item/Lot/Contract); not the same as fs_Post"
            if stock_related:
                hints["stock_related"] = True
        elif stock_related:
            domain_flag = "stock_related"
            hints["stock_related"] = True
            hints["note"] = "Inventory/lot summary report; use mode=snippet with keywords_suggested"
        elif custom_is_action:
            domain_flag = "custom_action_related"
            hints["custom_action_related"] = True
            hints["custom_related"] = True
            hints["custom_listing_related"] = True  # backward compatibility
            hints["note"] = "Custom transaction/action procedure (data manipulation/processing); inspect tables_write and key parameters"
        elif custom_is_report:
            domain_flag = "custom_report_related"
            hints["custom_report_related"] = True
            hints["custom_related"] = True
            hints["custom_listing_related"] = True
            hints["note"] = "Custom print/inquiry procedure; multiple result sets for form/report; use snippet result_set / processing"
        elif is_custom:
            domain_flag = "custom_related"
            hints["custom_related"] = True
            hints["custom_listing_related"] = True
            hints["note"] = "Custom procedure for system extension; inspect parameters and accessed tables"
        elif report_generic:
            domain_flag = "report_generic"
            hints["report_generic"] = True
            hints["note"] = "Standard FBO report (rs_* / #report); use snippet key_filter + result_set; keywords from params in this proc"
        elif "pivot" in self.zones_detected_set:
            hints["note"] = "Pivot report structure; use mode=snippet with zones=['pivot', 'result_set']"

        # Build keywords automatically using keyword_builder
        calls_for_builder = [DirectCall(name=c, kind="unknown") for c in self.calls_direct_set]
        keywords_suggested = build_keywords_suggested(
            full_text=self.full_text,
            params=self.params,
            temp_tables=self.temp_tables_set,
            tables_read=self.tables_read_set,
            calls_direct=calls_for_builder,
            domain_flag=domain_flag,
        )

        if keywords_suggested:
            hints["keywords_suggested"] = keywords_suggested
        if self.signals.options_keys:
            hints["options_keys"] = self.signals.options_keys

        return hints

    def finalize(self) -> ObjectSummary:
        """Run secondary regex scans for signals/options and package into ObjectSummary."""
        # Strip SQL comments so commented-out code doesn't produce phantom tables
        clean_code = re.sub(r"/\*.*?\*/", "", self.full_text, flags=re.DOTALL)
        clean_code = re.sub(r"--[^\r\n]*", "", clean_code)

        # 1. Fallback scanners if AST didn't populate (fast heuristic mode)
        if not self.tables_read_set:
            for tbl in re.findall(r"\b(?:FROM|JOIN)\s+(?:dbo\.)?([a-zA-Z0-9_$#]+)", clean_code, re.IGNORECASE):
                self._add_table(tbl, is_write=False)

        if not self.tables_write_set:
            for tbl in re.findall(r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:dbo\.)?([a-zA-Z0-9_$#]+)", clean_code, re.IGNORECASE):
                self._add_table(tbl, is_write=True)

        if not self.calls_direct_set:
            for call in re.findall(r"\bEXEC(?:UTE)?\s+(?:dbo\.)?([a-zA-Z0-9_$#]+)", clean_code, re.IGNORECASE):
                if not call.startswith("@") and not call.startswith("#"):
                    self._add_call(call)

        if not self.params:
            param_matches = re.findall(r"(@[a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+(?:\([^)]+\))?)(?:\s*=\s*([^,\n\r]+))?", self.full_text[:2500])
            for p_name, p_type, p_def in param_matches:
                if p_name.lower() not in [p.name.lower() for p in self.params]:
                    self.params.append(ParamInfo(name=p_name, type=p_type.upper(), default=p_def.strip() if p_def else None))

        # 2. Regex scan for options keys: options WHERE name = '...' or options a ... name = '...'
        options_matches = re.findall(
            r"options\b[\s\S]{0,200}?name\s*=\s*'([^']+)'",
            self.full_text,
            re.IGNORECASE,
        )
        for opt in options_matches:
            if opt not in self.signals.options_keys:
                self.signals.options_keys.append(opt)

        # 3. Pivot signals
        if (
            "#pivot" in self.full_text.lower()
            or "xpivot" in self.full_text.lower()
            or "xsearch" in self.full_text.lower()
            or re.search(r"\bPIVOT\s*\(", self.full_text, re.IGNORECASE)
        ):
            self.signals.uses_pivot_pattern = True
            self.zones_detected_set.add("pivot")

        # 4. Classify calls
        calls_direct: list[DirectCall] = []
        calls_business: list[DirectCall] = []

        for call_name in sorted(self.calls_direct_set):
            kind = classify_object(call_name)
            d_call = DirectCall(name=call_name, kind=kind)
            calls_direct.append(d_call)
            if kind == "business":
                calls_business.append(d_call)

        # 5. Extract key variables (used >= 2 times or in WHERE/JOIN)
        var_matches = re.findall(r"(@[a-zA-Z0-9_]+)", self.full_text)
        var_counts: dict[str, int] = {}
        for v in var_matches:
            v_lower = v
            var_counts[v_lower] = var_counts.get(v_lower, 0) + 1

        variables_key = [v for v, count in sorted(var_counts.items(), key=lambda x: x[1], reverse=True) if count >= 2][:8]

        # 6. Zone detection from comments
        if re.search(r"--\s*(KEY|JOIN)", self.full_text, re.IGNORECASE):
            self.zones_detected_set.add("key_filter")
        if re.search(r"CREATE\s+(PROCEDURE|PROC|FUNCTION|VIEW)", self.full_text, re.IGNORECASE):
            self.zones_detected_set.add("header")
        if "WHILE" in self.full_text.upper():
            self.zones_detected_set.add("processing")
            self.signals.has_while = True
        if "CURSOR" in self.full_text.upper():
            self.zones_detected_set.add("cursor")
            self.signals.has_cursor = True

        # 7. Dynamic SQL detection (universal across heuristic & full mode)
        if (
            re.search(r"\bsp_executesql\b", self.full_text, re.IGNORECASE)
            or re.search(r"\bEXEC(?:UTE)?\s*\(", self.full_text, re.IGNORECASE)
            or re.search(r"\bSET\s+@q\s*=", self.full_text, re.IGNORECASE)
            or any(c.name.lower().endswith("sp_executesql") for c in calls_direct)
        ):
            self.signals.has_dynamic_sql = True

        # 8. Heuristic result sets if not populated by AST visitor
        if not self.result_sets:
            select_blocks = re.finditer(
                r"(?im)^\s*SELECT\s+(?!@)(DISTINCT\s+|TOP\s+\d+\s+)?(.+?)\s+FROM\s+([#a-zA-Z0-9_\$]+)",
                self.full_text,
            )
            for m in select_blocks:
                cols_str = m.group(2).strip()
                from_table = m.group(3).strip()
                if " INTO " in cols_str.upper() or "CURSOR" in from_table.upper():
                    continue

                cols_raw = cols_str.split(",")
                cols: list[str] = []
                for c_raw in cols_raw:
                    c_str = c_raw.strip()
                    if " AS " in c_str.upper():
                        c_clean = c_str.split("AS")[-1].strip(" []\"'")
                    elif "." in c_str:
                        c_clean = c_str.split(".")[-1].strip(" []\"'")
                    else:
                        c_clean = c_str.strip(" []\"'")
                    if c_clean and re.match(r"^[a-zA-Z0-9_#$]+$", c_clean) and not c_clean.startswith("@"):
                        if c_clean.lower() not in [x.lower() for x in cols]:
                            cols.append(c_clean)

                ordinal = len(self.result_sets) + 1
                if ordinal <= 5:
                    if "@stt_rec" in self.full_text.lower():
                        if ordinal == 1:
                            rs_hint = "master"
                        elif ordinal == 2:
                            rs_hint = "detail"
                        elif any(k in from_table.lower() or k in cols_str.lower() for k in ["duyet", "sign", "signature", "pivot", "cap"]):
                            rs_hint = "signature"
                        else:
                            rs_hint = f"RS{ordinal}"
                    else:
                        rs_hint = "listing" if ordinal == 1 else f"RS{ordinal}"

                    self.result_sets.append(
                        ResultSetHint(
                            ordinal=ordinal,
                            hint=rs_hint,
                            confidence="medium" if len(cols) >= 2 else "low",
                            columns_hint=cols[:30],
                        )
                    )
                    self.zones_detected_set.add("result_set")

        snippet_index = self._compute_snippet_index()
        logic_hints = self._compute_logic_hints()

        return ObjectSummary(
            params=self.params,
            calls_direct=calls_direct,
            calls_business=calls_business,
            tables_read=sorted(list(self.tables_read_set)),
            tables_write=sorted(list(self.tables_write_set)),
            temp_tables=sorted(list(self.temp_tables_set)),
            variables_key=variables_key,
            result_sets=self.result_sets,
            signals=self.signals,
            param_effects=[],  # Will be populated by param_effects detector
            zones_detected=sorted(list(self.zones_detected_set)),
            snippet_index=snippet_index,
            logic_hints=logic_hints,
        )

