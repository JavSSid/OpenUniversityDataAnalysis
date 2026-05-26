"""
OULAD — Secrets Manager (GCP Secret Manager)

Resolves secrets from GCP Secret Manager (prod) or .env (dev).

Security:
  - Supports .env file loading via python-dotenv for local dev
  - Production uses GCP Secret Manager with workload identity
  - All secrets accessed through this class — never imported directly
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class SecretsManager:
    """Centralized secret resolution. Dev reads from .env; prod uses GCP Secret Manager."""

    def __init__(self, env_path: Optional[str] = None, use_gcp: bool = False):
        self.use_gcp = use_gcp or os.environ.get("ENVIRONMENT", "dev") == "prod"
        env_file = env_path or Path(__file__).parents[2] / ".env"

        if not self.use_gcp and Path(env_file).exists():
            load_dotenv(dotenv_path=str(env_file))
            logger.info(f"Loaded secrets from {env_file}")
        elif self.use_gcp:
            logger.info("Using GCP Secret Manager for secrets")
        else:
            logger.warning(f"No .env file found at {env_file}; relying on environment variables")

    def _get_from_gcp(self, secret_name: str) -> str:
        """Fetch a secret from GCP Secret Manager."""
        try:
            from google.cloud import secretmanager
            project_id = os.environ.get("GCP_PROJECT_ID", "oulad-platform")
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except ImportError:
            raise RuntimeError("google-cloud-secret-manager not installed. Install with: pip install google-cloud-secret-manager")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch secret '{secret_name}' from Secret Manager: {e}")

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Resolve a secret by key. Raises if missing and no default given."""
        if self.use_gcp:
            secret_name = os.environ.get(f"SECRET_{key}", f"oulad-{key.lower()}")
            return self._get_from_gcp(secret_name)
        value = os.environ.get(key, default)
        if value is None:
            raise RuntimeError(f"Required secret '{key}' is not set")
        return value

    def get_bigquery_client(self) -> dict:
        """Return BigQuery connection parameters."""
        return {
            "project_id": self.get("GCP_PROJECT_ID", "oulad-platform"),
            "private_key_id": self.get("BIGQUERY_PRIVATE_KEY_ID", ""),
            "private_key": self.get("BIGQUERY_PRIVATE_KEY", ""),
            "client_email": self.get("BIGQUERY_CLIENT_EMAIL", ""),
            "client_id": self.get("BIGQUERY_CLIENT_ID", ""),
        }

    def get_slack_webhook(self) -> str:
        """Return the Slack webhook URL for alerts."""
        return self.get("SLACK_WEBHOOK_URL", "")
