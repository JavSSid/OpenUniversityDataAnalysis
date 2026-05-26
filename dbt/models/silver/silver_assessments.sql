WITH source AS (
    SELECT * FROM {{ ref('bronze_assessments') }}
)

SELECT
    a.id_assessment,
    a.code_module,
    a.code_presentation,
    a.assessment_type,
    a.date AS deadline_day,
    a.weight,
    c.length AS module_length,
    ROUND(CAST(a.weight AS FLOAT64) / NULLIF(SUM(a.weight) OVER (
        PARTITION BY a.code_module, a.code_presentation
    ), 0), 4) AS weight_pct
FROM source a
LEFT JOIN {{ ref('bronze_courses') }} c
    ON a.code_module = c.code_module
    AND a.code_presentation = c.code_presentation
