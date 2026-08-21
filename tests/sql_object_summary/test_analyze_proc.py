"""Unit tests for sql_object_summary.analyze without database connection."""

import pytest
from sql_object_summary import analyze_definition, result_to_dict

FIXTURE_INTEREST_PROC = """
CREATE PROCEDURE dbo.rs_rptInterestDetailedByLoanContract
    @LoanFrom SMALLDATETIME,
    @LoanTo SMALLDATETIME,
    @ma_dvcs VARCHAR(8000),
    @ma_kh VARCHAR(33),
    @Status CHAR(1) = '0',
    @ContractType CHAR(1) = '1',
    @Language CHAR(1) = 'V',
    @UserID INT,
    @Admin BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    -- Options
    SELECT @days = CASE WHEN val = 1 THEN 30 ELSE (SELECT val FROM options WHERE name = 'm_ngay_ls_nam') END 
    FROM options WHERE name = 'm_kieu_ls';

    -- KEY & JOIN
    EXEC FastBusiness$Partition$Execute @name='r00$';
    EXEC FastBusiness$Balance$BContract @id=@ma_kh;

    SELECT a.ma_ku, a.so_ku, b.ten_kh, a.ngay_tu, a.ngay_den, a.so_du, a.tl_th, a.tl_qh
    INTO #report
    FROM dmku a 
    JOIN ctdmku b ON a.ma_ku = b.ma_ku
    LEFT JOIN cdku c ON a.ma_ku = c.ma_ku;

    IF @Status = '1'
    BEGIN
        UPDATE #report SET ngay_tu = DATEADD(day, 1, ngay_tu);
    END

    DECLARE cur CURSOR FOR SELECT ma_ku FROM #report;

    SELECT ma_ku, so_ku, ten_kh, ngay_tu, ngay_den, so_du, tl_th, tl_qh FROM #report;
END
"""

FIXTURE_PIVOT_PROC = """
CREATE PROCEDURE dbo.zc_bcthlv
    @nam_tu INT,
    @nam_den INT,
    @mau_bc CHAR(2) = '10'
AS
BEGIN
    EXEC FastBusiness$Partition$Execute @name='d91$';

    SELECT * INTO #lai_thang FROM d91$;
    SELECT * INTO #pivot FROM #lai_thang;

    IF @mau_bc = '10'
    BEGIN
        SELECT xpivot, gia_tri FROM #pivot;
    END

    SELECT ma_ku, xsearch FROM #pivot;
END
"""


def test_analyze_interest_proc():
    result = analyze_definition(FIXTURE_INTEREST_PROC, object_name="dbo.rs_rptInterestDetailedByLoanContract")
    assert result.success is True
    assert result.object == "dbo.rs_rptInterestDetailedByLoanContract"
    assert result.object_type == "PROCEDURE"
    assert result.spec_version == "1.0"
    assert result.parse_status == "ok"

    summary = result.summary
    assert len(summary.params) == 9
    param_names = [p.name for p in summary.params]
    assert "@LoanFrom" in param_names
    assert "@Status" in param_names

    # Calls
    call_names = [c.name for c in summary.calls_direct]
    assert "dbo.FastBusiness$Partition$Execute" in call_names
    assert "dbo.FastBusiness$Balance$BContract" in call_names

    # Tables: clean, no aliases (a, b, c), no temp tables (#report)
    assert "dmku" in summary.tables_read
    assert "ctdmku" in summary.tables_read
    assert "cdku" in summary.tables_read
    assert "options" in summary.tables_read
    assert "a" not in summary.tables_read
    assert "b" not in summary.tables_read
    assert "c" not in summary.tables_read
    assert "cur" not in summary.tables_read
    assert "#report" not in summary.tables_read
    assert "#report" in summary.temp_tables

    # Result sets: exactly 1 RS (the final select, no variable assignments, no INTO)
    assert len(summary.result_sets) == 1
    rs1 = summary.result_sets[0]
    assert rs1.ordinal == 1
    assert "ma_ku" in rs1.columns_hint
    assert "tl_th" in rs1.columns_hint
    assert "@days" not in rs1.columns_hint

    # Snippet Index
    assert "header" in summary.snippet_index
    assert "cursor" in summary.snippet_index
    assert "result_set" in summary.snippet_index
    assert summary.snippet_index["header"][0] == 1

    # Logic Hints
    assert summary.logic_hints.get("interest_related") is True
    assert "tl_th" in summary.logic_hints.get("keywords_suggested", [])

    # Signals
    assert summary.signals.uses_partition_execute is True
    assert summary.signals.uses_balance_helper is True
    assert summary.signals.has_cursor is True
    assert "m_kieu_ls" in summary.signals.options_keys
    assert "m_ngay_ls_nam" in summary.signals.options_keys

    # Param effects: status effect present, low confidence excluded
    status_effects = [pe for pe in summary.param_effects if pe.param == "@Status"]
    assert len(status_effects) > 0
    assert status_effects[0].role == "branching"
    assert status_effects[0].confidence in ("medium", "high")

    # Formatter output
    d = result_to_dict(result)
    assert d["spec_version"] == "1.0"
    assert "summary" in d
    assert "signals" in d["summary"]
    assert "snippet_index" in d["summary"]
    assert "logic_hints" in d["summary"]
    assert len(d["summary"]["result_sets"]) == 1


