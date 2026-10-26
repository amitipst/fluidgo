import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import WeakAreasPanel from '@/components/WeakAreasPanel'

// One workspace for what used to be two menu items over the same table:
// "Pipeline" (work the deals) and "Opportunities" (health and risk). They are
// now lenses on the same deals — Deals | Health & risk | Weak areas. Each lens
// is loaded only when opened, so the default view costs nothing extra.
const Pipeline = lazy(() => import('@/pages/Pipeline'))
const Opportunities = lazy(() => import('@/pages/Opportunities'))

const TABS = [['deals', 'Deals'], ['health', 'Health & risk'], ['weak', 'Weak areas & actions']] as const
type Tab = typeof TABS[number][0]

export default function Deals() {
  const [params, setParams] = useSearchParams()
  const raw = params.get('tab')
  const tab: Tab = (TABS.some(t => t[0] === raw) ? raw : 'deals') as Tab
  const go = (t: Tab) => setParams(t === 'deals' ? {} : { tab: t }, { replace: true })
  return (
    <div>
      <div className="px-4 md:px-6 pt-4 md:pt-6 max-w-5xl mx-auto">
        <div role="tablist" aria-label="Deals workspace" className="inline-flex max-w-full overflow-x-auto rounded-xl border border-wep-border">
          {TABS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => go(k)}
              className={`px-4 min-h-[44px] whitespace-nowrap text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-pink ${tab === k ? 'bg-brand-pink text-white' : 'text-wep-muted hover:bg-wep-surface'}`}>{label}</button>))}
        </div>
      </div>
      {tab === 'weak'
        ? <div className="p-4 md:p-6 max-w-5xl mx-auto"><WeakAreasPanel /></div>
        : <Suspense fallback={<div className="p-6"><div className="skeleton h-24 rounded-2xl" /></div>}>
            {tab === 'health' ? <Opportunities /> : <Pipeline />}
          </Suspense>}
    </div>
  )
}
