SELECT
    sv.id_student,
    sv.code_module,
    sv.code_presentation,
    sv.date,
    SUM(sv.sum_click) AS total_clicks,
    COUNT(DISTINCT sv.id_site) AS unique_resources,
    COUNT(DISTINCT sv.activity_type) AS unique_activity_types
FROM {{ ref('silver_student_vle') }} sv
GROUP BY sv.id_student, sv.code_module, sv.code_presentation, sv.date
