.PHONY: up down restart build seed dbt-run dbt-test lint clean init

# ── Docker ────────────────────────────────────────────────
up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

restart: down up

build:
	docker compose -f docker/docker-compose.yml build

logs:
	docker compose -f docker/docker-compose.yml logs -f

# ── Data ──────────────────────────────────────────────────
seed:
	python scripts/seed_data.py

seed-download:
	python scripts/seed_data.py --download

# ── dbt ────────────────────────────────────────────────────
dbt-run:
	cd dbt && dbt run

dbt-test:
	cd dbt && dbt test

dbt-docs:
	cd dbt && dbt docs generate && dbt docs serve

# ── Python ─────────────────────────────────────────────────
lint:
	ruff check src/ scripts/ dags/
	ruff format --check src/ scripts/ dags/

format:
	ruff format src/ scripts/ dags/

# ── Cleanup ────────────────────────────────────────────────
clean:
	rm -rf data/raw/ data/audit/ data/reports/
	rm -rf __pycache__/ src/**/__pycache__/

# ── Init ───────────────────────────────────────────────────
init: build up seed dbt-run
	@echo "OULAD pipeline initialized. Access Airflow at http://localhost:8080"
	@echo "PostgreSQL available at localhost:5432"
	@echo "  Connection: postgresql://oulad_admin:CHANGE_ME_STRONG_PASSWORD@localhost:5432/oulad_warehouse"
