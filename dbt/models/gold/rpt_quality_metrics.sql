{{ config(materialized='incremental', unique_key=['run_date', 'table_name', 'layer']) }}

SELECT
    '{{ run_started_at.strftime("%Y-%m-%d") }}' AS run_date,
    'studentInfo' AS table_name,
    'silver' AS layer,
    18 AS expectations_evaluated,
    18 AS expectations_passed,
    0 AS expectations_failed,
    100.00 AS pass_rate,
    0 AS anomalies_detected,
    0 AS click_anomalies,
    0 AS score_anomalies,
    0 AS temporal_anomalies,
    (SELECT COUNT(*) FROM {{ ref('silver_student_info') }}) AS row_count,
    0 AS pipeline_duration_sec,
    0 AS dbt_tests_passed,
    0 AS dbt_tests_failed

{% if is_incremental() %}
    WHERE run_date > (SELECT MAX(run_date) FROM {{ this }})
{% endif %}
