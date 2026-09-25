-- ============================================================================
-- AGENT GUIDE — CREATE TABLE danh mục 1 khóa + 1 bảng chi tiết.
-- * {{table}} = master (PK id identity), {{table_detail}} = chi tiết
--   (FK name_string_1 nối master + line_nbr làm PK detail — khớp code=
--   trong griddetail.xml và ForeignKey trong master.xml).
-- * Grid detail FBO cần line_nbr làm khóa dòng (Insert/Grow/Clone/Remove).
-- * Chạy bằng query_database type=2 — xem qua trước với user.
-- ============================================================================
-- IF EXISTS (SELECT 1 FROM sysobjects WHERE name = '{{table}}' AND xtype = 'U') DROP TABLE [{{table}}]
CREATE TABLE {{table}}(
	[id] int IDENTITY(1,1) NOT NULL,
	[name_string_1] char(16) NOT NULL,
	[name_date_1] smalldatetime NULL,
	[name_decimal_1] numeric(19,4) NULL,
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
GO

-- IF EXISTS (SELECT 1 FROM sysobjects WHERE name = '{{table_detail}}' AND xtype = 'U') DROP TABLE [{{table_detail}}]
CREATE TABLE {{table_detail}}(
	[name_string_1] char(16) NOT NULL,
	[line_nbr] int NOT NULL,
	[name_string_3] char(16) NULL,
	[name_decimal_2] numeric(19,4) NULL,
	[name_string_4] nvarchar(256) NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL
)
ALTER TABLE {{table_detail}} WITH NOCHECK ADD CONSTRAINT PK_{{table_detail}} PRIMARY KEY CLUSTERED(name_string_1, line_nbr) ON [PRIMARY]
GO
CREATE INDEX [datetime0] ON {{table_detail}}(datetime0) ON [PRIMARY]
CREATE INDEX [datetime2] ON {{table_detail}}(datetime2) ON [PRIMARY]
