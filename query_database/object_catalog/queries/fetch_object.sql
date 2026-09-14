SELECT
    o.object_id,
    SCHEMA_NAME(o.schema_id) AS schema_name,
    o.name,
    o.type,
    o.type_desc,
    m.definition,
    o.modify_date
FROM sys.objects o
JOIN sys.sql_modules m ON m.object_id = o.object_id
WHERE o.name = N'{safe_name}'
  AND SCHEMA_NAME(o.schema_id) = N'{safe_schema}'