def test_analyze_pivot_proc():
    result = analyze_definition(FIXTURE_PIVOT_PROC, object_name="dbo.zc_bcthlv")
    assert result.success is True
    summary = result.summary
    assert summary.signals.uses_pivot_pattern is True
    assert "#pivot" in summary.temp_tables
    assert "#lai_thang" in summary.temp_tables
    assert "d91$" in summary.tables_read


def test_sp_executesql_system_classification():
    sql = """
    CREATE PROCEDURE dbo.test_dynamic
        @q NVARCHAR(MAX)
    AS
    BEGIN
        EXEC sp_executesql @q;
    END
    """
    result = analyze_definition(sql, object_name="dbo.test_dynamic")
    assert result.success is True
    summary = result.summary
    calls = summary.calls_direct
    assert len(calls) == 1
    assert calls[0].name == "dbo.sp_executesql"
    assert calls[0].kind == "system"
    assert len(summary.calls_business) == 0
    assert summary.signals.has_dynamic_sql is True


def test_heuristic_dynamic_sql_and_noise_filtering():
    """Verify P0, P1, P2 in heuristic mode (line_count > 150):
    P0: has_dynamic_sql is True when sp_executesql is present.
    P1: 'set' is not in tables_write.
    P2: 'nvarchar' / data types are not in tables_read.
    """
    # Create > 150 lines definition to trigger heuristic parser
    lines = [
        "CREATE PROCEDURE dbo.rs_rptStockSummaryByLotItem",
        "    @ma_vt VARCHAR(33),",
        "    @ma_kho VARCHAR(33)",
        "AS",
        "BEGIN",
        "    SET NOCOUNT ON;",
        "    -- Setup temporary tables",
        "    SELECT * INTO #tmp FROM d91$000000;",
        "    UPDATE #tmp SET ma_vt = 'ITEM';",
        "    SELECT * FROM dbo.split(@ma_vt, ',') AS nvarchar;",
        "    EXEC sp_executesql N'SELECT 1';",
    ]
    # Pad to 160 lines
    for i in range(150):
        lines.append(f"    -- Padding line {i} to exceed 150 line threshold")
    lines.append("    SELECT ma_vt, ma_kho FROM #tmp;")
    lines.append("END")

    sql = "\n".join(lines)
    result = analyze_definition(sql, object_name="dbo.rs_rptStockSummaryByLotItem")
    assert result.success is True
    assert result.parse_status in ("ok", "partial")
    assert result.line_count > 150

    summary = result.summary
    # P0: Dynamic SQL flag must be True
    assert summary.signals.has_dynamic_sql is True

    # P1: 'set' must NOT be in tables_write
    assert "set" not in summary.tables_write

    # P2: 'nvarchar', 'split', keywords must NOT contaminate tables_read
    assert "nvarchar" not in summary.tables_read
    assert "where" not in summary.tables_read
    assert "from" not in summary.tables_read
    assert "d91$" in summary.tables_read
    assert "#tmp" in summary.temp_tables


