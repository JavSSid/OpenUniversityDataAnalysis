WITH source AS (
    SELECT * FROM {{ ref('bronze_courses') }}
)

SELECT
    code_module,
    code_presentation,
    length,
    CASE
        WHEN SUBSTR(code_presentation, -1) = 'B' THEN 'February'
        WHEN SUBSTR(code_presentation, -1) = 'J' THEN 'October'
        ELSE 'Unknown'
    END AS presentation_start,
    _ingested_at
FROM source
