-- ============================================================================
-- AGENT GUIDE — CREATE TABLE danh mục nhiều khóa (composite PK).
-- * {{table}} đã fill = tên bảng; PK = các cột name_* trùng isPrimaryKey
--   trong master.xml/upload.xml — đổi tên + cập nhật CONSTRAINT cho khớp.
-- * Check trùng PK nằm ở Dir/upload — bảng chỉ cần PK constraint.
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