def test_bctc_form_proc_analysis():
    """Verify Doc 03: BCTC form report (zc_bckqkdtda mock):
    1. '3' is not in tables_read (isdigit filter).
    2. 'res' is not in tables_write (alias noise filter).
    3. logic_hints.bctc_form_related is True.
    4. keywords_suggested has @form, @mau_bc, bcnsky, glns.
    5. param_effects contains @form, @mau_bc with high confidence.
    """
    lines = [
        "CREATE PROCEDURE dbo.zc_bckqkdtda",
        "    @thang_tu INT,",
        "    @nam_tu INT,",
        "    @form CHAR(1),",
        "    @mau_bc CHAR(1),",
        "    @ma_vv VARCHAR(33)",
        "AS",
        "BEGIN",
        "    SET NOCOUNT ON;",
        "    SELECT TOP 3 * FROM bcnsky WHERE form = @form;",
        "    SELECT * FROM glns WHERE mau_bc = @mau_bc;",
        "    SELECT * INTO #result FROM dmctns;",
        "    UPDATE res SET ten = 'X' FROM #result res;",
        "    EXEC dbo.FastBusiness$Report$CheckFormula;",
        "    EXEC dbo.fs20_JobCalcXStruct;",
    ]
    # Pad to 160 lines to trigger heuristic mode
    for i in range(150):
        lines.append(f"    -- padding line {i}")
    lines.append("    SELECT * FROM #result;")
    lines.append("END")

    sql = "\n".join(lines)
    result = analyze_definition(sql, object_name="dbo.zc_bckqkdtda")
    assert result.success is True
    summary = result.summary

    # P0: Table noise filtering
    assert "3" not in summary.tables_read
    assert "bcnsky" in summary.tables_read
    assert "glns" in summary.tables_read
    assert "dmctns" in summary.tables_read
    assert "res" not in summary.tables_write
    assert len(summary.tables_write) == 0

    # P1: Domain hints
    assert summary.logic_hints.get("bctc_form_related") is True
    kw = summary.logic_hints.get("keywords_suggested", [])
    assert "@form" in kw
    assert "@mau_bc" in kw
    assert "bcnsky" in kw

    # P1: Param effects
    form_effects = [e for e in summary.param_effects if e.param == "@form"]
    assert len(form_effects) > 0
    assert form_effects[0].confidence == "high"

    mau_effects = [e for e in summary.param_effects if e.param == "@mau_bc"]
    assert len(mau_effects) > 0
    assert mau_effects[0].confidence == "high"


def test_report_generic_and_custom_listing_domains():
    """Verify Doc 05: Generic report and custom listing domain detection & keyword extraction."""
    # 1. Generic report test (rs_* standard)
    sql_generic = """
    CREATE PROCEDURE dbo.rs_rptGeneralLedger
        @DateFrom SMALLDATETIME,
        @DateTo SMALLDATETIME,
        @Customer VARCHAR(33),
        @Language CHAR(1),
        @Admin BIT
    AS
    BEGIN
        SET NOCOUNT ON;
        SELECT * INTO #report FROM c00$000000 WHERE ngay_ct BETWEEN @DateFrom AND @DateTo;
        EXEC dbo.FastBusiness$Partition$Execute N'SELECT 1';
        SELECT * FROM #report;
    END
    """
    res_generic = analyze_definition(sql_generic, object_name="dbo.rs_rptGeneralLedger")
    assert res_generic.success is True
    summary_g = res_generic.summary
    assert summary_g.logic_hints.get("report_generic") is True
    kw_g = summary_g.logic_hints.get("keywords_suggested", [])
    assert "@DateFrom" in kw_g
    assert "@DateTo" in kw_g
    assert "#report" in kw_g
    assert "FastBusiness$Partition$Execute" in kw_g

    # 2. Custom listing test (zc_* custom)
    sql_custom = """
    CREATE PROCEDURE dbo.zc_ttdmtb
        @loai CHAR(1),
        @tao_yn CHAR(1),
        @Language CHAR(1),
        @Admin BIT,
        @UserID INT
    AS
    BEGIN
        SET NOCOUNT ON;
        IF @Admin = 1 PRINT 'admin';
        IF @tao_yn = '1'
        BEGIN
            SELECT * INTO #$da_tao FROM zcdmtb0 WHERE loai = @loai;
        END
        SELECT * FROM #$da_tao;
    END
    """
    res_custom = analyze_definition(sql_custom, object_name="dbo.zc_ttdmtb")
    assert res_custom.success is True
    summary_c = res_custom.summary
    assert summary_c.logic_hints.get("custom_listing_related") is True
    kw_c = summary_c.logic_hints.get("keywords_suggested", [])
    assert "@tao_yn" in kw_c
    assert "@loai" in kw_c
    assert "#$da_tao" in kw_c
    assert "zcdmtb0" in kw_c

    # Check that business params (@tao_yn, @loai) appear BEFORE infra params (@Admin, @Language, @UserID)
    param_names = [e.param for e in summary_c.param_effects]
    assert "@tao_yn" in param_names
    assert param_names.index("@tao_yn") < param_names.index("@Admin")


