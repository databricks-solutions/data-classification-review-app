import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAppStore } from '../store/useAppStore'
import { AppTopBar } from './AppTopBar'
import { AppSideNav } from './AppSideNav'
import { api } from '../store/api'

export function AppShell({ children }: { children: ReactNode }) {
  const { role, currentUser } = useAppStore()
  const location = useLocation()

  const isSteward = role === 'steward'
  const { data: myTables = [] } = useQuery({
    queryKey: ['tables', 'steward', currentUser?.id],
    queryFn: () => api.getStewardTables(currentUser!.id),
    enabled: !!currentUser && isSteward,
  })
  const { data: stats } = useQuery({
    queryKey: ['proposals', 'stats', ''],
    queryFn: () => api.getOverviewStats(),
    enabled: !!currentUser && !isSteward,
  })

  const pendingCount = myTables.reduce((s, t) => s + t.pending, 0)
  const adminPendingCount = stats?.pending ?? 0

  // Compute breadcrumb from location
  const breadcrumb = (() => {
    const path = location.pathname
    if (role === 'steward') {
      if (path.startsWith('/inbox/')) {
        const tableKey = decodeURIComponent(path.replace('/inbox/', ''))
        return [
          { label: 'My review queue', onClick: () => window.history.back() },
          { label: tableKey },
        ]
      }
      if (path === '/decided') return [{ label: 'My decisions' }]
      if (path === '/guide') return [{ label: 'Review guide' }]
      return [{ label: 'My review queue' }]
    }
    const adminLabels: Record<string, string> = {
      '/overview': 'Overview', '/assets': 'All assets',
      '/apply': 'Apply tags', '/audit': 'Audit log', '/stewards': 'Stewards',
    }
    return [{ label: 'Admin' }, { label: adminLabels[path] ?? 'Overview' }]
  })()

  if (!currentUser) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-sans)', color: 'var(--db-gray-text)', fontSize: 14 }}>
        Loading…
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--db-oat-light)' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <AppTopBar breadcrumb={breadcrumb} />
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <AppSideNav pendingCount={pendingCount} adminPendingCount={adminPendingCount} />
          <main style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}
