# fluidGo — FluidPro Sales Intelligence Platform

> **Status:** Live on AWS EC2 · v3.1 architecture · July 2026
> **Business:** fluidPro (IT Infra Managed Services) · **Tracks:** Sales · Pre-Sales · Service Delivery
> **Stack:** React 18 PWA · FastAPI · PostgreSQL 15 · Ollama (local LLM) · Docker Compose
>
> **📋 For current architecture, feature status, known issues, and roadmap: see [`MASTER_TRACKER.md`](./MASTER_TRACKER.md) — it's the living source of truth (Linear hit its free-tier issue cap 2026-07-11). This README covers quick-start, project layout, and stable reference material that doesn't change every session.

---

## ⚡ Quick Start (3 commands)

```bash
# 1. Copy env and fill in secrets
cp .env.example .env
# Edit .env — set DB_PASSWORD and JWT_SECRET

# 2. Start all 5 services
docker compose up -d

# 3. Seed database (Danish Sayyed May 2026 DSR data)
docker compose exec backend python seed.py
```

Open **http://localhost** — you're running.

> **First run only:** Ollama will auto-pull `phi3:mini` (~2GB). This takes 5–10 minutes.
> Check progress: `docker compose logs -f ollama`

---

## 🔐 Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Business Head | `amit.singh@wepsol.com` | `Admin@2026!` |
| Super Admin | `itsupport.blr@wepsol.com` | (see password vault) |
| Manager | `manager@fluidpro.in` | `Mgr@2026!` (⚠️ deactivated — see MASTER_TRACKER.md §6) |
| Sales Rep | `danish@fluidpro.in` | `Fluid@2026!` (⚠️ deactivated) |
| Inside Sales | `inside@fluidpro.in` | `Inside@2026!` (⚠️ deactivated) |

> **Session:** JWT access tokens auto-refresh via a silent retry-once
> interceptor. Idle sessions now auto-logout after 30 minutes (warning shown
> 60s before) — see `useIdleLogout.ts`.

---

## 📱 Mobile PWA Install

1. Open `http://localhost` on Android Chrome
2. Tap ⋮ → **Add to Home Screen**
3. iOS Safari: Share → **Add to Home Screen**

Installs as a native-feeling app with offline DSR entry.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Docker Compose (local)                 │
│                                                          │
│  nginx :80  ──→  frontend :3000  (React 18 PWA/Vite)   │
│              └─→  backend  :8000  (FastAPI + SQLAlchemy) │
│                     ↓                                    │
│               PostgreSQL :5432   (pgdata volume)         │
│               Ollama     :11434  (ollama_models volume)  │
└─────────────────────────────────────────────────────────┘
```

### Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `nginx` | nginx:1.25-alpine | 80 | Reverse proxy |
| `frontend` | node:20 (Vite dev) | 3000 | React PWA |
| `backend` | python:3.11 | 8000 | FastAPI API |
| `db` | postgres:15-alpine | 5432 | Primary database |
| `ollama` | ollama/ollama | 11434 | Local LLM runtime |

---

## 🧠 AI Model Selection

| Model | RAM | Quality | Switch command |
|-------|-----|---------|----------------|
| `phi3:mini` | 4 GB | Good · ~10s/response | Default |
| `mistral:7b` | 8 GB | Very Good · ~25s | `OLLAMA_MODEL=mistral` in `.env` |
| `llama3:8b` | 8 GB | Best · ~35s | `OLLAMA_MODEL=llama3:8b` in `.env` |

Change model: update `.env` then `docker compose restart backend`.

---

## 👥 Role Hierarchy (v3.1)

> Full current hierarchy, dual-role rules, and recursive scoping behavior:
> see [`MASTER_TRACKER.md` §2](./MASTER_TRACKER.md#2-role-hierarchy-current-as-of-0019).
> Summary: `CEO/super_admin → COO → Business Head (one business line, all
> regions) → Regional Manager (one region) → Manager (full reporting chain,
> recursive) → Rep/Inside Sales/Pre-Sales/Service Delivery Manager`. Hierarchy
> is defined by binding `manager_id` at role-assignment time (Team page),
> not hard-coded region/business rules — a manager's manager automatically
> sees the whole team beneath them, any depth.

### Supported roles in Team → Onboard form
`rep` · `inside_sales` · `pre_sales` · `manager` · `service_delivery_manager` · `regional_manager` · `business_head` · `coo` · `hr` · `finance` · `ceo` · `super_admin`

---

## 📊 API Reference

Full interactive docs: **http://localhost/api/docs**

### Auth
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | None | → JWT access + refresh tokens |
| POST | `/api/auth/refresh` | Refresh token | → New access token |

### DSR
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/dsr` | Rep+ | Submit/update today's DSR |
| GET | `/api/dsr?date=YYYY-MM-DD` | Rep+ | Get own DSR for a date |
| GET | `/api/dsr/team?date=YYYY-MM-DD` | Manager+ | All team DSRs for date |

