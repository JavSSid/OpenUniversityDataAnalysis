# OULAD Data Platform — End-to-End Plan

## Senior Data Engineer — Data Quality & Observability Pipeline

---

## 1. Dataset Overview

**OULAD** (Open University Learning Analytics Dataset) contains 7 interconnected tables capturing student demographics, online interactions, assessments, and course structures across 22 module presentations for ~32K students.

### Tables & Relationships

| Table | Rows | Key Columns | PK | FK Dependencies |
|-------|------|-------------|----|-----------------|
| `courses` | 22 | code_module, code_presentation, length | (code_module, code_presentation) | — |
| `assessments` | ~200 | id_assessment, assessment_type, date, weight | id_assessment | → courses |
| `vle` | ~6K | id_site, activity_type, week_from, week_to | id_site | → courses |
| `studentInfo` | ~32K | id_student, gender, region, age_band, disability, final_result | (id_student, code_module, code_presentation) | → courses |
| `studentRegistration` | ~32K | date_registration, date_unregistration | (id_student, code_module, code_presentation) | → courses, studentInfo |
| `studentAssessment` | ~173K | date_submitted, is_banked, score | (id_assessment, id_student) | → assessments, studentInfo |
| `studentVle` | ~10.6M | date, sum_click | (id_student, id_site, date) | → vle, studentInfo |

### Known Data Quality Issues

1. `date_unregistration` is **null for students who completed** the course
2. `imd_band` has **low/high ranges plus a "?" unknown** value
3. `score` can be **null when a student didn't submit** but the row still exists
4. `is_banked` is a **flag for credit transfers**, can be misleading without context
5. `region` contains **UK geographic codes** — PII-sensitive
6. `final_result` has only 4 values but needs consistency checks (Pass, Fail, Withdrawn, Distinction)
7. Courses have **B (Feb start) and J (Oct start)** presentations — structure differs, must be analysed separately

---

## 2. Architecture — Medallion Pipeline with Observability

```
┌──────────────┐     ┌─────────────────────────────────────────────────────┐
│  Kaggle CSV  │────▶│            CLOUD RUN (Python Ingestion)              │
│   (source)   │     │  Schema Validation → PII Hashing → Bulk Insert      │
└──────────────┘     └────────────────────┬────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BRONZE LAYER (BigQuery)                               │
│  7 tables: courses, assessments, vle, student_info, student_registration,   │
│  student_assessment, student_vle. Raw data as-is, typed, PII hashed.        │
│  TRUNCATE + reload per run. Ingestion_log table for audit.                  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │  ┌──────────────────────────────────────────────┐
          │  │    DATAFORM ASSERTIONS — Quality Checks      │
          ├──│  · NOT NULL checks on PK / required columns   │
          │  │  · Referential integrity (FK relationships)   │
          │  │  · Range checks (score 0-100, weight 0-100)   │
          │  │  · Accepted values (final_result, activity)   │
          │  └──────────────────────────────────────────────┘
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SILVER LAYER (Dataform → BigQuery)                     │
│  7 tables in silver dataset. Cleaned, type-cast, PII SHA-256 re-hashed,    │
│  derived columns (presentation_start, activity_category,                    │
│  assessment_result, has_unregistered, submission_delay_days).               │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │  ┌──────────────────────────────────────────────┐
          │  │    DATAFORM ASSERTIONS — Distribution & Drift│
          ├──│  · Cross-table consistency checks            │
          │  │  · Business rule enforcement                 │
          └──────────────────────────────────────────────┘
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       GOLD LAYER (Dataform → BigQuery)                       │
│  Analytics-ready marts in gold dataset:                                     │
│   · dim_student, dim_course                                                  │
│   · fact_student_interaction, fact_student_assessment                       │
│   · fact_engagement_summary, rpt_student_performance                        │
│   · rpt_quality_metrics (incremental, for Power BI)                         │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │
    ┌──────────┼────────────────────────────────────┐
    │          │                                     │
    ▼          ▼                                     ▼
┌──────────┐ ┌──────────────────────────────────┐ ┌─────────────────────────┐
│ ANOMALY  │ │      OPS REPORTING               │ │   POWER BI DASHBOARD    │
│ DETECTION │ │  · Slack alert (critical fails)  │ │ · Data Quality Monitor │
│ · Clicks  │ │  · HTML report (dev reference)   │ │ · Student demographics │
│ · Scores  │ │  · Audit log                     │ │ · Course performance   │
│ · Temp.   │ │                                  │ │ · Engagement trends    │
└──────────┘ └──────────────────────────────────┘ │ · At-risk prediction   │
                                                    └─────────────────────────┘
```

### Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Warehouse** | **BigQuery** | Serverless columnar warehouse, native Power BI connector, zero ops. All 3 layers (bronze/silver/gold) in same project, free tier for 44MB. |
| **SQL Transforms** | **Dataform** (native GCP) | Built into BigQuery console — replaces dbt. SQLX format, incremental models, assertions, scheduling. $0 cost. |
| **Python Jobs** | Cloud Run Jobs | Serverless container execution for ingestion + anomaly detection. Pay-per-use (~$0.01/run). |
| **Orchestration** | Dataform schedules + Cloud Scheduler | Dataform handles SQL DAG; Cloud Scheduler triggers Python jobs. No Airflow/Composer. |
| **Storage** | Cloud Storage (GCS) | Single bucket: oulad-raw-data for CSV uploads. |
| **Quality** | Dataform Assertions + Python | Native SQL assertions for schema/integrity; Python (SciPy) for statistical anomaly detection. |
| **Security** | GCP Secret Manager | All service account keys stored in Secret Manager, accessed via workload identity. |
| **BI & Analytics** | Power BI Desktop + Service | Native BigQuery connector (DirectQuery or Import). |

---

## 3. Phased Implementation Plan

### Phase 1: Foundation & Ingestion (Week 1)

**Goal**: Automated, validated ingestion from CSV to Bronze layer with full audit trail.

#### 1.1 Infrastructure Setup
- [ ] GCP project created with BigQuery, Dataform, Cloud Run, Cloud Scheduler enabled
- [ ] Terraform applied: BigQuery datasets (bronze/silver/gold), GCS bucket, Secret Manager, service account
- [ ] `.env` + Secret Manager setup for dev/prod secrets
- [ ] Dataform repository created in GCP Console, linked to GitHub

#### 1.2 Ingestion Module (`src/ingestion/`)
- [ ] `SchemaValidator` — validates raw CSV columns against canonical schema registry
- [ ] `BronzeLoader` — reads CSV → validates → hashes PII (SHA-256) → bulk inserts into BigQuery (`bronze` dataset)
- [ ] Tables truncated and reloaded each run (idempotent)
- [ ] Metadata columns: `_ingested_at`, `_source_file` per row
- [ ] `ingestion_log` table records every load (table, file, row count, errors)
- [ ] Audit logging on every write (who, what, when, row count)

#### 1.3 Seed Script (`scripts/seed_data.py`)
- [ ] Download OULAD zip from Kaggle/UCI (or accept local path)
- [ ] Extract to `data/raw/`
- [ ] Upload to GCS: `python scripts/seed_data.py --upload-gcs`
- [ ] Invoke `load_all_tables()` for initial BigQuery load

#### 1.4 Deliverable
- Cloud Run job `oulad-ingestion` triggers daily via Cloud Scheduler
- Tables populated in BigQuery `bronze` dataset
- `ingestion_log` table with load history
- Audit log entries in `bronze.audit_events`

---

### Phase 2: Data Quality — Dataform Assertions (Week 1-2)

**Goal**: Prevent bad data from poisoning downstream systems. Fail fast, fail gracefully.

#### 2.1 Assertion Suites (`dataform/assertions/`)
Native Dataform SQLX assertions replace Great Expectations. Each quality rule is a SQL query that returns failing rows:

| Assertion | Target | Tags |
|-----------|--------|------|
| NOT NULL on PKs (inline in each model) | All bronze+silver | `quality` |
| Referential integrity (FK) | student_assessment, student_vle, student_registration | `quality`, `bronze` |
| Score 0–100 | student_assessment | `quality`, `bronze` |
| sum_click >= 0 | student_vle | `quality`, `bronze` |
| Weight 0–100 | assessments | `quality`, `bronze` |
| Valid `final_result` ∈ {Pass,Fail,Withdrawn,Distinction} | student_info | `quality`, `bronze` |
| Valid `assessment_type` ∈ {TMA,CMA,Exam} | assessments | `quality`, `bronze` |
| Valid `activity_type` (17 known values) | vle | `quality`, `bronze` |

#### 2.2 Failure Handling
- Dataform assertions fail the run if any rows returned (configurable per-assertion)
- Failed assertions written to `dataform_assertions` dataset in BigQuery
- Slack notification via Dataform webhook integration