def test_universal_table_denylist_and_dynamic_sql_exec():
    """Verify Doc 05: Universal table denylist (sys, information_schema) and EXEC(@q) dynamic SQL."""
    sql = """
    CREATE PROCEDURE dbo.test_proc_dynamic
        @q NVARCHAR(MAX)
    AS
    BEGIN
        SET NOCOUNT ON;
        SELECT * FROM information_schema.tables;
        SELECT * FROM sys.sysobjects;
        SET @q = 'SELECT 1';
        EXEC(@q);
    END
    """
    res = analyze_definition(sql, object_name="dbo.test_proc_dynamic")
    assert res.success is True
    summary = res.summary
    assert "sysobjects" not in summary.tables_read


def test_custom_proc_action_vs_report():
    """Verify that zc_* customize procs distinguish between action/insert/update vs report/inquiry."""
    # 1. Action/insert procedure
    sql_action = """
    CREATE PROCEDURE dbo.zc_PostVoucher
        @stt_rec VARCHAR(33),
        @Action VARCHAR(10)
    AS
    BEGIN
        SET NOCOUNT ON;
        UPDATE d91$000000 SET status = '2' WHERE stt_rec = @stt_rec;
        INSERT INTO zcdmtb0 (stt_rec, ma_tb) VALUES (@stt_rec, 'TB01');
    END
    """
    res_act = analyze_definition(sql_action, object_name="dbo.zc_PostVoucher")
    assert res_act.success is True
    assert res_act.summary.logic_hints.get("custom_action_related") is True
    assert res_act.summary.logic_hints.get("custom_related") is True
    assert "Custom transaction/action" in res_act.summary.logic_hints.get("note", "")

    # 2. Report/inquiry procedure
    sql_report = """
    CREATE PROCEDURE dbo.zc_bc_DoanhThuTheoKhachHang
        @DateFrom SMALLDATETIME,
        @DateTo SMALLDATETIME,
        @ma_kh VARCHAR(33)
    AS
    BEGIN
        SET NOCOUNT ON;
        SELECT ma_kh, SUM(tien) AS tong_tien FROM m91$000000 WHERE ngay_ct BETWEEN @DateFrom AND @DateTo GROUP BY ma_kh;
    END
    """
    res_rpt = analyze_definition(sql_report, object_name="dbo.zc_bc_DoanhThuTheoKhachHang")
    assert res_rpt.success is True
    assert res_rpt.summary.logic_hints.get("custom_report_related") is True
    assert res_rpt.summary.logic_hints.get("custom_related") is True
    assert "inquiry" in res_rpt.summary.logic_hints.get("note", "").lower()


def test_rs_sales_report_is_report_generic_not_custom_listing():
    """rs_rpt* with dmkh + d91$ must NOT be custom_listing; it must be report_generic."""
    sql = """
    CREATE PROCEDURE dbo.rs_rptSalesByCustomer
        @DateFrom SMALLDATETIME,
        @DateTo SMALLDATETIME,
        @Customer VARCHAR(33)
    AS
    BEGIN
        SET NOCOUNT ON;
        SELECT a.* INTO #report FROM d91$000000 a JOIN m91$000000 b ON a.stt_rec = b.stt_rec
        JOIN dmkh k ON a.ma_kh = k.ma_kh;
        EXEC FastBusiness$Partition$Execute @q;
    END
    """
    res = analyze_definition(sql, object_name="dbo.rs_rptSalesByCustomer")
    assert res.success is True
    hints = res.summary.logic_hints
    assert hints.get("custom_listing_related") is not True
    assert hints.get("custom_report_related") is not True
    assert hints.get("report_generic") is True


def test_fs_post_is_post_related():
    res = analyze_definition("CREATE PROC dbo.fs_PostAdjustmentInventory AS SELECT 1",
                             object_name="dbo.fs_PostAdjustmentInventory")
    assert res.summary.logic_hints.get("post_related") is True


