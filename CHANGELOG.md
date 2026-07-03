# fluidGo — Changelog

All notable changes to fluidGo are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [1.0.0-uat] — 2026-07-03

> **UAT Release** — First production-grade release of fluidGo for WEP Solutions.
> This version is deployed to the UAT environment for user acceptance testing
> before promotion to production (`v1.0.0`).
>
> **UAT test period:** 3 July 2026 → 10 July 2026
> **Pilot users:** West BU — fluidPro Sales + Pre-Sales + Managers + BU Head

### ✅ Acceptance Testing
- 75/75 vertical slice checks PASS (100%)
- All 10 roles authenticate with correct JWT + permissions
- Complete DSR lifecycle: Sales Rep → Manager → BU Head
- Pre-Sales DSR with separate activity fields (demos, POC, proposals)
- RBAC: all 5 cross-role security blocks verified (403)
- Dashboard wiring: real-time data refresh after DSR submit
- Analytics: rigor score, BANT, revenue — all computed from real SQL
- FGA workflow: freeze → manager → HR → VP → Finance CSV export

### Added — Backend
- v3 Role hierarchy (10 roles: rep, inside_sales, pre_sales, manager, bu_head,
  business_head, hr, finance, ceo, super_admin)
- Multi-BU data isolation with `business` + `bu` + `manager_id` FK scoping
- Pre-sales DSR fields: demos_conducted, pocs_conducted, proposals_supported,
  tech_discussions, workshops_conducted, trainings_delivered, trainings_attended,
  docs_created, linked_opportunity_id, dsr_type, proposal_value, travel_day
- Pre-sales self-score dimensions: solution_support, technical_conversion,
  knowledge_excellence, operational_excellence
- FGA Approval Workflow (5-stage: pending_manager → pending_hr → pending_vp → approved)
- Incentive Schemes engine (8 metric types, 4 reward types)
- Gamification: points ledger, 10 badge catalogue, BU leaderboard
- HR/Finance excluded from gamification leaderboard
- Pre-sales rigor formula (demos/POC/workshops scoring model)
- `/api/analytics/dashboard?month=` — role-aware month-selectable KPIs
- `/api/fga/*` — full approval workflow endpoints
- `/api/incentives/*` — schemes, progress, leaderboard, badges
- Alembic migrations 0001–0006 applied
- Gunicorn + uvicorn workers for production (3 workers on t3.large)
- Non-root Docker user for backend container security

### Added — Frontend
- WEPSol / fluidPro brand identity applied throughout
  - fluidGo logo (SVG): angular stripe icon + "fluidGo" wordmark in brand purple `#92278E`
  - Brand colours: fluidPro pink `#F0115E`, purple `#92278E`, grey `#808083`
  - Deep purple sidebar (`#1A0B2E` → `#2D1452`) with pink active states
  - Orange CTA buttons replaced with brand-correct fluidPro pink
- Login page: split-screen brand design, "Challenge the Norm. Elevate Sales."
- Role-aware org label: CEO sees "All BUs", BU Head sees "West BU · fluidpro"
- Dashboard: month picker, BU-aggregated KPIs, AI panel, quick-action tiles
- DSREntry: role-conditional forms — sales vs pre-sales activities + self-scores
- Leads: search + source + status filters, inline ➕ Add Lead form
- Pipeline: search + stage + practice filters, inline ➕ Add Deal form
- FGAApproval: full approval workflow UI with status-aware review modal
- Gamification: My Progress (rep), Scheme Manager (manager), BU Leaderboard
- Vite host security fix: `allowedHosts: true` for nginx Docker proxy
- TypeScript types updated for v3 roles (AuthUser, Role type)
- PWA manifest updated with fluidGo brand (theme-color `#92278E`)

### Added — Infrastructure
- `Dockerfile.prod` (backend): gunicorn + uvicorn, non-root user, health check
- `Dockerfile.prod` (frontend): multi-stage build → nginx alpine, SPA routing
- `docker-compose.prod.yml`: production compose, EBS-bound volumes, memory limits
- `nginx/prod.conf`: SSL termination, rate limiting, security headers, CSP
- `.env.prod.example`: production environment template with auto-generated secrets
- `setup-ec2.sh`: one-command EC2 bootstrap (Ubuntu 22.04, Docker, UFW, fail2ban)
- `.github/workflows/release.yml`: full release pipeline with test/build/UAT/prod gates
- `.github/workflows/deploy.yml`: legacy deploy workflow (replaced by release.yml)
- `backend/smoke_test.py`: 45-check smoke test, runs post-deploy against live URL
- `backend/vertical_slice_test.py`: 75-check full acceptance suite
- `package-lock.json`: generated for reproducible CI builds
- Daily PostgreSQL backup cron (30 2 * * *)
- systemd service for auto-restart on reboot
- fail2ban nginx rate limiting

### Fixed
- 502 Bad Gateway: Vite v5 `allowedHosts` breaking nginx→frontend proxy
- Pre-sales rigor showing 0/100 (separate formula for presales dsr_type)
- HR Manager + Finance Head appearing in gamification leaderboard
- `ScoreSlider` React key spread warning in DSREntry.tsx
- BU Head dashboard showing 0 KPIs (was fetching own DSRs instead of BU aggregate)
- FGA freeze returning MultipleResultsFound (scoped to user+template+period)
- JWT refresh race condition under concurrent 401 responses (singleton pattern)

### Security
- All API endpoints enforce role-level guards
- Production: ports 8000/5432 bind to 127.0.0.1 only (not exposed externally)
- nginx: X-Frame-Options, X-Content-Type-Options, HSTS, CSP headers
- Rate limiting: 30 req/min general, 5 req/min on /auth/login
- fail2ban: 5 failed logins → 1h ban
- Non-root Docker user for backend (uid 1001)

### Database
- 6 Alembic migrations applied (0001–0006)
- 27 users seeded (2 BU Head, 4 Manager, 12 Sales Rep, 6 Pre-Sales, 3 support)
- 1,036 DSR rows (Apr–Jul 2026, ~85% compliance rate)
- 160+ meetings with BANT scoring
- 105 pipeline deals (20 won, 15 lost, 70 active)
- 42 leads with AI scores
- Revenue targets: 4 months × 12 reps
- 15 incentive schemes (May/Jun/Jul × 5 schemes)

### Known Issues (to fix in v1.0.1)
- Revenue targets set via API only — no UI for BU Head to set targets inline
- manager_id not assignable via Team onboard form (API-only)
- Ollama cold start: 15–30s for first AI analysis after container restart
- Duplicate scoring_result rows if FGA freeze called on already-frozen period

---

## Version Guide

```
v1.0.0-uat   → UAT release (this version)
v1.0.0       → Production promotion after UAT sign-off (target: 10 July 2026)
v1.0.1       → First hotfix release
v1.1.0       → Next feature sprint (Manager coaching notes, DSR reminder,
                Revenue targets UI, Multiple BU support)
v2.0.0       → Multi-business release (fluidPrint, floxtax, Hooks)
```

---

## Release Process

```
Feature branch → PR to main
    ↓ (automated)
Full test suite (vertical_slice_test.py — 75 checks)
TypeScript compilation check
    ↓ (if all pass)
Merge to main → Auto-deploy to UAT
    ↓ (manual: 5-7 day UAT period)
git tag v1.0.0 && git push origin v1.0.0
    ↓ (automated CI)
Build production Docker images
    ↓ (manual: GitHub Environment approval gate)
Deploy to Production
Create GitHub Release with auto-generated notes
```
