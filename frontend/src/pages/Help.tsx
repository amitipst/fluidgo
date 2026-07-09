import { useAuthStore } from '@/store/authStore'
import { APP_VERSION, APP_BUILD_DATE } from '@/version'

// Role tiers for showing/hiding sections
const FIELD_ROLES = ['rep', 'inside_sales', 'pre_sales', 'manager']
const MANAGER_ROLES = ['manager', 'bu_head', 'business_head', 'practice_head', 'coo', 'ceo', 'super_admin']

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

export default function Help() {
  const { user } = useAuthStore()
  const isField = FIELD_ROLES.includes(user?.role ?? '')
  const isManager = MANAGER_ROLES.includes(user?.role ?? '')

  return (
    <div className="p-4 md:p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="font-display font-bold text-xl text-wep-navy">❔ Help &amp; Guide</h1>
        <p className="text-wep-muted text-sm">
          Everything you need to use fluidGo · v{APP_VERSION} ({APP_BUILD_DATE})
        </p>
      </div>

      <Section icon="🎯" title="What is fluidGo?">
        <p>
          fluidGo is your daily sales companion. It captures what you do each day, turns your
          meetings into a tracked pipeline, and uses on-device AI to score deal health and
          coach you — all while keeping your data private on WEP's own servers.
        </p>
        <p className="text-wep-muted">
          The core idea is a <strong>funnel</strong>: a meeting that shows buying signals becomes a
          <strong> lead</strong>, a qualified lead becomes a <strong>pipeline deal</strong>, and a
          won deal becomes <strong>revenue</strong>.
        </p>
      </Section>

      {isField && (
        <Section icon="✏️" title="Your daily routine (2 minutes)">
          <Step n={1}>Open <strong>Submit DSR</strong> each working day. Set your day status
            (Working / Leave / Holiday / WFH), then enter your activity counts — visits, calls,
            follow-ups, new leads, proposals.</Step>
          <Step n={2}>Give yourself an honest <strong>self-score (0–5)</strong> across the five
            discipline areas. This feeds your Rigor Score.</Step>
          <Step n={3}>Submit. The AI generates a short performance insight in the background
            (about 2–3 minutes — you don't need to wait on the screen).</Step>
          <p className="text-wep-muted mt-1">
            Your <strong>Rigor Score</strong> reflects the consistency and quality of your daily
            effort. You can review past entries any time under <strong>My DSR Log</strong>.
          </p>
        </Section>
      )}

      <Section icon="🔄" title="The Meeting → Lead → Opportunity funnel">
        <p>This is the heart of fluidGo. Follow it in order:</p>
        <Step n={1}><strong>Log a meeting</strong> under <strong>Meetings</strong>. Fill in the
          BANT signals (Budget, Authority, Need, Timeline) — the AI uses these to score buying
          intent.</Step>
        <Step n={2}>If the meeting shows real interest, click <strong>→ Convert to Lead</strong>.
          Company, contact, and discussion carry forward automatically — no re-typing.</Step>
        <Step n={3}>When a lead is qualified, click <strong>→ Convert to Deal</strong>. It becomes
          a pipeline opportunity carrying all its context.</Step>
        <Step n={4}>Work the deal in <strong>Pipeline</strong>: update the stage
          (Cold → Warm → Hot), deal value, and next steps.</Step>
        <Step n={5}>When it resolves, click <strong>🏁 Close</strong> and record the outcome
          honestly (Won / Lost / On Hold / Dropped) with a reason.</Step>
        <p className="text-wep-muted mt-1">
          Each conversion is one-way and tracked, so nothing is double-counted and you can always
          trace a deal back to the meeting it started from.
        </p>
      </Section>

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

      {isManager && (
        <Section icon="📊" title="For managers">
          <p><strong>Analytics</strong> — your team's conversion funnel (Meetings → Leads → Deals →
            Won) with stage-to-stage conversion rates. This is where you spot where the funnel
            leaks.</p>
          <p><strong>Revenue</strong> — set Revenue and Order Booking targets per team member, and
            track achievement against them. The two target types are always kept separate.</p>
          <p><strong>Team</strong> — see each member's activity and rigor at a glance.</p>
          <p><strong>Meetings / Opportunities</strong> — use the <strong>Team</strong> toggle to
            switch from your own records to your whole team's.</p>
        </Section>
      )}

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
      </Section>

      <Section icon="💬" title="Need more help?">
        <p>
          Something not working, or a feature you'd like? Reach out to the fluidGo team or your
          manager. For account or login issues, contact IT support at{' '}
          <strong>itsupport.blr@wepsol.com</strong>.
        </p>
      </Section>

      <p className="text-center text-xs text-wep-muted mt-6">
        fluidGo v{APP_VERSION} · WEP Solutions · Internal Platform
      </p>
    </div>
  )
}