#### 2.3 Deliverable
- `dataform/assertions/` — 3 assertion SQLX files covering all critical rules
- Inline assertions in model configs (uniqueKey, nonNull)
- `config/quality_rules.yaml` maintained as documentation SSOT

---

### Phase 3: Transform — Dataform Medallion (Week 2-3)

**Goal**: Clean, conformed, analytics-ready data in Silver/Gold layers.

#### 3.1 Bronze → Silver (`dataform/definitions/silver/`)

| Model | Source | Key Transforms |
|-------|--------|----------------|
| `silver_courses` | bronze.courses | Cast to types, derive presentation_start |
| `silver_assessments` | bronze.assessments | Normalize weight, derive weight_pct |
| `silver_vle` | bronze.vle | Recode activity_type to activity_category |
| `silver_student_info` | bronze.studentInfo | SHA-256 re-hash PII at rest |
| `silver_student_registration` | bronze.studentRegistration | Handle null date_unregistration, derive registration_timing |
| `silver_student_assessment` | bronze.studentAssessment | Derive passed/failed/not_submitted, submission_delay_days |
| `silver_student_vle` | bronze.studentVle | Join activity metadata, filter negative clicks |

#### 3.2 Silver → Gold (`dataform/definitions/gold/`)

| Mart | Description |
|------|-------------|
| `dim_student` | Student demographics + registration details |
| `dim_course` | Course/presentation dimension with assessment summary |
| `fact_student_interaction` | Daily interaction clicks by student |
| `fact_student_assessment` | Per-assessment scores with submission timing |
| `fact_engagement_summary` | Weekly aggregate: active_days, total_clicks, unique_resources |
| `rpt_student_performance` | Feature-engineered view: total_clicks, avg_score, dropout_signals |
| `rpt_quality_metrics` | Incremental quality metrics table for Power BI |

#### 3.3 Dataform Assertions (inline in model configs)
- `uniqueKey` for PK uniqueness on dim_student, dim_course
- `nonNull` for required columns on all models
- Accepted values enforced via `assert_accepted_values.sqlx`

#### 3.4 Deliverable
- `dataform/` directory with 21 SQLX files + 3 assertion files
- Materialized tables in BigQuery silver + gold datasets
- Dataform schedules run daily at 06:00 UTC

---

### Phase 4: Anomaly Detection (Week 3)

**Goal**: Identify statistical outliers and temporal inconsistencies automatically.

#### 4.1 Click Anomalies (`src/quality/anomaly/anomaly_detector.py`)
- **Z-score threshold** (default 3.0): flag students with sum_click > 3σ from the per-course mean
- **Absolute threshold** (default 5,000/day): hard cap for bot detection
- **Output**: DataFrame with `id_student`, `anomaly_reason`, `anomaly_score`

#### 4.2 Assessment Anomalies
- **IQR method**: lower/upper fence = Q1 − 1.5×IQR / Q3 + 1.5×IQR — flags extreme scores
- **Zero-activity pattern**: detect students who submitted exam but had minimal VLE activity

#### 4.3 Temporal Anomalies
- **VLE before registration**: `date < date_registration` → data integrity issue or backdated registration
- **Assessment before registration**: impossible submission dates
- **Activity after unregistration**: student withdrew but continued clicking

#### 4.4 Delivery
- `AnomalyDetector.detect_all()` — single call returns consolidated result dict
- Anomalies written to `gold.anomaly_flags` table for reporting
- Thresholds configurable in `config/pipeline_config.yaml`

---

### Phase 5: Reporting & Observability (Week 3-4)

**Goal**: Expose pipeline quality metrics to Power BI for trend analysis and alert engineering on critical failures.

#### 5.1 Quality Metrics Mart (`dbt/models/gold/rpt_quality_metrics.sql`)
A Gold table materialized in PostgreSQL that Power BI queries directly:

| Column | Source | Description |
|--------|--------|-------------|
| `run_date` | Pipeline execution timestamp | Partition key for time-series |
| `table_name` | Per-table breakdown | studentInfo, studentVle, ... |
| `layer` | bronze / silver | Which pipeline stage |
| `expectations_evaluated` | GE summary | Count of expectations run |
| `expectations_passed` | GE summary | Passed count |
| `expectations_failed` | GE summary | Failed count |
| `pass_rate` | Derived | passed / evaluated |
| `anomalies_detected` | AnomalyDetector | Sum of all anomaly types |
| `click_anomalies` | AnomalyDetector | Click outliers count |
| `score_anomalies` | AnomalyDetector | Score outliers count |
| `temporal_anomalies` | AnomalyDetector | Temporal inconsistencies |
| `row_count` | Ingestion | Rows ingested per table |
| `pipeline_duration_sec` | Airflow | End-to-end pipeline latency |
| `dbt_tests_passed` | dbt test | Number of passed dbt tests |
| `dbt_tests_failed` | dbt test | Number of failed dbt tests |

This table is materialized **incrementally** (append-only) so Power BI can build time-series charts of quality trends over days/weeks.

#### 5.2 Power BI — Data Quality Monitor Page
Built on `rpt_quality_metrics` with these visuals:

| Visual | Purpose |
|--------|---------|
| **Pass rate gauge** | Overall pipeline health — red/yellow/green threshold bands |
| **Pass rate by table (bar)** | Spot which table is degrading |
| **Pass rate trend (line)** | 30-day rolling quality score — detect drift early |
| **Anomaly count KPI cards** | Total, click, score, temporal — with sparklines |
| **Anomaly trend (area)** | Daily anomaly volume — spike detection |
| **Table row count comparison** | Bar chart of current vs previous run — detect missing data |
| **Pipeline latency (bar)** | Execution time per run — performance regression detection |
| **dbt test results (table)** | List of failed dbt tests with details |

#### 5.3 Slack Alert (`src/reporting/slack_notifier.py`)
```
╔══════════════════════════════════════╗
║  🟢 OULAD Pipeline — 97.3% Pass     ║
║  172/177 expectations passed         ║
║  42 anomalies flagged                ║
║  ⚠️  studentVle: 1 warning (clicks)  ║
║  Full report: Power BI > DQ Monitor ║
╚══════════════════════════════════════╝
```
- **Critical** (≤90% pass rate): `@channel` + red X + link to Power BI DQ page
- **Warning** (90-95%): no mention, yellow warning
- **Healthy** (>95%): green check, summary only
- **PagerDuty/Email** fallback if Slack unreachable

#### 5.4 HTML Report (`src/reporting/html_reporter.py`)
Simplified version kept for quick terminal reference during dev — links to Power BI as the SSOT.

#### 5.5 Deliverable
- `dbt/models/gold/rpt_quality_metrics.sql` — incremental materialization
- Power BI Data Quality Monitor page (within OULAD_Dashboard.pbix)
- `SlackNotifier` — alerts with Power BI deep-link
- `HtmlReporter` — lightweight dev reference

---

### Phase 6: Power BI Dashboard (Week 3-4)

**Goal**: Build an interactive analytics dashboard on top of the Gold layer for stakeholder consumption.

#### 6.1 Data Source Connection
- Power BI Desktop connects to PostgreSQL via **native PostgreSQL connector**
- **DirectQuery mode** (not Import) — queries hit Gold views directly; no data duplication into Power BI
- Row-level security (RLS) via PostgreSQL roles if multi-user access is needed later
- Connection string stored in Power BI Data Source settings (not embedded in `.pbix`)

#### 6.2 Dashboard Pages & Metrics

| Page | Visuals | Gold Models Used |
|------|---------|-----------------|
| **Data Quality Monitor** *(default landing page)* | Pass rate gauge (red/yellow/green), pass rate by table (bar), 30-day pass rate trend (line), anomaly KPIs with sparklines, anomaly trend (area), row count comparison, pipeline latency bar, failed dbt tests table | `rpt_quality_metrics` |
| **Student Overview** | Total students (cards), gender/age/region slicers, final_result pie chart, prev_attempts histogram | `dim_student` |
| **Course Performance** | Pass/fail/distinction by module (bar), presentation comparison (line), avg score by assessment type | `dim_course`, `fact_student_assessment` |
| **Engagement Analysis** | Daily clicks trend (area), clicks by activity_type (tree map), active days vs final_result (scatter) | `fact_student_interaction`, `fact_engagement_summary` |
| **At-Risk Identification** | Avg clicks trend: Withdrawn vs Pass (overlay), score trajectory per student (line), interaction drop-off flag table | `rpt_student_performance`, `fact_engagement_summary` |

