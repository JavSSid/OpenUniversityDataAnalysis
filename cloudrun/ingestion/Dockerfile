FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY cloudrun/ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY config/ config/
COPY scripts/ scripts/
COPY dataform/ dataform/

ENV PYTHONPATH="/app/src:${PYTHONPATH}"
ENV ENVIRONMENT=prod

ENTRYPOINT ["python", "scripts/seed_data.py", "--upload-gcs"]
