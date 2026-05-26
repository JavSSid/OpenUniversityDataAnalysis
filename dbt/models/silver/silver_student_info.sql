{% set pii_fields = ['region', 'imd_band'] %}

WITH source AS (
    SELECT * FROM {{ ref('bronze_student_info') }}
)

SELECT
    id_student,
    code_module,
    code_presentation,
    gender,
    {% for field in pii_fields %}
    TO_HEX(SHA256(CAST({{ field }} AS STRING))) AS {{ field }}{% if not loop.last %},{% endif %}
    {% endfor %},
    highest_education,
    age_band,
    num_of_prev_attempts,
    studied_credits,
    disability,
    final_result,
    _ingested_at
FROM source
