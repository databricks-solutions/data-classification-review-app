import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from 'react-router-dom'
import { useAppStore } from './store/useAppStore'
import { api } from './store/api'
import { AppShell } from './shell/AppShell'

import { StewardInbox } from './steward/StewardInbox'
import { ReviewDetail } from './steward/ReviewDetail'
import { ReviewGuide } from './steward/ReviewGuide'
import { AdminDashboard } from './admin/AdminDashboard'
import { AdminAssets } from './admin/AdminAssets'
import { ApplyTags } from './admin/ApplyTags'
import { AuditLog } from './admin/AuditLog'
import { StewardsAdminScreen } from './admin/StewardsAdminScreen'
import { TagsAdminScreen } from './admin/TagsAdminScreen'

function RoleGuard({ allow, children }: { allow: 'steward' | 'admin'; children: React.ReactNode }) {
  const { role } = useAppStore()
  if (role !== allow) return <Navigate to="/" replace />
  return <>{children}</>
}

function ReviewDetailRoute() {
  const { tableKey } = useParams<{ tableKey: string }>()
  const navigate = useNavigate()
  return (
    <ReviewDetail
      tableKey={decodeURIComponent(tableKey ?? '')}
      onBack={() => navigate('/inbox')}
    />
  )
}

function MyDecisions() {
  const { currentUser } = useAppStore()
  return <AuditLog hideFilters reviewerFilter={currentUser?.id} />
}

function AppRoutes() {
  const { role, setIdentity } = useAppStore()
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    const load = (attempt = 0) => {
      api.getMe().then(me => {
        if (cancelled) return
        setIdentity(
          { id: me.id, name: me.name, email: me.email, initials: me.initials,
            accent: me.accent, team: me.team, isAdmin: me.isAdmin, kind: 'user' },
          me.isMockMode,
          me.allUsers,
        )
      }).catch(err => {
        if (cancelled) return
        console.error('getMe failed:', err)
        if (attempt < 5) setTimeout(() => load(attempt + 1), 1000 * (attempt + 1))
      })
    }
    load()
    return () => { cancelled = true }
  }, [setIdentity])

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to={role === 'admin' ? '/overview' : '/inbox'} replace />} />
        {/* Steward routes */}
        <Route path="/inbox" element={
          <RoleGuard allow="steward">
            <StewardInbox onOpenTable={(k) => navigate(`/inbox/${encodeURIComponent(k)}`)} />
          </RoleGuard>
        } />
        <Route path="/inbox/:tableKey" element={<RoleGuard allow="steward"><ReviewDetailRoute /></RoleGuard>} />
        <Route path="/decided" element={<RoleGuard allow="steward"><MyDecisions /></RoleGuard>} />
        <Route path="/guide" element={<RoleGuard allow="steward"><ReviewGuide /></RoleGuard>} />
        {/* Admin routes */}
        <Route path="/overview" element={<RoleGuard allow="admin"><AdminDashboard /></RoleGuard>} />
        <Route path="/assets" element={<RoleGuard allow="admin"><AdminAssets /></RoleGuard>} />
        <Route path="/apply" element={<RoleGuard allow="admin"><ApplyTags /></RoleGuard>} />
        <Route path="/tags" element={<RoleGuard allow="admin"><TagsAdminScreen /></RoleGuard>} />
        <Route path="/audit" element={<RoleGuard allow="admin"><AuditLog /></RoleGuard>} />
        <Route path="/stewards" element={<RoleGuard allow="admin"><StewardsAdminScreen /></RoleGuard>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