#### 6.3 DAX Measures (examples)
```
Pass Rate = DIVIDE(COUNTROWS(FILTER(dim_student, dim_student[final_result] IN {"Pass","Distinction"})), COUNTROWS(dim_student))

Avg Engagement Score = AVERAGEX(fact_student_interaction, fact_student_interaction[sum_click]) / MAX(fact_engagement_summary[max_clicks])

Dropout Signal = COUNTROWS(FILTER(fact_engagement_summary, fact_engagement_summary[active_days] < 5 && fact_engagement_summary[assessment_completion_rate] < 0.5))
```

#### 6.4 Refresh Strategy
- Power BI Desktop: manual refresh during development
- Power BI Service: scheduled daily refresh (triggers after Airflow pipeline completes, via Power BI API or XMLA endpoint)
- Gold views are materialized by dbt; Power BI reads the results — no modeling in Power BI, all logic in dbt

#### 6.5 Deliverable
- `dashboard/OULAD_Dashboard.pbix` — Power BI Desktop file with all pages + DAX measures
- `dashboard/dataset_metadata.json` — mapping of Gold views to Power BI fields
- Data Quality page embedded in the ops report workflow

---

### Phase 7: Orchestration — Dataform Schedules + Cloud Scheduler (Week 4)

**Goal**: Fully automated, scheduled, observable pipeline — zero ops.

#### 7.1 Daily Pipeline Schedule
```
Schedule: 0 6 * * * (daily at 06:00 UTC)

┌──────────────────┐
│ Cloud Scheduler   │  triggers Cloud Run Job `oulad-ingestion`
│ 05:00 UTC         │  → Python: download, validate, hash PII, load to BQ bronze
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Cloud Run Job     │  Loads CSVs → BigQuery bronze dataset
│ (ingestion)       │  Writes audit events & ingestion_log
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Dataform Schedule │  Triggered by GCS event or time-based
│ 06:00 UTC         │  → bronze views → silver tables → gold tables → assertions
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Dataform          │  Materializes silver/gold, runs assertions
│ (tag: all)        │  Fails on assertion failure → Slack webhook
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Cloud Run Job     │  Anomaly detection + Power BI refresh trigger
│ (analysis)        │  (optional, can run in same image as ingestion)
└──────────────────┘
```

#### 7.2 Scheduling Mechanism
- **Dataform built-in scheduler**: Set up in GCP Console under Dataform → Workflow settings. Tag-based: `bronze` views first, then `silver`, then `gold`, then `assertions`.
- **Cloud Scheduler**: HTTP trigger invokes Cloud Run Job for Python steps (ingestion, anomaly). Retry with 2 attempts, exponential backoff.
- **No Airflow required** — saves $150-300/mo on Composer/GKE.

#### 7.3 Deliverable
- `dataform/workflow_settings.yaml` — schedule definitions
- `terraform/main.tf` — Cloud Scheduler + Cloud Run Jobs
- No Airflow DAGs needed; Python steps run as containerized Cloud Run Jobs

---

### Phase 8: Security & Compliance (Cross-cutting, Weeks 1-4)

**Goal**: Protect PII, ensure auditability, prevent credential leakage.

#### 7.1 Secrets Management (`src/security/secrets_manager.py`)
- Production: HashiCorp Vault API integration
- Development: `.env` file loaded via `python-dotenv`
- All DB passwords, API keys, encryption keys stored here — **never in code**
- Secret rotation ready: versioned paths in Vault

#### 7.2 PII Protection
| Field | Classification | Treatment |
|-------|---------------|-----------|
| `region` | PII | SHA-256 hashed at Bronze ingestion; original never stored in warehouse |
| `imd_band` | Sensitive | Range bucketed, low-cardinality → hashed only if config flag set |
| `gender` | Non-PII | Retained as-is (needed for analytics) |
| `age_band` | Non-PII | Retained |
| `disability` | Sensitive | Pseudonymized via hashing if opt-in |
| `id_student` | PII by association | Keep as-is (anonymized in source dataset) but treat as sensitive |

#### 7.3 Encryption in Transit & At Rest
- **In transit**: All service-to-service via internal Docker network (isolated). TLS optional for dev.
- **At rest**: Parquet files in MinIO can be encrypted with server-side SSE-S3.
- **Audit**: All encryption operations logged with timestamp and principal.

#### 7.4 Audit Logging (`src/security/audit_logger.py`)
- Immutable append-only log stored in `s3://oulad-audit/logs/year=YYYY/month=MM/`
- Log format: JSON Lines (one event per line)
- Events captured:
  - Data ingestion (table, row count, file name)
  - Quality check execution (pass/fail counts)
  - Anomaly detection results
  - Report generation
  - DAG execution (start, end, failure)
  - Secret access (accessor, resource, timestamp)

