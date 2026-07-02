# fluidGo — AI Revenue Operating System

## Vision

fluidGo replaces the manual Excel DSR chain at FluidPro (WEPSol's IT infrastructure managed
services business) with a config-driven, AI-powered revenue platform — no hardcoded formulas,
roles, KPIs, or targets anywhere in the code. Everything a manager can tune (scoring weights, org
roles, revenue targets) lives in the database and is editable through the product, not a deploy.

## Product Overview

fluidGo started as a 7-day MVP (Daily Sales Report + rule-based rigor/BANT scoring + local AI
insights) and is evolving module by module into a full Revenue Operating System: Opportunity
Management, AI Deal Health, a config-driven Sales Performance Engine (Sales/PreSales FGA), Revenue
Intelligence dashboards, and — on the roadmap — AI Coaching, a Variable Pay Engine, Kylas CRM sync,
and Teams/Email notifications. DSR is now one module among several, not the whole product.

## Business Goals

Increase revenue, win ratio, and forecast accuracy · increase field productivity and visibility ·
automate variable pay · give every rep AI coaching instead of a manager's spare time.

## Core Modules

| Module | Status | Notes |
|---|---|---|
| **Authentication** | ✅ Shipped | JWT access/refresh, role guards, account deactivation (soft-disable, keeps all historical data) |
| **DSR** | ✅ Shipped | Daily activity + self-scoring, offline-capable PWA entry |
| **Revenue Intelligence** | ✅ Shipped (v2 Phase 1) | Forecast, target achievement, gap, pipeline coverage, win %, avg deal size — `/revenue`, manager/bu_head only |
| **Opportunity Management** | ✅ Shipped (v2 Phase 1) | Extends the existing pipeline/deal model with account, OEM, practice, revenue split, risk, competition, decision maker, etc. — `/opportunities` |
| **Pipeline Intelligence (Deal Health)** | ✅ Shipped (v2 Phase 1) | Rule-based 0-100 health score + AI recommendation per opportunity |
| **AI Coaching** | 🗺️ Roadmap (Phase 2) | Daily/weekly/monthly briefs, reusing the existing Ollama layer |
| **Variable Pay Engine** | 🗺️ Roadmap (Phase 3) | Needs HR/Finance sign-off before it ships — see Risk Register in the v2 plan |
| **Analytics** | ✅ Shipped, extended | Per-rep and team analytics; Revenue Intelligence is the new BU-level layer |
| **Notifications** | 🗺️ Roadmap (Phase 4, deferred) | Email/Teams — needs Redis/worker infra not yet in the stack |
| **Administration** | ✅ Shipped | User onboarding/deactivation (`/team`), Scoring Admin (`/scoring-admin`), org-role assignment (API only — no dedicated UI yet, see Known Limitations) |

## User Roles

Two role systems coexist by design (see the v2 architecture plan for why):

- **Legacy roles** (`users.role`, unchanged since v1): `rep`, `inside_sales`, `manager`, `bu_head` — still gate every v1 route exactly as before.
- **Org-role hierarchy** (`org_roles` table, additive): `sales`, `presales`, `manager`, `bu_head`, `practice_head`, `hr`, `admin`, `super_admin` — each with a `data_scope` (`own` / `team` / `bu` / `practice` / `all`) that new v2 endpoints (Opportunities, Revenue Intelligence) use to filter what a user sees. A user's `org_role_key` is optional; if unset, they default to seeing only their own data.

## AI Architecture

All inference runs locally through Ollama — no OpenAI/Anthropic/cloud AI calls, so no per-request
cost and no customer data leaves the box.

1. **Rule-based (instant, no LLM):** rigor score, BANT completeness/closure %/intent, lead quality
   score, and Deal Health score — all pure Python, same philosophy: the LLM never decides a number,
   only writes the narrative.
2. **LLM (Ollama, `phi3:mini` by default — swap to `mistral:7b` via `OLLAMA_MODEL` for better
   quality on a bigger box):** narrative generation from prompt templates in `backend/app/prompts/`:
   `daily_insight`, `deal_analysis`, `pipeline_review`, `team_analysis`, `lead_scoring`, and
   `deal_health` (v2). Responses are cached in `ai_insights` for 6 hours per entity, and a streaming
   endpoint (`POST /api/ai/analyse/stream`) is available for progressive rendering.

Measured on this dev box: ~50-90s for a cold `phi3:mini` inference on CPU. That's the reason Deal
Health's *score* is rule-based and only the recommendation text touches the LLM (see Risk Register).

## Revenue Health Index

A single 0-100 score per person, computed by `backend/app/services/scoring_engine.py` from whichever
`ScoringTemplate` matches their org role — weights and which metrics compose it are DB rows
(`scoring_templates`/`scoring_parameters`), never a Python constant. Edit them live at `/scoring-admin`
(admin/super_admin/practice_head only) or via `PATCH /api/scoring/templates/{id}/parameters`.

## Sales FGA

