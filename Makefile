# Phase 1  -  run targets
# Prerequisites: Docker Desktop running, .env copied from .env.example and filled in.

.PHONY: setup db-up db-down ingest-legislation ingest-acas seed-rules ingest-sample-eat embed freshness all-ingest

## First-time setup
setup:
	pip install -e ".[dev]"

## Database
db-up:
	docker compose up -d db
	@echo "Waiting for Postgres to be ready..."
	@docker compose exec db pg_isready -U lawapp -d lawapp || (sleep 5 && docker compose exec db pg_isready -U lawapp -d lawapp)

db-down:
	docker compose down

## Ingest steps (run in order)
ingest-legislation:
	python -m ingestion.legislation.ingest

ingest-acas:
	python -m ingestion.acas.ingest

seed-rules:
	python -m ingestion.rules.seed

## EAT sample ingestion (Phase 1  -  no bulk licence needed)
ingest-sample-eat:
	python -m ingestion.case_law.ingest --sample

## Embed all unembedded chunks
embed:
	python -m ingestion.embeddings.embedder

## Freshness report
freshness:
	python -m ingestion.freshness.report

## Full Phase 1 pipeline (run once, in order)
all-ingest: ingest-legislation ingest-acas seed-rules ingest-sample-eat embed freshness

## Start the API (Phase 1 stub)
api:
	uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

## Verify rules without writing (dry run)
check-rules:
	python -m ingestion.rules.seed --check

## Verify chapter numbers with live API calls
check-chapters:
	python -m ingestion.legislation.ingest --section ukpga/1996/18/94
