import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

const NAV = [
  { to: '/',          label: '⚡ Dashboard',   exact: true  },
  { to: '/dsr',       label: '✏️ Submit DSR'               },
  { to: '/meetings',  label: '🤝 Meetings'                 },
  { to: '/leads',     label: '🎯 Leads'                    },
  { to: '/pipeline',  label: '📊 Pipeline'                 },
  { to: '/analytics', label: '📈 Analytics'               },
]
const MANAGER_NAV = { to: '/team', label: '👥 Team' }

export default function Layout() {
  const { user, clearAuth } = useAuthStore()
  const navigate = useNavigate()
  const canSeeTeam = ['manager','bu_head','inside_sales'].includes(user?.role ?? '')
  const navItems = canSeeTeam ? [...NAV, MANAGER_NAV] : NAV

  return (
    <div className="flex flex-col h-screen md:flex-row">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-52 bg-white border-r border-wep-border shrink-0">
        <div className="p-4 border-b border-wep-border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-wep-electric to-wep-accent flex items-center justify-center">
              <span className="font-display text-white text-xs font-bold">fG</span>
            </div>
            <div>
              <div className="font-display font-bold text-wep-navy text-sm">fluidGo</div>
              <div className="text-wep-muted text-[10px] uppercase tracking-wide">{user?.bu} BU</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {navItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.exact}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                ${isActive ? 'bg-wep-accent/10 text-wep-accent' : 'text-wep-muted hover:bg-wep-surface hover:text-wep-navy'}`
              }>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-wep-border">
          <div className="text-xs text-wep-muted mb-1 truncate">{user?.name}</div>
          <div className="text-[10px] text-wep-muted/60 uppercase tracking-wide mb-2">{user?.role?.replace('_',' ')}</div>
          <button onClick={() => { clearAuth(); navigate('/login') }}
            className="text-xs text-wep-muted hover:text-red-500 transition-colors">
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="md:hidden bg-wep-navy text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-wep-electric to-wep-accent flex items-center justify-center">
            <span className="font-display text-white text-[11px] font-bold">fG</span>
          </div>
          <span className="font-display font-bold text-sm">fluidGo</span>
        </div>
        <span className="text-xs text-wep-muted">{user?.name?.split(' ')[0]}</span>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-y-auto bg-wep-surface pb-20 md:pb-0">
        <Outlet />
      </main>

      {/* Mobile bottom nav — scrollable so no item (incl. Team, for managers) gets clipped */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-wep-border flex overflow-x-auto">
        {navItems.map(item => (
          <NavLink key={item.to} to={item.to} end={item.exact}
            className={({ isActive }) =>
              `flex-1 min-w-[64px] shrink-0 flex flex-col items-center py-2 text-[10px] gap-0.5 transition-colors
              ${isActive ? 'text-wep-accent' : 'text-wep-muted'}`
            }>
            <span className="text-lg leading-none">{item.label.split(' ')[0]}</span>
            <span className="truncate w-full text-center">{item.label.split(' ').slice(1).join(' ')}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
