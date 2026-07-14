# fluidGo — Master Tracker

> **Why this file exists:** Linear's free-tier issue cap was hit on 2026-07-11
> (see WEP-86 for the last issue that went through). Until the plan is
> upgraded or old issues are archived, **this file is the source of truth**
> for architecture state, feature status, known issues, and roadmap — update
> it every session instead of assuming Linear has the full picture. Linear
> is still used where it has room; this file always wins on conflict since
> it's guaranteed current.

**Update convention:** add a dated entry to the Session Log at the bottom
every session. Update the status tables above it when something's state
changes. Don't delete old session log entries — this is a history, not just
a snapshot.

---

## 1. Current Architecture Snapshot

- **Stack:** React 18 PWA (Vite+TS) · FastAPI · PostgreSQL 15 · SQLAlchemy 2.0 async · Ollama (phi3:mini) · Docker Compose · Nginx reverse proxy
- **Deployed:** AWS EC2 (Mumbai/ap-south-1), IP `65.2.205.77`, app dir `/opt/fluidgo/app`
- **Repo:** `amitipst/fluidgo` (GitHub), branch `main`
- **Migrations:** Alembic, current head **0019** (see §4)
- **Deploy pattern:** local edit (Desktop Commander) → `git push` → on EC2: `bash <(curl -fsSL https://raw.githubusercontent.com/amitipst/fluidgo/main/update.sh)` — builds both images, runs migrations, restarts, runs smoke tests automatically.


## 2. Role Hierarchy (current, as of 0019)

```
CEO / super_admin  (level 99/50) — all businesses, all regions
  └── COO           (level 45)  — all businesses (not scoped to one `business`)
        └── Business Head        (level 40, scope=business) — ALL regions within ONE business line
              │   ("BU" = business line: fluidpro/fluidprint/floxtax/hooks — NOT a region)
              └── Regional Manager (level 30, scope=region) — ONE region within ONE business
                    │   ("bu_head" = deprecated old name for this role, kept as alias only)
                    └── Manager      (level 20, scope=team) — FULL reporting chain via manager_id,
                    │                  any depth (recursive) — not just direct reports
                    │     ├── Sales Rep / Inside Sales / Pre-Sales (level 10) — own data only
                    │     └── Service Delivery Manager (level 20, scope=team) — own reportees +
                    │                  Service Delivery FGA/DOR track (separate from Sales/PreSales)
HR       (level 25, scope=hr)      — all users' FGA scores, no sales data
Finance  (level 25, scope=finance) — approved FGA export only
```

**Dual role (any level):** anyone can ALSO be personally set as someone's
`manager_id` via Team page → "Reports to (Manager)", independent of their
own region/business/scope. `resolve_visible_user_ids()` unions that whole
personal reporting subtree (recursive, any depth) into whatever their
primary role already grants — works everywhere (DSR approval, targets, FGA,
meetings, pipeline...), not just one screen. This is also how Sales and
Pre-Sales (or Service Delivery) run entirely separate manager chains under
the same Business Head.

**Assignable via Team page today:** `rep` · `inside_sales` · `pre_sales` ·
`manager` · `service_delivery_manager` · `regional_manager` · `business_head`
· `coo` · `hr` · `finance` · `ceo` · `super_admin`. (`bu_head` still works if
referenced by old data/integrations, but is no longer offered in the picker.)

---

## 3. FGA / Scoring Architecture

Config-driven — templates and weights live in `scoring_templates` /
`scoring_parameters`, never hardcoded. Two calc types:

- **`calc_type='pct'`** — value is a straight 0-100 achievement %; contribution
  = value × (weight/100). Used by Sales (40/25/20/15) and PreSales (35/35/15/15).