### Analytics
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/analytics/dashboard?month=YYYY-MM` | Rep+ | Role-scoped KPI summary |
| GET | `/api/analytics/rep/{user_id}` | Rep (own) / Manager+ | Per-day DSR history |
| GET | `/api/analytics/team` | Manager+ | Team performance matrix |
| GET | `/api/analytics/revenue?period=YYYY-MM` | Manager+ | Revenue vs target |
| POST | `/api/analytics/revenue/targets` | Manager+ | Set revenue target |

### AI
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/ai/analyse` | Rep+ | Ollama analysis (6h cache) |
| POST | `/api/ai/analyse/stream` | Rep+ | Streaming Ollama response |
| GET | `/api/ai/dashboard/{user_id}` | Rep+ | Dashboard insight |

### Users
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/users` | Manager+ | List visible users (scoped) |
| POST | `/api/users` | Manager+ | Onboard new team member |
| PATCH | `/api/users/{id}` | Manager+ | Update user details/role |
| PATCH | `/api/users/{id}/status` | Manager+ | Activate/deactivate |
| GET | `/api/users/roles` | Manager+ | Assignable roles for this actor |
| GET | `/api/users/me` | Rep+ | Current user profile |

### FGA Approval Workflow
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/fga/freeze` | BU Head | Lock scores for period |
| GET | `/api/fga/pending?period=` | Manager+ | Scores awaiting review |
| POST | `/api/fga/{id}/manager-review` | Manager+ | Approve / dispute |
| POST | `/api/fga/{id}/hr-review` | BU Head (HR) | Override / approve |
| POST | `/api/fga/{id}/vp-approve` | BU Head (VP) | Final approval |
| GET | `/api/fga/export?period=` | Manager+ | CSV download for Finance |

### Incentives & Gamification
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/incentives/schemes?period=` | Rep+ | Active schemes for BU |
| POST | `/api/incentives/schemes` | Manager+ | Create incentive scheme |
| PATCH | `/api/incentives/schemes/{id}` | Manager+ | Update scheme |
| GET | `/api/incentives/leaderboard?period=` | Rep+ | Points leaderboard |
| GET | `/api/incentives/my-progress?period=` | Rep+ | Own scheme progress |
| GET | `/api/incentives/badges` | Rep+ | Badge catalogue |
| POST | `/api/incentives/award-badge` | Manager+ | Manually award badge |

### Scoring
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/scoring/templates` | Regional Manager+ | FGA weight templates (any parameter count) |
| POST | `/api/scoring/templates` | Regional Manager+ | Create/version template (auto-provisions `org_roles` row) |
| PATCH | `/api/scoring/templates/{id}/parameters` | Regional Manager+ | Full replace — add/remove/enable/disable parameters freely |
| PATCH | `/api/scoring/parameters/{id}/toggle` | Regional Manager+ | Quick enable/disable, no weight revalidation |
| GET | `/api/scoring/metrics` | Regional Manager+ | Available auto-calculator metric keys |
| GET | `/api/scoring/manual-entry/fields?role_key=` | Rep+ | Manual KPI fields for a role's active template (drives the entry form dynamically) |
| GET/POST | `/api/scoring/manual-entry` | Rep+ (own or in-scope) | Get/submit a period's manual KPI value |
| GET | `/api/scoring/my-score?period=` | Rep+ | Own FGA score |

