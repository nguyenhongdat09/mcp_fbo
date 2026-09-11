-- clone_things: dbo.zc_sctnt | SQL_STORED_PROCEDURE | from source
IF OBJECT_ID(N'[dbo].[zc_sctnt]', N'P') IS NOT NULL
    DROP PROCEDURE [dbo].[zc_sctnt]
GO
CREATE PROCEDURE [dbo].[zc_sctnt]
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

-- clone_things: dbo.FastBusiness$Balance$BContract | SQL_STORED_PROCEDURE | from source
IF OBJECT_ID(N'[dbo].[FastBusiness$Balance$BContract]', N'P') IS NOT NULL
    DROP PROCEDURE [dbo].[FastBusiness$Balance$BContract]
GO
CREATE PROCEDURE [dbo].[FastBusiness$Balance$BContract]
	@Date SMALLDATETIME, 
	@Unit VARCHAR(1023),
	@Account VARCHAR(33),
	@BContract VARCHAR(33),
	@ContractType CHAR(1), -- 1 - Borrow, 2 - Lend
	@BalanceType TINYINT, -- 1 - Begining, 2 - Closing
	@ResultType TINYINT, -- 1 One Contract, 2 Multi Contract
	@UserID INT,
	@Admin BIT,
	@JoinClause NVARCHAR(4000) = N'',
	@WhereClause NVARCHAR(4000) = N''
