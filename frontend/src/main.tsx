import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/store/authStore'
import Login from '@/pages/Login'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import DSREntry from '@/pages/DSREntry'
import Meetings from '@/pages/Meetings'
import Leads from '@/pages/Leads'
import Pipeline from '@/pages/Pipeline'
import Analytics from '@/pages/Analytics'
import Team from '@/pages/Team'
import Opportunities from '@/pages/Opportunities'
import RevenueIntelligence from '@/pages/RevenueIntelligence'
import ScoringAdmin from '@/pages/ScoringAdmin'
import FGAApproval from '@/pages/FGAApproval'
import Gamification from '@/pages/Gamification'
import DSRHistory from '@/pages/DSRHistory'
import ErrorBoundary from '@/components/ErrorBoundary'
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

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={qc}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
              <Route index element={<Dashboard />} />
              <Route path="dsr" element={<DSREntry />} />
              <Route path="dsr/history" element={<DSRHistory />} />
              <Route path="meetings" element={<Meetings />} />
              <Route path="leads" element={<Leads />} />
              <Route path="pipeline" element={<Pipeline />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="opportunities" element={<Opportunities />} />
              <Route path="team" element={
                <ProtectedRoute roles={['manager','bu_head','inside_sales']}>
                  <Team />
                </ProtectedRoute>
              } />
              <Route path="revenue" element={
                <ProtectedRoute roles={['manager','bu_head']}>
                  <RevenueIntelligence />
                </ProtectedRoute>
              } />
              <Route path="scoring-admin" element={<ScoringAdmin />} />
              <Route path="fga-approval" element={
                <ProtectedRoute roles={['manager','bu_head','business_head','ceo','super_admin','hr','finance']}>
                  <FGAApproval />
                </ProtectedRoute>
              } />
              <Route path="gamification" element={<Gamification />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
