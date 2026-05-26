"""
OULAD — Audit Logger (Local + Cloud Logging)

Immutable append-only audit trail written as JSON Lines to local disk
and optionally to GCP Cloud Logging. Every data access, quality check,
and anomaly detection event is recorded with timestamp and principal.

Security:
  - Append-only: logs are never modified after writing
  - Rotated daily: log/YYYY/MM/DD/audit.jsonl
  - All timestamps in UTC
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Immutable event logger for pipeline auditability."""

    def __init__(self, log_dir: Optional[str] = None, use_cloud_logging: Optional[bool] = None):
        self.log_dir = Path(log_dir or Path(__file__).parents[2] / "data" / "audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if use_cloud_logging is None:
            self.use_cloud_logging = os.environ.get("ENVIRONMENT", "dev") == "prod"
        else:
            self.use_cloud_logging = use_cloud_logging

    def _daily_path(self) -> Path:
        """Return path like audit/2026/05/25/audit.jsonl"""
        today = datetime.now(timezone.utc)
        return self.log_dir / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}" / "audit.jsonl"

    def log(
        self,
        action: str,
        resource: str,
        detail: Optional[Dict[str, Any]] = None,
        principal: str = "pipeline",
    ) -> None:
        """Write a single audit event.

        Args:
            action: One of 'ingest', 'validate', 'anomaly_detected', 'report', 'dag_run'
            resource: The affected resource, e.g. 'bronze/studentInfo'
            detail: Arbitrary structured data about the event
            principal: Who/what performed the action
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "principal": principal,
            "action": action,
            "resource": resource,
            "detail": detail or {},
        }

        # Local file log (always)
        path = self._daily_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except OSError as e:
            logger.error(f"Audit log write failed: {e}")

        # GCP Cloud Logging (production)
        if self.use_cloud_logging:
            try:
                from google.cloud import logging as cloud_logging
                client = cloud_logging.Client()
                logger_gcp = client.logger("oulad-audit")
                logger_gcp.log_struct(event)
            except ImportError:
                logger.warning("google-cloud-logging not installed; skipping Cloud Logging")
            except Exception as e:
                logger.error(f"Cloud Logging write failed: {e}")

    def read_today(self) -> list[Dict[str, Any]]:
        """Read all audit events from today's log file."""
        path = self._daily_path()
        if not path.exists():
            return []
        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events
