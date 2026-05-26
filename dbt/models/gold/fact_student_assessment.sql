SELECT
    id_student,
    id_assessment,
    date_submitted,
    score,
    is_banked,
    assessment_type,
    assessment_result,
    submission_delay_days,
    weight
FROM {{ ref('silver_student_assessment') }}
