"""
OULAD — Ingestion: Schema Validator & Bronze Loader (BigQuery)

Validates raw CSVs against defined schemas and loads them into
BigQuery Bronze datasets.

Security:
  - All PII fields are flagged and hashed at ingestion time (SHA-256)
  - Credentials sourced from Secret Manager / environment, never hardcoded
  - Audit log written for every load
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from src.security.secrets_manager import SecretsManager
from src.security.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

# Schema Registry
TABLE_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "courses": {
        "db_table": "courses",
        "dataset": "bronze",
        "columns": ["code_module", "code_presentation", "length"],
        "aliases": {"module_presentation_length": "length"},
        "pii_fields": [],
        "pk": ["code_module", "code_presentation"],
    },
    "assessments": {
        "db_table": "assessments",
        "dataset": "bronze",
        "columns": ["code_module", "code_presentation", "id_assessment", "assessment_type", "date", "weight"],
        "pii_fields": [],
        "pk": ["id_assessment"],
    },
    "vle": {
        "db_table": "vle",
        "dataset": "bronze",
        "columns": ["id_site", "code_module", "code_presentation", "activity_type", "week_from", "week_to"],
        "pii_fields": [],
        "pk": ["id_site"],
    },
    "studentInfo": {
        "db_table": "student_info",
        "dataset": "bronze",
        "columns": [
            "code_module", "code_presentation", "id_student", "gender", "region",
            "highest_education", "imd_band", "age_band", "num_of_prev_attempts",
            "studied_credits", "disability", "final_result",
        ],
        "pii_fields": ["region", "imd_band"],
        "pk": ["id_student", "code_module", "code_presentation"],
    },
    "studentRegistration": {
        "db_table": "student_registration",
        "dataset": "bronze",
        "columns": ["code_module", "code_presentation", "id_student", "date_registration", "date_unregistration"],
        "pii_fields": [],
        "pk": ["id_student", "code_module", "code_presentation"],
    },
    "studentAssessment": {
        "db_table": "student_assessment",
        "dataset": "bronze",
        "columns": ["id_assessment", "id_student", "date_submitted", "is_banked", "score"],
        "pii_fields": [],
        "pk": ["id_assessment", "id_student"],
    },
    "studentVle": {
        "db_table": "student_vle",
        "dataset": "bronze",
        "columns": ["code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"],
        "pii_fields": [],
        "pk": ["id_student", "id_site", "date"],
    },
}


class SchemaValidator:
    """Validate raw CSV structure against defined schemas before loading."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self.schema_def = TABLE_SCHEMAS.get(table_name)
        if self.schema_def is None:
            raise ValueError(f"Unknown table: {table_name}. Options: {list(TABLE_SCHEMAS.keys())}")

    def validate_schema(self, df: pd.DataFrame) -> List[str]:
        """Check that required columns exist.
        Returns a list of validation error messages (empty = valid)."""
        errors: List[str] = []
        expected_cols = set(self.schema_def["columns"])
        actual_cols = set(df.columns.str.strip())

        missing = expected_cols - actual_cols
        if missing:
            errors.append(f"Missing columns: {missing}")

        extra = actual_cols - expected_cols
        if extra:
            errors.append(f"Unexpected columns: {extra}")

        return errors