Default weights (seeded by `seed_v2.py`, fully editable afterward):

| Parameter | Weight | Metric |
|---|---|---|
| Business Generation | 40% | Revenue closed vs. target for the period |
| Sales Execution | 25% | Average rigor score |
| Pipeline Quality | 20% | Average BANT closure % across meetings |
| Professional Excellence | 15% | Average self-score (proxy until manager ratings exist) |

## PreSales FGA

| Parameter | Weight | Metric |
|---|---|---|
| Solution Support | 35% | % of assigned opportunities with recent activity |
| Technical Conversion | 35% | Win rate on assigned opportunities |
| Knowledge Excellence | 15% | Self-score proxy (training/certification capture is a Phase 2 gap — see Known Limitations) |
| Operational Excellence | 15% | DSR compliance % |

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind, TanStack Query, Zustand, vite-plugin-pwa |
| Backend | FastAPI (Python 3.11), SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 15 |
| AI | Ollama (local), `phi3:mini` / `mistral:7b` |
| Auth | JWT (python-jose), bcrypt via passlib |
| Testing | pytest + pytest-asyncio (`backend/tests/`) |
| Deployment | Docker Compose (dev) → k3s on EC2 (prod), GitHub Actions CI/CD |

## Database

v1 tables (unchanged): `users`, `dsr_daily`, `self_scores`, `meetings`, `leads`, `pipeline`, `ai_insights`.

v2 additions (migration `0003_v2_foundation.py`, fully additive — nothing dropped/renamed):
- `pipeline` gains ~20 nullable Opportunity columns (account/OEM/practice/revenue split/risk/etc.) — it doubles as the Opportunity entity rather than a parallel table
- `users` gains a nullable `org_role_key`
- `org_roles`, `scoring_templates`, `scoring_parameters`, `scoring_results`, `revenue_targets` — the config-driven scoring/targets engine

## APIs

v1 (unchanged): `/api/auth`, `/api/dsr`, `/api/meetings`, `/api/leads`, `/api/pipeline`, `/api/analytics`, `/api/ai`, `/api/users`.

v2 additions:
- `GET /api/opportunities` — scoped opportunity list (filters: practice, oem, risk_level)
- `GET /api/opportunities/{id}/health` — Deal Health score + AI recommendation
- `GET/POST/PATCH /api/scoring/templates`, `GET /api/scoring/metrics`, `GET /api/scoring/my-score`
- `GET/POST /api/roles`, `PATCH /api/roles/assign/{user_id}`
- `GET /api/analytics/revenue`, `POST /api/analytics/revenue/targets`

Full interactive docs at `/api/docs` once running.

## Docker

