import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

const NAV_CORE = [
  { to: '/',              icon: '⚡', label: 'Dashboard',    exact: true },
  { to: '/dsr',           icon: '✏️', label: 'Submit DSR'              },
  { to: '/dsr/history',   icon: '📋', label: 'My DSR Log'              },
  { to: '/meetings',      icon: '🤝', label: 'Meetings'                },
  { to: '/leads',         icon: '🎯', label: 'Leads'                   },
  { to: '/pipeline',      icon: '📊', label: 'Pipeline'                },
  { to: '/opportunities', icon: '🧭', label: 'Opportunities'           },
  { to: '/analytics',     icon: '📈', label: 'Analytics'              },
  { to: '/gamification',  icon: '🎮', label: 'My Schemes'             },
]
const NAV_MANAGER = [
  { to: '/team',     icon: '👥', label: 'Team'     },
  { to: '/revenue',  icon: '💰', label: 'Revenue'  },
  { to: '/regional', icon: '🗺️', label: 'Regions'  },   // business_head+ only
  { to: '/gamification', icon: '🎮', label: 'Schemes' },
]
const NAV_FGA     = { to: '/fga-approval',  icon: '🏆', label: 'FGA Approval' }
const NAV_SCORING = { to: '/scoring-admin', icon: '⚙️', label: 'Scoring'     }

// ── fluidGo compact logo for sidebar header ──────────────────────────────────
function SidebarLogo() {
  return (
    <div className="flex items-center gap-3">
      {/* Stripe icon — inline SVG */}
      <svg width="28" height="34" viewBox="0 0 52 64" fill="none"
        xmlns="http://www.w3.org/2000/svg" className="shrink-0">
        <rect x="0"  y="0"  width="52" height="11" rx="2.5" fill="#F0115E"/>
        <rect x="7"  y="16" width="45" height="11" rx="2.5" fill="#F0115E"/>
        <rect x="14" y="32" width="38" height="11" rx="2.5" fill="#F0115E"/>
        <rect x="21" y="48" width="31" height="10" rx="2.5" fill="#F0115E"/>
        <rect x="0"  y="16" width="5"  height="11" rx="2" fill="#808083" opacity="0.6"/>
        <rect x="0"  y="32" width="12" height="11" rx="2" fill="#808083" opacity="0.6"/>
        <rect x="0"  y="48" width="19" height="10" rx="2" fill="#808083" opacity="0.6"/>
      </svg>
      <div className="min-w-0">
        <div className="font-display font-extrabold text-white text-base leading-tight tracking-tight">
          fluidGo
        </div>
        <div className="text-[9px] tracking-[0.18em] uppercase font-medium mt-0.5"
          style={{ color: 'rgba(255,255,255,0.35)' }}>
          WEP Solutions
        </div>
      </div>
    </div>
  )
}

