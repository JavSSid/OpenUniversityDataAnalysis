# ──────────────────────────────────────────────────────────────
# OULAD Data Platform — GCP Infrastructure (Terraform)
# Architecture: BigQuery + Dataform + Cloud Run Jobs
# ──────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── BigQuery Datasets (Bronze, Silver, Gold) ────────────────

resource "google_bigquery_dataset" "bronze" {
  dataset_id    = "bronze"
  friendly_name = "OULAD Bronze Layer"
  description   = "Raw ingested data with PII hashed — loaded by Cloud Run ingestion job"
  location      = var.location
  project       = var.project_id

  labels = {
    environment = var.environment
    layer       = "bronze"
  }
}

resource "google_bigquery_dataset" "silver" {
  dataset_id    = "silver"
  friendly_name = "OULAD Silver Layer"
  description   = "Cleaned, conformed data — Dataform materialized tables"
  location      = var.location
  project       = var.project_id

  labels = {
    environment = var.environment
    layer       = "silver"
  }
}

resource "google_bigquery_dataset" "gold" {
  dataset_id    = "gold"
  friendly_name = "OULAD Gold Layer"
  description   = "Analytics-ready marts and quality metrics — Power BI source"
  location      = var.location
  project       = var.project_id

  labels = {
    environment = var.environment
    layer       = "gold"
  }
}

# ── Cloud Storage Buckets ───────────────────────────────────

resource "google_storage_bucket" "raw_data" {
  name          = "${var.project_id}-raw-data"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = false

  labels = {
    environment = var.environment
    purpose     = "raw-data-ingestion"
  }
}

resource "google_storage_bucket" "dataform_artifacts" {
  name          = "${var.project_id}-dataform-artifacts"
  location      = var.region
  storage_class = "STANDARD"
  force_destroy = false

  labels = {
    environment = var.environment
    purpose     = "dataform-artifacts"
  }
}

# ── Secret Manager ──────────────────────────────────────────

resource "google_secret_manager_secret" "slack_webhook" {
  secret_id = "oulad-slack-webhook"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "bigquery_service_account" {
  secret_id = "oulad-bigquery-service-account"
  project   = var.project_id

  replication {
    auto {}
  }
}

# ── Service Account (shared across pipeline) ────────────────

resource "google_service_account" "pipeline_sa" {
  account_id   = "oulad-pipeline-sa"
  display_name = "OULAD Pipeline Service Account"
  description  = "Used by Dataform, Cloud Run Jobs, and ingestion scripts"
  project      = var.project_id
}

resource "google_project_iam_member" "pipeline_sa_bq_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_sa_bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_sa_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_sa_dataform_editor" {
  project = var.project_id
  role    = "roles/dataform.editor"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_sa_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# ── Cloud Run Jobs (Python steps) ───────────────────────────

resource "google_cloud_run_v2_job" "ingestion" {
  name     = "oulad-ingestion"
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.pipeline_sa.email

      containers {
        image = "europe-west1-docker.pkg.dev/${var.project_id}/oulad/ingestion:latest"
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "ENVIRONMENT"
          value = "prod"
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }
}

# ── Cloud Scheduler (trigger pipeline daily) ────────────────

resource "google_cloud_scheduler_job" "daily_ingestion" {
  name        = "oulad-daily-ingestion"
  description = "Trigger ingestion Cloud Run job daily at 05:00 UTC"
  schedule    = "0 5 * * *"
  region      = var.region

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/oulad-ingestion:run"
    oauth_token {
      service_account_email = google_service_account.pipeline_sa.email
    }
  }
}