#### 7.5 Access Control (RBAC)
- **Airflow**: Admin, Operator, Viewer roles (built-in)
- **MinIO**: Bucket-level policies — raw=read-only for transforms, curated=write for dbt
- **PostgreSQL**: Schema-level grants, no direct table access from outside Airflow
- **Service accounts**: Individual accounts for each service, rotated quarterly

---

## 4. Error Handling & Resilience Strategy

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| CSV file missing | `FileNotFoundError` in load | Skip table, log warning, alert Slack |
| Schema mismatch | Great Expectations critical fail | Halt table, no Silver load, alert |
| Transient DB connection | Airflow retry (2x, backoff) | Retry, then alert on 3rd failure |
| MinIO/S3 unavailable | `S3ConnectionError` | Retry with backoff, circuit breaker after 3 |
| Pipeline stuck > SLA | Airflow SLA miss callback | Alert to Slack, investigate |
| Anomaly spike > 5% | Daily trend comparison | Warning in report, escalation if sustained |
| Secret rotation fails | Vault `ConnectError` | Use cached secret (24h TTL), alert ops |

---

## 5. Scalability Considerations

| Scenario | Current (PostgreSQL) | Path to Scale (Distributed) |
|----------|---------------------|----------------------------|
| Dataset size | 44 MB (OULAD) | 10+ TB |
| Engine | PostgreSQL single-node | Amazon Redshift / Snowflake |
| Storage | PostgreSQL tables | Columnar cloud warehouse |
| Quality checks | Pandas GE | PySpark GE integration |
| Anomaly detection | Pandas + SciPy | Distributed PySpark UDF |
| Orchestration | Airflow (same) | Airflow (same) |
| Migration effort | — | Rewrite dbt models for warehouse dialect (minimal) |

---

## 6. Project Structure (Final)

```
open-university-data-platform/
│
├── .env.example                  # Template for secrets
├── .gitignore
├── Makefile                      # dev commands (make up, make test, make lint)
├── README.md
├── PLAN.md                       # ← this document
│
├── config/
│   ├── pipeline_config.yaml      # Pipeline & storage configuration
│   └── quality_rules.yaml        # Single source of truth for all quality rules
│
├── cloudbuild.yaml               # Cloud Build CI/CD (build + deploy Cloud Run)
├── cloudrun/
│   └── ingestion/
│       ├── Dockerfile            # Container for Python ingestion + anomaly
│       └── requirements.txt      # Python dependencies (GCP libs, pandas, scipy)
│
├── dashboard/
│   ├── OULAD_Dashboard.pbix      # Power BI Desktop file
│   └── dataset_metadata.json     # Gold view → Power BI field mapping
│
├── data/
│   ├── raw/                      # Original CSVs (gitignored)
│   ├── audit/                    # JSON Lines audit trail (gitignored)
│   └── reports/                  # HTML reports (gitignored)
│
├── dataform/
│   ├── dataform.json             # Project config (BigQuery target)
│   ├── workflow_settings.yaml    # Schedule definitions
│   ├── includes/
│   │   └── constants.js          # Shared constants
│   ├── definitions/
│   │   ├── bronze/               # Source declarations + views (7 files)
│   │   ├── silver/               # Cleaned tables (7 files)
│   │   └── gold/                 # Analytics marts (7 files)
│   ├── assertions/               # Quality assertions (3 files)
│   └── tests/                    # Custom test SQL (optional)
│
├── dbt/                          # Legacy dbt project (archived reference)
│
├── terraform/
│   ├── main.tf                   # BigQuery, GCS, Secret Manager, Cloud Run, Dataform
│   ├── variables.tf
│   ├── outputs.tf
│   └── backend.tf
│
├── notebooks/
│   └── 01_exploratory_analysis.ipynb
│
├── scripts/
│   └── seed_data.py              # Download & initial load
│
└── src/
    ├── ingestion/
    │   ├── __init__.py
    │   └── load_to_bronze.py     # SchemaValidator + BronzeLoader
    │
    ├── quality/
    │   ├── __init__.py
    │   ├── quality_validator.py   # Great Expectations integration
    │   └── anomaly/
    │       ├── __init__.py
    │       └── anomaly_detector.py
    │
    ├── reporting/
    │   ├── __init__.py
    │   ├── html_reporter.py
    │   ├── slack_notifier.py
    │   └── templates/
    │       └── daily_report.html
    │
    └── security/
        ├── __init__.py
        ├── secrets_manager.py     # Vault / env-based secret resolution
        └── audit_logger.py        # Immutable JSON Lines audit trail
```

