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

### 2026-07-14 (this session)
Resolved the DSR-editability investigation from the prior session: added a
manager-facing badge instead of changing the edit-lock logic itself (which
was confirmed working as designed). Sidebar now shows a live count, polled
every 60s, from `GET /dsr/team/edit-requests` on the DSR nav link for any
role that can act on it (manager/regional_manager/bu_head/business_head/
ceo/super_admin). Also fixed a related gap found while building this:
regional_manager+ roles had **zero** sidebar path to DSR Team review at
all, since "My DSR Log" is `fieldOnly` and hidden for them — added a
dedicated "DSR Approvals" nav item under Management for those roles,
deep-linking via `?view=team` (`DSRHistory.tsx` now reads that query param
on mount). Verified (`tsc --noEmit` clean) and deployed to EC2 alongside
the previously-pending AI-truncation/deal-stage fixes — all three (AI
panel truncation, lead-qualification reversal, DSR badge) confirmed live
via `alembic current` (0021, unchanged) and 200 responses on both local
and public HTTPS. Commits `59a55fd`, `0ca1436`.

Built the AI trend analysis deferred from 2026-07-13's pipeline-history
work, now that `pipeline_updates` gives an ordered per-deal remark
sequence to analyse:
- **Stall detection** (pure SQL, no LLM): `GET /pipeline` now returns
  `days_since_activity` and `is_stalled` per deal, computed from
  `last_activity_at` (already bumped on every PATCH). A deal counts as
  stalled at 7+ days with no activity, but only while it's in an open
  stage (cold/warm/hot/qualification) — `on_hold` is an intentional pause
  and closed_* are terminal, so both are excluded. Surfaced as a
  🐌 Stalled badge on the Pipeline card.
- **AI momentum check** (on-demand, rep-triggered): new
  `POST /pipeline/{id}/momentum` feeds the last 5 `pipeline_updates` rows
  (chronological) to phi3:mini via the existing `analyse()` call pattern
  (same as `generate_deal_postmortem`), asking for one short verdict —
  moving forward / stalled / going in circles — with supporting evidence.
  Deliberately rep-triggered rather than auto-run on every save, to keep
  Ollama load bounded on the 2-vCPU host. Result caches on the deal row
  (`ai_momentum_summary`/`ai_momentum_generated_at`, migration 0022) so
  `GET /pipeline/{id}/momentum` can hydrate the last verdict without
  re-running it. New `DealMomentum.tsx` component adds a "Check momentum"
  section to the Pipeline card edit form, next to the existing history
  timeline. Needs at least 2 logged updates to produce a verdict.
Verified locally (`py_compile` on the three backend files, `tsc --noEmit`
on the frontend — both clean); not yet deployed to EC2 or run against a
live DB.

**Migrations added:** 0022 — additive (two nullable columns on `pipeline`),
no destructive changes.

### 2026-07-14, later same day — production regression + 3 more fixes
Deployed the AI trend analysis above, then Amit reported Pipeline showing
"0 of 0 deals" in production while Opportunities (same underlying table)
still showed all 10. Root cause: the stall-detection code just shipped
subtracted a naive `datetime.utcnow()` from `last_activity_at`/`created_at`,
which come back tz-aware from asyncpg on `DateTime(timezone=True)` columns
- the exact bug class already fixed once in `dsr.py`'s `_edit_lock_state`.
The `TypeError` 500'd `GET /pipeline`; the frontend's `useQuery` silently
falls back to an empty array on a failed request, so it just looked like
no deals existed, no visible error. Fixed with the same `_aware()`
normalization pattern already established in `dsr.py`. Commit `5057f7f`.

Also fixed while investigating the same report:
- **DSR reject not clearing the pending list.** `approve_dsr`'s reject
  branch set `approval_status` back to `"submitted"` — the exact status
  `team/pending` filters on — so a rejected DSR immediately reappeared in
  the same queue the manager just acted on. Reject now sets a distinct
  `"rejected"` status; `_edit_lock_state()` always leaves it unlocked (the
  rep must be able to fix it regardless of the 24h window), and any save
  resets it back to `"submitted"` (existing behavior), which is what puts
  it up for re-review. `GET /dsr/team/pending` gained a `status` query
  param (submitted/approved/rejected/all, default submitted — existing
  callers unaffected). `DSRHistory.tsx` adds Pending/Approved/Rejected
  tabs in Team Approval view. Commit `cb8d835`.
