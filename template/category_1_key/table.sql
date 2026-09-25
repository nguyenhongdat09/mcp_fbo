-- ============================================================================
-- AGENT GUIDE — CREATE TABLE danh mục 1 khóa (identity PK).
-- * {{table}} đã được clone_things fill = tên bảng; đổi name_* theo field
--   thật trong master.xml/grid.xml (PHẢI khớp nhau).
-- * PK = id identity — danh mục không check trùng.
-- * Thêm cột nghiệp vụ theo UR; datatype hay gặp: char(n) mã,
--   nvarchar(n) tên/diễn giải, smalldatetime ngày, numeric(19,4) số/tiền.
-- * Chạy bằng query_database type=2 (file .sql) — xem qua trước với user.
-- ============================================================================
-- IF EXISTS (SELECT 1 FROM sysobjects WHERE name = '{{table}}' AND xtype = 'U') DROP TABLE [{{table}}]
CREATE TABLE {{table}}(
	[id] int IDENTITY(1,1) NOT NULL,
	[name_date_1] smalldatetime NULL,
	[name_lookup_1] char(16) NULL,
	[name_decimal_1] numeric(19,4) NULL,
	[name_decimal_2] numeric(19,4) NULL,
	[name_string_2] nvarchar(256) NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL
)
ALTER TABLE {{table}} WITH NOCHECK ADD CONSTRAINT PK_{{table}} PRIMARY KEY CLUSTERED(id) ON [PRIMARY]
GO
CREATE INDEX [datetime0] ON {{table}}(datetime0) ON [PRIMARY]
CREATE INDEX [datetime2] ON {{table}}(datetime2) ON [PRIMARY]
