# ──────────────────────────────────────────────────────────────
# OULAD Data Platform — Terraform Variables
# ──────────────────────────────────────────────────────────────

variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "openuniversitydataanalysis"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-west1"
}

variable "location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "EU"
}

variable "environment" {
  description = "Environment label (dev, staging, prod)"
  type        = string
  default     = "dev"
}