AS
BEGIN
	SET NOCOUNT ON
	SET ANSI_NULLS OFF

	-- Declare
	DECLARE @Key NVARCHAR(4000), @UnitKey NVARCHAR(4000), @q NVARCHAR(4000), @DateFrom SMALLDATETIME
	SELECT @DateFrom = dbo.ff_GetStartDate(@Date)

	-- Struct
	SELECT TOP 0 tk, ma_ku, du_no00 AS du_no, du_co00 AS du_co, du_no_nt00 AS du_no_nt, du_co_nt00 AS du_co_nt INTO #t FROM cdku

	SELECT @Key = '', @UnitKey = NULL
	IF @Unit IS NOT NULL SET @UnitKey = dbo.FastBusiness$Function$System$GetUnitFilter('ma_dvcs', @Unit, @UserID, @Admin)
	IF @UnitKey IS NOT NULL SET @Key = @UnitKey
	IF @Account <> '' SET @Key = @Key + CASE WHEN @Key = '' THEN '' ELSE ' and ' END + dbo.FastBusiness$Function$System$GetAccountFilter('a.tk', 'like', @Account)
	IF @BContract <> '' SET @Key = @Key + CASE WHEN @Key = '' THEN '' ELSE ' and ' END + 'a.ma_ku like ''' + REPLACE(@BContract, '''', '''''') + '%'''

	-- Balance (year)
	SET @q = 'insert into #t select a.tk, a.ma_ku, sum(a.du_no00), sum(a.du_co00), sum(a.du_no_nt00), sum(a.du_co_nt00)'
	SET @q = @q + ' from cdku a with(nolock, index(nam_tk_ma_ku)) '
	IF @JoinClause <> '' SET @q = @q + @JoinClause
	SET @q = @q + ' where a.nam = ' + STR(YEAR(@Date), 4)
	SET @q = @q + CASE WHEN @Key = '' THEN '' ELSE ' and ' + @Key END
	IF @WhereClause <> '' SET @q = @q + ' and ' + @WhereClause
	SET @q = @q + ' group by a.tk, a.ma_ku'
	EXEC sp_executesql @q

	-- Arising
	IF @BalanceType = 1	SET @Date = @Date - 1

	SET @q = 'insert into #t select a.tk, a.ma_ku, sum(a.ps_no), sum(a.ps_co), sum(a.ps_no_nt), sum(a.ps_co_nt)'
	SET @q = @q + ' from r00$%Partition a with (nolock, index(tk)) '
	IF @JoinClause <> '' SET @q = @q + @JoinClause
	SET @q = @q + ' where %[a.status = ' + CHAR(39) + '1' + CHAR(39)
	SET @q = @q + CASE WHEN @Key <> '' THEN ' and ' + @Key ELSE '' END
	IF @WhereClause <> '' SET @q = @q + ' and ' + @WhereClause
	SET @q = @q + ']% group by a.tk, a.ma_ku'
	EXEC FastBusiness$Partition$Execute @q, NULL, 'ngay_ct', @DateFrom, @Date, @UserID, @Admin

	Result:
	IF @ResultType = 1 BEGIN
		SET @q = 'select isnull(sum(case when b.loai_ku = ''1'' then (a.du_co - a.du_no) else (a.du_no - a.du_co) end), 0) as du'
		SET @q = @q + ', isnull(sum(case when b.loai_ku = ''1'' then (a.du_co_nt - a.du_no_nt) else (a.du_no_nt - a.du_co_nt) end), 0) as du_nt'
		SET @q = @q + ' from #t a join dmku b on a.ma_ku = b.ma_ku and a.tk = b.tk'
	END ELSE BEGIN
		SET @q = 'select tk, ma_ku'
		SET @q = @q + ', case when sum(du_no - du_co) > 0 then sum(du_no - du_co) else 0 end as du_no'
		SET @q = @q + ', case when sum(du_co - du_no) > 0 then sum(du_co - du_no) else 0 end as du_co'
		SET @q = @q + ', case when sum(du_no_nt - du_co_nt) > 0 then sum(du_no_nt - du_co_nt) else 0 end as du_no_nt'
		SET @q = @q + ', case when sum(du_co_nt - du_no_nt) > 0 then sum(du_co_nt - du_no_nt) else 0 end as du_co_nt'
		SET @q = @q + ' from #t group by tk, ma_ku order by tk, ma_ku'
	END
	EXEC sp_executesql @q
	
	SET NOCOUNT OFF
	RETURN
END
GO

-- clone_things: dbo.FastBusiness$System$UpdateOrderField | SQL_STORED_PROCEDURE | from source
IF OBJECT_ID(N'[dbo].[FastBusiness$System$UpdateOrderField]', N'P') IS NOT NULL
    DROP PROCEDURE [dbo].[FastBusiness$System$UpdateOrderField]
GO
CREATE PROCEDURE [dbo].[FastBusiness$System$UpdateOrderField]
	@groupList VARCHAR(1024),
	@orderList VARCHAR(1024),
	@Table VARCHAR(128),
	@Field VARCHAR(128),
	@Key NVARCHAR(1024),
	@debugMode INT = 0
AS  
BEGIN
	SET NOCOUNT ON

	DECLARE @q NVARCHAR(4000), @i INT, @c VARCHAR(128), @s1 VARCHAR(1024), @s2 VARCHAR(1024), @s3 VARCHAR(1024)

	--
	SELECT @q = 'create index iOrder on ' + @Table + '(' + @orderList + ')'

	IF @debugMode > 0 PRINT @q
	IF @debugMode < 2 EXEC sp_executesql @q

	--
	IF @groupList = ''
		SET @q = 'declare @i int; update ' + @Table + ' set @i = case when @i is null then 1 else @i + 1 end, ' + @Field + ' = @i from ' + @Table + ' with(index(iOrder))'
	ELSE BEGIN
		SELECT @i = 1, @s1 = '', @s2 = '', @s3 = ''
		WHILE @i <= dbo.FastBusiness$Function$GetWordCount(@groupList, ',') BEGIN
			SELECT @c = RTRIM(dbo.FastBusiness$Function$GetWordNum(@groupList, @i, ','))
			SELECT @s1 = @s1 + ', @c' + RTRIM(@i) + ' varchar(128)', @s2 = @s2 + CASE WHEN @s2 = '' THEN '' ELSE ' and ' END + @c + ' = @c' + RTRIM(@i), @s3 = @s3 + ', @c' + RTRIM(@i) + ' = ' + @c


			SELECT @i = @i + 1
		END
		SELECT @q = 'declare @i int' + @s1 + '; update ' + @Table + ' set @i = case when ' + @s2 + ' then @i + 1 else 1 end, ' + @Field + ' = @i' + @s3 + ' from ' + @Table + ' with(index(iOrder))'
	END

	--
	IF @Key <> '' SET @q = @q + ' where ' + @Key
	SELECT @q = @q + ' option(maxdop 1)'

	IF @debugMode > 0 PRINT @q
	IF @debugMode < 2 EXEC sp_executesql @q

	SET NOCOUNT OFF
END
GO

-- clone_things: dbo.cdku | USER_TABLE | from source
IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[cdku]') AND type = N'U')
BEGIN
CREATE TABLE cdku(
	[nam] numeric(4,0) NOT NULL,
	[ma_dvcs] char(8) NOT NULL,
	[tk] char(16) NOT NULL,
	[ma_ku] char(16) NOT NULL,
	[du_no00] numeric(19,2) NOT NULL,
	[du_co00] numeric(19,2) NOT NULL,
	[du_no_nt00] numeric(19,2) NOT NULL,
	[du_co_nt00] numeric(19,2) NOT NULL,
	[dien_giai] nvarchar(432) NULL,
	[ma_nt] char(3) NULL,
	[ty_gia] numeric(24,12) NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL,
	[ma_td1] char(18) NULL,
	[ma_td2] char(16) NULL,
	[ma_td3] char(16) NULL,
	[sl_td1] numeric(19,4) NULL,
	[sl_td2] numeric(19,4) NULL,
	[sl_td3] numeric(19,4) NULL,
	[ngay_td1] smalldatetime NULL,
	[ngay_td2] smalldatetime NULL,
	[ngay_td3] smalldatetime NULL,
	[s1] char(16) NULL,
	[s2] char(16) NULL,
	[s3] char(16) NULL,
	[s4] numeric(19,4) NULL,
	[s5] numeric(19,4) NULL,
	[s6] numeric(19,4) NULL,
	[s7] smalldatetime NULL,
	[s8] smalldatetime NULL,
	[s9] smalldatetime NULL
)
ALTER TABLE cdku WITH NOCHECK ADD CONSTRAINT PK_cdku PRIMARY KEY CLUSTERED(ma_dvcs, ma_ku, nam, tk) ON [PRIMARY]

CREATE INDEX [nam] ON cdku(nam) ON [PRIMARY]
CREATE INDEX [ma_dvcs] ON cdku(ma_dvcs) ON [PRIMARY]
CREATE INDEX [tk] ON cdku(tk) ON [PRIMARY]
CREATE INDEX [ma_ku] ON cdku(ma_ku) ON [PRIMARY]
CREATE INDEX [nam_tk_ma_ku] ON cdku(nam, tk, ma_ku) ON [PRIMARY]

ALTER TABLE cdku ADD CONSTRAINT [DF_cdku_dien_giai]  DEFAULT ('') FOR dien_giai
END
GO

-- clone_things: dbo.dmdvcs | USER_TABLE | from source
IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[dmdvcs]') AND type = N'U')
BEGIN
CREATE TABLE dmdvcs(
	[ma_dvcs] char(8) NOT NULL,
	[ten_dvcs] nvarchar(128) NOT NULL,
	[ten_dvcs2] nvarchar(128) NOT NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL,
	[ma_td1] char(18) NULL,
	[ma_td2] char(16) NULL,
	[ma_td3] char(16) NULL,
	[sl_td1] numeric(19,4) NULL,
	[sl_td2] numeric(19,4) NULL,
	[sl_td3] numeric(19,4) NULL,
	[ngay_td1] smalldatetime NULL,
	[ngay_td2] smalldatetime NULL,
	[ngay_td3] smalldatetime NULL,
	[gc_td1] nchar(64) NULL,
	[gc_td2] nchar(64) NULL,
	[gc_td3] nchar(64) NULL,
	[s1] char(16) NULL,
	[s2] char(16) NULL,
	[s3] char(16) NULL,
	[s4] numeric(19,4) NULL,
	[s5] numeric(19,4) NULL,
	[s6] numeric(19,4) NULL,
	[s7] smalldatetime NULL,
	[s8] smalldatetime NULL,
	[s9] smalldatetime NULL,
	[id] int NULL,
	[ma_nh_pos] char(16) NULL,
	[ma_nh] char(16) NULL,
	[loai_cty] char(1) NULL,
	[ma_cn_ql] char(16) NULL,
	[nh_nha_hang] char(16) NULL,
	[ma_kh0] char(18) NULL,
	[ma_phap_nhan] char(16) NULL,
	[ma_kho0] char(18) NULL,
	[tk_thu_nb] char(16) NULL,
	[tk_tra_nb] char(16) NULL,
	[ma_kh_pn] char(18) NULL,
	[ma_nhan_hang] char(16) NULL,
	[dv_kho_tong_yn] tinyint NULL,
	[ma_kho] char(18) NULL,
	[ma_ngan] char(2) NULL,
	[ma_nh_dt] char(16) NULL,
	[ngay_khai_truong] smalldatetime NULL,
	[ngay_dong_cua] smalldatetime NULL,
	[dai_dien_cn_yn] tinyint NULL,
	[ghi_chu] nvarchar(256) NULL
)
ALTER TABLE dmdvcs WITH NOCHECK ADD CONSTRAINT PK_dmdvcs PRIMARY KEY CLUSTERED(ma_dvcs) ON [PRIMARY]
END
GO

-- clone_things: dbo.dmku | USER_TABLE | from source
IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[dmku]') AND type = N'U')
BEGIN
CREATE TABLE dmku(
	[ma_ku] char(16) NOT NULL,
	[ten_ku] nvarchar(128) NOT NULL,
	[ten_ku2] nvarchar(128) NOT NULL,
	[ma_kh] char(18) NULL,
	[ma_nvbh] char(8) NULL,
	[ma_bp] char(12) NULL,
	[ma_ku_me] char(16) NULL,
	[bac_ku] tinyint NULL,
	[loai_ku] tinyint NULL,
	[nh_ku1] char(8) NULL,
	[nh_ku2] char(8) NULL,
	[nh_ku3] char(8) NULL,
	[ngay_ku] smalldatetime NULL,
	[so_ku] char(16) NULL,
	[ngay_ku1] smalldatetime NULL,
	[ngay_ku2] smalldatetime NULL,
	[ku_sd_pslk] tinyint NULL,
	[ma_nt] char(3) NULL,
	[tien_nt] numeric(19,2) NULL,
	[tien] numeric(19,2) NULL,
	[tien_gt_nt] numeric(19,2) NULL,
	[tien_gt] numeric(19,2) NULL,
	[tinh_trang] tinyint NULL,
	[kl_kh] numeric(19,4) NULL,
	[kl_th] numeric(19,4) NULL,
	[ck_tt] numeric(18,0) NULL,
	[sl_tt] numeric(18,0) NULL,
	[ls_t] numeric(19,4) NULL,
	[ls_qh] numeric(19,4) NULL,
	[ls_td] numeric(19,4) NULL,
	[tk] char(16) NULL,
	[ma_hd] char(16) NULL,
	[ma_vv] char(16) NULL,
	[ghi_chu] ntext NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL,
	[ngay_th] smalldatetime NULL,
	[ma_td1] char(18) NULL,
	[ma_td2] char(16) NULL,
	[ma_td3] char(16) NULL,
	[sl_td1] numeric(19,4) NULL,
	[sl_td2] numeric(19,4) NULL,
	[sl_td3] numeric(19,4) NULL,
	[ngay_td1] smalldatetime NULL,
	[ngay_td2] smalldatetime NULL,
	[ngay_td3] smalldatetime NULL,
	[gc_td1] nchar(64) NULL,
	[gc_td2] nchar(64) NULL,
	[gc_td3] nchar(64) NULL,
	[s1] char(16) NULL,
	[s2] char(16) NULL,
	[s3] char(16) NULL,
	[s4] numeric(19,4) NULL,
	[s5] numeric(19,4) NULL,
	[s6] numeric(19,4) NULL,
	[s7] smalldatetime NULL,
	[s8] smalldatetime NULL,
	[s9] smalldatetime NULL,
	[ds_dvcs] varchar(512) NULL,
	[ky_tinh_thue] tinyint NULL,
	[ky_thue] int NULL,
	[nam] int NULL,
	[ky] int NULL,
	[ky_nop_thue] int NULL,
	[han_nop_thue] smalldatetime NULL,
	[ma_nh] char(16) NULL
)
ALTER TABLE dmku WITH NOCHECK ADD CONSTRAINT PK_dmku PRIMARY KEY CLUSTERED(ma_ku) ON [PRIMARY]

CREATE INDEX [u] ON dmku(ds_dvcs) ON [PRIMARY]
CREATE INDEX [status] ON dmku(status) ON [PRIMARY]
CREATE INDEX [ten_ku] ON dmku(ten_ku) ON [PRIMARY]
CREATE INDEX [ten_ku2] ON dmku(ten_ku2) ON [PRIMARY]
CREATE INDEX [datetime0] ON dmku(datetime0) ON [PRIMARY]
CREATE INDEX [datetime2] ON dmku(datetime2) ON [PRIMARY]
END
GO

-- clone_things: dbo.r00$000000 | USER_TABLE | from source
IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[r00$000000]') AND type = N'U')
BEGIN
CREATE TABLE r00$000000(
	[stt_rec] char(13) NOT NULL,
	[ma_dvcs] char(8) NOT NULL,
	[loai_ct] char(2) NULL,
	[ma_ct] char(3) NOT NULL,
	[ngay_ct] smalldatetime NOT NULL,
	[ngay_lct] smalldatetime NOT NULL,
	[so_ct] char(20) NOT NULL,
	[so_ctgs] char(20) NULL,
	[ngay_ctgs] smalldatetime NULL,
	[so_lo] char(20) NOT NULL,
	[ngay_lo] smalldatetime NULL,
	[ong_ba] nvarchar(128) NULL,
	[head_item] char(1) NULL,
	[dien_giai_h] nvarchar(432) NULL,
	[dien_giai] nvarchar(432) NULL,
	[nh_dk] char(3) NOT NULL,
	[tk] char(16) NOT NULL,
	[tk_du] char(16) NOT NULL,
	[ps_no_nt] numeric(19,2) NOT NULL,
	[ps_co_nt] numeric(19,2) NOT NULL,
	[ma_nt] char(3) NOT NULL,
	[ty_gia] numeric(24,12) NULL,
	[ps_no] numeric(19,2) NOT NULL,
	[ps_co] numeric(19,2) NOT NULL,
	[ma_kh] char(18) NULL,
	[ma_vv] char(16) NULL,
	[ma_nk] char(8) NULL,
	[ma_sp] char(16) NULL,
	[ma_bp] char(12) NULL,
	[so_lsx] char(16) NULL,
	[so_ct0] char(20) NULL,
	[ngay_ct0] smalldatetime NULL,
	[ct_nxt] tinyint NULL,
	[ma_gd] char(2) NULL,
	[nam] numeric(4,0) NULL,
	[ky] tinyint NULL,
	[gt_no] numeric(19,2) NULL,
	[gt_co] numeric(19,2) NULL,
	[gt_tinh] numeric(1,0) NULL,
	[gt_dd] numeric(1,0) NULL,
	[sua_tg_yn] numeric(1,0) NULL,
	[line_nbr] int NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL,
	[ma_hd] char(16) NULL,
	[ma_ku] char(16) NULL,
	[ma_phi] char(16) NULL,
	[so_dh] char(16) NULL,
	[ma_td1] char(18) NULL,
	[ma_td2] char(16) NULL,
	[ma_td3] char(16) NULL,
	[sl_td1] numeric(19,4) NULL,
	[sl_td2] numeric(19,4) NULL,
	[sl_td3] numeric(19,4) NULL,
	[ngay_td1] smalldatetime NULL,
	[ngay_td2] smalldatetime NULL,
	[ngay_td3] smalldatetime NULL,
	[gc_td1] nchar(24) NULL,
	[gc_td2] nchar(1) NULL,
	[gc_td3] nchar(1) NULL,
	[s1] char(16) NULL,
	[s2] char(16) NULL,
	[s3] char(16) NULL,
	[s4] numeric(19,4) NULL,
	[s5] numeric(19,4) NULL,
	[s6] numeric(19,4) NULL,
	[s7] smalldatetime NULL,
	[s8] smalldatetime NULL,
	[s9] smalldatetime NULL
)

CREATE INDEX [ma_kh] ON r00$000000(ma_kh) ON [PRIMARY]
CREATE INDEX [tk] ON r00$000000(tk) ON [PRIMARY]
CREATE INDEX [so_lo] ON r00$000000(so_lo) ON [PRIMARY]
CREATE INDEX [ngay_lo] ON r00$000000(ngay_lo) ON [PRIMARY]
CREATE INDEX [stt_rec] ON r00$000000(stt_rec) ON [PRIMARY]
CREATE INDEX [stt_rec0] ON r00$000000(stt_rec, nh_dk, tk, tk_du) ON [PRIMARY]
CREATE INDEX [ma_vv] ON r00$000000(ma_vv) ON [PRIMARY]
CREATE INDEX [ma_dvcs] ON r00$000000(ma_dvcs) ON [PRIMARY]
CREATE INDEX [ngay_ctgs] ON r00$000000(ngay_ctgs) ON [PRIMARY]
CREATE INDEX [so_ctgs] ON r00$000000(so_ctgs) ON [PRIMARY]
CREATE INDEX [ma_bp] ON r00$000000(ma_bp) ON [PRIMARY]
CREATE INDEX [ma_sp] ON r00$000000(ma_sp) ON [PRIMARY]
CREATE INDEX [tk_ma_kh] ON r00$000000(tk, ma_kh) ON [PRIMARY]

ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_loai_ct]  DEFAULT ('') FOR loai_ct
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_td1]  DEFAULT ('') FOR ma_td1
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_head_item]  DEFAULT ('') FOR head_item
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_dien_giai_h]  DEFAULT ('') FOR dien_giai_h
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_dien_giai]  DEFAULT ('') FOR dien_giai
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_nh_dk]  DEFAULT ('') FOR nh_dk
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_vv]  DEFAULT ('') FOR ma_vv
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_nk]  DEFAULT ('') FOR ma_nk
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_sp]  DEFAULT ('') FOR ma_sp
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_so_lsx]  DEFAULT ('') FOR so_lsx
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ct_nxt]  DEFAULT (0) FOR ct_nxt
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_gd]  DEFAULT ('') FOR ma_gd
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_nam]  DEFAULT (0) FOR nam
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ky]  DEFAULT (0) FOR ky
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_gt_tinh]  DEFAULT (0) FOR gt_tinh
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_gt_dd]  DEFAULT (0) FOR gt_dd
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_hd]  DEFAULT ('') FOR ma_hd
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_ku]  DEFAULT ('') FOR ma_ku
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_phi]  DEFAULT ('') FOR ma_phi
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_so_dh]  DEFAULT ('') FOR so_dh
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_td2]  DEFAULT ('') FOR ma_td2
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_td3]  DEFAULT ('') FOR ma_td3
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_gc_td1]  DEFAULT ('') FOR gc_td1
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_gc_td2]  DEFAULT ('') FOR gc_td2
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_gc_td3]  DEFAULT ('') FOR gc_td3
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_s1]  DEFAULT ('') FOR s1
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_s2]  DEFAULT ('') FOR s2
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_s3]  DEFAULT ('') FOR s3
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_so_ctgs]  DEFAULT ('') FOR so_ctgs
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_so_lo]  DEFAULT ('') FOR so_lo
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_so_ct0]  DEFAULT ('') FOR so_ct0
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_gt_no]  DEFAULT ((0)) FOR gt_no
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_gt_co]  DEFAULT ((0)) FOR gt_co
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_sl_td1]  DEFAULT ((0)) FOR sl_td1
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_sl_td2]  DEFAULT ((0)) FOR sl_td2
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_sl_td3]  DEFAULT ((0)) FOR sl_td3
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ong_ba]  DEFAULT ('') FOR ong_ba
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_s4]  DEFAULT ((0)) FOR s4
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_s5]  DEFAULT ((0)) FOR s5
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_s6]  DEFAULT ((0)) FOR s6
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_bp]  DEFAULT ('') FOR ma_bp
ALTER TABLE r00$000000 ADD CONSTRAINT [DF_r00$000000_ma_kh]  DEFAULT ('') FOR ma_kh
END
GO