`docker compose up --build` — see Quick Start below. `docker-compose.yml` is unchanged by v2 (no
new services yet; that's Phase 4).

## Kubernetes

See `k8s/` — namespace, secrets, Postgres, Ollama, backend, frontend, ingress + cert-manager.
Unchanged by v2 Phase 1 (no new services to deploy yet).

## Deployment

Provisioning EC2, DNS, and running `kubectl apply` against a live cluster needs your AWS
credentials/SSH access — see the comments at the top of each `k8s/` manifest for the exact
commands, and `.github/workflows/deploy.yml` for the CI/CD pipeline (needs `EC2_HOST`,
`EC2_SSH_USER`, `EC2_SSH_KEY` repo secrets).

## Security

JWT access (15 min) + refresh (7 day) tokens; legacy `require_role()` guards unchanged; new
`require_org_role()`/`resolve_visible_user_ids()` in `permission_service.py` add data-scope
filtering for v2 endpoints without touching any existing route. Deactivated accounts are rejected
at login, token refresh, *and* on every authenticated request (`get_current_user`), so revocation is
immediate even for an already-issued access token.

## Roadmap

| Phase | Scope |
|---|---|
| **Phase 1 — shipped this pass** | Opportunity model extension, org-role hierarchy, config-driven Sales/PreSales FGA scoring engine, Deal Health, Revenue Intelligence, Scoring Admin UI |
| **Phase 2** | AI Coach (daily/weekly/monthly), Leaderboards, Practice/Executive dashboards, self-scoring UI retired in favour of the Revenue Health Index |
| **Phase 3** | Variable Pay Engine — ships in shadow/dry-run mode first; needs HR/Finance sign-off on formulas before any payroll export |
| **Phase 4 (deferred)** | Redis + background workers, Kylas CRM sync, Teams/Email notifications, audit logs, delegated admin, multi-BU support |

## Sprint Backlog

Tracked in Linear under the fluidGo project. v1.0 (WEP-27–35) is done. v2 work is organized into 8
epics — see Linear Tasks below for the mapping.

## Linear Tasks

fluidGo project in Linear (team `wepsol1`):
- **Epic 1 – Revenue Intelligence Dashboard** (Phase 1)
- **Epic 2 – Opportunity Intelligence** (Phase 1)
- **Epic 3 – Sales Performance Engine** (Phase 1 engine → Phase 2 full rollout)
- **Epic 4 – Variable Pay Automation** (Phase 3, needs HR sign-off)
- **Epic 5 – AI Coaching** (Phase 2)
- **Epic 6 – Role-Based Governance** (Phase 1 core → Phase 4 audit/delegated admin)
- **Epic 7 – Kylas Integration** (Phase 4, deferred)
- **Epic 8 – Platform & Infrastructure** (Phase 4, deferred)

---

## Quick start (local dev)

Requirements: Docker + Docker Compose. ~6GB free RAM recommended (Ollama needs 4-8GB depending on model).

```bash
cp .env.example .env
# edit .env — set a real JWT_SECRET (see the comment in the file for how to generate one)

docker compose up --build
```

This starts 5 containers: `db` (Postgres), `ollama` (local LLM, auto-pulls `phi3:mini` on first run),
`backend` (FastAPI, runs Alembic migrations automatically on boot), `frontend` (Vite dev server), `nginx`
(reverse proxy tying it all together on port 80).

Once healthy:

- App: **http://localhost**
- API health check: **http://localhost/api/health** → `{"status":"ok"}`
- API docs (Swagger): **http://localhost/api/docs**
- Ollama: **http://localhost:11434/api/tags**

If another local project already uses ports 80/3000/5432/etc., see the comments in
`docker-compose.yml` — the `db` and `frontend` ports are already remapped (5433, 3002) to coexist
with other projects on this machine; only `db:5432`/`frontend:3000` internal container networking
matters, host ports are just for direct access.

First Ollama model pull can take a few minutes — AI panels show a "model warming up" style error
until `phi3:mini` finishes downloading.

## Seed data

```bash
docker compose exec backend python seed.py     # v1: 4 users + a month of DSR/meeting/lead data
docker compose exec backend python seed_v2.py  # v2: org roles + default Sales/PreSales FGA templates
```

Both are idempotent — safe to re-run. `seed_v2.py` also bootstraps `org_role_key` on the four
`seed.py` users (amit → `super_admin`, manager → `manager`, danish → `sales`, inside → `presales`)
so there's at least one admin able to reach `/scoring-admin` on a fresh deploy.

Test logins (role in parentheses):

| Email | Password | Legacy Role | Org Role |
|---|---|---|---|
| danish@fluidpro.in | `Fluid@2026!` | rep | sales |
| amit@wepsol.com | `Admin@2026!` | bu_head | super_admin |
| manager@fluidpro.in | `Mgr@2026!` | manager | manager |
| inside@fluidpro.in | `Inside@2026!` | inside_sales | presales |

**Change or remove these before any real deployment** — they're dev-only seed credentials.

## Running tests

```bash
docker compose exec backend python -m pytest tests/ -v
```

Covers `scoring_engine` period math, `deal_health_service` rule scoring, `permission_service`
data-scope isolation (mocked repos), and regression coverage for the v1 rigor/BANT/lead scorers.

## Installing as a PWA (no app store needed)

On a phone, open `http://<host>` in Chrome (Android) or Safari (iOS) and choose
**Add to Home Screen**. It installs like a native app icon and works offline for DSR entry
(queued submissions sync automatically once back online).

## Project layout

```
backend/
├── app/
│   ├── models/          SQLAlchemy models (v1 + v2, all in one module)
│   ├── repositories/    v2 data-access layer (opportunity/scoring/role repos)
│   ├── routers/         v1 + v2 API routes
│   ├── services/        rigor/BANT/AI (v1) + scoring_engine/deal_health/permission (v2)
│   └── prompts/         Ollama prompt templates
├── alembic/versions/    0001 (v1 schema) → 0002 (user deactivation) → 0003 (v2 foundation)
├── tests/                pytest suite
├── seed.py / seed_v2.py
frontend/src/
├── pages/                one file per route, incl. Opportunities/RevenueIntelligence/ScoringAdmin
├── components/layout/    role-gated nav
└── store/                Zustand auth store
k8s/        Kubernetes manifests for the k3s/EC2 production deployment
.github/    CI/CD (GitHub Actions — build, push, deploy on push to main)
```

## Known limitations

- **Org-role assignment has no dedicated UI yet** — only the four seeded users have an `org_role_key`
  (set by `seed_v2.py`). Assigning more requires `PATCH /api/roles/assign/{user_id}` directly (via
  `/api/docs`) until a Phase 2 admin UI exists.
- **"Team" data-scope currently falls back to "BU" scope** — there's no manager→report reporting-line
  column on `users` yet, so a manager's data-scope is same-BU rather than their actual direct reports.
- **Knowledge Excellence (PreSales FGA) and Professional Excellence (Sales FGA)** are proxied via
  self-scoring — no dedicated training/certification/manager-rating capture exists yet.
- Everything in Phase 2-4 of the Roadmap above (AI Coach, Variable Pay, Kylas sync, notifications,
  multi-BU, audit logs) is not built.
