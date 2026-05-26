WITH student_base AS (
    SELECT DISTINCT id_student, code_module, code_presentation
    FROM {{ ref('silver_student_registration') }}
)

SELECT
    s.id_student,
    s.code_module,
    s.code_presentation,
    si.gender,
    si.age_band,
    si.highest_education,
    si.disability,
    si.num_of_prev_attempts,
    si.studied_credits,
    si.final_result,
    sr.date_registration,
    sr.date_unregistration,
    sr.has_unregistered,
    sr.registration_timing,
    si._ingested_at
FROM student_base s
LEFT JOIN {{ ref('silver_student_info') }} si
    ON s.id_student = si.id_student
    AND s.code_module = si.code_module
    AND s.code_presentation = si.code_presentation
LEFT JOIN {{ ref('silver_student_registration') }} sr
    ON s.id_student = sr.id_student
    AND s.code_module = sr.code_module
    AND s.code_presentation = sr.code_presentation
