import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import Login from '@/pages/Login'
import ResetPassword from '@/pages/ResetPassword'
import ChangePassword from '@/pages/ChangePassword'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import DSREntry from '@/pages/DSREntry'
import DSRHistory from '@/pages/DSRHistory'
import Meetings from '@/pages/Meetings'
import MeetingDetail from '@/pages/MeetingDetail'
import Leads from '@/pages/Leads'
import Contacts from '@/pages/Contacts'
import CompanyDetail from '@/pages/CompanyDetail'
import Deals from '@/pages/Deals'
import Analytics from '@/pages/Analytics'
import Team from '@/pages/Team'
import RevenueIntelligence from '@/pages/RevenueIntelligence'
import RegionalPerformance from '@/pages/RegionalPerformance'
import ScoringAdmin from '@/pages/ScoringAdmin'
import SystemHealth from '@/pages/SystemHealth'
import FGAApproval from '@/pages/FGAApproval'
import SchemeWinners from '@/pages/SchemeWinners'
import ActivityLogs from '@/pages/ActivityLogs'
import Gamification from '@/pages/Gamification'
import Help from '@/pages/Help'
import FeedbackInbox from '@/pages/FeedbackInbox'
import DOREntry from '@/pages/DOREntry'
import ManualKPIEntry from '@/pages/ManualKPIEntry'
import Governance from '@/pages/Governance'
import Reports from '@/pages/Reports'
import CompanyKPIEntry from '@/pages/CompanyKPIEntry'
import ExecutiveDigest from '@/pages/ExecutiveDigest'
import Orders from '@/pages/Orders'
import ErrorBoundary from '@/components/ErrorBoundary'
import Toaster from '@/components/Toaster'
import './index.css'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } }
})

function ProtectedRoute({ children, roles }: { children: React.ReactNode; roles?: string[] }) {
  const { user } = useAuthStore()
  if (!user) return <Navigate to="/login" replace />
  // Hard gate: forced password change (first login, or an admin reset)
  // takes priority over every other route, regardless of role. Backend
  // enforces this independently too (deps.get_current_user) — this is the
  // UX side of the same rule, not the security boundary itself.
  if (user.must_change_password) return <Navigate to="/change-password" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <>{children}</>
}