---

## 7. Getting Started (Dev)

```bash
# 1. Clone and configure
git clone <repo>
cd open-university-data-platform
cp .env.example .env           # fill in GCP service account fields

# 2. Provision GCP infrastructure (one-time)
cd terraform
terraform init && terraform apply

# 3. Upload raw data to GCS + load to BigQuery bronze
cd ..
python scripts/seed_data.py --upload-gcs

# 4. Deploy Dataform (SQL transforms)
#    a. Open GCP Console → BigQuery → Dataform
#    b. Create repository from GitHub
#    c. Push dataform/ directory to main branch
#    d. Run "dataform run --all" to materialize silver + gold

# 5. Build & deploy Cloud Run for Python jobs
gcloud builds submit --tag gcr.io/oulad-platform/oulad-ingestion
gcloud run jobs create oulad-ingestion --image gcr.io/oulad-platform/oulad-ingestion

# 6. Open Power BI dashboard
#    - Open dashboard/OULAD_Dashboard.pbix in Power BI Desktop
#    - Data Source: BigQuery (project=oulad-platform, dataset=gold)
#    - Auth: Service Account (oulad-pipeline-sa)
#    - Click Refresh → dashboards populate from gold views
```

---

## 8. Key Design Decisions & Tradeoffs

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| **BigQuery over PostgreSQL** | Serverless, zero ops, free tier covers 44MB. Native Dataform + Power BI connectors. | Cloud SQL (still requires ops, no Dataform) |
| **Dataform over dbt** | Native GCP, $0 cost, built into BigQuery Console. No adapter config, no separate deployment. | dbt-core + Cloud Composer ($150-300/mo for GKE) |
| **Dataform assertions over Great Expectations** | SQL-native, no Python runtime needed for quality. Runs as part of same Dataform execution. | Great Expectations (separate Python env, more complex) |
| **Cloud Run Jobs over Cloud Composer** | Serverless, pay-per-use (~$0.01/run). No always-on GKE cluster. | Cloud Composer 2 ($150-300/mo) |
| **TRUNCATE + reload Bronze** | Idempotent, simple, no merge logic needed for a static snapshot dataset. | Incremental upserts (overengineered for academic data) |
| **SHA-256 PII hashing** | Irreversible pseudonymization, deterministic for joins, no key management overhead for non-critical PII. | AES encryption (key rotation overhead for low-risk PII) |

---

## 9. Success Metrics

| Metric | Target | How Measured |
|--------|--------|-------------|
| Quality check pass rate | > 95% per run | Dataform assertion pass rate |
| Pipeline freshness | < 24h from source | `_ingested_at` max |
| Anomaly detection recall | > 90% synthetic anomalies found | Injection tests |
| Pipeline duration | < 30 min end-to-end | Cloud Run + Dataform execution logs |
| Alert response time | < 15 min on critical failure | Slack acknowledgment |
| Data volume completeness | 100% of source rows in Bronze | Row count comparison |
| PII exposure incidents | 0 | Audit log review |

---

## 10. GCP Migration — PostgreSQL → BigQuery

### Rationale

Migrating from local PostgreSQL to GCP BigQuery for a fully cloud-native, serverless architecture:

| Factor | PostgreSQL (Before) | BigQuery (After) |
|--------|-------------------|-------------------|
| Ops overhead | Manual Docker/container mgmt | Serverless — zero ops |
| Scaling | Manual sharding/replication | Auto-scale — petabytes |
| Cost | Local machine cost | ~$0.10/month for 44MB (free tier) |
| dbt adapter | dbt-postgres | dbt-bigquery (feature-rich) |
| Power BI | PostgreSQL DirectQuery | Native BigQuery connector |
| Security | .env file | Secret Manager + IAM |
| Orchestration | Local Docker Airflow | Cloud Composer 2 (managed) |

### Key SQL Dialect Changes

