import { useAuthStore } from '@/store/authStore'
import { APP_VERSION, APP_BUILD_DATE } from '@/version'

// Role tiers — mirrors the exact gating logic in Layout.tsx so this guide
// only ever shows a role the features they can actually see. Keep these in
// sync with Layout.tsx if the nav gating changes.
const FIELD_ROLES = ['rep', 'inside_sales', 'pre_sales', 'manager']
const DSR_MANAGER_ROLES = ['manager', 'regional_manager', 'bu_head', 'business_head', 'ceo', 'super_admin']
const TEAM_ROLES = ['manager', 'regional_manager', 'bu_head', 'inside_sales', 'business_head', 'ceo', 'super_admin']
const REVENUE_ROLES = ['manager', 'regional_manager', 'bu_head', 'business_head', 'ceo', 'super_admin']
const FGA_ROLES = ['manager', 'regional_manager', 'bu_head', 'business_head', 'ceo', 'super_admin', 'hr', 'finance']
const SCORING_ROLES = ['regional_manager', 'bu_head', 'business_head', 'practice_head', 'ceo', 'super_admin']
const FEEDBACK_ADMIN_ROLES = ['business_head', 'practice_head', 'coo', 'ceo', 'super_admin']
const REGIONAL_ROLES = ['business_head', 'ceo', 'super_admin']

const ROLE_LABELS: Record<string, string> = {
  rep: 'Sales Rep', inside_sales: 'Inside Sales', pre_sales: 'Pre-Sales',
  manager: 'Manager', service_delivery_manager: 'Service Delivery Manager',
  regional_manager: 'Regional Manager', bu_head: 'Regional Manager', business_head: 'Business Head',
  practice_head: 'Practice Head', hr: 'HR', finance: 'Finance', coo: 'COO', ceo: 'CEO',
  super_admin: 'Super Admin',
}

function Section({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) {
  return (
    <div className="card mb-4">
      <h2 className="font-display font-bold text-base text-wep-navy mb-3 flex items-center gap-2">
        <span>{icon}</span> {title}
      </h2>
      <div className="text-sm text-wep-text leading-relaxed space-y-2">{children}</div>
    </div>
  )
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white"
        style={{ background: 'linear-gradient(135deg,#F0115E,#92278E)' }}>{n}</span>
      <span className="flex-1">{children}</span>
    </div>
  )
}

// One row in a "Feature" reference list — icon, name, one-line explanation
// of what it's for and where to find it.
function Feature({ icon, name, children }: { icon: string; name: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 py-1.5">
      <span className="shrink-0 text-base w-6 text-center">{icon}</span>
      <div className="flex-1">
        <span className="font-semibold text-wep-navy">{name}</span>
        <span className="text-wep-text"> — {children}</span>
      </div>
    </div>
  )
}

