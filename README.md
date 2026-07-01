# fluidGo — FluidPro Sales Intelligence Platform

Mobile-first Daily Sales Report (DSR) web app with a local, private AI layer (Ollama) that scores
deals with BANT, tracks rep "rigor," and gives BU heads / managers / inside sales / field reps
real-time sales intelligence — with zero external AI API dependency.

## Stack

React (Vite, TS, Tailwind) PWA · FastAPI · PostgreSQL · Ollama (phi3:mini / mistral:7b) · nginx ·
Docker Compose (dev) · k3s on EC2 (prod)

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

First Ollama model pull can take a few minutes depending on connection speed — the `backend` and
`nginx` containers will be up before Ollama finishes downloading `phi3:mini`; AI panels will show a
"model warming up" style error until it's ready.

## Seed test data

The DB starts empty. To load 4 test users + a realistic month of DSR/meeting/lead data for the
Danish Sayyed persona:

```bash
docker compose exec backend python seed.py
```

Test logins (role in parentheses):

| Email | Password | Role |
|---|---|---|
| danish@fluidpro.in | `Fluid@2026!` | rep |
| amit@wepsol.com | `Admin@2026!` | bu_head |
| manager@fluidpro.in | `Mgr@2026!` | manager |
| inside@fluidpro.in | `Inside@2026!` | inside_sales |

**Change or remove these before any real deployment** — they're dev-only seed credentials.

## Installing as a PWA (no app store needed)

On a phone, open `http://<host>` in Chrome (Android) or Safari (iOS) and choose
**Add to Home Screen**. It installs like a native app icon and works offline for DSR entry
(queued submissions sync automatically once back online).

## Project layout

```
backend/    FastAPI app — routers, models, services (rigor/BANT scoring, Ollama integration), Alembic migrations
frontend/   React PWA — pages, layout, Zustand auth store, TanStack Query
nginx/      Dev reverse-proxy config (dev.conf)
k8s/        Kubernetes manifests for the k3s/EC2 production deployment
.github/    CI/CD (GitHub Actions — build, push, deploy on push to main)
```

## AI design

All inference runs locally through Ollama — no OpenAI/Anthropic/cloud AI calls, so no per-request
cost and no customer data leaves the box. Two layers:

1. **Rule-based (instant, no LLM):** rigor score (0-100, weighted from visits/calls/follow-ups/leads/proposals),
   BANT completeness + closure % + intent (hot/warm/cold/engaged), lead quality score.
2. **LLM (Ollama, `phi3:mini` by default — swap to `mistral:7b` via `OLLAMA_MODEL` env var for
   better quality on a bigger box):** narrative insight generation from prompt templates in
   `backend/app/prompts/` (daily rigor+gap analysis, single-deal BANT coaching, full pipeline
   prioritisation, team coaching, lead-scoring rationale). Responses are cached in the `ai_insights`
   table for 6 hours per entity so the model isn't re-run on every page load, and a streaming
   endpoint (`POST /api/ai/analyse/stream`, Server-Sent Events) is available for progressive
   rendering in the UI.

## Production deployment (k3s on EC2)

See `k8s/` for the manifests (namespace, secrets, Postgres, Ollama, backend, frontend, ingress +
cert-manager) and `.github/workflows/deploy.yml` for the CI/CD pipeline. Provisioning the EC2 box,
pointing DNS, and running the actual `kubectl apply` against your cluster needs your AWS
credentials/SSH access and is intentionally not automated here — see the comments at the top of
each manifest for the exact commands.

## Known limitations / v1.1 backlog

Out of scope for v1.0 by design — tracked in Linear (fluidGo project, issue WEP-35):
WhatsApp/email nudges for missed DSRs, manager coaching notes on a DSR, PDF export, historical Excel
import, CRM webhook integration, admin UI for user management (currently seed-script only),
multi-BU support (currently hardcoded to West BU).