class BronzeLoader:
    """Load validated CSV data into BigQuery Bronze dataset."""

    def __init__(self, secrets: Optional[SecretsManager] = None):
        self.secrets = secrets or SecretsManager()
        self.config = self._load_config()
        self.audit = AuditLogger()
        self.bq_client = self._create_bq_client()

    def _load_config(self) -> dict:
        config_path = Path(__file__).parents[2] / "config" / "pipeline_config.yaml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        return self._resolve_env_placeholders(config)

    def _resolve_env_placeholders(self, value):
        if isinstance(value, dict):
            return {k: self._resolve_env_placeholders(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._resolve_env_placeholders(v) for v in value]
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            expression = value[2:-1]
            key, _, default = expression.partition(":")
            return os.environ.get(key, default or value)
        return value

    def _create_bq_client(self):
        project = self.config["storage"]["bronze"]["project"]
        return bigquery.Client(project=project)

    def _anonymize_pii(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """SHA-256 hash PII fields to pseudonymize sensitive data."""
        schema_def = TABLE_SCHEMAS.get(table_name)
        if not schema_def:
            return df
        for col in schema_def["pii_fields"]:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: hashlib.sha256(str(x).encode()).hexdigest()[:16]
                    if pd.notna(x) else None
                )
        return df

    def _ensure_table_exists(self, table_ref: str, df: pd.DataFrame) -> None:
        """Create table if it doesn't exist, using the DataFrame schema."""
        try:
            self.bq_client.get_table(table_ref)
        except NotFound:
            job_config = bigquery.LoadJobConfig(
                autodetect=True,
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            )
            # Load a single row to create the table
            sample = df.head(1)
            job = self.bq_client.load_table_from_dataframe(
                sample, table_ref, job_config=job_config
            )
            job.result()
            logger.info(f"Created table {table_ref} via autodetect")

    def load(
        self,
        table_name: str,
        csv_path: str,
        execution_ts: Optional[datetime] = None,
    ) -> Tuple[int, List[str]]:
        """Load CSV → validate → anonymize → write to BigQuery Bronze.

        Returns:
            Tuple of (row_count, error_list)
        """
        exec_ts = execution_ts or datetime.now(timezone.utc)
        validator = SchemaValidator(table_name)
        schema_def = TABLE_SCHEMAS[table_name]

        logger.info(f"Ingesting {table_name} from {csv_path}")

        # 1. Read CSV
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            return 0, [f"CSV read failed: {e}"]

        # 2. Apply column aliases
        aliases = schema_def.get("aliases", {})
        if aliases:
            df = df.rename(columns=aliases, errors="ignore")

        # 3. Schema validation
        errors = validator.validate_schema(df)
        if errors:
            logger.error(f"Schema validation failed for {table_name}: {errors}")
            return 0, errors

        # 4. Normalise column names
        df.columns = df.columns.str.strip()

        # 5. Cast numeric columns
        int_cols = ["id_student", "id_assessment", "id_site", "date", "sum_click",
                     "num_of_prev_attempts", "studied_credits", "week_from", "week_to", "length",
                     "date_registration"]
        for col in int_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                df[col] = df[col].fillna(0).astype("int64")

        float_cols = ["score", "weight", "date_unregistration"]
        for col in float_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 6. Aggregate duplicate PK rows
        pk_cols = schema_def.get("pk", [])
        if pk_cols and any(df.duplicated(subset=pk_cols)):
            sum_cols = [c for c in df.columns if c not in pk_cols
                        and pd.api.types.is_numeric_dtype(df[c])]
            agg_dict = {c: "sum" if c in sum_cols else "first" for c in df.columns if c not in pk_cols}
            df = df.groupby(pk_cols, as_index=False).agg(agg_dict)

        # 7. Anonymize PII
        df = self._anonymize_pii(df, table_name)

        # 8. Add metadata columns
        df["_ingested_at"] = exec_ts.isoformat()
        df["_source_file"] = os.path.basename(csv_path)

        # 9. Build BigQuery table reference
        project = self.config["storage"]["bronze"]["project"]
        dataset = schema_def["dataset"]
        db_table = schema_def["db_table"]
        table_ref = f"{project}.{dataset}.{db_table}"

        # 10. Ensure table exists
        self._ensure_table_exists(table_ref, df)

        # 11. Truncate and load via BigQuery
        row_count = len(df)
        try:
            # Truncate existing table
            self.bq_client.query(f"TRUNCATE TABLE `{table_ref}`").result()

            # Load data
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                autodetect=True,
            )
            job = self.bq_client.load_table_from_dataframe(
                df, table_ref, job_config=job_config
            )
            job.result()
            logger.info(f"Loaded {row_count} rows into {table_ref}")
        except Exception as e:
            logger.error(f"BigQuery insert failed for {table_name}: {e}")
            return 0, [f"BigQuery write failed: {e}"]

        # 12. Log ingestion to audit table
        audit_table_ref = f"{project}.bronze.ingestion_log"
        audit_row = {
            "table_name": db_table,
            "file_name": os.path.basename(csv_path),
            "row_count": row_count,
            "errors": None if not errors else str(errors),
            "_ingested_at": exec_ts.isoformat(),
        }
        try:
            audit_df = pd.DataFrame([audit_row])
            self._ensure_table_exists(audit_table_ref, audit_df)
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
                autodetect=True,
            )
            self.bq_client.load_table_from_dataframe(
                audit_df, audit_table_ref, job_config=job_config
            ).result()
        except Exception as e:
            logger.warning(f"Failed to write ingestion_log: {e}")

        # 13. Audit
        self.audit.log(
            action="ingest",
            resource=f"bronze.{db_table}",
            detail={"rows": row_count, "source": csv_path, "errors": errors},
        )

        logger.info(f"Loaded {row_count} rows into bronze.{db_table}")
        return row_count, []


def load_all_tables(data_dir: str = "data/raw") -> Dict[str, Tuple[int, List[str]]]:
    """Load every known CSV from data_dir into Bronze BigQuery."""
    loader = BronzeLoader()
    results: Dict[str, Tuple[int, List[str]]] = {}
    for table_name in TABLE_SCHEMAS:
        csv_path = Path(data_dir) / f"{table_name}.csv"
        if csv_path.exists():
            results[table_name] = loader.load(table_name=table_name, csv_path=str(csv_path))
        else:
            logger.warning(f"Skipping {table_name}: {csv_path} not found")
    return results
