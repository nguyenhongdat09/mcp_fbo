-- ============================================================================
-- AGENT GUIDE — CREATE TABLE danh mục composite PK + 2 bảng chi tiết.
-- * {{table}} = master (PK name_date_1 + name_string_1),
--   {{table_detail}}/{{table_detail2}} = chi tiết — FK name_string_1
--   + line_nbr làm PK (khớp ForeignKey master.xml + code= griddetail*.xml).
-- * FK nối detail = name_string_1 (1 cột); nếu detail cần nối cả composite
--   key: thêm name_date_1 vào bảng detail + ForeignKey + PK.
-- * Chạy bằng query_database type=2 — xem qua trước với user.
-- ============================================================================
-- IF EXISTS (SELECT 1 FROM sysobjects WHERE name = '{{table}}' AND xtype = 'U') DROP TABLE [{{table}}]
CREATE TABLE {{table}}(
	[name_date_1] smalldatetime NOT NULL,
	[name_string_1] char(16) NOT NULL,
	[name_decimal_1] numeric(19,4) NULL,
	[name_string_2] nvarchar(256) NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL
)
ALTER TABLE {{table}} WITH NOCHECK ADD CONSTRAINT PK_{{table}} PRIMARY KEY CLUSTERED(name_string_1, name_date_1) ON [PRIMARY]
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
GO

-- IF EXISTS (SELECT 1 FROM sysobjects WHERE name = '{{table_detail2}}' AND xtype = 'U') DROP TABLE [{{table_detail2}}]
CREATE TABLE {{table_detail2}}(
	[name_string_1] char(16) NOT NULL,
	[line_nbr] int NOT NULL,
	[name_string_3] char(16) NULL,
	[name_decimal_2] numeric(19,4) NULL,
	[status] char(1) NULL,
	[datetime0] datetime NULL,
	[datetime2] datetime NULL,
	[user_id0] int NULL,
	[user_id2] int NULL
)
ALTER TABLE {{table_detail2}} WITH NOCHECK ADD CONSTRAINT PK_{{table_detail2}} PRIMARY KEY CLUSTERED(name_string_1, line_nbr) ON [PRIMARY]
GO
CREATE INDEX [datetime0] ON {{table_detail2}}(datetime0) ON [PRIMARY]
CREATE INDEX [datetime2] ON {{table_detail2}}(datetime2) ON [PRIMARY]
