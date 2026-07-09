# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MTE SIVE** — energy visualization system (Universidad de Nariño). Decoupled architecture: **Django 5.2 + DRF** backend and **React 19 (Create React App)** frontend. Displays historical data and KPIs for energy consumption/generation and climate variables, sourced from a remote SCADA connector API and Colombia's XM energy market.

## Critical rule: everything runs in Docker

Do NOT run Django/Python/manage.py commands on the host. Always exec into the containers using `docker-compose.prod.yml`:

```bash
# Bring up the stack
docker compose -f docker-compose.prod.yml up -d

# Django management commands (migrate, shell, makemigrations, collectstatic, createsuperuser...)
docker compose -f docker-compose.prod.yml exec backend python manage.py <command>

# Logs
docker compose -f docker-compose.prod.yml logs backend   # or celery_worker, celery_beat, frontend, db, redis
```

Services (container names): `db` (postgres:17, `mte_postgres_prod`), `redis` (redis:7, password-protected), `backend` (`mte_backend_prod`, built from `Dockerfile.backend`), `celery_worker`, `celery_beat` (django-celery-beat DatabaseScheduler), `frontend` (`mte_frontend_prod`, nginx). Environment comes from `.env` (template: `env.example`).

## Commands

### Backend tests (inside the container)
```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py test          # all
docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_external_energy   # single module
```
Tests live in the top-level `tests/` directory (Django TestCase / DRF APITestCase style). That directory also holds many one-off debug/validation scripts (`debug_*.py`, `validate_*.py`) that are diagnostic tools, not test suites.

### Frontend (in `frontend/`)
```bash
npm install
npm start        # CRA dev server
npm run build    # production build
npm test         # Jest + Testing Library
```

### Deployment
`scripts/deploy_production.sh` (Linux) / `.ps1` (Windows). Full guide: `DEPLOYMENT_PRODUCTION.md`. Troubleshooting reference: `BACKEND_FRONTEND_ANALYSIS.md`.

## Architecture

### Django apps (project package is `core/`)
- **`authentication`** — custom token auth: `authentication.authentication.CustomTokenAuthentication` (tokens with expiration + refresh), rate limiting, temporary lockout on failed attempts, forced password change. Routes under `/auth/` (`/auth/login/`, `/auth/refresh/`).
- **`indicators`** — KPI models and Celery tasks that compute monthly/daily consumption, generation, balance indicators; served under `/api/`. Calculation methodology is documented in `indicators/indicators.md`.
- **`scada_proxy`** — proxy to the remote SCADA connector API (a separate NestJS service, `scada-connector`). `scada_client.py` (`ScadaConnectorClient`) authenticates against `SCADA_BASE_URL` with `SCADA_USERNAME`/`SCADA_PASSWORD` and caches the JWT. Three URL groups: `/scada/` (remote proxy), `/local/` (locally synced data), `/tasks/` (sync task management). Management commands: `bootstrap_scada_if_empty`, `repair_device_relationships`.
- **`external_energy`** — XM (Colombian energy market) integration via `pydataxm`: prices, savings, demand, emissions. Services like `XMEnergyService`; routes under `/api/external-energy/`. See `external_energy/README.md` and `quick_start.md`.
- API docs: OpenAPI schema at `/schema/`, Swagger at `/docs/`, Redoc at `/redocs/` (drf-spectacular). Document new endpoints with `@extend_schema`.
- Async pipeline: Celery + Redis broker; periodic tasks scheduled via django-celery-beat (schedules live in the DB, editable in Django admin).

### Backend conventions
- DRF views default to `IsAuthenticated`; public endpoints must set `permission_classes = [AllowAny]` explicitly. Auth header format is `Authorization: Token <key>` (not `Bearer`).
- Requirements are split in `requirements/` (`base.txt`, `development.txt`, `production.txt`); top-level `requirements.txt` is the combined pin list.

### Frontend (React, `frontend/`)
- CRA + Tailwind; charts with Chart.js (`react-chartjs-2`, `chartjs-plugin-zoom`).
- API base URL is `process.env.REACT_APP_API_URL`, injected at **build time** — a Docker build without this variable produces broken API URLs (most common deployment failure; see `BACKEND_FRONTEND_ANALYSIS.md`).
- Two config files: `src/config.js` (auth/profile endpoints) and `src/utils/apiConfig.js` (everything else — `ENDPOINTS`, `buildApiUrl`, `getDefaultFetchOptions`, `fetchWithAuth`, `handleApiResponse`). New API calls must go through these utilities; don't hand-roll fetch/token logic. Token is stored in `localStorage` as `authToken`; `fetchWithAuth` handles 401 (clears token, redirects to login).
- Screens receiving `authToken` as a prop: Dashboard, ElectricalDetails, InverterDetails, WeatherStationDetails, ExternalEnergyData, ExportReports. Follow the same pattern for new API-consuming components.
- Don't break the login contract: response includes `access_token`, `username`, `is_superuser`.

### Language conventions
- **User-facing messages** (API errors, UI text, OpenAPI tags): Spanish.
- **Identifiers** (variables, functions, classes, endpoints): English.
- Docstrings/comments: Spanish for business logic; brief technical comments in English are fine.

### Common pitfalls
- CORS: backend only accepts exact origins in `CORS_ALLOWED_ORIGINS` (scheme + host + port must match).
- `.cursor/rules/*.mdc` contains the full original conventions (docker-execution, api-backend, api-frontend, testing, troubleshooting, domain) — keep this file consistent with them if either changes.
