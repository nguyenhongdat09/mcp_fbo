SET NOCOUNT ON
DECLARE @cTable VARCHAR(33), @strSQL NVARCHAR(4000), @cRef VARCHAR(128), @cFields VARCHAR(1000), @Max INT, @xOrder INT, @i INT, @cTmp VARCHAR(128), @cName VARCHAR(128), @isCreateTable BIT, @isCreateIndex BIT, @isCreateTrigger BIT, @isCreateDF BIT, @cNewLine VARCHAR(5)
SELECT @cTable = '{{table_name}}', @isCreateTable = '1', @isCreateIndex = '1', @isCreateTrigger = '1', @isCreateDF = '1', @strSQL = '', @cNewLine = CHAR(13) + CHAR(10)

CREATE TABLE #result(val NVARCHAR(4000))

DECLARE @id INT
SELECT @id = OBJECT_ID(@cTable)

IF @isCreateTable = '1'
BEGIN
	SELECT CAST(CASE WHEN b.column_name IS NULL THEN 0 ELSE 1 END AS BIT) AS pkey, a.COLUMN_NAME AS val, CAST('' AS NVARCHAR(128)) AS textname, a.DATA_TYPE AS datatype
			, a.DATA_TYPE + ISNULL('(' + RTRIM(CHARACTER_MAXIMUM_LENGTH) + ')', '') + ISNULL('(' + RTRIM(NUMERIC_PRECISION) + ',' + RTRIM(NUMERIC_SCALE) + ')', '')  AS type
			, CAST(CASE WHEN IS_NULLABLE = 'NO' THEN 'NOT NULL' ELSE 'NULL' END AS VARCHAR(33)) AS xnull, a.ORDINAL_POSITION AS xorder
		INTO #t
		FROM INFORMATION_SCHEMA.COLUMNS a 
			LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE b ON a.table_name = b.table_name AND a.column_name  = b.column_name AND b.CONSTRAINT_NAME IN (SELECT name FROM sysobjects c WHERE c.xtype = 'PK')
		WHERE a.TABLE_NAME = @cTable 

		select name, cast(seed_value as int) as seed_value, cast(increment_value as int) as increment_value into #identity from sys.identity_columns where object_id = @id
		

	UPDATE #t SET type = datatype WHERE datatype IN ('ntext', 'smalldatetime', 'datetime', 'bit', 'tinyint', 'int', 'image', 'binary')
	UPDATE #t SET type = REPLACE(type, '(-1)', '(max)') 
	
	UPDATE #t SET type = type + ' identity(' + rtrim(b.seed_value) + ',' + rtrim(b.increment_value) + ')' FROM #t a join #identity b on a.val = b.name
	SELECT @Max = MAX(xorder) FROM #t
	UPDATE #t SET xnull = xnull + ',' WHERE xorder <> @Max
	UPDATE #t SET xnull = xnull + @cNewLine + ')' WHERE xorder = @Max

	SET @strSQL = 'CREATE TABLE ' + @cTable + '('
	INSERT INTO #result SELECT @strSQL + @cNewLine

	DECLARE cr1 CURSOR FOR SELECT xorder FROM #t
	OPEN cr1
	FETCH NEXT FROM cr1 INTO @xOrder
		WHILE @@FETCH_STATUS = 0
		BEGIN		
			SELECT @strSQL = CHAR(9) + '[' + val + '] ' + type + ' ' + xnull FROM #t WHERE xorder = @xOrder
			INSERT INTO #result SELECT @strSQL + @cNewLine
			FETCH NEXT FROM cr1 INTO @xOrder
		END
	CLOSE cr1
	DEALLOCATE cr1

	SELECT a.CONSTRAINT_NAME AS name, a.COLUMN_NAME AS col, b.xtype, OBJECT_NAME(c.rkeyid) AS rname, a.ORDINAL_POSITION AS xorder INTO #key 
		FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE a LEFT JOIN sysobjects b ON a.CONSTRAINT_NAME = b.name 
			LEFT JOIN sysreferences c ON b.id = c.constid
	WHERE a.TABLE_NAME = @cTable 

	IF EXISTS(SELECT 1 FROM #key WHERE xtype = 'PK')
	BEGIN
		SELECT @strSQL = '', @cFields = ''
		SELECT @strSQL = name, @cFields = @cFields + col + ', ' FROM #key WHERE xtype = 'PK'
		SET @strSQL = 'ALTER TABLE ' + @cTable + ' WITH NOCHECK ADD CONSTRAINT ' + @strSQL + ' PRIMARY KEY CLUSTERED(' + SUBSTRING(@cFields, 1, LEN(@cFields) - 1) + ') ON [PRIMARY]'
		INSERT INTO #result SELECT @strSQL + @cNewLine
	END

	IF EXISTS(SELECT 1 FROM #key WHERE xtype = 'F')
	BEGIN
		INSERT INTO #result SELECT 'GO' + @cNewLine
		SELECT @strSQL = '', @cFields = ''
		SELECT @strSQL = name, @cFields = col, @cRef = rname FROM #key WHERE xtype = 'F'
		SET @strSQL = 'ALTER TABLE ' + @cTable + ' ADD CONSTRAINT ' + @strSQL + ' FOREIGN KEY (' + @cFields + ') REFERENCES ' + @cRef + '(' + @cFields + ')'
		INSERT INTO #result SELECT @strSQL + @cNewLine
	END

	DROP TABLE #key 
	DROP TABLE #t
	drop table #identity
END

IF @isCreateIndex = 1
BEGIN
	IF EXISTS (SELECT 1 FROM #result)
	BEGIN
		INSERT INTO #result SELECT 'GO' + @cNewLine
	END
	SELECT name, indid INTO #index FROM sysindexes i WHERE id = @id AND status = 0 
		AND (INDEXPROPERTY(@id, i.name, N'IsStatistics') <> 1) AND (INDEXPROPERTY(@id, i.name, N'IsAutoStatistics') <> 1) AND (INDEXPROPERTY(@id, i.name, N'IsHypothetical') <> 1) AND indid BETWEEN 0 AND 255 
	DELETE #index WHERE name IS NULL

	DECLARE cr2 CURSOR FOR SELECT name, indid FROM #index
	OPEN cr2
	FETCH NEXT FROM cr2 INTO @cName, @xOrder
		WHILE @@FETCH_STATUS = 0
		BEGIN			
			SELECT @cFields = '', @i = 1
			WHILE 1=1
			BEGIN
				SET @cTmp = NULL
				SET @cTmp = INDEX_COL(@cTable, @xOrder, @i)			
				IF @cTmp IS NULL 
				BEGIN
					GOTO ExitWhile
				END
				SET @cFields =  @cFields + CASE WHEN @cFields = '' THEN '' ELSE ', ' END + @cTmp
				SET @i = @i + 1
			END
			
ExitWhile:	SET @strSQL = 'CREATE INDEX ['+@cName+'] ON ' + @cTable + '('+@cFields+') ON [PRIMARY]'
			INSERT INTO #result SELECT @strSQL + @cNewLine
			FETCH NEXT FROM cr2 INTO @cName, @xOrder
		END
	CLOSE cr2
	DEALLOCATE cr2
	DROP TABLE #index
END

IF @isCreateTrigger = 1
BEGIN
	SELECT name, xtype INTO #tr FROM sysobjects WHERE parent_obj = @id AND xtype IN ('TR', 'V', 'D')
	IF EXISTS (SELECT 1 FROM #tr) AND EXISTS (SELECT 1 FROM #result)
	BEGIN
		INSERT INTO #result SELECT 'GO' + @cNewLine
	END
	CREATE TABLE #txt(val NVARCHAR(MAX))
	
	SET @strSQL = ''
	SELECT @strSQL = @strSQL + 'INSERT INTO #txt EXEC sp_helptext ' + name + @cNewLine + 'INSERT INTO #txt SELECT CHAR(13) + CHAR(10) + ''GO'' + CHAR(13) + CHAR(10)' + @cNewLine FROM #tr WHERE xtype = 'TR'
	EXEC sp_executesql @strSQL
	
	INSERT INTO #result SELECT val FROM #txt
	
	DECLARE cr3 CURSOR FOR SELECT val FROM #txt
	OPEN cr3
	FETCH NEXT FROM cr3 INTO @strSQL
		WHILE @@FETCH_STATUS = 0
		BEGIN		
			FETCH NEXT FROM cr3 INTO @strSQL
		END
	CLOSE cr3
	DEALLOCATE cr3
	DROP TABLE #txt
END

IF @isCreateDF = 1 AND @isCreateTrigger = 1
BEGIN
	SELECT x.name AS name, COL_NAME(a.id, a.colid) AS colname, a.colid, b.definition INTO #df 
		FROM sysconstraints a 
			LEFT JOIN sysobjects x ON a.constid = x.id
			LEFT JOIN sys.default_constraints b ON x.name = b.name
		WHERE x.name IN (SELECT name FROM #tr)
	INSERT INTO #result SELECT 'ALTER TABLE ' + @cTable + ' ADD CONSTRAINT [' + name + ']  DEFAULT ' + definition + ' FOR ' + colname + @cNewLine FROM #df 

	DROP TABLE #df
	DROP TABLE #tr	
END
SELECT * FROM #result

DROP TABLE #result
