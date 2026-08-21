SELECT
    p.name,
    TYPE_NAME(p.user_type_id) AS type_name,
    p.max_length,
    p.is_output,
    p.has_default_value,
    p.default_value
FROM sys.parameters p
WHERE p.object_id = {object_id}
ORDER BY p.parameter_id
