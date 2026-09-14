SELECT DISTINCT
    OBJECT_SCHEMA_NAME(d.referencing_id) + '.' + OBJECT_NAME(d.referencing_id) AS caller
FROM sys.sql_expression_dependencies AS d
WHERE d.referenced_id = {object_id}
  AND d.referencing_id <> d.referenced_id
ORDER BY caller