### Daily Operations Report (DOR) — Service Delivery
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/dor` | Service Delivery Manager | Submit/update a day's ops report |
| GET | `/api/dor/history?month=` | Rep+ (own) | Own DOR entries for a month |
| GET | `/api/dor/team?month=` | Manager+ | Team's DOR entries, scoped |
| POST | `/api/dor/{id}/flag-opportunity` | Manager+ | Turn a delivery signal into a real (farming) PipelineDeal — CSG Phase 1 |

### Revenue Targets (Quarterly/FY)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/analytics/revenue/team-targets?mode=&fy=` | Manager+ | Monthly, or full FY quarterly grid |
| POST | `/api/analytics/revenue/targets/quarterly` | Business Head+ | Bulk-set Q1-Q4 for any number of members in one call |
| GET | `/api/analytics/revenue/targets/rollover-preview?fy=&growth_pct=` | Business Head+ | Suggests next-FY targets from prior-FY actuals + growth% |

---

## 🗄️ Database Schema

### Migrations (Alembic)

Current head: **0019**. Full table: [`MASTER_TRACKER.md` §4](./MASTER_TRACKER.md#4-migrations-alembic).
Highlights: `0003` = org_roles/scoring engine foundation, `0005` = v3 roles/incentives,
`0017` = Service Delivery FGA + DOR, `0018` = CSG Phase 1 (accounts, hunting/farming),
`0019` = fixed a real duplicate-row bug in `scoring_results`.

Run all migrations: `docker compose exec backend alembic upgrade head` (automatic via `update.sh`)

### Key tables

```
users               — all team members (all BUs, all businesses)
dsr_daily           — one row per user per date
self_scores         — 5-dimension self-scoring linked to dsr_daily
meetings            — F2F/virtual/call log with BANT fields
leads               — new lead pipeline
pipeline            — deals (extended to Opportunity in v2)
scoring_templates   — FGA weight templates (config-driven, pct or tiered)
scoring_parameters  — individual weight line items (tiers JSONB for banded scoring)
scoring_results     — computed FGA scores with approval workflow
manual_metric_entries — period KPI values for manual.* metric sources (Service Delivery)
dor_daily           — Service Delivery Manager's daily operations log
accounts            — persistent customer identity (anchors Sales + Service Delivery)
revenue_targets     — per-user per-period targets (monthly grain; quarterly/FY editor sums these)
ai_insights         — cached Ollama responses (6h TTL)
incentive_schemes   — Manager/BU Head created incentive programs
points_ledger       — gamification points earned
user_badges         — badges awarded
```

---

## 🏆 FGA Approval Workflow

**Flow:** BU Head freezes → Manager reviews → HR reviews/overrides → VP approves → Finance exports CSV

```
Score Freeze (BU Head)
        ↓
pending_manager  ─[Manager: approve]──→ pending_hr
                 └[Manager: dispute]──→ disputed ──→ pending_hr (HR can reopen)
                                                ↓
                                         pending_vp
                                                ↓
                                         approved ──→ Finance CSV export
```

**FGA Score composition (Sales FGA — editable in Scoring Admin):**

| Component | Weight | Metric |
|-----------|--------|--------|
| Business Generation | 40% | Revenue vs target |
| Sales Execution | 25% | Avg rigor score |
| Pipeline Quality | 20% | Avg BANT closure % |
| Professional Excellence | 15% | Self-score avg |

**PreSales FGA:**

| Component | Weight | Metric |
|-----------|--------|--------|
| Solution Support | 35% | Active presales engagements |
| Technical Conversion | 35% | Win rate % |
| Knowledge Excellence | 15% | Self-score avg |
| Operational Excellence | 15% | DSR compliance % |

---

## 🎮 Gamification & Incentive Schemes

Manager/BU Head creates schemes targeting any metric:

**Supported metrics:** `calls` · `visits` · `new_leads` · `proposals` · `followups` · `rigor_avg` · `bant_meetings` · `closed_won_value`

**Reward types:** `cash` (₹ amount) · `points` · `badge` · `recognition`

**Badge catalogue (10 badges):**

| Badge | Trigger |
|-------|---------|
| 🎩 Hat Trick | 3 deals closed in a month |
| ⭐ First Deal | First ever closed-won |
| 🔥 5-Day Streak | DSR submitted 5 days straight |
| 🔥🔥 10-Day Streak | DSR submitted 10 days straight |
| 🎯 Lead Machine | 10+ new leads in a month |
| 🧠 BANT Master | 5+ fully-qualified BANT meetings |
| 🏅 Consistent | Rigor > 70 for 3 months straight |
| 👑 Deal King | Highest revenue in BU for the month |
| ⚡ Rigor Champion | Rigor score > 90 for the month |
| 📞 Top Caller | Most calls in BU for the month |

---

## 🔢 Rigor Score Formula

Calculated per working day, excludes leave/holiday days from averages.

| Activity | Points | Max |
|----------|--------|-----|
| Customer visit (physical) | 15 per visit | 15 |
| Phone calls | 5 per call | 25 |
| Follow-ups completed | 3 per follow-up | 30 |
| New leads added | 10 per lead | 20 |
| Proposals sent | 10 per proposal | 10 |
| **Total** | | **100** |

WFH days: virtual meetings replace physical visits (max 15 pts for meetings).

**Labels:** `needs_improvement` (<50) · `average` (50–69) · `good` (70–84) · `excellent` (85+)

---

## 🗂️ Project Structure

```
fluidgo/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app, all routers
│   │   ├── config.py                 # Env settings
│   │   ├── database.py               # SQLAlchemy async engine
│   │   ├── models/__init__.py        # All ORM models + role hierarchy constants
│   │   ├── routers/
│   │   │   ├── auth.py               # Login, refresh
│   │   │   ├── dsr.py                # DSR submit/get
│   │   │   ├── meetings.py           # Meeting log
│   │   │   ├── leads.py              # Lead pipeline
│   │   │   ├── pipeline.py           # Deal pipeline
│   │   │   ├── opportunities.py      # Opportunity intelligence (v2)
│   │   │   ├── analytics.py          # Dashboard, team, revenue analytics
│   │   │   ├── ai.py                 # Ollama integration
│   │   │   ├── users.py              # User management (v3 roles)
│   │   │   ├── scoring.py            # FGA scoring templates
│   │   │   ├── fga_approval.py       # FGA approval workflow
│   │   │   ├── incentives.py         # Incentive schemes & gamification
│   │   │   ├── roles.py              # Org role CRUD
│   │   │   └── dor.py                # Daily Operations Report (Service Delivery) + opportunity flagging
│   │   ├── services/
│   │   │   ├── auth_service.py       # JWT + bcrypt
│   │   │   ├── deps.py               # Route guards (require_role/level/scope)
│   │   │   ├── ai_service.py         # Ollama prompt builder + streaming
│   │   │   ├── rigor_service.py      # Rigor score + BANT calculator
│   │   │   ├── scoring_engine.py     # FGA computation engine (pct + tiered)
│   │   │   ├── deal_health_service.py # Deal health scoring
│   │   │   ├── account_service.py    # Customer identity resolution (CSG Phase 1)
│   │   │   └── permission_service.py # Data-scope resolver (recursive hierarchy)
│   │   ├── repositories/             # DB query helpers
│   │   └── prompts/                  # Ollama prompt templates
│   ├── alembic/                      # DB migrations (0001–0019)
│   ├── seed.py                       # Dev seed (Danish May 2026 data)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Login.tsx             # Split-screen WEPSol branded login
│   │   │   ├── Dashboard.tsx         # Role-aware KPIs, AI panel, quick tiles
│   │   │   ├── DSREntry.tsx          # Daily DSR form with self-scoring
│   │   │   ├── Meetings.tsx          # BANT-scored meeting log
│   │   │   ├── Leads.tsx             # Lead pipeline
│   │   │   ├── Pipeline.tsx          # Deal pipeline
│   │   │   ├── Opportunities.tsx     # Opportunity intelligence (v2)
│   │   │   ├── Analytics.tsx         # Charts: calls, follow-ups, rigor trend
│   │   │   ├── Team.tsx              # Team management + performance matrix
│   │   │   ├── RevenueIntelligence.tsx # Revenue vs target dashboard
│   │   │   ├── FGAApproval.tsx       # FGA approval workflow (all stages)
│   │   │   ├── ScoringAdmin.tsx      # FGA weight configuration — dynamic parameters, tier editor
│   │   │   ├── DOREntry.tsx          # Service Delivery daily ops log + Flag Opportunity
│   │   │   └── ManualKPIEntry.tsx    # Monthly manual.* metric entry (dynamic per template)
│   │   ├── components/
│   │   │   └── layout/Layout.tsx     # Dark navy sidebar + mobile nav + idle-logout warning
│   │   ├── hooks/
│   │   │   ├── useApi.ts             # Axios + JWT refresh (singleton pattern)
│   │   │   └── useIdleLogout.ts      # 30-min idle timeout, warning + auto-logout
│   │   └── store/authStore.ts        # Zustand auth state
│   ├── tailwind.config.js            # WEPSol brand tokens
│   ├── vite.config.ts                # PWA manifest
│   └── Dockerfile.dev
├── nginx/dev.conf                    # Reverse proxy config
├── docker-compose.yml                # All 5 services
├── .env.example                      # Required env vars
├── README.md                         # This file
└── MASTER_TRACKER.md                 # Living architecture/status/roadmap doc (see top of this file)
```

---

## 🛠️ Dev Commands

```bash
# View all logs
docker compose logs -f

# Backend only
docker compose logs -f backend

# Run a new migration
docker compose exec backend alembic upgrade head

# Connect to database
docker compose exec db psql -U fluidgo fluidgo

# List Ollama models
docker compose exec ollama ollama list

# Pull a better model (needs t3.large / 8GB RAM)
docker compose exec ollama ollama pull mistral

# Restart backend after code changes
docker compose restart backend

# Re-seed database (safe — skips existing records)
docker compose exec backend python seed.py

# Run auth/permission verification
docker compose exec backend python debug_auth.py
```

---

## 💰 Monthly Cost (AWS Production)

| Resource | Spec | Cost/month |
|----------|------|-----------|
| EC2 t3.large (1yr reserved) | 8GB RAM, 2 vCPU | ~₹3,200 |
| EBS gp3 50GB | Root + data | ~₹350 |
| Data transfer | ~5GB/mo | ~₹45 |
| **Total** | | **~₹3,600/month** |

---

## 🚀 Production Deployment (EC2 + k3s)

> See WEP-33 in Linear for full k8s manifests.

**Quick steps:**
1. Launch EC2 t3.large, Ubuntu 22.04, 50GB gp3
2. SSH in, run `setup-ec2.sh`
3. Point DNS `dsr.fluidpro.in` → EC2 public IP
4. Push to `main` branch → GitHub Actions CI/CD deploys automatically

**k8s manifests location:** `k8s/` directory (apply with `kubectl apply -f k8s/`)

---

## 📋 Linear Sprint Status

> Linear hit its free-tier issue cap 2026-07-11 — table below is a snapshot,
> may not reflect the newest work. See [`MASTER_TRACKER.md` §5](./MASTER_TRACKER.md#5-feature--epic-status)
> for current status, and the "Epic 9 – CSG Roadmap & Phasing" project doc
> in Linear (a document, not an issue, since the cap blocked issue creation).

| Issue | Title | Status |
|-------|-------|--------|
| WEP-27 | Docker Compose scaffold | ✅ Done |
| WEP-28 | DB schema + migrations | ✅ Done |
| WEP-29 | FastAPI backend + Ollama | ✅ Done |
| WEP-30 | React PWA frontend | ✅ Done |
| WEP-31 | AI engine (Ollama + BANT) | ✅ Done |
| WEP-32 | Integration + E2E testing | 🔄 In Review |
| WEP-33 | EC2 + k3s + HTTPS | ⏳ Todo |
| WEP-34 | CI/CD + pilot onboarding | ⏳ Todo |
| WEP-35 | Pilot feedback + full rollout | ⏳ Todo |
| WEP-36 | Revenue Intelligence Dashboard | 🔄 In Progress |
| WEP-37 | Opportunity Intelligence | 🔄 In Progress |
| WEP-38 | Sales Performance Engine (FGA) | 🔄 In Progress |
| WEP-39 | Variable Pay Automation | 📋 Backlog |
| WEP-40 | AI Coaching | 📋 Backlog |
| WEP-41 | Role-Based Governance (v3) | 🔄 In Progress |
| WEP-42 | Kylas CRM Integration | 📋 Backlog (deferred) |
| WEP-43 | Platform & Infrastructure | 📋 Backlog (deferred) |

---

## 🔮 What's Next

> Roadmap moved to [`MASTER_TRACKER.md` §7](./MASTER_TRACKER.md#7-roadmap-near--far) —
> kept current there since it changes every session. This section previously
> listed items (Gamification UI, Team v3, EC2 deploy) that are now all long done.

---

## 🏢 Multi-Business Roadmap

| Business | Status | Notes |
|----------|--------|-------|
| fluidPro | ✅ Phase 1 (active) | IT Infra Managed Services — West BU |
| fluidPrint | 📋 Phase 2 | Managed Print Services |
| floxtax | 📋 Phase 2 | GST / ASP / GSP Solutions |
| Hooks | 📋 Phase 2 | POS / Printer / AIDC / Channel Sales |

Data model supports all 4 businesses. Phase 1 = fluidPro West BU only. Phase 2 activates other businesses when ready.

---

## ⚠️ Known Issues / Limitations

> Current, actively-maintained list: [`MASTER_TRACKER.md` §6](./MASTER_TRACKER.md#6-known-issues) —
> this section is now historical/stable-only entries that don't change often.

- **FGA period default** — FGA Approval page defaults to previous month (correct). Current month scores can only be frozen after month-end.
- **Ollama cold start** — first AI analysis after container start takes 15–30s on CPU-only mode.
- **PostCSS warning** — `postcss.config.js` needs `"type": "module"` in `package.json`. Non-blocking.

---

## 🧾 Recent Progress

> Session-by-session log moved to [`MASTER_TRACKER.md` §8](./MASTER_TRACKER.md#8-session-log) —
> that's the current, growing history. Entries below predate that file and
> are kept for continuity.

- **Fixed:** `/dsr/history` 500 error — `_edit_lock_state()` in `dsr.py` compared a tz-naive `datetime.utcnow()` against tz-aware `submitted_at`/`edit_granted_until` (Postgres `timestamptz`), raising `TypeError`. Same bug present in approve/reject, request-edit, grant-edit, and `/dsr/team/edit-requests`. All six spots now normalize via a shared `_aware()` helper and `datetime.now(timezone.utc)`.
- **Fixed:** `smoke_test.py` was silently broken two ways — wrong port in the run command, and 4 of its 6 test accounts had been deactivated (left deactivated per Amit's call — see MASTER_TRACKER.md §6).
- **Solved — dual-hat role mapping**, later generalized into the fully recursive hierarchy described in §2 above (any depth, not just one level).

---

*Built by WEP Solutions Ltd · Internal Confidential · fluidGo v1 · July 2026*