-- clone_things: dbo.reports | USER_TABLE | from source
IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[reports]') AND type = N'U')
BEGIN
CREATE TABLE reports(
	[ccode] char(8) NOT NULL,
	[cname] nvarchar(128) NULL,
	[cname2] nvarchar(128) NULL
)
ALTER TABLE reports WITH NOCHECK ADD CONSTRAINT PK_reports PRIMARY KEY CLUSTERED(ccode) ON [PRIMARY]
END
GO

-- clone_things: dbo.zcdmcnql | USER_TABLE | from source
IF NOT EXISTS (SELECT 1 FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[zcdmcnql]') AND type = N'U')
BEGIN
CREATE TABLE zcdmcnql(
	[ma_cn_ql] varchar(16) NOT NULL,
	[ten_cn_ql] nvarchar(128) NULL,
	[ten_cn_ql2] nvarchar(128) NULL,
	[ghi_chu] nvarchar(128) NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL,
	[sl_td1] numeric(16,4) NULL,
	[sl_td2] numeric(16,4) NULL,
	[sl_td3] numeric(16,4) NULL,
	[ngay_td1] smalldatetime NULL,
	[ngay_td2] smalldatetime NULL,
	[ngay_td3] smalldatetime NULL,
	[gc_td1] nchar(64) NULL,
	[gc_td2] nchar(64) NULL,
	[gc_td3] nchar(64) NULL,
	[s1] char(16) NULL,
	[s2] char(16) NULL,
	[s3] char(16) NULL,
	[s4] numeric(16,4) NULL,
	[s5] numeric(16,4) NULL,
	[s6] numeric(16,4) NULL,
	[s7] smalldatetime NULL,
	[s8] smalldatetime NULL,
	[s9] smalldatetime NULL
)
ALTER TABLE zcdmcnql WITH NOCHECK ADD CONSTRAINT PK_zcdmcnql PRIMARY KEY CLUSTERED(ma_cn_ql) ON [PRIMARY]
END
GO

USE [VLOTUS_eInv]
GO
