WITH source AS (
    SELECT * FROM {{ ref('bronze_vle') }}
)

SELECT
    id_site,
    code_module,
    code_presentation,
    activity_type,
    week_from,
    week_to,
    CASE
        WHEN activity_type IN ('forumng', 'glossary') THEN 'communication'
        WHEN activity_type IN ('oucontent', 'htmlactivity', 'page', 'subpage') THEN 'content'
        WHEN activity_type IN ('quiz', 'externalquiz', 'questionnaire') THEN 'assessment'
        WHEN activity_type IN ('resource', 'url', 'folder', 'sharedsubpage') THEN 'reference'
        WHEN activity_type IN ('homepage', 'dataplus', 'dualpane', 'repeatactivity') THEN 'tool'
        ELSE 'other'
    END AS activity_category
FROM source
