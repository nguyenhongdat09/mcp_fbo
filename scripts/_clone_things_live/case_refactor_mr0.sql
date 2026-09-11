USE [VLOTUS_SP228_A]
GO

-- clone_things type=1: dbo.zc_sctnt | SQL_STORED_PROCEDURE | paste-for-edit | from source
ALTER PROCEDURE [dbo].[zc_sctnt]
	@ngay_ct1 SMALLDATETIME,
	@ngay_ct2 SMALLDATETIME,
	@ma_ku VARCHAR(4000),
	@tk VARCHAR(33),
	@ma_kh VARCHAR(4000),
	@ma_cn_ql VARCHAR(4000),
	@mau_bc CHAR(2),
	@Language CHAR(1),
	@UserID INT,
	@Admin BIT
	--DATNH
AS
BEGIN
	SET NOCOUNT ON
	SET ANSI_NULLS OFF

	-- Struct
	DECLARE @Key NVARCHAR(MAX), @q NVARCHAR(MAX), @WhereBal NVARCHAR(4000)
		, @UnitList VARCHAR(8000), @UnitKey NVARCHAR(4000), @AccFilter NVARCHAR(512)
		, @name NVARCHAR(256) = '', @code VARCHAR(256) = ''
		, @num NUMERIC(19, 4) = 0, @num_int INT = 0, @date SMALLDATETIME = NULL
		, @sysorder INT = 5, @sysprint INT = 1, @systotal INT = 1
		, @s_total NVARCHAR(1024), @o VARCHAR(1024)

	SELECT TOP 0 a.ma_dvcs, a.ma_cn_ql, a.ma_phap_nhan
		INTO #dvcs
			FROM dmdvcs a

	SELECT TOP 0 a.ma_ku, a.tk, a.ma_kh, a.ngay_ku1, a.tien, a.tien_nt, a.ds_dvcs
			, a.ky_tinh_thue, a.ky_thue, a.nam, a.han_nop_thue
		INTO #ku
			FROM dmku a

	SELECT TOP 0 @code AS ma_ku, @code AS ma_dvcs
		INTO #ku_map
			FROM dmku a

	SELECT TOP 0 a.tk, a.ma_ku, a.du_no00 AS du_no, a.du_co00 AS du_co
			, a.du_no_nt00 AS du_no_nt, a.du_co_nt00 AS du_co_nt
		INTO #b
			FROM cdku a

	SELECT TOP 0 @code AS ma_ku, @code AS tk, @code AS ma_dvcs
			, @date AS ngay_ct, @code AS so_ct, @code AS stt_rec
			, @num AS ps_no, @num AS ps_no_nt
		INTO #ps_no
			FROM r00$000000 a

	SELECT TOP 0 @sysorder AS sysorder, @sysprint AS sysprint, @systotal AS systotal
			, @num_int AS stt, @code AS ma_phap_nhan, @code AS ma_cn_ql, @name AS ten_cn_ql
			, @code AS tk, @code AS ma_ku
			, @num AS ky_tinh_thue, @num AS ky_thue, @num AS nam, @date AS han_nop_thue
			, @num AS so_thue_phai_nop, @date AS ngay_nop, @code AS so_ct
			, @num AS so_da_nop, @num AS so_con_phai_nop
			, @num AS so_thue_phai_nop_nt, @num AS so_da_nop_nt, @num AS so_con_phai_nop_nt
			, @num_int AS is_first, @num_int AS is_last
		INTO #report
			FROM dmku a

	-- Key & Join
	SELECT @Key = '1 = 1', @UnitList = '', @UnitKey = NULL, @WhereBal = ''
	SELECT @AccFilter = CASE WHEN ISNULL(@tk, '') <> ''
			THEN dbo.FastBusiness$Function$System$GetAccountFilter('a.tk', 'like', RTRIM(REPLACE(@tk, '''', '''''')))
			ELSE '1 = 1' END

	IF ISNULL(@ma_cn_ql, '') <> ''
		INSERT INTO #dvcs (ma_dvcs, ma_cn_ql, ma_phap_nhan)
			SELECT a.ma_dvcs, a.ma_cn_ql, a.ma_phap_nhan
				FROM dmdvcs a
				WHERE a.status = '1' AND dbo.ff_Inlist_(a.ma_cn_ql, @ma_cn_ql) = 1
	ELSE
		INSERT INTO #dvcs (ma_dvcs, ma_cn_ql, ma_phap_nhan)
			SELECT a.ma_dvcs, a.ma_cn_ql, a.ma_phap_nhan
				FROM dmdvcs a
				WHERE a.status = '1' AND ISNULL(a.ma_cn_ql, '') <> ''

	SELECT @UnitList = STUFF((
			SELECT ',' + RTRIM(ma_dvcs) FROM #dvcs FOR XML PATH('')
		), 1, 1, '')
	SELECT @UnitKey = dbo.FastBusiness$Function$System$GetUnitFilter('ma_dvcs', @UnitList, @UserID, @Admin)
	IF @UnitKey IS NOT NULL BEGIN
		SET @q = N'DELETE #dvcs WHERE NOT (' + @UnitKey + N')'
		EXEC sp_executesql @q
	END

	SET @q = N'
		INSERT INTO #ku (ma_ku, tk, ma_kh, ngay_ku1, tien, tien_nt, ds_dvcs
				, ky_tinh_thue, ky_thue, nam, han_nop_thue)
			SELECT a.ma_ku, a.tk, a.ma_kh, a.ngay_ku1
					, ISNULL(a.tien, 0), ISNULL(a.tien_nt, 0), a.ds_dvcs
					, a.ky_tinh_thue, a.ky_thue, a.nam, a.han_nop_thue
				FROM dmku a WITH (NOLOCK)
				WHERE a.loai_ku = 3 AND ISNULL(a.status, ''1'') <> ''0'''
	IF ISNULL(@ma_ku, '') <> ''
		SET @q = @q + N' AND dbo.ff_Inlist_(a.ma_ku, ''' + REPLACE(RTRIM(@ma_ku), '''', '''''') + N''') = 1'
	IF ISNULL(@tk, '') <> ''
		SET @q = @q + N' AND ' + REPLACE(@AccFilter, 'a.tk', 'a.tk')
	IF ISNULL(@ma_kh, '') <> ''
		SET @q = @q + N' AND dbo.ff_Inlist_(a.ma_kh, ''' + REPLACE(RTRIM(@ma_kh), '''', '''''') + N''') = 1'
	EXEC sp_executesql @q

	INSERT INTO #ku_map (ma_ku, ma_dvcs)
		SELECT k.ma_ku, RTRIM(s.val)
			FROM #ku k
				CROSS APPLY dbo.fsd_StringToTable(ISNULL(k.ds_dvcs, '')) s
				JOIN #dvcs d ON d.ma_dvcs = RTRIM(s.val)
			WHERE RTRIM(ISNULL(s.val, '')) <> ''

	INSERT INTO #ku_map (ma_ku, ma_dvcs)
		SELECT k.ma_ku, MIN(c.ma_dvcs)
			FROM #ku k JOIN cdku c ON c.ma_ku = k.ma_ku AND c.nam = YEAR(@ngay_ct1)
						JOIN #dvcs d ON d.ma_dvcs = c.ma_dvcs
			WHERE NOT EXISTS (SELECT 1 FROM #ku_map m WHERE m.ma_ku = k.ma_ku)
			GROUP BY k.ma_ku

	DECLARE @ma_dvcs0 VARCHAR(8)
	SELECT @ma_dvcs0 = MIN(ma_dvcs) FROM #dvcs
	IF @ma_dvcs0 IS NOT NULL
		INSERT INTO #ku_map (ma_ku, ma_dvcs)
			SELECT k.ma_ku, @ma_dvcs0
				FROM #ku k
				WHERE NOT EXISTS (SELECT 1 FROM #ku_map m WHERE m.ma_ku = k.ma_ku)

	SELECT @WhereBal = 'EXISTS(SELECT 1 FROM #ku z WHERE z.ma_ku = a.ma_ku)'
			+ ' AND EXISTS(SELECT 1 FROM #dvcs d WHERE d.ma_dvcs = a.ma_dvcs)'

	-- Data
	INSERT INTO #b (tk, ma_ku, du_no, du_co, du_no_nt, du_co_nt)
		EXEC dbo.FastBusiness$Balance$BContract
			@ngay_ct1, NULL, @tk, '', '3', 1, 2, @UserID, @Admin, '', @WhereBal

	DELETE b FROM #b b
		WHERE NOT EXISTS (SELECT 1 FROM #ku k WHERE k.ma_ku = b.ma_ku)

	SELECT @Key = 'a.status = ''1'' AND a.ps_no <> 0 AND ' + @AccFilter
			+ ' AND EXISTS(SELECT 1 FROM #ku z WHERE z.ma_ku = a.ma_ku)'
			+ ' AND EXISTS(SELECT 1 FROM #dvcs d WHERE d.ma_dvcs = a.ma_dvcs)'
	SELECT @Key = dbo.FastBusiness$Function$System$GetCheckKey(@Key)

	SET @q = N'
		INSERT INTO #ps_no (ma_ku, tk, ma_dvcs, ngay_ct, so_ct, stt_rec, ps_no, ps_no_nt)
			SELECT a.ma_ku, a.tk, a.ma_dvcs, a.ngay_ct, a.so_ct, a.stt_rec
					, a.ps_no, ISNULL(a.ps_no_nt, 0)
				FROM r00$%Partition a WITH (NOLOCK)
				WHERE %[' + @Key + ']%'
	EXEC FastBusiness$Partition$Execute @q, NULL, 'a.ngay_ct', @ngay_ct1, @ngay_ct2, @UserID, @Admin

	-- Processing Data
	;WITH c_one AS (
		SELECT ma_ku, MIN(ma_dvcs) AS ma_dvcs FROM #ku_map GROUP BY ma_ku
	), c_ku AS (
		SELECT d.ma_phap_nhan, d.ma_cn_ql, k.tk, k.ma_ku
				, k.tien, k.tien_nt, k.ngay_ku1
				, k.ky_tinh_thue, k.ky_thue, k.nam, k.han_nop_thue
				, ISNULL(b.du_co, 0) AS phai_nop_dk, ISNULL(b.du_co_nt, 0) AS phai_nop_dk_nt
				, CASE WHEN k.ngay_ku1 BETWEEN @ngay_ct1 AND @ngay_ct2 THEN k.tien ELSE 0 END AS phai_nop_tk
				, CASE WHEN k.ngay_ku1 BETWEEN @ngay_ct1 AND @ngay_ct2 THEN k.tien_nt ELSE 0 END AS phai_nop_tk_nt
			FROM #ku k JOIN c_one m ON m.ma_ku = k.ma_ku
						JOIN #dvcs d ON d.ma_dvcs = m.ma_dvcs
						LEFT JOIN #b b ON b.ma_ku = k.ma_ku AND b.tk = k.tk
		WHERE ISNULL(b.du_co, 0) <> 0 OR ISNULL(b.du_co_nt, 0) <> 0
			OR (k.ngay_ku1 BETWEEN @ngay_ct1 AND @ngay_ct2)
	), c_ps AS (
		SELECT k.ma_phap_nhan, k.ma_cn_ql, k.ma_ku, k.tk
				, p.ngay_ct, p.so_ct, p.stt_rec, p.ps_no, p.ps_no_nt
			FROM c_ku k JOIN #ps_no p ON p.ma_ku = k.ma_ku
	), c_detail AS (
		SELECT k.ma_phap_nhan, k.ma_cn_ql, k.tk, k.ma_ku
				, k.ky_tinh_thue, k.ky_thue, k.nam, k.han_nop_thue
				, k.tien AS so_thue_phai_nop, k.tien_nt AS so_thue_phai_nop_nt
				, p.ngay_ct AS ngay_nop, p.so_ct, p.stt_rec
				, ISNULL(p.ps_no, 0) AS so_da_nop, ISNULL(p.ps_no_nt, 0) AS so_da_nop_nt
				, k.phai_nop_dk, k.phai_nop_dk_nt, k.phai_nop_tk, k.phai_nop_tk_nt
				, CASE WHEN p.ma_ku IS NULL THEN 1 ELSE 0 END AS is_blank
			FROM c_ku k LEFT JOIN c_ps p ON p.ma_ku = k.ma_ku AND p.ma_phap_nhan = k.ma_phap_nhan AND p.ma_cn_ql = k.ma_cn_ql
	), c_run AS (
		SELECT d.*
				, SUM(CASE WHEN d.is_blank = 1 THEN 0 ELSE d.so_da_nop END)
					OVER (PARTITION BY d.ma_ku ORDER BY d.is_blank, d.ngay_nop, d.so_ct, d.stt_rec
						ROWS UNBOUNDED PRECEDING) AS lk_da_nop
				, SUM(CASE WHEN d.is_blank = 1 THEN 0 ELSE d.so_da_nop_nt END)
					OVER (PARTITION BY d.ma_ku ORDER BY d.is_blank, d.ngay_nop, d.so_ct, d.stt_rec
						ROWS UNBOUNDED PRECEDING) AS lk_da_nop_nt
				, ROW_NUMBER() OVER (PARTITION BY d.ma_ku ORDER BY d.is_blank, d.ngay_nop, d.so_ct, d.stt_rec) AS rn
				, COUNT(1) OVER (PARTITION BY d.ma_ku) AS cnt
			FROM c_detail d
	)
	INSERT INTO #report (sysorder, sysprint, systotal, stt, ma_phap_nhan, ma_cn_ql, ten_cn_ql, tk, ma_ku
			, ky_tinh_thue, ky_thue, nam, han_nop_thue
			, so_thue_phai_nop, ngay_nop, so_ct, so_da_nop, so_con_phai_nop
			, so_thue_phai_nop_nt, so_da_nop_nt, so_con_phai_nop_nt, is_first, is_last)
		SELECT 5, 1, 1, 0, r.ma_phap_nhan, r.ma_cn_ql
				, CASE WHEN @Language = 'V' THEN cn.ten_cn_ql ELSE cn.ten_cn_ql2 END
				, r.tk, r.ma_ku
				, r.ky_tinh_thue, r.ky_thue, r.nam, r.han_nop_thue
				, r.so_thue_phai_nop
				, CASE WHEN r.is_blank = 1 THEN NULL ELSE r.ngay_nop END
				, CASE WHEN r.is_blank = 1 THEN NULL ELSE r.so_ct END
				, CASE WHEN r.is_blank = 1 THEN NULL ELSE r.so_da_nop END
				, r.phai_nop_dk + r.phai_nop_tk - r.lk_da_nop
				, r.so_thue_phai_nop_nt
				, CASE WHEN r.is_blank = 1 THEN NULL ELSE r.so_da_nop_nt END
				, r.phai_nop_dk_nt + r.phai_nop_tk_nt - r.lk_da_nop_nt
				, CASE WHEN r.rn = 1 THEN 1 ELSE 0 END
				, CASE WHEN r.rn = r.cnt THEN 1 ELSE 0 END
			FROM c_run r LEFT JOIN zcdmcnql cn ON cn.ma_cn_ql = r.ma_cn_ql

	SELECT @o = 'ma_phap_nhan, ma_cn_ql, tk, ma_ku, ngay_nop, so_ct'
	EXEC FastBusiness$System$UpdateOrderField '', @o, '#report', 'stt', ''

	SELECT @s_total = CASE WHEN @Language = 'V' THEN cname ELSE cname2 END
		FROM reports WHERE ccode = 'Total'

	INSERT INTO #report (sysorder, sysprint, systotal, ten_cn_ql
			, so_thue_phai_nop, so_da_nop, so_con_phai_nop
			, so_thue_phai_nop_nt, so_da_nop_nt, so_con_phai_nop_nt)
		SELECT 0, 0, 0, @s_total
				, SUM(CASE WHEN is_first = 1 THEN ISNULL(so_thue_phai_nop, 0) ELSE 0 END)
				, SUM(ISNULL(so_da_nop, 0))
				, SUM(CASE WHEN is_last = 1 THEN ISNULL(so_con_phai_nop, 0) ELSE 0 END)
				, SUM(CASE WHEN is_first = 1 THEN ISNULL(so_thue_phai_nop_nt, 0) ELSE 0 END)
				, SUM(ISNULL(so_da_nop_nt, 0))
				, SUM(CASE WHEN is_last = 1 THEN ISNULL(so_con_phai_nop_nt, 0) ELSE 0 END)
			FROM #report
			WHERE systotal = 1
	INSERT INTO #report (sysorder, sysprint, systotal) VALUES (1, 0, 0)

	SELECT sysorder, sysprint, systotal, stt, ma_phap_nhan, ma_cn_ql, ten_cn_ql, tk, ma_ku
			, ky_tinh_thue, ky_thue, nam, han_nop_thue
			, so_thue_phai_nop_nt, ngay_nop, so_ct, so_da_nop_nt, so_con_phai_nop_nt
			, so_thue_phai_nop, so_da_nop, so_con_phai_nop
		FROM #report
		ORDER BY sysorder, stt

	SET ANSI_NULLS ON
	SET NOCOUNT OFF
END
GO

USE [VLOTUS_SP228_S]
GO
