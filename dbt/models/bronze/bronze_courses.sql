SELECT
    code_module,
    code_presentation,
    length,
    _ingested_at,
    _source_file
FROM bronze.courses
WHERE length > 0
