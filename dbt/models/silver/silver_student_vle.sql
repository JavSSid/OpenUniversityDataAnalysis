WITH source AS (
    SELECT * FROM {{ ref('bronze_student_vle') }}
)

SELECT
    sv.id_student,
    sv.code_module,
    sv.code_presentation,
    sv.id_site,
    sv.date,
    sv.sum_click,
    v.activity_type,
    v.activity_category,
    v.week_from,
    v.week_to
FROM source sv
LEFT JOIN {{ ref('silver_vle') }} v
    ON sv.id_site = v.id_site
    AND sv.code_module = v.code_module
    AND sv.code_presentation = v.code_presentation
