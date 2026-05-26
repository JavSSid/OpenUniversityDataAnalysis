SELECT
    code_module,
    code_presentation,
    id_student,
    id_site,
    date,
    sum_click,
    _ingested_at,
    _source_file
FROM bronze.student_vle
WHERE sum_click >= 0