// ── Sidebar nav link ──────────────────────────────────────────────────────────
function SideLink({ to, icon, label, exact }: { to:string; icon:string; label:string; exact?:boolean }) {
  return (
    <NavLink to={to} end={exact}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-150
         ${isActive
           ? 'text-white font-semibold'
           : 'text-white/40 hover:text-white/80 hover:bg-white/5'}`
      }
      style={({ isActive }) => isActive
        ? { background: 'linear-gradient(135deg, rgba(240,17,94,0.85), rgba(194,0,90,0.85))',
            boxShadow: '0 2px 8px rgba(240,17,94,0.30)' }
        : {}
      }>
      <span className="text-base w-5 text-center shrink-0 leading-none">{icon}</span>
      <span className="truncate">{label}</span>
    </NavLink>
  )
}

// ── Section label ─────────────────────────────────────────────────────────────
function NavSection({ label }: { label: string }) {
  return (
    <div className="px-3 pt-4 pb-1">
      <span className="text-[9px] font-bold uppercase tracking-[0.15em]"
        style={{ color: 'rgba(255,255,255,0.22)' }}>
        {label}
      </span>
    </div>
  )
}

export default function Layout() {
  const { user, clearAuth } = useAuthStore()
  const navigate = useNavigate()

  const canSeeTeam    = ['manager','bu_head','inside_sales','business_head','ceo','super_admin'].includes(user?.role ?? '')
  const canSeeRevenue = ['manager','bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')
  const canSeeFGA     = ['manager','bu_head','business_head','ceo','super_admin','hr','finance'].includes(user?.role ?? '')
  const canSeeScoring = ['bu_head','business_head','ceo','super_admin'].includes(user?.role ?? '')
    || ['admin','super_admin','practice_head'].includes(user?.org_role_key ?? '')

  // Remove gamification from core if user is manager+ (they see it in Management section)
  const coreNav = canSeeTeam
    ? NAV_CORE.filter(n => n.to !== '/gamification')
    : NAV_CORE

  const initials = user?.name?.split(' ').map(n => n[0]).join('').slice(0,2).toUpperCase() ?? '?'

  const ROLE_LABELS: Record<string, string> = {
    rep: 'Sales Rep', inside_sales: 'Inside Sales', pre_sales: 'Pre-Sales',
    manager: 'Manager', bu_head: 'BU Head', business_head: 'Business Head',
    hr: 'HR', finance: 'Finance', ceo: 'CEO', super_admin: 'Super Admin',
  }

  // Org label — role-aware, region-aware, never hardcoded
  const orgLabel = (() => {
    const r = user?.role ?? ''
    if (r === 'ceo' || r === 'super_admin') return 'All Regions · All Businesses'
    if (r === 'business_head') return `${user?.business?.toUpperCase() ?? 'fluidPro'} · Global`
    const region = user?.region || user?.bu
    return region ? `${region} · ${user?.business ?? 'fluidPro'}` : 'fluidPro'
  })()

  return (
    <div className="flex flex-col h-screen md:flex-row">

      {/* ══════════════════════════════════════════════════════════════
          DESKTOP SIDEBAR — fluidPro deep purple brand
      ══════════════════════════════════════════════════════════════ */}
      <aside className="hidden md:flex flex-col w-60 shrink-0 select-none"
        style={{ background: 'linear-gradient(180deg, #1A0B2E 0%, #2D1452 100%)' }}>

        {/* Logo */}
        <div className="px-5 py-5 border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
          <SidebarLogo />
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-0.5">
          <NavSection label="My Work" />
          {coreNav.map(item => (
            <SideLink key={item.to} {...item} />
          ))}

          {(canSeeTeam || canSeeRevenue) && (
            <>
              <NavSection label="Management" />
              {canSeeTeam    && <SideLink {...NAV_MANAGER[0]} />}
              {canSeeRevenue && <SideLink {...NAV_MANAGER[1]} />}
              {/* Regional view — business_head / CEO only */}
              {['business_head','ceo','super_admin'].includes(user?.role ?? '') &&
                <SideLink {...NAV_MANAGER[2]} />}
              {canSeeTeam    && <SideLink {...NAV_MANAGER[3]} />}
              {canSeeFGA     && <SideLink {...NAV_FGA} />}
            </>
          )}

          {canSeeScoring && (
            <>
              <NavSection label="Admin" />
              <SideLink {...NAV_SCORING} />
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="px-4 py-4 border-t" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
          <div className="flex items-center gap-3 mb-3">
            {/* Avatar — brand pink gradient */}
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold text-white shrink-0"
              style={{ background: 'linear-gradient(135deg, #F0115E, #92278E)' }}>
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-semibold text-white truncate">{user?.name}</div>
              <div className="text-[10px] truncate" style={{ color: 'rgba(255,255,255,0.38)' }}>
                {ROLE_LABELS[user?.role ?? ''] ?? user?.role} · {orgLabel}
              </div>
            </div>
          </div>
          <button
            onClick={() => { clearAuth(); navigate('/login') }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left"
            style={{ color: 'rgba(255,255,255,0.35)' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#F0115E')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}>
            <span>↩</span> Sign out
          </button>
        </div>
      </aside>

      {/* ══════════════════════════════════════════════════════════════
          MOBILE TOP BAR
      ══════════════════════════════════════════════════════════════ */}
      <header className="md:hidden flex items-center justify-between px-4 py-3"
        style={{ background: 'linear-gradient(135deg, #1A0B2E 0%, #3D1A6E 100%)',
                 borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        {/* Compact logo */}
        <div className="flex items-center gap-2">
          <svg width="20" height="24" viewBox="0 0 52 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="0" y="0" width="52" height="11" rx="2.5" fill="#F0115E"/>
            <rect x="7" y="16" width="45" height="11" rx="2.5" fill="#F0115E"/>
            <rect x="14" y="32" width="38" height="11" rx="2.5" fill="#F0115E"/>
            <rect x="21" y="48" width="31" height="10" rx="2.5" fill="#F0115E"/>
            <rect x="0" y="16" width="5" height="11" rx="2" fill="#808083" opacity="0.6"/>
            <rect x="0" y="32" width="12" height="11" rx="2" fill="#808083" opacity="0.6"/>
            <rect x="0" y="48" width="19" height="10" rx="2" fill="#808083" opacity="0.6"/>
          </svg>
          <span className="font-display font-bold text-white text-sm tracking-tight">fluidGo</span>
        </div>
        <span className="text-xs font-medium px-2.5 py-1 rounded-lg"
          style={{ background: 'rgba(240,17,94,0.20)', color: '#F0115E' }}>
          {user?.name?.split(' ')[0]}
        </span>
      </header>

      {/* ══════════════════════════════════════════════════════════════
          MAIN CONTENT
      ══════════════════════════════════════════════════════════════ */}
      <main className="flex-1 overflow-y-auto bg-wep-surface pb-20 md:pb-0 min-w-0">
        <Outlet />
      </main>

      {/* ══════════════════════════════════════════════════════════════
          MOBILE BOTTOM NAV
      ══════════════════════════════════════════════════════════════ */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t border-wep-border flex overflow-x-auto z-40"
        style={{ boxShadow: '0 -2px 16px rgba(26,11,46,0.10)' }}>
        {coreNav.slice(0, 5).map(item => (
          <NavLink key={item.to} to={item.to} end={'exact' in item ? item.exact : undefined}
            className={({ isActive }) =>
              `flex-1 min-w-[60px] shrink-0 flex flex-col items-center py-2 gap-0.5 text-[10px] font-medium transition-colors
               ${isActive ? 'text-brand-pink' : 'text-wep-muted'}`
            }>
            <span className="text-[18px] leading-none">{item.icon}</span>
            <span className="truncate w-full text-center">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
