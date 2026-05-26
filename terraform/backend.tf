# ──────────────────────────────────────────────────────────────
# Terraform Backend — GCS Remote State
# ──────────────────────────────────────────────────────────────
# Run this first:
#   gsutil mb gs://openuniversitydataanalysis-tfstate
#   gsutil versioning set on gs://openuniversitydataanalysis-tfstate

terraform {
  backend "gcs" {
    bucket = "openuniversitydataanalysis-tfstate"
    prefix = "terraform/state"
  }
}