export default function Help() {
  const { user } = useAuthStore()
  const role = user?.role ?? ''

  const isField     = FIELD_ROLES.includes(role)
  const isDsrManager= DSR_MANAGER_ROLES.includes(role)
  const canSeeTeam  = TEAM_ROLES.includes(role)
  const canSeeRevenue = REVENUE_ROLES.includes(role)
  const canSeeFGA   = FGA_ROLES.includes(role)
  const canSeeScoring = SCORING_ROLES.includes(role)
  const canSeeFeedbackInbox = FEEDBACK_ADMIN_ROLES.includes(role)
  const canSeeRegional = REGIONAL_ROLES.includes(role)
  const isSuperAdmin = role === 'super_admin'
  const isSDM = role === 'service_delivery_manager'
  const isHR = role === 'hr'
  const isFinance = role === 'finance'
  // Sales funnel concepts (Leads/Pipeline/Opportunities/Analytics/Schemes)
  // don't apply to Service Delivery or HR — matches Layout.tsx's salesOnly filter.
  const seesSalesFunnel = !isSDM && !isHR

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">❔ Help &amp; Guide</h1>
        <p className="text-wep-muted text-sm">
          Everything fluidGo does for your role — {ROLE_LABELS[role] ?? role} · v{APP_VERSION} ({APP_BUILD_DATE})
        </p>
      </div>

      <Section icon="🎯" title="What is fluidGo?">
        <p>
          fluidGo is your daily sales operating system. It captures what your team does each day,
          turns activity into a tracked pipeline, and uses AI to score deal health, coach reps, and
          surface what's really driving (or blocking) revenue — with a transparent, single picture
          everyone works from.
        </p>
        <p className="text-wep-muted">
          The core idea is a <strong>funnel</strong>: a meeting that shows buying signals becomes a
          <strong> lead</strong>, a qualified lead becomes a <strong>pipeline deal</strong>, and a
          won deal becomes <strong>revenue</strong>. Everything else in the app — analytics, scoring,
          incentives — is built on top of that one chain.
        </p>
        <p className="text-wep-muted">
          This page only shows you the features your role actually has access to, so treat it as
          your own quick reference — not a manual for the whole app.
        </p>
      </Section>

      {isField && (
        <Section icon="✏️" title="Submit DSR — your daily routine (2 minutes)">
          <Step n={1}>Open <strong>Submit DSR</strong> each working day. Set your day status
            (Working / Leave / Holiday / WFH), then enter your activity counts — visits, calls,
            follow-ups, new leads, proposals.</Step>
          <Step n={2}>Give yourself an honest <strong>self-score (0–5)</strong> across the five
            discipline areas. This feeds your Rigor Score.</Step>
          <Step n={3}>Submit. The AI generates a short performance insight in the background
            (about 2–3 minutes — you don't need to wait on the screen).</Step>
          <p className="text-wep-muted mt-1">
            <strong>Missed a day?</strong> You can backfill a DSR for up to <strong>7 days back</strong> —
            the date picker on Submit DSR only allows dates inside that window, and a
            backdated entry is clearly marked "⏳ Backfill DSR" so nothing is silently
            back-dated without a trail. Once submitted, you have the usual 24-hour edit
            window; after that, an edit needs your manager's approval via an edit request.
          </p>
          <p className="text-wep-muted">
            Your <strong>Rigor Score</strong> reflects the consistency and quality of your daily
            effort. Review past entries any time under <strong>My DSR Log</strong> — a backfilled
            entry shows a "🕒 Backfilled (Nd late)" badge there so you and your manager can both
            see it was filed late.
          </p>
        </Section>
      )}

      {seesSalesFunnel && (
        <Section icon="🔄" title="The Meeting → Lead → Opportunity funnel">
          <p>This is the heart of fluidGo. Follow it in order:</p>
          <Step n={1}><strong>Log a meeting</strong> under <strong>Meetings</strong>. Fill in the
            BANT signals (Budget, Authority, Need, Timeline) — the AI uses these to score buying
            intent.</Step>
          <Step n={2}>If the meeting shows real interest, click <strong>→ Convert to Lead</strong>
            under <strong>Leads</strong>. Company, contact, and discussion carry forward
            automatically — no re-typing.</Step>
          <Step n={3}>When a lead is qualified, click <strong>→ Convert to Deal</strong>. It becomes
            a pipeline opportunity carrying all its context.</Step>
          <Step n={4}>Work the deal in <strong>Pipeline</strong>: update the stage
            (Cold → Warm → Hot), deal value, and next steps.</Step>
          <Step n={5}>When it resolves, click <strong>🏁 Close</strong> under
            <strong> Opportunities</strong> and record the outcome honestly (Won / Lost / On Hold /
            Dropped) with a reason.</Step>
          <p className="text-wep-muted mt-1">
            Each conversion is one-way and tracked, so nothing is double-counted and you can always
            trace a deal back to the meeting it started from.
          </p>
        </Section>
      )}

      {!seesSalesFunnel && (
        <Section icon="🤝" title="Meetings">
          <p>
            Log every client meeting under <strong>Meetings</strong> — company, contact, discussion,
            and how it went. This feeds the same activity record sales uses, so a delivery-side
            client touchpoint is visible and counted just as much as a sales one.
          </p>
        </Section>
      )}

      {seesSalesFunnel && (
        <Section icon="🧭" title="Opportunities &amp; deal health">
          <p>
            The <strong>Opportunities</strong> page shows all your open deals with a funnel progress
            bar, a portfolio summary (open pipeline value, weighted forecast, at-risk count), and an
            AI deal-health score out of 100.
          </p>
          <p>
            Click <strong>✨ AI Deal Health Coaching</strong> on any deal for a specific read on what's
            strong, what's at risk, and what to do next. (It runs on the local model, so give it a
            moment.)
          </p>
        </Section>
      )}

      {seesSalesFunnel && (
        <Section icon="📉" title="Win-loss &amp; win-back">
          <p>
            When you close a deal, the reason you pick feeds a <strong>Win-Loss Analysis</strong> that
            shows your win rate and the patterns behind losses — so the team learns what's really
            costing deals.
          </p>
          <p>
            If a deal was on a fixed-term contract (yours or a competitor's), fluidGo schedules a
            <strong> Win-Back Alert</strong> before it expires — turning a past loss into a future
            opportunity. Alerts appear on the Opportunities page when they're due.
          </p>
        </Section>
      )}

      {seesSalesFunnel && (
        <Section icon="📈" title="Analytics &amp; My Schemes">
          <Feature icon="📈" name="Analytics">
            your own conversion funnel (Meetings → Leads → Deals → Won) with stage-to-stage
            conversion rates, so you can see exactly where deals are slipping.
          </Feature>
          <Feature icon="🎮" name="My Schemes">
            active incentive schemes you're enrolled in, your live progress toward each target, and
            points/badges you've earned. All figures exclude any placeholder/demo data, so what you
            see is exactly what counts toward payout.
          </Feature>
        </Section>
      )}

      {isSDM && (
        <Section icon="🛠️" title="Service Delivery">
          <Feature icon="🛠️" name="Daily Ops Report (DOR)">
            your daily service-delivery operations log — the delivery-side equivalent of a sales DSR.
          </Feature>
          <Feature icon="📋" name="Monthly KPI Entry">
            enter monthly achievement figures for KPIs fluidGo can't compute automatically (e.g.
            ticket/collections numbers sourced from other systems) — these feed directly into your
            scorecard.
          </Feature>
        </Section>
      )}

      {canSeeTeam && (
        <Section icon="👥" title="Team">
          <p>
            See every team member's daily activity, Rigor Score, and DSR compliance at a glance.
            Use the <strong>Team</strong> toggle on Meetings and Opportunities to switch from your
            own records to your whole team's.
          </p>
        </Section>
      )}

      {isDsrManager && !isField && (
        <Section icon="📝" title="DSR Approvals">
          <p>
            When a rep needs to edit a DSR outside their 24-hour window, the request lands here
            (also reachable via <strong>DSR History → Team</strong>). Approve or decline with a
            reason — approving re-opens that one entry for editing.
          </p>
        </Section>
      )}

      {canSeeRevenue && (
        <Section icon="💰" title="Revenue">
          <p>
            Set Revenue and Order Booking targets per team member, and track achievement against
            them over time. The two target types are always kept separate, so a strong order book
            doesn't mask weak collections (or vice versa).
          </p>
        </Section>
      )}

      {canSeeRegional && (
        <Section icon="🗺️" title="Regions">
          <p>
            A roll-up view across every region within your business (or, for CEO/Super Admin, across
            every business) — for spotting which regions are pulling their weight and which need
            attention, without having to open each region's Team page individually.
          </p>
        </Section>
      )}

      {canSeeFGA && (
        <Section icon="🏆" title="FGA Approval &amp; Scheme Winners">
          <Feature icon="🏆" name="FGA Approval">
            the multi-step approval workflow for computed scorecards (FGA = the scoring framework
            behind incentive payouts) — review and approve/reject each person's score before it's
            finalised for the period.
          </Feature>
          <Feature icon="🎉" name="Scheme Winners">
            once a scheme period closes, the qualifying winners and their payouts are listed here
            for record-keeping and sign-off.
          </Feature>
        </Section>
      )}

      {(isHR || isFinance) && (
        <Section icon="🗂️" title="Activity Logs">
          <p>
            A read-only audit trail of rigor scores and DSR/meeting activity across the org —
            scoped for HR and Finance to review compliance and payout-relevant activity without
            needing the action/approval permissions that manager-tier roles have.
          </p>
        </Section>
      )}

      {canSeeScoring && (
        <Section icon="⚙️" title="Scoring (Admin)">
          <p>
            Configure the scorecard templates behind FGA scoring — the weighted parameters, their
            metric sources, and (for banded KPIs) the tier tables that convert an achievement % into
            a score. Changes here are what everyone's FGA Approval scorecards are computed from, so
            treat it as the source of truth for "how is performance measured."
          </p>
        </Section>
      )}

      {isSuperAdmin && (
        <Section icon="🩺" title="System Health">
          <p>
            A super-admin-only operational view: background job status, AI model connectivity, and
            other platform health signals — for diagnosing "something feels off" before it becomes a
            support ticket.
          </p>
        </Section>
      )}

      <Section icon="💬" title="Feedback — report an issue or share an idea">
        <p>
          The <strong>💬 button</strong> in the bottom-right corner of every screen is always there,
          for every role. Use it to flag a bug, suggest an idea, ask a question, or raise anything
          else — pick a category, describe it, and send. It automatically notes which screen you
          were on, so you don't have to explain that part.
        </p>
        <p className="text-wep-muted">
          Every submission is saved and immediately emails the fluidGo admin team, so nothing sits
          unseen. Where a tracking system (Jira) is connected, a matching issue is filed
          automatically too — but reporting always works and always reaches an admin, even without
          that connection.
        </p>
        {canSeeFeedbackInbox && (
          <p>
            As {ROLE_LABELS[role] ?? 'an admin'}, you also have the <strong>Feedback Inbox</strong>
            {' '}in the sidebar (badge shows the open count) — the single place to see every issue and
            idea raised across the team, filter by status, and mark items In Progress / Resolved /
            Won't Fix as you work through them.
          </p>
        )}
      </Section>

      <Section icon="🔐" title="Account &amp; access">
        <p>
          Forgot your password? On the login screen, click <strong>Forgot password?</strong>, enter
          your work email, and you'll get a secure reset link (valid for 30 minutes).
        </p>
        <p className="text-wep-muted">
          Your data is scoped to your role — reps see their own work, managers see their team, and
          everything stays on WEP's own servers.
        </p>
      </Section>

      <Section icon="🤖" title="About the AI">
        <p>
          fluidGo runs a local AI model (Ollama) on WEP's server — <strong>nothing leaves the
          building</strong>. Because it's on-premise hardware, AI insights take a couple of minutes
          to generate. They're created in the background and appear automatically when ready; you
          never have to wait on a loading screen.
        </p>
        <p className="text-wep-muted">
          Anything you see in Analytics or an AI insight reflects real, live activity only —
          placeholder/demo data used during setup is automatically excluded from what you're shown.
        </p>
      </Section>

      <Section icon="🆘" title="Need more help?">
        <p>
          The fastest way to reach us for anything platform-related — a bug, a question, or an idea
          — is the <strong>💬 feedback button</strong> described above; it's monitored and alerts an
          admin the moment you send it.
        </p>
        <p className="text-wep-muted">
          For account or login issues specifically, contact IT support at{' '}
          <strong>itsupport.blr@wepsol.com</strong>.
        </p>
      </Section>

      <p className="text-center text-xs text-wep-muted mt-6">
        fluidGo v{APP_VERSION} · WEP Solutions · Internal Platform
      </p>
    </div>
  )
}
