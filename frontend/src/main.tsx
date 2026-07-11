import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import Login from '@/pages/Login'
import ResetPassword from '@/pages/ResetPassword'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import DSREntry from '@/pages/DSREntry'
import DSRHistory from '@/pages/DSRHistory'
import Meetings from '@/pages/Meetings'
import Leads from '@/pages/Leads'
import Pipeline from '@/pages/Pipeline'
import Analytics from '@/pages/Analytics'
import Team from '@/pages/Team'
import Opportunities from '@/pages/Opportunities'
import RevenueIntelligence from '@/pages/RevenueIntelligence'
import RegionalPerformance from '@/pages/RegionalPerformance'
import ScoringAdmin from '@/pages/ScoringAdmin'
import SystemHealth from '@/pages/SystemHealth'
import FGAApproval from '@/pages/FGAApproval'
import Gamification from '@/pages/Gamification'
import Help from '@/pages/Help'
import DOREntry from '@/pages/DOREntry'
import ManualKPIEntry from '@/pages/ManualKPIEntry'
import ErrorBoundary from '@/components/ErrorBoundary'
import Toaster from '@/components/Toaster'
import './index.css'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } }
})

function ProtectedRoute({ children, roles }: { children: React.ReactNode; roles?: string[] }) {
  const { user } = useAuthStore()
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <>{children}</>
}

const MANAGER_ROLES = ['manager','regional_manager','bu_head','business_head','ceo','super_admin']
const MGMT_FINANCE  = [...MANAGER_ROLES, 'hr', 'finance']
const KPI_ENTRY_ROLES = [...MANAGER_ROLES, 'service_delivery_manager', 'rep', 'inside_sales', 'pre_sales']

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={qc}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
              <Route index element={<Dashboard />} />
              {/* DSR */}
              <Route path="dsr"         element={<DSREntry />} />
              <Route path="dsr/history" element={<DSRHistory />} />
              {/* Field activities */}
              <Route path="meetings"      element={<Meetings />} />
              <Route path="leads"         element={<Leads />} />
              <Route path="pipeline"      element={<Pipeline />} />
              <Route path="opportunities" element={<Opportunities />} />
              <Route path="help"          element={<Help />} />
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
              {/* Management — manager+ */}
              <Route path="team" element={
                <ProtectedRoute roles={[...MANAGER_ROLES, 'inside_sales']}>
                  <Team />
                </ProtectedRoute>
              } />
              <Route path="revenue" element={
                <ProtectedRoute roles={MANAGER_ROLES}>
                  <RevenueIntelligence />
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
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster />
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
