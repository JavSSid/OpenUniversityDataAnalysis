WITH source AS (
    SELECT * FROM {{ ref('bronze_student_assessment') }}
)

SELECT
    sa.id_assessment,
    sa.id_student,
    sa.date_submitted,
    sa.is_banked,
    sa.score,
    a.assessment_type,
    a.deadline_day,
    a.weight,
    CASE
        WHEN sa.score IS NULL THEN 'not_submitted'
        WHEN sa.score >= 40 THEN 'passed'
        ELSE 'failed'
    END AS assessment_result,
    sa.date_submitted - a.deadline_day AS submission_delay_days
FROM source sa
LEFT JOIN {{ ref('silver_assessments') }} a
    ON sa.id_assessment = a.id_assessment