def test_apv_is_approval_related():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$APV$LoadApproval AS SELECT 1",
                             object_name="dbo.FastBusiness$APV$LoadApproval")
    assert res.summary.logic_hints.get("approval_related") is True


def test_afterupdate_is_lifecycle_not_post():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$Voucher$AfterUpdate$PO AS SELECT 1",
                             object_name="dbo.FastBusiness$Voucher$AfterUpdate$PO")
    assert res.summary.logic_hints.get("voucher_lifecycle_related") is True
    assert res.summary.logic_hints.get("post_related") is not True


def test_inputinvoice_not_einvoice():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$InputInvoice$UpdateStatus AS SELECT 1",
                             object_name="dbo.FastBusiness$InputInvoice$UpdateStatus")
    assert res.summary.logic_hints.get("input_invoice_related") is True
    assert res.summary.logic_hints.get("einvoice_related") is not True


def test_einvoice_publish():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$EInvoice$Publish AS SELECT 1",
                             object_name="dbo.FastBusiness$EInvoice$Publish")
    assert res.summary.logic_hints.get("einvoice_related") is True


def test_discount():
    res = analyze_definition("CREATE PROC dbo.ds_PostDiscount AS SELECT 1",
                             object_name="dbo.ds_PostDiscount")
    assert res.summary.logic_hints.get("discount_related") is True
    assert res.summary.logic_hints.get("post_related") is not True


def test_balance_account():
    res = analyze_definition("CREATE PROC dbo.FastBusiness$Balance$Account AS SELECT 1",
                             object_name="dbo.FastBusiness$Balance$Account")
    assert res.summary.logic_hints.get("balance_related") is True


def test_zc_dxtlccdc_is_custom_report_not_action():
    sql = """
    CREATE PROCEDURE dbo.zc_dxtlccdc
        @stt_rec VARCHAR(33),
        @user_id INT
    AS
    BEGIN
        SET NOCOUNT ON;
        -- Options check
        SELECT a.val FROM options a WHERE name = 'zc_7_cd_tl';

        -- Extract master and detail
        SELECT a.so_ct, a.nguoi_de_xuat, a.ly_do_thanh_ly INTO #m89 FROM m89$000000 a WHERE a.stt_rec = @stt_rec;
        SELECT b.ma_tb, b.ten_tb, b.so_luong INTO #d89 FROM d89$000000 b WHERE b.stt_rec = @stt_rec;

        ;WITH ranked AS (
            SELECT nguoi_duyet, cap FROM zcdmsignature WHERE stt_rec = @stt_rec
        ), max_reset AS (
            SELECT * FROM ranked
        )
        SELECT * INTO #cap_duyet FROM max_reset;

        -- Result Set 1: Master
        SELECT so_ct, nguoi_de_xuat, ly_do_thanh_ly FROM #m89;

        -- Result Set 2: Detail
        SELECT ma_tb, ten_tb, so_luong FROM #d89;

        -- Result Set 3: Signature with PIVOT
        SELECT * FROM (SELECT nguoi_duyet, cap FROM #cap_duyet) src
        PIVOT (MAX(nguoi_duyet) FOR cap IN ([1], [2], [3])) pvt;
    END
    """
    res = analyze_definition(sql, object_name="dbo.zc_dxtlccdc")
    assert res.success is True
    summary = res.summary
    hints = summary.logic_hints

    # 1. Custom report domain (print/inquiry), NOT action
    assert hints.get("custom_report_related") is True
    assert hints.get("custom_action_related") is not True
    assert "print/inquiry" in hints.get("note", "").lower()

    # 2. CTE names filtered out from tables_read
    assert "ranked" not in summary.tables_read
    assert "max_reset" not in summary.tables_read
    assert "nguoi_duyet" not in summary.tables_read

    # 3. Partition collapsed
    assert "m89$000000" not in summary.tables_read
    assert "d89$000000" not in summary.tables_read
    assert "m89$" in summary.tables_read
    assert "d89$" in summary.tables_read

    # 4. Options and PIVOT detected
    assert "zc_7_cd_tl" in summary.signals.options_keys
    assert summary.signals.uses_pivot_pattern is True

    # 5. Result sets detected
    assert len(summary.result_sets) >= 2
    assert summary.result_sets[0].hint == "master"
    assert summary.result_sets[1].hint == "detail"

