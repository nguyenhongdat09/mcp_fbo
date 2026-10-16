-- CHUA DEPLOY — file skeleton cho agent sua placeholder roi deploy TUNG PHAN.
-- Mode: PARTITIONED (bang nguon m/d/i{ext}$YYYYMM)
-- Dien {{...}} theo UR; cac khoi trong /* */ la snippet de copy vao XML, KHONG chay.

-- ========== 1. fsd_addFields ==========
-- Cot "da lay" tren bang detail NGUON (pattern phan ky co $):
exec fsd_addFields '{{src_d_table_arg}}','{{src_taken_col}}','{{src_taken_sql_type}}'
-- vd: exec fsd_addFields 'd64$','sl_ycn','numeric(18,3)'

-- Cac truong VET tren bang detail DICH (lap lai cho moi truong vet):
-- exec fsd_addFields '{{dest_d_table}}','{{stt_rec_src_col}}','char(13)'
-- exec fsd_addFields '{{dest_d_table}}','{{stt_rec0_src_col}}','char(13)'
-- exec fsd_addFields '{{dest_d_table}}','<field vet khac vd so_ct_src/line_src>','<type>'

-- ========== 2. CREATE PROC BeforeAfterUpdate ==========
IF OBJECT_ID(N'dbo.{{proc_name}}', N'P') IS NOT NULL
  DROP PROCEDURE dbo.{{proc_name}}
GO

CREATE PROCEDURE {{proc_name}}
	@IDNumber CHAR(13),
	@Dtable CHAR(33),
	@Mtable CHAR(33),
	@Type CHAR(1), -- 1: before, 2: after
	@UserID INT
AS
BEGIN
	DECLARE @ngay VARCHAR(6), @status CHAR(1), @q NVARCHAR(MAX)

	SELECT TOP 0 {{stt_rec_src_col}}, {{stt_rec0_src_col}}, {{dest_line_qty_col}}--{{he_so_cols}}
		INTO #{{identity}}_1
		FROM {{dest_d_table}}000000 a

	SET @q = ' insert into #{{identity}}_1
		select a.{{stt_rec_src_col}}, a.{{stt_rec0_src_col}}, a.{{dest_line_qty_col}}--{{he_so_cols_a}}
		from '+@Dtable+' a with(nolock)
		left join '+@Mtable+' b with(nolock) on a.stt_rec = b.stt_rec
		where a.stt_rec = '''+@IDNumber+''' '
	EXEC(@q)

	SELECT a.{{stt_rec_src_col}}, a.{{stt_rec0_src_col}}, a.{{dest_line_qty_col}}, b.ngay_ct--{{he_so_cols_a}},
	       RTRIM(YEAR(b.ngay_ct)) + REPLACE(str(MONTH(b.ngay_ct), 2), ' ', '0') AS parti
		INTO #stt_rec_{{identity}}
		FROM #{{identity}}_1 a
		JOIN {{src_c_table}} b ON a.{{stt_rec_src_col}} = b.stt_rec

	SET @q = ''
	SELECT @q += '
		;with t as (
			select {{stt_rec_src_col}}, {{stt_rec0_src_col}},
			       b.{{dest_line_qty_col}} as {{src_taken_col}}
			-- NEU quy doi he_so: thay dong tren bang
			-- CASE WHEN a.he_so = 0 THEN 0 ELSE ROUND(b.{{dest_line_qty_col}} * (b.he_so / a.he_so), 3) END as {{src_taken_col}}
			from {{src_d_table_arg}}'+parti+' a
			join #stt_rec_{{identity}} b
			  on a.stt_rec = b.{{stt_rec_src_col}} and a.stt_rec0 = b.{{stt_rec0_src_col}}
		), t1 as (
			select {{stt_rec_src_col}}, {{stt_rec0_src_col}}, sum({{src_taken_col}}) as {{src_taken_col}}
			from t group by {{stt_rec_src_col}}, {{stt_rec0_src_col}}
		)
		update a set {{src_taken_col}} = a.{{src_taken_col}} ' + CASE WHEN @Type = '1' THEN '-' ELSE ' + ' END + ' b.{{src_taken_col}}
		from {{src_d_table_arg}}'+parti+' a
		join t1 b on a.stt_rec = b.{{stt_rec_src_col}} and a.stt_rec0 = b.{{stt_rec0_src_col}}
	'
	FROM #stt_rec_{{identity}}
	GROUP BY parti

	PRINT @q
	EXEC(@q)
