# LawApp Docker Test Environment

This document describes how to run and test LawApp locally on Windows with Docker Compose.

## Start the stack

From `F:\lawapp`:

```powershell
docker compose up -d
docker compose ps
```

Optional (only if you explicitly want local Ollama in Docker):

```powershell
docker compose --profile ollama up -d ollama
```

## Stop the stack

```powershell
docker compose down
```

## Primary URLs to open in browser

- Main frontend (served by backend static mount): http://localhost:8000/
- Intake/start flow: http://localhost:8000/pages/intake.html
- API docs (FastAPI Swagger): http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

## API and service URLs

- Main API base: http://localhost:8000
- Main API health: http://localhost:8000/health
- Rules service: http://localhost:8016/health
- RAG service: http://localhost:8017/health
- Redaction service: http://localhost:8019/health
- Audit service: http://localhost:8020/health
- Admin service: http://localhost:8007/health
- Case service: http://localhost:8008/health
- Notification service: http://localhost:8009/health
- Graph RAG service: http://localhost:8018/health (currently restarting/failing in this environment)

## Auth / test credentials and mode

- `LAWAPP_AUTH_MODE=jwt` in this Docker setup.
- `PAYMENT_MODE=test` in `docker-compose.override.yml`.
- No fixed app login credentials are pre-seeded by default; create a test user via:
  - http://localhost:8000/pages/register.html
  - or API endpoints `/auth/register` then `/auth/token`.
- Local DB test credentials in the override are:
  - user: `lawapp`
  - password: `lawapp` (override aligns services; `.env` may still say `change_this_password` — use `lawapp` for host scripts on :5435)
  - db: `lawapp`
  - host port: `5435` (container internal 5432)

## What works without Ollama vs what needs it

- Works for basic UI and API testing without running Ollama container:
  - Landing page and static frontend pages.
  - Auth/register/login.
  - Core API connectivity and DB-backed flows that do not require live model inference.
- LLM-backed legal analysis paths rely on Ollama endpoint configuration:
  - backend points to `http://host.docker.internal:11434`.
  - If no Ollama is available there, LLM-dependent flows may fail or degrade.
- Current blocker unrelated to Ollama:
  - `lawapp-graph-rag-service` is restarting due missing module import (`backend.core.rag.graphrag_traversal`).

## Health check commands

```powershell
docker compose ps
```

```powershell
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:8016/health -UseBasicParsing
Invoke-WebRequest http://localhost:8017/health -UseBasicParsing
Invoke-WebRequest http://localhost:8019/health -UseBasicParsing
Invoke-WebRequest http://localhost:8020/health -UseBasicParsing
Invoke-WebRequest http://localhost:8007/health -UseBasicParsing
Invoke-WebRequest http://localhost:8008/health -UseBasicParsing
Invoke-WebRequest http://localhost:8009/health -UseBasicParsing
Invoke-WebRequest http://localhost:8018/health -UseBasicParsing
```
