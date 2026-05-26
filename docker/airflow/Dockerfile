# ── OULAD Airflow Dockerfile (Legacy — use Cloud Composer 2 on GCP) ──
# Local dev only. In production, PyPI packages are installed
# via gcloud composer environments update.
#
# Usage (local dev, optional):
#   docker build -f docker/airflow/Dockerfile -t oulad-airflow .
#   docker run oulad-airflow
#
# For GCP deployment, see docker/docker-compose.yml for instructions.

FROM apache/airflow:2.7.2-python3.11

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY --chown=airflow:root docker/airflow/requirements-airflow.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV PYTHONPATH="/opt/opencode/src:${PYTHONPATH}"
