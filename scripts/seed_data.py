"""
OULAD — Seed Script (GCS + BigQuery)

Downloads the OULAD dataset (via Kaggle or local zip) and loads
all CSVs into BigQuery Bronze dataset. Optionally uploads to GCS first.

Usage:
    python scripts/seed_data.py                              # uses data/raw/ if CSVs exist
    python scripts/seed_data.py --download                    # prompts for zip path
    python scripts/seed_data.py --upload-gcs                  # also upload CSVs to GCS
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.ingestion.load_to_bronze import TABLE_SCHEMAS, load_all_tables  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parents[1] / "data" / "raw"


def extract_zip(zip_path: str) -> None:
    """Extract a zip of CSVs into data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_files = [f for f in zf.namelist() if f.endswith(".csv")]
        if not csv_files:
            logger.error("No CSV files found in the zip archive")
            sys.exit(1)
        for csv_file in csv_files:
            target = RAW_DIR / Path(csv_file).name
            with zf.open(csv_file) as source, open(target, "wb") as dest:
                dest.write(source.read())
            logger.info(f"Extracted {csv_file} -> {target}")

    logger.info(f"Extracted {len(csv_files)} CSV files to {RAW_DIR}")


def upload_to_gcs(bucket_name: str = "openuniversitydataanalysis-raw-data") -> None:
    """Upload CSV files from data/raw/ to GCS bucket."""
    try:
        from google.cloud import storage
    except ImportError:
        logger.error("google-cloud-storage not installed. Run: pip install google-cloud-storage")
        sys.exit(1)

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    for csv_file in RAW_DIR.glob("*.csv"):
        blob = bucket.blob(csv_file.name)
        blob.upload_from_filename(str(csv_file))
        logger.info(f"Uploaded {csv_file.name} -> gs://{bucket_name}/{csv_file.name}")

    logger.info(f"All CSVs uploaded to gs://{bucket_name}/")


def check_raw_files() -> bool:
    """Check if all expected CSV files exist in data/raw/."""
    expected = [f"{name}.csv" for name in TABLE_SCHEMAS]
    missing = [f for f in expected if not (RAW_DIR / f).exists()]
    if missing:
        logger.warning(f"Missing CSV files: {missing}")
        return False
    logger.info(f"All {len(expected)} CSV files found in {RAW_DIR}")
    return True


def main():
    parser = argparse.ArgumentParser(description="OULAD Data Seed Script")
    parser.add_argument(
        "--download", "-d",
        metavar="ZIP_PATH",
        nargs="?",
        const="prompt",
        help="Path to OULAD zip archive.",
    )
    parser.add_argument(
        "--upload-gcs",
        action="store_true",
        help="Upload CSVs to GCS bucket after extraction",
    )
    args = parser.parse_args()

    if args.download:
        if args.download == "prompt":
            zip_path = input("Enter path to OULAD zip file: ").strip()
        else:
            zip_path = args.download
        if not Path(zip_path).exists():
            logger.error(f"File not found: {zip_path}")
            sys.exit(1)
        extract_zip(zip_path)
    elif not check_raw_files():
        logger.info("Tip: Download OULAD from https://analyse.kmi.open.ac.uk/open-dataset")
        sys.exit(1)

    if args.upload_gcs:
        upload_to_gcs()

    # Load all tables into Bronze BigQuery
    logger.info("=" * 60)
    logger.info("Starting Bronze ingestion into BigQuery...")
    results = load_all_tables()

    logger.info("=" * 60)
    logger.info("Ingestion Results:")
    total_rows = 0
    for table_name, (row_count, errors) in results.items():
        status = "OK" if not errors else "FAIL"
        logger.info(f"  {table_name:25s} -> {row_count:>8,} rows  [{status}]")
        if errors:
            for err in errors:
                logger.error(f"    └─ {err}")
        total_rows += row_count

    logger.info("=" * 60)
    logger.info(f"Total rows ingested: {total_rows:,}")


if __name__ == "__main__":
    main()