const MANAGER_ROLES = ['manager','regional_manager','bu_head','business_head','ceo','super_admin']
// Everyone except hr/finance (backend contacts router denies them)
const CONTACT_ROLES = ['rep','inside_sales','pre_sales','service_delivery_manager','governance', ...MANAGER_ROLES, 'practice_head', 'coo', 'crm_admin']
const MGMT_FINANCE  = [...MANAGER_ROLES, 'hr', 'finance']
const KPI_ENTRY_ROLES = [...MANAGER_ROLES, 'service_delivery_manager', 'rep', 'inside_sales', 'pre_sales']
// Company KPI Entry — org-wide numbers (e.g. Company Revenue Target),
// Finance's own screen. Matches backend's _can_enter_company_kpi exactly:
// 'finance' by name, plus regional_manager/bu_head/business_head/ceo/
// super_admin (role_level >= 30) — deliberately NOT plain 'manager'
// (level 20, part of MANAGER_ROLES elsewhere) or 'hr' (same level as
// finance but not Finance) — either would see the nav link and page, then
// get a 403 from every call.
const COMPANY_KPI_ROLES = ['regional_manager', 'bu_head', 'business_head', 'ceo', 'super_admin', 'finance']
// Matches backend feedback.py's REVIEW_LEVEL (role_level >= 40)
const FEEDBACK_ADMIN_ROLES = ['business_head', 'practice_head', 'coo', 'ceo', 'super_admin']
// Executive Digest (2026-10-24) — matches backend's require_level(40) on
// GET/POST /analytics/exec-digest*, which is the exact same role_level >= 40
// threshold as FEEDBACK_ADMIN_ROLES above. Reusing that constant rather than
// re-deriving an identical role list, per the hardcoded-list-must-match-
// backend-gate lesson flagged twice already in claude/README.md's Open Items.
const EXEC_DIGEST_ROLES = FEEDBACK_ADMIN_ROLES
// Orders register (v1.6.1) — matches backend can_view_orders: finance or role_level >= 20, governance excluded.
const ORDERS_ROLES = [...MANAGER_ROLES, 'practice_head', 'coo', 'crm_admin', 'finance']

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={qc}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/change-password" element={<ChangePassword />} />
            <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
              <Route index element={<Dashboard />} />
              {/* DSR — field roles only (matches backend DSR_ALLOWED_ROLES).
                  Previously unguarded: any logged-in role (HR included)
                  could reach the submit form directly, even though the
                  backend already 403'd the actual POST. */}
              <Route path="dsr" element={
                <ProtectedRoute roles={['rep', 'inside_sales', 'pre_sales', 'manager']}>
                  <DSREntry />
                </ProtectedRoute>
              } />
              <Route path="dsr/history" element={<DSRHistory />} />
              {/* Field activities */}
              <Route path="meetings"      element={<Meetings />} />
              {/* Governance reaches this via its own nav link (Layout.tsx);
                  every other role reaches it from the Meetings list. Same
                  route serves both edit and read-only render modes — see
                  MeetingDetail.tsx's isGovernance check — one screen to
                  maintain instead of a parallel governance-only view. */}
              <Route path="meetings/:id"  element={<MeetingDetail />} />
              <Route path="contacts" element={
                <ProtectedRoute roles={CONTACT_ROLES}><Contacts /></ProtectedRoute>
              } />
              <Route path="companies/:id" element={
                <ProtectedRoute roles={CONTACT_ROLES}><CompanyDetail /></ProtectedRoute>
              } />
              <Route path="leads"         element={<Leads />} />
              <Route path="deals"         element={<Deals />} />
              {/* Old links keep working: Pipeline and Opportunities are now tabs of Deals. */}
              <Route path="pipeline"      element={<Navigate to="/deals" replace />} />
              <Route path="opportunities" element={<Navigate to="/deals?tab=health" replace />} />
              <Route path="help"          element={<Help />} />
              <Route path="feedback" element={
                <ProtectedRoute roles={FEEDBACK_ADMIN_ROLES}>
                  <FeedbackInbox />
                </ProtectedRoute>
              } />
              <Route path="analytics"     element={<Analytics />} />
              <Route path="gamification"  element={<Gamification />} />
              {/* Service Delivery */}
              <Route path="dor" element={
                <ProtectedRoute roles={['service_delivery_manager', ...MANAGER_ROLES]}>
                  <DOREntry />
                </ProtectedRoute>
              } />
              <Route path="kpi-entry" element={
                <ProtectedRoute roles={KPI_ENTRY_ROLES}>
                  <ManualKPIEntry />
                </ProtectedRoute>
              } />
              <Route path="company-kpi-entry" element={
                <ProtectedRoute roles={COMPANY_KPI_ROLES}>
                  <CompanyKPIEntry />
                </ProtectedRoute>
              } />
              <Route path="orders" element={
                <ProtectedRoute roles={ORDERS_ROLES}>
                  <Orders />
                </ProtectedRoute>
              } />
              <Route path="exec-digest" element={
                <ProtectedRoute roles={EXEC_DIGEST_ROLES}>
                  <ExecutiveDigest />
                </ProtectedRoute>
              } />
              {/* Management — manager+ */}
              <Route path="team" element={
                <ProtectedRoute roles={[...MANAGER_ROLES, 'inside_sales', 'crm_admin']}>
                  <Team />
                </ProtectedRoute>
              } />
              <Route path="revenue" element={
                <ProtectedRoute roles={[...MANAGER_ROLES, 'crm_admin']}>
                  <RevenueIntelligence />
                </ProtectedRoute>
              } />
              {/* Same audience as /revenue — Reports catalog added 2026-10-23 */}
              <Route path="reports" element={
                <ProtectedRoute roles={[...MANAGER_ROLES, 'crm_admin']}>
                  <Reports />
                </ProtectedRoute>
              } />
              <Route path="regional" element={
                <ProtectedRoute roles={['business_head','ceo','super_admin']}>
                  <RegionalPerformance />
                </ProtectedRoute>
              } />
              <Route path="fga-approval" element={
                <ProtectedRoute roles={MGMT_FINANCE}>
                  <FGAApproval />
                </ProtectedRoute>
              } />
              <Route path="scheme-winners" element={
                <ProtectedRoute roles={MGMT_FINANCE}>
                  <SchemeWinners />
                </ProtectedRoute>
              } />
              <Route path="activity-logs" element={
                <ProtectedRoute roles={['hr','finance','super_admin']}>
                  <ActivityLogs />
                </ProtectedRoute>
              } />
              {/* Admin */}
              <Route path="scoring-admin" element={
                <ProtectedRoute roles={['regional_manager','bu_head','business_head','practice_head','ceo','super_admin']}>
                  <ScoringAdmin />
                </ProtectedRoute>
              } />
              <Route path="system-health" element={
                <ProtectedRoute roles={['super_admin']}>
                  <SystemHealth />
                </ProtectedRoute>
              } />
              {/* Governance — validation-only, no data entry, no financial
                  visibility (see backend can_see_financials()/deny_governance()) */}
              <Route path="governance" element={
                <ProtectedRoute roles={['governance', 'super_admin']}>
                  <Governance />
                </ProtectedRoute>
              } />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster />
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