| PostgreSQL | BigQuery |
|------------|----------|
| `RIGHT(col, 1)` | `SUBSTR(col, -1)` |
| `ENCODE(SHA256(CAST(x AS BYTEA)), 'hex')` | `TO_HEX(SHA256(CAST(x AS STRING)))` |
| `x::DOUBLE PRECISION` | `CAST(x AS FLOAT64)` |
| `incremental_strategy: delete+insert` | `incremental_strategy: merge` |
| `FROM bronze.table` | Same (dataset.table format) |

### Migration Files Changed

| File | Change |
|------|--------|
| `config/pipeline_config.yaml` | `type: postgres` → `type: bigquery`, added GCS + project config |
| All dbt/ files | **Archived** — replaced by `dataform/` directory |
| `src/ingestion/load_to_bronze.py` | PostgreSQL COPY → BigQuery `to_gbq()` + GCS |
| `src/security/secrets_manager.py` | .env/Vault → GCP Secret Manager |
| `src/security/audit_logger.py` | Local files → optional Cloud Logging |
| `scripts/seed_data.py` | Local PostgreSQL → GCS upload + BigQuery load |
| `.env.example` | PostgreSQL creds → GCP service account fields |
| `docker/docker-compose.yml` | Local stack → Dataform + Cloud Run instructions |
| `docker/airflow/requirements-airflow.txt` | `dbt-postgres` → `dbt-bigquery` + GCP libs |
| `terraform/main.tf` | **Removed Composer** → Dataform + Cloud Run Jobs + Cloud Scheduler |

### New Files Created

| File | Purpose |
|------|---------|
| `dataform/dataform.json` | Dataform project config (BigQuery warehouse) |
| `dataform/workflow_settings.yaml` | Schedule definitions (daily at 06:00 UTC) |
| `dataform/definitions/bronze/*.sqlx` | Source declarations + views (8 files) |
| `dataform/definitions/silver/*.sqlx` | Cleaned tables with transforms (7 files) |
| `dataform/definitions/gold/*.sqlx` | Analytics marts + incremental quality metrics (7 files) |
| `dataform/assertions/*.sqlx` | Quality assertions: accepted values, ranges, FK integrity (3 files) |
| `dataform/includes/constants.js` | Shared constants (PII fields, valid values, activity map) |
| `terraform/main.tf` | BigQuery datasets, GCS, Secret Manager, Cloud Run Jobs, Cloud Scheduler, IAM |
| `terraform/variables.tf` | Terraform input variables |
| `terraform/outputs.tf` | Infrastructure outputs |
| `cloudbuild.yaml` | Cloud Build CI/CD: build container → push to Artifact Registry → deploy Cloud Run job |
| `cloudrun/ingestion/Dockerfile` | Container for Python ingestion + anomaly detection + Slack alerts |
| `cloudrun/ingestion/requirements.txt` | Python dependencies pinned for container |

---

### CI/CD Pipeline

```
Git push to main
      │
      ▼
Cloud Build Trigger
      │
      ├── docker build -t oulad-ingestion:latest
      ├── docker push to Artifact Registry
      └── gcloud run jobs deploy oulad-ingestion --image=...
```

- **Dataform layer**: Built-in CI/CD via GCP Console (GitHub PR previews, auto-deploy on merge)
- **Python layer**: `cloudbuild.yaml` auto-builds and deploys the Cloud Run container on push to `main`
- **Terraform**: Manual `terraform apply` for infrastructure changes (state stored in GCS bucket)

### Migration Steps

1. **Provision GCP infrastructure** via Terraform (BigQuery + Cloud Run + Scheduler):
   ```bash
   cd terraform
   gcloud auth application-default login
   terraform init && terraform apply
   ```

2. **Upload raw data** to GCS + load to BigQuery bronze:
   ```bash
   python scripts/seed_data.py --upload-gcs
   ```

3. **Deploy Dataform** (no CLI — via GCP Console):
   - Open GCP Console → BigQuery → Dataform
   - Create repository, connect to GitHub, push `dataform/` to main
   - Run "dataform run --all" to materialize silver + gold
   - Set schedule in Workflow Settings

4. **Build & deploy Cloud Run** for Python ingestion:
   ```bash
   gcloud builds submit --tag gcr.io/oulad-platform/oulad-ingestion
   gcloud run jobs create oulad-ingestion --image gcr.io/oulad-platform/oulad-ingestion
   ```

5. **Connect Power BI** to BigQuery dataset `gold`:
   - Auth: Service Principal (oulad-pipeline-sa)
   - Mode: Import (44MB fits in Power BI Desktop free)

6. **Verify** the pipeline runs end-to-end via Cloud Scheduler
