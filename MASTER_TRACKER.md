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

---

*This file supersedes README.md's "Recent Progress" and "Known Issues"
sections going forward — check here first. README.md stays the quick-start
reference; this file is the detailed, chronological record.*