- **`calc_type='tiered'`** — value is looked up against a `tiers` JSON list of
  bands to find a MULTIPLIER; contribution = weight × multiplier (can exceed
  the parameter's base weight for strong performance, or hit 0 for weak).
  Used by Service Delivery FGA — validated to reproduce the source Excel
  exactly (112.5 total, all 6 KRAs match).

**`manual.*` metric_source** — no auto-calculator; value comes from
`ManualMetricEntry` (Monthly KPI Entry screen), for KPIs sourced outside
fluidGo (collections, ticketing). All 6 Service Delivery KRAs are manual.

**Scoring Admin (`/scoring-admin`)** — any number of parameters (not fixed to
4), enable/disable a parameter without losing its config, tier band editor,
create new templates in-UI. **Known gotcha:** `scoring_templates.role_key`
has an enforced FK to `org_roles.role_key` — creating a template with a
role_key that has no `org_roles` row 500s. `create_template` now
auto-provisions the row (fixed 2026-07-11), so this shouldn't recur, but
it's the thing to check first if "+ New Template" ever 500s again.

**Approval workflow (Sales/PreSales only so far):** BU/Business Head freezes
→ Manager reviews → HR reviews/overrides → VP approves → Finance exports CSV.
**Service Delivery FGA has no approval workflow yet** — direct entry only.
Open question, not yet decided: wire it into the same workflow before UAT,
or leave direct-entry for now.


## 4. Migrations (Alembic)

| Rev | File | Content |
|-----|------|---------|
| 0001-0002 | initial_schema, add_user_is_active | Core tables |
| 0003 | v2_foundation | org_roles, scoring_templates/parameters/results, revenue_targets, pipeline v2 fields |
| 0004-0013 | (see alembic/versions/) | FGA approval workflow, v3 roles/incentives, win-loss, target unique-by-type, etc. |
| 0014-0016 | password_reset_tokens, ..., win_loss_analysis | |
| **0017** | sdm_fga_and_dor | `scoring_parameters.tiers`/`is_active`, `manual_metric_entries`, `dor_daily` |
| **0018** | csg_accounts_farming | `accounts` table, `pipeline.deal_type`/`source`/`account_id`, `dor_daily.account_id` |
| **0019** | scoring_results_unique | De-dupes + adds missing UNIQUE constraint on `scoring_results(user_id, template_id, period)` — fixes a real FGA-freeze 500 bug, see §6 |

Run all: `docker compose exec backend alembic upgrade head` (also runs automatically via `update.sh`).

---

## 5. Feature / Epic Status

| Area | Status | Notes |
|---|---|---|
| Revenue Intelligence (targets, quarterly/FY editor) | ✅ Live | Q1-Q4 grid, auto FY total, rollover pre-fill with growth% |
| RBAC — Regional Manager, dual-role, recursive hierarchy | ✅ Live | See §2 |
| Sales FGA / DSR | ✅ Live (UAT in progress per Amit) | |
| PreSales FGA / DSR | ✅ Live (believed UAT-ready, not independently re-verified this session) | |
| Service Delivery Manager — FGA + DOR | ✅ Live, 🔶 UAT blocked until org_roles fix + template reseed deployed (see §6) | |
| Reports section (CSV/PDF export) | ❌ Not started | Discussed, not built — see roadmap |
| CSG Phase 1 — Account entity, hunting/farming, delivery→sales signal | ✅ Live | `POST /api/dor/{id}/flag-opportunity` |
| CSG Phase 2-6 (Meetings/MOM/SIP/Timeline/AI engines/integrations) | 📋 Roadmap only | See Linear doc "Epic 9 – CSG Roadmap & Phasing" (project doc, not an issue — plan limit) |
| Auto session logoff (idle timeout) | ✅ Live | 30 min idle → warning banner (60s countdown) → auto-logout. Tunable in `useIdleLogout.ts` |
| Reports/README/architecture docs | ✅ Updated 2026-07-11 | This file + README.md |


## 6. Known Issues

### 🔴 Open — needs your input or a repro
- **Team page crash on "Add Member" with a new role.** Reported 2026-07-11
  trying to onboard Hemant as Service Delivery Manager — full-page React
  ErrorBoundary crash, then several endpoints (`/analytics/team`, `/dsr/team`,
  `/ai/team/...`, `/users/roles`) started returning 401 afterward. Reviewed
  `create_user`, `/api/analytics/team` (incl. `calculate_avg_rigor` on an
  empty DSR list — confirmed safe, returns 0.0 not a crash), and the auth
  refresh interceptor — found no bug via static review. The 401 pattern
  across 4 unrelated endpoints strongly suggests the session had already
  gone stale (token expiry) rather than a data-shape crash — auto-logout
  (§5) should help going forward, but the ORIGINAL crash cause is still
  unconfirmed. **Next time it happens: scroll UP in the browser console
  above the stack trace to the actual red error line (e.g. "TypeError:
  Cannot read properties of undefined...") and paste that — the stack trace
  alone (minified function names) isn't enough to pinpoint it.**
- **Service Delivery FGA approval workflow** — not built. Direct-entry only
  right now. Needs a decision (see §3) before UAT if approval is required.
- **Reports section (CSV/PDF export)** — discussed at length, not built yet.

### ✅ Fixed this session (2026-07-11)
- **`org_roles` FK violation** — `scoring_templates.role_key` has an enforced
  FK to `org_roles.role_key`. Nothing had ever inserted a `service_delivery`
  row, so BOTH `seed_sdm_fga.py` (deleted, superseded) AND the Scoring Admin
  "+ New Template" UI button 500'd for ANY brand-new role_key, not just this
  one. Fixed two ways: (1) `seed_service_delivery.py` — new idempotent,
  direct-DB script that registers the role AND seeds the 6-KRA template
  atomically; (2) `create_template` now auto-provisions the `org_roles` row
  inline, so this class of bug can't recur for a future role_key typed into
  the UI.
- **FGA freeze 500** — `scoring_results` only ever had an INDEX on
  `(user_id, template_id, period)`, never a UNIQUE constraint. If any earlier
  freeze run raced or double-inserted, duplicate rows exist, and
  `.scalar_one_or_none()` throws `MultipleResultsFound` — a real 500.
  Migration 0019 de-dupes (keeps most-recent row per group) then adds the
  missing constraint. `freeze_period` also now: fetches all matches instead
  of assuming one, isolates each rep in a try/except so one bad row can't
  crash the freeze for everyone else, and returns a `failed` array with the
  actual Python error message per rep if it does happen again.

### ✅ Fixed in earlier sessions (carried over from README, still accurate)
- `/dsr/history` 500 — tz-naive/aware datetime comparison in `_edit_lock_state()`.
- `smoke_test.py` wrong port + 4 deactivated test accounts (reactivation
  script exists at `backend/reactivate_smoke_accounts.py` — **not run**,
  Amit chose to leave those accounts deactivated, 2026-07-11).
- Dual-hat role mapping (business_head personally managing a team) — now
  superseded by the fully recursive hierarchy in §2.


## 7. Roadmap (near → far)

1. **Immediate:** deploy today's fixes, run `seed_service_delivery.py`,
   retry onboarding Hemant, retry FGA freeze, retry "+ New Template" — confirm
   all three are actually fixed against production, not just reasoned about.
2. **Reports section** — CSV/PDF export with date-range selector (DSR,
   Revenue, OB, Pipeline, Opportunities, Meetings). Designed, not built.
3. **CSG Phase 2** — Meeting Management + AI MOM Generator. Foundational
   data-capture layer; nothing in Phase 4/5 has data to analyze until this
   exists. See Linear project doc "Epic 9 – CSG Roadmap & Phasing" for full
   phasing and the reasoning behind the order.
4. **CSG Phase 3** — Service Improvement Plans (SIP) + Customer Timeline.
5. **CSG Phase 4-5** — AI Customer Intelligence (health/risk scoring), AI
   Opportunity Engine (auto-surfaced expansion signals) — supersedes Phase
   1's manual "Flag as Opportunity" once there's enough meeting data to
   automate it.
6. **CSG Phase 6 (deferred)** — external integrations (ServiceDesk Plus,
   Site24x7, Seceon, Teams, Outlook), matching the existing WEP-42/43
   deferred-integration pattern.
7. **Linear plan** — upgrade or archive old issues; convert the CSG roadmap
   doc into a proper Epic 9 with sub-issues once there's room.

---

## 8. Session Log

### 2026-07-11 (this session)
Built: Service Delivery Manager role + tiered/manual FGA scoring + DOR daily
log + dynamic Scoring Admin (add/remove/enable-disable parameters, tier
editor, new-template UI) — validated against the source Excel exactly
(112.5 total, all 6 KRAs match). Regional Manager role (fixed the "BU Head"
mislabeling — BU = business line, not region). Dual-role RBAC (personal
manager_id assignment honored everywhere, not just one screen). Recursive
org-chart hierarchy (a manager's manager sees the whole team, any depth) via
`WITH RECURSIVE` CTE. CSG Phase 1 (Account entity, hunting/farming pipeline
split, Service Delivery → Sales opportunity flagging). Fixed two real
production bugs (`org_roles` FK violation, `scoring_results` missing unique
constraint — see §6). Built auto session logoff (30 min idle timeout).
Created this tracker (Linear free-tier issue cap hit mid-session).

**Not resolved:** Team page crash on member creation — see §6 Open Issues.
Needs the actual browser console error text (not just the stack trace) next
time it happens.

**Migrations added:** 0017, 0018, 0019 — all additive, no destructive changes.

### 2026-07-13 (this session)
Built: Pipeline update history. Today's Update / Next Step on a deal were
overwritten in place on every Save — no trail of what a rep reported over
time. Added `pipeline_updates` append-only table (migration 0020, soft
references, no FK constraint — same pattern as `account_id`/
`presales_owner_id` on `pipeline`). `PATCH /pipeline/{id}` now writes a
history row whenever `todays_update` changes, in the same transaction as
the deal update; existing `todays_update`/`next_step` columns stay as the
current-state snapshot so the Pipeline list view is unchanged. New
`GET /pipeline/{id}/updates` returns the ordered timeline (same visibility
rule as the deal itself). `PipelineHistory.tsx` adds a collapsible "Show
history" section to the Pipeline card edit form. Verified locally
(`py_compile` on the three backend files, `tsc --noEmit` on the frontend —
both clean) and pushed to `main` (commit `89e876e`); not yet deployed to
EC2 or run against a live DB. Logged on WEP-37 (Epic 2 – Opportunity
Intelligence) instead of a new sub-issue — workspace is over Linear's free
issue limit, update-in-place still works.

**Not resolved / next step:** this is the foundation, not the full ask —
the actual AI trend analysis (stall detection: flag deals with no update
in N days; momentum summary via the same Ollama call pattern as
`generate_deal_postmortem` in pipeline.py) still needs to be built on top
of the now-ordered `pipeline_updates` sequence.

**Migrations added:** 0020 — additive, no destructive changes.

---

### 2026-07-14 (this session)
Built: forced password change security hardening. Audited existing auth
first — bcrypt hashing, mandatory JWT_SECRET, short-lived access tokens,
single-use hashed reset tokens, and no-enumeration login/forgot-password
were already solid. What was missing: no must_change_password flag, no
admin-initiated reset (only the email-link self-service flow existed), no
logged-in "change my password" endpoint at all.

Added: `must_change_password` + `password_changed_at` on users (migration
0021, backfilled true for all existing rows — nobody grandfathered out).
Enforced server-side in `deps.get_current_user` via a path allowlist, not
just a frontend redirect — a still-valid access token cannot be used for
anything else until the password is changed. New
`POST /auth/change-password` (self-service, requires current password) and
`POST /users/{id}/reset-password` (admin/manager, generates a random temp
password server-side — the actor never chooses one — returned once,
never logged). NIST 800-63B aligned policy (min 10 chars, no forced
complexity classes, blocks common passwords + name/email substrings),
shared between change-password and the existing reset-password endpoint so
they can't drift apart. Frontend: `ChangePassword.tsx`, `ProtectedRoute`
hard-gate, axios interceptor catches the mid-session case (admin resets
a password while the user is already logged in on a valid token), Team.tsx
"Reset Password" action with a one-time temp-password reveal modal.

**Important operational note — every existing UAT user, including Amit,
will hit the forced change-password screen on their very next action after
this deploys**, since the migration backfills `must_change_password=true`
for all pre-existing rows. This is intentional (see rationale above) but
is a real behavior change on a live UAT with real reps — worth a heads-up
to the pilot team before/immediately after deploying, not a silent surprise.

**Migrations added:** 0021 — additive (two nullable/defaulted columns), no
destructive changes, but see the operational note above for the app-level
behavior change it triggers.

Also fixed two rep-reported bugs same session: (1) Dashboard AI Performance
Intelligence panel was cutting off mid-sentence - `ai_service.analyse()`'s
`num_predict=250` was too low for the 4-section ~220-word `daily_insight`
prompt; bumped to 400 (timeout 360->420 to match). (2) Any deal sitting at
stage `qualification` (the default when a lead is converted, see
`Leads.convert_lead_to_deal`) or `on_hold` (a `close_deal` outcome) could not
be edited or saved at all - `pipeline.py`'s `DealIn.stage` Literal only
allowed cold/warm/hot/closed_won/closed_lost, and PATCH always sends the
full body, so the unchanged-but-invalid current stage 422'd regardless of
which field the rep was actually trying to edit. This is what reps meant by
"once a lead is qualified we can't reverse it" - fixed by expanding the
Literal (backend) and the STAGES/stageCfg dropdown (frontend) to cover every
stage value the app can actually produce.

**Investigated, not a code bug:** reps also reported DSRs "not editable."
The 24h self-edit window + manager request/grant-exception flow
(`request-edit` -> `team/edit-requests` -> `grant-edit`) is fully wired
end-to-end on both backend and frontend (DSRHistory.tsx fetches AND renders
pending requests in the Team view). Most likely explanation is reps hitting
the window and not knowing "Request Edit" exists, or managers not checking
the Team tab - a workflow/visibility gap, not a defect. Flagged to Amit for
a decision (longer window? a badge/notification for managers?) rather than
guess-fixing a system that's working as designed.

---

*This file supersedes README.md's "Recent Progress" and "Known Issues"
sections going forward — check here first. README.md stays the quick-start
reference; this file is the detailed, chronological record.*