- **DOR/DMR approval — did not exist at all.** Confirmed `dor.py` had no
  `approval_status`, no approve/reject, no edit-lock — the model docstring
  literally said "no approval workflow, unlike DSR." Amit chose the
  lightest of three scoping options (full DSR-equivalent workflow /
  simple approve-reject / read-only-for-now): simple approve/reject, no
  edit-lock or window. Migration 0023 adds `approval_status`/
  `approved_by`/`approved_at`/`manager_comment` to `dor_daily` (same
  shape as DSR's, minus the lock fields). New `POST /dor/{id}/approve`.
  `submit_dor` resets `approval_status` to `"submitted"` on every save,
  same escape hatch as DSR. There was no frontend page listing individual
  DOR entries at all (Team.tsx's Operations tab only ever showed an
  aggregated monthly rollup) — added a "pending DORs awaiting review"
  card above that matrix, reusing the same `dor-team` query already
  fetched there, rather than building a whole new page. Commit pending.
- **Team meetings showing only 1 for a Business Head — investigated, not
  a bug.** `list_meetings`'s `scope=team` correctly uses
  `resolve_visible_user_ids` (same helper Pipeline/Opportunities use, and
  Opportunities was visibly returning the full 10-deal BU scope). Meeting
  Intelligence is a separate, manually-logged BANT record - `Meeting(` is
  only ever instantiated in `create_meeting`, nothing auto-populates it
  from DSR calls/visits. Most likely explanation: reps are filling DSR
  daily counters but not separately using "Log Meeting." Flagged as an
  adoption gap, not a defect - same class of finding as the DSR-edit
  investigation two sessions ago.

**Migrations added:** 0023 — additive (four nullable/defaulted columns on
`dor_daily`), no destructive changes.

### 2026-07-14, same day — HR role investigation + scheme winner validation
Amit reported HR's login was "of no use" and asked for an architect-level
review, given HR should be approving FGA and validating scheme winners.
Two distinct findings:

- **FGA Approval was a nav bug, not missing functionality.** The backend
  was already fully correct for HR — `resolve_visible_user_ids` explicitly
  grants HR org-wide visibility ("FGA audit only"), and `fga_approval.py`'s
  HR review step (`pending_hr` → approve/override/dispute → `pending_vp`)
  works exactly as designed. The bug: `Layout.tsx`'s Management section was
  gated on `(canSeeTeam || canSeeRevenue)`, and HR is in neither list —
  so the FGA Approval link (despite `canSeeFGA` already including HR) never
  rendered, and the whole Management section was invisible to HR. Fixed by
  adding `canSeeFGA` to that gate.
- **Scheme winner validation genuinely didn't exist.** `incentives.py`'s
  "achieved" was just a boolean computed on the fly in Gamification.tsx's
  progress view — nothing was ever persisted, and `PointsLedger` was never
  actually written to by anything despite the model existing since v3.
  Amit chose: HR sign-off gate before payout, cash-only (points/badges
  stay automatic). Built: new `scheme_winners` table (migration 0024) with
  a status machine (`pending_hr` → `approved`/`rejected`, plus a `paid`
  flag); `POST /incentives/schemes/{id}/detect-winners` scans everyone a
  scheme applies to and is now the first thing that actually credits
  `PointsLedger`/`UserBadge` (points/badge/recognition auto-approve
  immediately; cash stops at `pending_hr`); `GET /incentives/winners`,
  `POST /incentives/winners/{id}/review`, `POST /incentives/winners/{id}
  /mark-paid`. Frontend: "🔍 Detect Winners" button on manager scheme
  cards in Gamification.tsx, new `SchemeWinners.tsx` review page (Pending/
  Approved/Rejected tabs, same visual pattern as DSR/DOR approval), nav
  link gated on `canSeeFGA` (same audience as FGA Approval).
Verified locally (`py_compile` + `tsc --noEmit` both clean); not yet
deployed to EC2.

**Migrations added:** 0024 — additive (new `scheme_winners` table), no
destructive changes.

### 2026-07-14, same day — HR nav trim + read-only Activity Logs
After deploying the HR fixes above, Amit tested as an actual HR user
(Pankaj Sharma) and flagged two more things: Leads/Pipeline/Opportunities/
Analytics/My Schemes are sales-pipeline concepts HR has no use for, and HR
needs to see rigor scores + logs for DSR/DMR(pre-sales)/DOR — read-only,
no approve/reject.

- `Layout.tsx`: those five nav items were already tagged `salesOnly` and
  excluded for `isSDM`, but not for HR — extended the same filter to HR.
  Meetings deliberately stays (not tagged `salesOnly`, shared across Sales
  and Delivery already).
- New `ActivityLogs.tsx`: read-only page, three tabs (Sales DSR / Pre-Sales
  DMR / Service Delivery DOR — "DMR" is Amit's term for what the backend
  just calls `dsr_type='presales'` on the same `dsr_daily` table; flagging
  this mapping in case it's wrong), month picker, no action buttons at
  all. Deliberately built as a NEW page rather than reusing DSRHistory.tsx/
  Team.tsx (which have approve/reject/manage-team actions baked in) — this
  keeps the "read-only for HR" guarantee structural rather than relying on
  remembering to hide buttons correctly on a shared page. No backend
  changes needed: both `GET /dsr/team/pending?status=all` and
  `GET /dor/team` already work for HR today (`require_level(20)`, HR is
  level 25) — this page just renders them without the action affordances.
  Nav link gated to `hr`/`finance` only (managers already have full
  read+action access via the existing pages).
Verified locally (`tsc --noEmit` clean); no migration, pure frontend +
existing-endpoint reuse; not yet deployed to EC2.

## 2026-07-14 — HR governance dashboard, SDM FGA inclusion, FGA-exempt flag (commit `df0041f`)

Follow-up to HR's trimmed nav: Amit flagged (a) HR could still reach the
DSR submit form via the Dashboard's leftover "Submit Today's DSR" widget,
(b) Service Delivery Manager's FGA scores never actually reached HR, (c)
the sidebar org label lied about HR/Finance/COO's actual (org-wide) scope,
(d) onboarding a company-wide role still forced a meaningless single
Business/Region pick, and (e) there was no way to mark someone FGA-exempt
or to give HR a real dashboard instead of the generic sales one.

- **Root cause of (b)**: `fga_approval.py`'s `freeze_period()` role filter
  was `["rep","inside_sales","pre_sales","manager"]` — `service_delivery_manager`
  was never in it, so no `ScoringResult` row was ever created for an SDM,
  at any point. Fixed by adding it to the same freeze/approval pipeline.
- **Root cause of (a)**: `Dashboard.tsx`'s "Today's DSR" card was gated
  `!isBU && !isSDM` — HR is neither, so it rendered by accident. Also the
  `/dsr` route in `main.tsx` had **no role guard at all** (any logged-in
  user could open the form directly; only the backend POST was blocked).
  Fixed both; HR now gets a dedicated `HRDashboard` component instead of
  the generic layout.
- **New `GET /fga-approval/bu-overview`** (HR/Finance/COO/CEO/super_admin
  only): headcount, FGA submission coverage %, avg score — grouped by
  business, across ALL businesses. Deliberately bypasses
  `resolve_visible_user_ids`' business-equality branches (which scope
  business_head/regional_manager to their own business) since a
  company-level role needs every business side by side.
- **New `fga_exempt` boolean on `User`** (migration `0025`): freeze skips
  exempt users; HR's overview excludes them from the coverage denominator
  and reports them separately rather than as a missing submission. Toggle
  lives in Team.tsx's edit panel, surfaced as a "🚫 FGA N/A" badge.
- **orgLabel fix**: `hr`/`finance`/`coo` now show "All Regions · All
  Businesses" (previously fell through to a region/business string that
  didn't reflect their actual org-wide scope — only `ceo`/`super_admin`
  got this before).