END
GO
-- Ghi chu: {{he_so_cols}} = ', he_so' ; {{he_so_cols_a}} = ', a.he_so' — CHI dien khi quy doi he_so.
-- Naming chuan proc: fsd_FastBusiness$Voucher$BeforeAfterUpdate${DestTran}From${SrcTran}
-- vd: fsd_FastBusiness$Voucher$BeforeAfterUpdate$YCNTranFromSOTran

-- ========== 3. sysfilterdeclares (cho column filter tren MultiGrid) ==========
/*
DELETE FROM sysfilterdeclares WHERE controller = '{{identity}}MultiGrid'
-- Lap lai INSERT cho moi declare can thiet (id_suffix = so thu tu):
INSERT INTO sysfilterdeclares([controller], [id], [name], [exname], [xtable], [fieldkey], [exfieldkey], [reftable], [reffieldkey], [joinclause], [conditionalreplace])
  VALUES(N'{{identity}}MultiGrid', N'{{identity}}MultiGrid.<id_suffix>', N'<name>', N'<exname>', NULL, NULL, NULL, NULL, NULL, NULL, NULL)
*/

-- ========== 4. Snippet dan vao XML voucher DICH ==========
/**
<!ENTITY VoucherBeforeUpdate "
	exec {{proc_name}} @stt_rec, '{{dest_d_table}}$partition$previous', '{{dest_m_table}}$partition$previous', '1', @@userID
">
<!ENTITY VoucherAfterUpdate "
	exec {{proc_name}} @stt_rec, '{{dest_d_table}}$partition$current', '{{dest_m_table}}$partition$current', '2', @@userID
">
<!ENTITY UpdatefsdSttRecRef "
	delete a from fsdSttRecRef a where a.stt_rec = @stt_rec
	insert into fsdSttRecRef (stt_rec, stt_rec0, ma_ct, ngay_ct, so_ct, so_luong, he_so, stt_rec_pre, stt_rec0pre)
		select stt_rec, stt_rec0, ma_ct, ngay_ct, so_ct, so_luong, he_so, {{stt_rec_src_col}}, {{stt_rec0_src_col}}
			from {{dest_d_table}}$partition$current
			where {{stt_rec_src_col}} &lt;&gt; '' and stt_rec = @stt_rec
">
<!ENTITY DeletefsdSttRecRef "
	delete a from fsdSttRecRef a join {{dest_d_table}}$partition$current b on a.stt_rec = b.stt_rec where a.stt_rec = @stt_rec
">

-- Vi tri dan tren Dir/{{dest_tran}}.xml (DOCTYPE, NGOAI CDATA):
-- &VoucherBeforeUpdate;  -> Updating (truoc #IF partition) + Deleting
-- &VoucherAfterUpdate;   -> Inserted, Updated
-- &UpdatefsdSttRecRef;   -> Inserted, Updated (sau detail da ghi)
-- &DeletefsdSttRecRef;   -> Deleting (truoc khi xoa detail)
-- Luu y: &...; phai nam NGOAI <![CDATA[...]]> neu khong entity khong expand.

-- ========== Detail XML — copy tay vao Grid/{{dest_tran_detail}}.xml ==========
-- 1) Them vao <fields>: moi truong vet 1 <field> (an neu khong header):
-- <field name="{{stt_rec_src_col}}" width="0" hidden="true" readOnly="true">
--   <header v="" e=""></header>
-- </field>
-- <field name="{{stt_rec0_src_col}}" width="0" hidden="true" readOnly="true">
--   <header v="" e=""></header>
-- </field>
-- 2) Them vao <view id="Grid">: <field name="{{stt_rec_src_col}}"/> <field name="{{stt_rec0_src_col}}"/> ...

-- ========== Menu Retrieve (Grid/{{dest_tran_detail}}.xml, ExecuteCommand) ==========
-- case 'Retrieve':
--     if (f._action == 'View') break;
--     g.showForm('{{identity}}Filter');
--     break;
*/
