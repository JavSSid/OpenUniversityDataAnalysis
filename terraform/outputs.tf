# ──────────────────────────────────────────────────────────────
# OULAD Data Platform — Terraform Outputs
# ──────────────────────────────────────────────────────────────

output "pipeline_service_account" {
  description = "Email of the pipeline service account"
  value       = google_service_account.pipeline_sa.email
}

output "bronze_dataset" {
  description = "BigQuery Bronze dataset ID"
  value       = google_bigquery_dataset.bronze.dataset_id
}

output "silver_dataset" {
  description = "BigQuery Silver dataset ID"
  value       = google_bigquery_dataset.silver.dataset_id
}

output "gold_dataset" {
  description = "BigQuery Gold dataset ID"
  value       = google_bigquery_dataset.gold.dataset_id
}

output "raw_data_bucket" {
  description = "GCS bucket for raw CSVs"
  value       = google_storage_bucket.raw_data.name
}

output "ingestion_job_name" {
  description = "Cloud Run ingestion job name"
  value       = google_cloud_run_v2_job.ingestion.name
}

output "scheduler_job_name" {
  description = "Cloud Scheduler job name"
  value       = google_cloud_scheduler_job.daily_ingestion.name
}
