WITH source AS (
    SELECT * FROM {{ ref('bronze_student_registration') }}
)

SELECT
    id_student,
    code_module,
    code_presentation,
    date_registration,
    NULLIF(date_unregistration, 0) AS date_unregistration,
    has_unregistered,
    CASE WHEN date_registration < 0 THEN 'early' WHEN date_registration = 0 THEN 'on_time' ELSE 'late' END AS registration_timing
FROM source
