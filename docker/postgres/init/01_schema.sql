-- OULAD — PostgreSQL Schema Initialization
-- All three layers (bronze, silver, gold) live in PostgreSQL.

-- ── Bronze layer (raw ingested data) ─────────────────────
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.courses (
    code_module         TEXT NOT NULL,
    code_presentation   TEXT NOT NULL,
    length              INTEGER,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT,
    PRIMARY KEY (code_module, code_presentation)
);

CREATE TABLE IF NOT EXISTS bronze.assessments (
    id_assessment       BIGINT NOT NULL,
    code_module         TEXT NOT NULL,
    code_presentation   TEXT NOT NULL,
    assessment_type     TEXT,
    date                INTEGER,
    weight              DOUBLE PRECISION,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT,
    PRIMARY KEY (id_assessment)
);

CREATE TABLE IF NOT EXISTS bronze.vle (
    id_site             BIGINT NOT NULL,
    code_module         TEXT NOT NULL,
    code_presentation   TEXT NOT NULL,
    activity_type       TEXT,
    week_from           INTEGER,
    week_to             INTEGER,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT,
    PRIMARY KEY (id_site)
);

CREATE TABLE IF NOT EXISTS bronze.student_info (
    id_student          BIGINT NOT NULL,
    code_module         TEXT NOT NULL,
    code_presentation   TEXT NOT NULL,
    gender              TEXT,
    region              TEXT,
    highest_education   TEXT,
    imd_band            TEXT,
    age_band            TEXT,
    num_of_prev_attempts INTEGER,
    studied_credits     INTEGER,
    disability          TEXT,
    final_result        TEXT,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT,
    PRIMARY KEY (id_student, code_module, code_presentation)
);

CREATE TABLE IF NOT EXISTS bronze.student_registration (
    id_student          BIGINT NOT NULL,
    code_module         TEXT NOT NULL,
    code_presentation   TEXT NOT NULL,
    date_registration   INTEGER,
    date_unregistration DOUBLE PRECISION,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT,
    PRIMARY KEY (id_student, code_module, code_presentation)
);

CREATE TABLE IF NOT EXISTS bronze.student_assessment (
    id_assessment       BIGINT NOT NULL,
    id_student          BIGINT NOT NULL,
    date_submitted      INTEGER,
    is_banked           INTEGER,
    score               DOUBLE PRECISION,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT,
    PRIMARY KEY (id_assessment, id_student)
);

CREATE TABLE IF NOT EXISTS bronze.student_vle (
    code_module         TEXT NOT NULL,
    code_presentation   TEXT NOT NULL,
    id_student          BIGINT NOT NULL,
    id_site             BIGINT NOT NULL,
    date                INTEGER NOT NULL,
    sum_click           INTEGER,
    _ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    _source_file        TEXT,
    PRIMARY KEY (id_student, id_site, date)
);

-- ── Silver layer (cleaned) ──────────────────────────────
CREATE SCHEMA IF NOT EXISTS silver;

-- ── Gold layer (analytics marts) ────────────────────────
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.rpt_quality_metrics (
    run_date                DATE NOT NULL,
    table_name              TEXT NOT NULL,
    layer                   TEXT NOT NULL,
    expectations_evaluated  INT NOT NULL DEFAULT 0,
    expectations_passed     INT NOT NULL DEFAULT 0,
    expectations_failed     INT NOT NULL DEFAULT 0,
    pass_rate               NUMERIC(5,2) NOT NULL DEFAULT 0,
    anomalies_detected      INT NOT NULL DEFAULT 0,
    click_anomalies         INT NOT NULL DEFAULT 0,
    score_anomalies         INT NOT NULL DEFAULT 0,
    temporal_anomalies      INT NOT NULL DEFAULT 0,
    row_count               BIGINT NOT NULL DEFAULT 0,
    pipeline_duration_sec   INT NOT NULL DEFAULT 0,
    dbt_tests_passed        INT NOT NULL DEFAULT 0,
    dbt_tests_failed        INT NOT NULL DEFAULT 0,
    PRIMARY KEY (run_date, table_name, layer)
);

-- ── Audit trail ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bronze.audit_events (
    id          BIGSERIAL PRIMARY KEY,
    event_time  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action      TEXT NOT NULL,
    resource    TEXT NOT NULL,
    principal   TEXT NOT NULL DEFAULT 'pipeline',
    detail      JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_action ON bronze.audit_events (action);
CREATE INDEX IF NOT EXISTS idx_audit_time   ON bronze.audit_events (event_time DESC);

-- ── Ingestion tracking ──────────────────────────────────
CREATE TABLE IF NOT EXISTS bronze.ingestion_log (
    id              BIGSERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    row_count       BIGINT NOT NULL,
    errors          JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
