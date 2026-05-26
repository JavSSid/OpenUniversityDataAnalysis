SELECT DISTINCT
    c.code_module,
    c.code_presentation,
    c.length,
    c.presentation_start,
    a.assessment_type,
    a.count AS assessment_count,
    a.total_weight
FROM {{ ref('silver_courses') }} c
LEFT JOIN (
    SELECT
        code_module,
        code_presentation,
        COUNT(DISTINCT id_assessment) AS count,
        SUM(weight) AS total_weight
    FROM {{ ref('silver_assessments') }}
    GROUP BY code_module, code_presentation
) a
    ON c.code_module = a.code_module
    AND c.code_presentation = a.code_presentation
