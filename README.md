# Local Video Editing Platform

This repository contains a production-shaped local platform for video editing orchestration:

- API gateway (`FastAPI`)
- Temporal workflow (`VideoEditWorkflow`) + worker
- Planner / safety / QA / knowledge services
- Self-designed Ops dashboard (`Vue 3 + Vite`, service: `ops-web`)
- Docker Compose dependencies: PostgreSQL, Redis, MinIO, Qdrant, Temporal

## Quick Start

1. Start services:

```powershell
./scripts/start-platform.ps1 -Build
```

2. Open:

- API docs: `http://localhost:8000/docs`
- Ops web (Vue): `http://localhost:8080`
- Temporal UI: `http://localhost:8088`
- MinIO Console: `http://localhost:9001`

3. Local tokens:

- API token: `dev-token` (`X-API-Token` or `Authorization: Bearer dev-token`)
- Admin token: `dev-admin-token` (`X-Admin-Token`, only for safety override requests)

## Run Tests

```powershell
./scripts/run-tests.ps1
```

## Frontend (Vue)

- Source: `frontend/` (`Vue 3 + Vite`)
- Production assets: `frontend/dist/`
- `./scripts/start-platform.ps1 -Build` now builds Vue assets before starting containers.

## Implemented API Endpoints

- `GET /health`
- `GET /health/ready`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/events`
- `GET /api/v1/jobs/{job_id}/artifacts`
- `GET /api/v1/jobs/{job_id}/qa-report`
- `POST /api/v1/reviews/{job_id}/decision`
- `POST /api/v1/models/recommend`
- `POST /api/v1/models/install`
- `POST /api/v1/cases/search`
- `GET /api/v1/cases/{case_id}`

## Runtime and Quality Policy

- Default model mode is API runtime:
  - `MODEL_RUNTIME_MODE=api`
  - no local model bundle download required
- Local bundles are disabled by default:
  - `ALLOW_LOCAL_MODEL_INSTALL=false`
- QA gate:
  - pass threshold `>= 0.82`
  - hard-fail flags always block auto pass
  - random manual spot-check ratio default `20%`
  - high-risk tasks always route to manual review
- Iteration budget:
  - max `3` rounds, then forced `human_review`

## Safety Policy

- Strict blocking for high-risk face swap, explicit violence, sexual content, hate/terror patterns.
- Admin override is available only when all are true:
  - request sets `safety_override=true` and `override_reason`
  - request carries valid `X-Admin-Token`
  - matched blocked rules are in `SAFETY_OVERRIDE_ALLOW_RULES`
- Every safety decision and override is written to audit events.

## Ops Notes

- Frontend source is in `frontend/` and no longer depends on embedding third-party UI pages.
- If Temporal is unavailable, the API can run in fallback orchestrator mode (`ENABLE_FALLBACK_ORCHESTRATOR=true`).
- All status transitions, QA results, callbacks, and review actions are auditable via `GET /api/v1/jobs/{job_id}/events`.
- `GET /health/ready` returns dependency-level readiness for DB/Temporal/Qdrant/MinIO.