- **Company-wide role onboarding**: Team.tsx's create/edit forms now hide
  the Business/Region pickers for `hr`/`finance`/`coo`/`ceo`/`super_admin`
  and show an explanatory note instead, since those fields never affected
  what the role actually sees (`resolve_visible_user_ids` already ignored
  them for these scopes — this was a UX-only gap, not a permissions bug).

Scope note: "Service operations" in Amit's request is treated as the same
role as "Service Delivery" (`service_delivery_manager`) — the only such
role that exists in the system today. If a genuinely separate ops role is
needed later, it isn't built yet. COO/CEO were not given the same literal
`HRDashboard` UI in this pass (only the backend `bu-overview` endpoint,
which they're already allowlisted for) — flagged as a reasonable next
step, not done.

Verified: `python -m py_compile` clean on all backend changes, `tsc
--noEmit` clean on all frontend changes. Migration `0025` not yet applied
to EC2 — needs `alembic upgrade head` on next deploy.

## 2026-07-15 — Ishaant/Modassir dashboard zeros investigation + soft-delete/archive (migration `0026`)

Ishaant and Modassir (both `rep`) reported their own Dashboard KPI totals
showing 0 despite having submitted real DSR data, and a resubmit attempt
that appeared to fail. Investigated live via DB queries run through
`docker compose exec backend python3 <<'EOF' ... EOF` heredocs (no direct
DB/SSH access from this side — Amit ran them):

- Confirmed via direct query: both users have a single account each (no
  duplicate/orphaned user_id), and their DSR rows for July 2026 are fully
  intact and tied to the correct current user_id — Ishaant 32 calls/4
  visits/12 follow-ups/3 leads, Modassir 66 calls/0 visits/28 follow-ups/8
  leads. `bu_dashboard`'s own-scope query (`analytics.py`) matches this
  exactly when run directly against the DB — so the query logic itself,
  as it exists in this repo, is correct.
- Found along the way: Ishaant has `manager_id=None` — no manager
  assigned at all. Not the cause of this bug, but a separate gap worth
  fixing (nobody to route his DSR approvals to going forward).
- **Root cause, most likely**: `git log -1` on EC2 showed the repo pulled
  up to `df0041f` (this session's latest push), but `docker compose
  images backend` showed the running image was built **13 hours
  earlier** — i.e. `git pull` had happened but `docker compose build`
  had not, so the live site was serving stale code the whole time,
  unrelated to anything actually wrong in the current repo. Instructed
  Amit to do a full rebuild (`docker compose build backend frontend` +
  `up -d` + `alembic upgrade head` to `0026`) and have Ishaant/Modassir
  hard-refresh to confirm. **Not yet confirmed fixed as of this entry** —
  if it recurs after a genuine rebuild, the Network-tab response body of
  `GET /analytics/dashboard?month=2026-07` is the next thing to check
  (would distinguish a real backend bug from a frontend rendering bug).

Separately, Amit flagged that Pipeline/Opportunities show dummy data left
behind by deactivated/test accounts when logged in as super_admin, with
no way to delete it. Root-caused: `resolve_visible_user_ids` returns
`None` for `scope="all"` (ceo/coo/super_admin) meaning **no owner filter
at all** gets applied in `pipeline.py`'s `list_deals` or
`opportunity_repo.list_opportunities` — every deal in the table shows up
for those roles regardless of the owner's `is_active` status. There was
also no DELETE endpoint anywhere in the backend for either entity. Asked
Amit to choose the remedy (soft-delete/archive vs hard delete vs
hide-only) — chose soft-delete/archive.

- migration `0026`: `archived` (bool, default false) / `archived_at` /
  `archived_by` added to `pipeline`. Deals never hard-delete — they feed
  revenue/win-loss/FGA history — archiving just excludes them from every
  list view by default.
- `pipeline.py`: `POST /{deal_id}/archive` and `/unarchive`, gated to
  manager level (20) and above and scoped through
  `resolve_visible_user_ids` like every other deal action (so a
  business_head can clean up their own business without needing
  super_admin). `list_deals` now excludes `archived=True` by default for
  **every** scope, not just "all" — `include_archived=true` opts back in.
- `opportunity_repo.list_opportunities` / `opportunities.py`: identical
  `include_archived` param and default-exclude, since Opportunities reads
  the same underlying `pipeline` table via `opportunity_repo`.
- `Pipeline.tsx` / `Opportunities.tsx`: Archive/Unarchive button
  (manager+ only, with a confirm dialog explaining it's reversible), an
  "🗄️ Archived" badge on archived cards, and a "Show archived" checkbox
  for admins.

Verified: `python -m py_compile` and `tsc --noEmit` both clean. Not yet
deployed — bundled into the same rebuild as the stale-deploy fix above.

---

*This file supersedes README.md's "Recent Progress" and "Known Issues"
sections going forward — check here first. README.md stays the quick-start
reference; this file is the detailed, chronological record.*

## 2026-07-16 — End-to-end review (Claude/Rambo Commander session)

Requested: confirm current `main` works end-to-end before splitting
patch-only (`main`) vs. new-feature (`develop`, ships as `v1.1.0`) work,
per the policy already stated in `CHANGELOG.md`'s `v1.0.5` entry.

**Git/branch state:** `main` and `develop` point at the identical commit
(`725534b`, 2 commits past tag `v1.0.5`) — perfectly in sync, nothing to
reconcile. No `v1.1.0` tag exists yet, correctly, since no feature commits
exist on `develop` yet. Next feature work should branch from/land on
`develop`; tag `v1.1.0` once that's ready to ship.

**Smoke suite was reporting 53% (16/30) — root-caused, not a real app
regression, in two parts:**

1. `backend/smoke_test.py` predates the `v1.0.5` mandatory
   change-password gate. Every seeded account has `must_change_password
   = true` (confirmed: all 30 users in the local DB), so literally every
   endpoint except `/auth/login` and `/auth/change-password` 403'd for
   every role — DSR submit, Meetings, Leads, Pipeline, Opportunities, FGA
   queues, incentives, manager team views, all of it. The feature itself
   (backend gate + `ChangePassword.tsx` frontend) is correctly built end
   to end; the smoke test just never exercised it. Patched
   `smoke_test.py` to clear the gate via the real change-password flow on
   login and restore the original password immediately after, so re-runs
   don't rotate real credentials.
   - While fixing this, found 2 of the 6 seeded smoke credentials
     predate the current password policy and could never pass
     `validate_password_policy()` to be restored: `manager@fluidpro.in`
     (9 chars, policy min is 10) and `inside@fluidpro.in` (contains its
     own email local-part). Rotated both in the live DB and in
     `smoke_test.py`'s `CREDS` to `TeamLead@2026!` / `SalesOps@2026!`.
2. Local docker-compose DB was on alembic `0025`; code expects `0026`
   (the `pipeline.archived`/`archived_at`/`archived_by` columns from the
   soft-delete work in the 2026-07-15 session above) — every Pipeline/
   Opportunities read threw `UndefinedColumnError`, surfacing as
   401/403 to the client. Ran `alembic upgrade head` locally to fix. **This
   is the same gap the 2026-07-15 entry above flagged as "not yet
   confirmed fixed" on EC2** — worth explicitly re-checking `alembic
   current` on EC2 before the 1 August production promotion, not just
   assuming the rebuild picked it up.

After both fixes: **42/42 (100%)** smoke checks pass.

**Real bug found and patched (security):** `fga_approval.py`'s
`manager-review` endpoint (`POST /{result_id}/manager-review`) gated only
on `require_level(20)` — the caller's own tier — never checked that the
target result's rep was actually in the caller's scope, unlike
`list_pending()` in the same file which already does this via
`resolve_visible_user_ids()`. Any manager-level+ user could approve or
dispute any other manager's team member's FGA score by `result_id`. Fixed
with the same scope check. This was already flagged from a prior session
(see repo history) — now actually closed.

**Still open, unconfirmed (carried over, no action taken):**
- Team page crash on "Add Member" with a new role (§6) — still needs the
  actual browser console error text next repro.
- Service Delivery FGA approval workflow — decision still pending.
- Reports section (CSV/PDF export) — not started.

**Committed locally, not pushed** (`b22eb3f`, on `main`) — held for Amit's
review before it goes anywhere near the CI/CD release pipeline given the
1 August promotion date. Diff: `backend/app/routers/fga_approval.py` (+10)
and `backend/smoke_test.py` (+34/-2).

Also deleted a stray empty untracked file (`ssh_test_out.txt`, 0 bytes,
not gitignored) from the working tree — no commit needed, it was never
tracked.
## 2026-08-04 — R0 kickoff: consolidate 4 undeployed branches (Claude/Rambo Commander session, local dev on blr-dsk-amits)

Context: a separate strategic exercise (Rambo Commander, full Team RAMBO
Constitution review) validated evolving fluidGo from a CRM/sales tool into
an "AI-Native Services Intelligence Platform" — Sales → Pre-sales →
Delivery → Governance → Customer Success → Renewals → Executive
Intelligence. Verdict: achievable without a rebuild, via two new
architectural primitives (a polymorphic `interactions` ledger + a
generalized config-driven `health_engine`) rather than 12 separate new
modules. Full assessment lives in the fluidGo Claude Project
(`fluidgo-services-intelligence-platform-assessment.md`) and a roadmap
summary in this repo's own `README.md` going forward. Roadmap: **R0
(stabilize) → R1 (primitives + DSR↔Meeting link) → R2 (Customer Voice +
Executive digest) → R3 (Governance/Escalation consolidation) → R4
(Delivery Intelligence, build-vs-buy decision required) → R5 (Practice
Mgmt + Knowledge Intelligence) → R6 (Farming Intelligence + single AI
Copilot)**. Amit's direction: work locally branch-by-branch with proper
git tags, target a **new UAT instance** (to be provisioned separately)
rather than continuing to push directly to the existing EC2 production
box.

**This session = R0, step 1: ship what's already built.** Three feature
branches had been sitting on GitHub since 2026-07-26, verified but never
deployed. Confirmed via `git merge-base --is-ancestor` that all four
relevant branches form one clean linear stack off `main`:

```
main (725534b)
 └─ feature/dsr-backfill-and-seed-cleanup   (migration 0027)
     └─ feature/feedback-and-help-guide      (migration 0028)
         └─ feature/seed-data-pipeline-fix    (migration 0029)
             └─ feature/compliance-export-governance (migration 0030)
```

`develop` was still sitting at `725534b` (unchanged since the 2026-07-16
end-to-end review). Fast-forwarded it straight to
`origin/feature/compliance-export-governance` (`b8180b2`) — a true
fast-forward, zero conflicts, since the stack is strictly linear.

**Local dev environment:** this repo already had a working Docker Compose
stack on this machine (`blr-dsk-amits`, Windows, Docker Desktop) running
continuously for 6 days prior to this session — nginx:80, frontend:3002,
backend:8000, db:5433, ollama:11434. Restarted `backend` to pick up the
fast-forwarded code; its entrypoint auto-ran `alembic upgrade head`,
applying `0027 → 0030` cleanly.

**Verification results:**
- `pytest tests/`: 24 passed, 7 failed — the 7 are the pre-existing
  `test_permission_service.py` failures already confirmed unrelated to
  this work in an earlier session (`git stash` reproduces them on an
  unmodified checkout). No new failures.
- `vertical_slice_test.py`: still broken as previously documented — stale
  against current schema/RBAC (crashes on `bu_head`/`inside_sales`/
  `manager` logins failing against this local DB's credentials). Not
  fixed in this pass; flagged as a concrete R0 follow-up.
- `smoke_test.py --base http://nginx` (had to override the default
  `http://localhost`, which resolves to the container's own loopback
  when run via `docker compose exec backend`, not the nginx-fronted
  stack): **32/37 (86%)**. All 5 failures are local-environment
  artifacts, not code regressions:
  - `manager@fluidpro.in` / `inside@fluidpro.in` logins → 401. Root
    cause: a password rotation for these two test accounts (from the
    2026-07-16 session, commit `b22eb3f`) only ever landed in the *live*
    EC2 DB and in an **unpushed local commit on `main`** — it never made
    it into this branch's `smoke_test.py` or into this local Docker DB's
    seed. Not a defect in the merged code.
  - Cascading "4/6 tokens obtained" from the above.
  - `Dashboard: calls > 0` / `avg_rigor > 0` for `danish@fluidpro.in` →
    0. Root cause, confirmed via direct query: 58 of his 62 real DSR rows
    (loaded from the actual May-2026 Excel export via `backend/seed.py`)
    predate migration 0027's 2026-07-04 seed-cutoff and got flagged
    `is_seed=true` — **this is the exact tradeoff migration 0027's own
    docstring already calls out** ("a genuine pre-07-04 real entry would
    also get flagged; recoverable via `include_seed=true` + manual unset
    if any are found"). Local-DB-only; not touched in this pass since
    it's cosmetic to this dev environment, not a code bug.
- Frontend `tsc --noEmit`: clean. `npm run build`: clean (PWA bundle
  generated, main chunk ~294 KB gzipped — the existing >500KB chunk-size
  warning is pre-existing, not introduced here).

**Pushed:** `develop` → `origin/develop` (`725534b..b8180b2`, fast-forward).
**Opened:** [PR #1](https://github.com/amitipst/fluidgo/pull/1),
`develop` → `main`, with the verification results above in the PR body.
**Deliberately not merged** — the existing auto-deploy-to-EC2 pipeline on
`main` merges is exactly the pipeline this session is trying to route
around now that the plan is a fresh UAT instance; merge timing is Amit's
call, not automated in this pass.

**Still open (R0, next steps):**
1. GitHub Actions billing lock — unresolved status not re-checked this
   session; still assumed blocking until Amit confirms otherwise.
2. Branch protection / required-status-checks on `main` — not yet applied,
   recommended before PR #1 or anything after it merges.
3. `vertical_slice_test.py` repair — still stale, still open.
4. The 2 unpushed commits on local `main` (`b22eb3f` scope-leak fix,
   `12582bc` docs) from the 2026-07-16 session — never reconciled with
   `develop`/`origin`; worth deciding whether to cherry-pick the
   scope-leak fix forward.
5. New UAT instance provisioning — Amit-owned, not started this session.
6. Version tag: `v1.1.0` already exists at the older `725534b` commit
   (tagged prematurely per the 2026-07-21 finding, predates all 4
   branches above) — recommend tagging the consolidated state `v1.2.0`
   once PR #1 merges, rather than moving/re-tagging `v1.1.0`.

Once R0 is actually closed out, next work starts R1: the `interactions`
ledger + generalized `health_engine` primitives, proven first against the
DSR↔Meeting structural-link gap (finding #3, open since 2026-07-21).

## 2026-08-04 (same day, continued) — Branch protection enabled on `main` and `develop`

Per Amit's explicit direction ("branch protection is needed as per best
practice and right time, we will be using free version only"). Confirmed
first that plan tier is not actually a constraint here: the repo
(`amitipst/fluidgo`) is **public**, and GitHub's free plan has always
included full branch protection rules on public repositories — no
Team/Enterprise upgrade needed. (The free-tier limitation people usually
mean only affects *private* repos under an organization account, which
doesn't apply here — this is a public repo under a personal account.)

Applied identically to both `main` and `develop` via `gh api PUT
.../branches/{branch}/protection`:
- Pull request required before merging — **no direct pushes, including
  for repo admins** (`enforce_admins: true`). This directly closes the
  gap flagged repeatedly in this tracker and the fluidGo Claude Project
  assessment: most work had been landing straight on `main` with no
  PR/review step, `develop` included, despite `develop`'s own documented
  policy (CHANGELOG.md "Release Process") already saying feature
  branches should PR into `develop`.
- `required_approving_review_count: 0` — deliberate: a PR object is
  still mandatory, but no second reviewer is required. GitHub does not
  allow a PR author to approve their own PR, so requiring ≥1 approval
  would make solo merging impossible without a second GitHub identity.
  This keeps the workflow solo-friendly while still forcing every change
  through a reviewable, diffable PR instead of a silent direct push.
- Force-pushes and branch deletion blocked on both branches.
- `required_conversation_resolution: true`.
- **No required status checks yet, on either branch** — deliberate, not
  an oversight: `vertical_slice_test.py` is still broken/stale and
  GitHub Actions' billing-lock status hasn't been re-confirmed this
  session. Wiring in required checks now would just block every future
  PR on a suite that's already known-broken. Revisit once (a) Actions is
  confirmed unblocked and (b) the test suite is genuinely green or the
  known-bad tests are explicitly quarantined.

This PR (`chore/branch-protection-r0` → `develop`) is itself the first
PR merged under the new rule — recording the policy change through the
same mechanism it introduces, rather than pushing it directly.

**R0 still open after this:** GitHub Actions billing-lock status,
`vertical_slice_test.py` repair, the 2 old unpushed commits on local
`main`, new UAT instance provisioning, and merging/tagging PR #1
(`develop`→`main`, the 4-branch consolidation) — all unchanged from the
entry immediately above this one.

## 2026-08-04 (same day, continued 2) — PR #1 merged, reconciliation fix, encoding repair, v1.2.0 tagged

Amit approved merging PR #1 ("go ahead for pr1 as per recommendation").
Sequence, in order:

1. **PR #1 merged** (`develop` → `main`, `d99b40e`) — the 4-branch R0
   consolidation described in the entries above.
2. **Caught before it caused real damage:** attempting to reconcile the 2
   old commits sitting unpushed on local `main` since 2026-07-16
   (`b22eb3f`, `12582bc`) via a plain `git pull` on `main` hit a merge
   conflict — and a chained shell command kept executing after the
   conflict, so `git tag v1.2.0` ran against the wrong, still-conflicted
   local `main` tip. **Caught immediately** (checked `git rev-parse
   v1.2.0` against the intended commit before telling Amit it was done),
   deleted the bad tag locally and on origin, aborted the merge, and
   redid the reconciliation properly: pushed the 2 old commits to their
   own branch (`reconcile/2026-07-16-fixes`) off a clean `main`, resolved
   the one real conflict (`MASTER_TRACKER.md`, both sides had appended a
   new dated entry — kept both, chronological order) on that branch, and
   merged via **PR #3**. This surfaced a real, previously-unmerged
   security fix (`fga_approval.py` manager-review scope-leak, see the
   2026-07-16 entry above) and the `smoke_test.py` password-rotation/
   change-password-gate handling — both now on `main`.
3. **Caught a second issue from my own tooling, same session:** the
   PowerShell one-liner used to strip conflict markers from
   `MASTER_TRACKER.md` during step 2 (`Get-Content | Where-Object |
   Set-Content -Encoding UTF8`, no `-Encoding` on the *read* side) misread
   the file's UTF-8 BOM content through the console's default codepage,
   then wrote it back out re-encoded — corrupting every em-dash/middle-dot
   in the **entire file** (260 occurrences, from line 1 onward) into
   garbled 2-3-character sequences. Found by spot-checking the merged
   file's headers before moving on, confirmed the scope with a byte-level
   scan, fixed via `ftfy.fix_text()` on its own branch, verified
   zero corrupted sequences remain — **PR #4**.
4. **Synced `develop`** back up to `main` (`main` had gained PR #3 and #4
   as direct patches, which never passed through `develop`) via **PR #5**
   (`main` → `develop`, fast-forward content, no new diffs).
5. **Tagged `v1.2.0`** at the verified-correct `main` HEAD (`07e66af`) —
   consolidates PR #1, #3, #4, #5. Supersedes the `v1.1.0` tag, which was
   applied prematurely at an earlier commit (`725534b`) and predates all
   of the DSR backfill / compliance / Governance / Feedback work.

**Deploy status — deliberately not touched:** the `main`-push deploy job
is gated behind a manual "production" GitHub Environment approval (per
`release.yml`). Each of today's 3 merges to `main` (PR #1, #3, #4) queued
its own deploy run, all currently sitting in `waiting` state — **none
approved, none deployed**, on purpose, since the target for the next real
promotion is the new UAT instance Amit is provisioning separately, not
this existing EC2 box. **Also found while checking this:** 2 *unrelated*,
much older deploy approvals (`ci: rewrite release pipeline for v1.0.5...`
and `ci: grant contents:write...`, both from 2026-07-15) have been sitting
in `waiting` for ~20 days, untouched — flagging for Amit to decide whether
to reject/clear those (deploying a 3-week-stale commit at this point
would almost certainly be wrong) rather than leaving them queued
indefinitely.

**GitHub Actions billing lock: confirmed resolved.** Every workflow run
today completed normally (`test` job green, no billing-lock error) — this
was the #1 blocker flagged repeatedly in earlier entries; it's clear now,
though nobody explicitly confirmed *when* it cleared.

**R0 status after this entry:**
- ✅ 4 undeployed branches consolidated onto `main`+`develop`, tagged `v1.2.0`
- ✅ Branch protection on `main`+`develop`
- ✅ GitHub Actions billing lock (confirmed clear)
- ✅ The 2 old unpushed local-`main` commits reconciled
- ⛔ Still open: `vertical_slice_test.py` repair; required status checks
  (deliberately not wired up until the test suite above is fixed);
  new UAT instance provisioning; the 5 stacked/stale deploy approvals
  above (Amit's call); actually deploying anything from `v1.2.0` anywhere
  (still nowhere — by design, until the UAT instance exists)

Once Amit clears the stale deploy-approval queue (or decides to leave it),
R0 is functionally done. Next: R1 — the `interactions` ledger +
`health_engine` primitives, proven first against the DSR↔Meeting link.

## 2026-08-04 (same day, continued 3) — R0 closed: stale deploy-approval queue rejected

Amit confirmed: real deploys to the EC2 box have always been done
manually (VS Code Remote-SSH), never through this pipeline's automated
"production" Environment approval gate — matching what section 0.5 of
the earlier fluidGo Claude Project doc already documented. That means
every `waiting` deploy job on this pipeline is inherently dead on
arrival: nobody was ever going to click "approve" on it.

Confirmed the actual count first (an earlier `--json` filtered query gave
an inconsistent/misleading count due to what looks like a pagination
quirk — cross-checked against the plain-text `gh run list`, which is
authoritative): exactly **5** runs in `waiting` state, not the dozens the
raw history might suggest — everything else from 2026-07-13/14 that looks
similar is already `completed failure` (the deploy job failed outright on
those, rather than sitting in the approval queue — different failure
mode, already resolved one way or another).

Rejected all 5 via `gh api POST .../pending_deployments` with
`state: rejected` and an explanatory comment (manual-SSH is the real
deploy path; next real promotion target is the still-unprovisioned new
UAT instance):
- 3 from today: PR #1, #3, #4 merges to `main`
- 2 stale, from 2026-07-15: `ci: rewrite release pipeline for v1.0.5...`
  and `ci: grant contents:write...`

All 5 now show `completed failure` (rejected, not actually failed) —
Actions dashboard is clean, no dangling approvals.

**R0 is now fully closed.** Everything from the original punch list is
either done or explicitly deferred with a reason:
- ✅ 4 undeployed branches consolidated, `v1.2.0` tagged
- ✅ Branch protection on `main` + `develop`
- ✅ GitHub Actions billing lock (confirmed resolved)
- ✅ 2 old unpushed local-`main` commits reconciled (including a real
  security fix)
- ✅ Stale/dead deploy-approval queue cleared
- ⛔ Deferred, with reason: `vertical_slice_test.py` repair (tracked, not
  blocking — required status checks intentionally not wired up until
  it's fixed); new UAT instance provisioning (Amit-owned, separate
  infra task, not a code change)

**Next: R1** — the `interactions` ledger + `health_engine` primitives
(see the fluidGo Claude Project's
`fluidgo-services-intelligence-platform-assessment.md`), proven first
against the DSR↔Meeting structural link (finding #3, open since
2026-07-21).
