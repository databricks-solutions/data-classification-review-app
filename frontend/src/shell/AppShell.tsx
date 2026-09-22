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

  const { data: tables = [] } = useQuery({ queryKey: ['tables'], queryFn: api.getTables })
  const { data: proposals = [] } = useQuery({ queryKey: ['proposals'], queryFn: () => api.getProposals() })
  const { data: myAssignments = [] } = useQuery({
    queryKey: ['assignments', currentUser?.id],
    queryFn: () => api.getAssignments(currentUser!.id),
    enabled: !!currentUser,
  })

  const pendingCount = tables
    .filter(t => myAssignments.some(a => {
      if (a.catalog !== t.catalog) return false
      if (a.scope === 'catalog') return true
      if (a.scope === 'schema') return a.schemaName === t.schema
      return a.schemaName === t.schema && a.tableName === t.table
    }))
    .reduce((s, t) => s + t.pending, 0)
  const adminPendingCount = proposals.filter(p => p.status === 'pending').length

  // Compute breadcrumb from location
  const breadcrumb = (() => {
    const path = location.pathname
    if (role === 'steward') {
      if (path.startsWith('/inbox/')) {
        const tableKey = decodeURIComponent(path.replace('/inbox/', ''))
        const table = tables.find(t => t.key === tableKey)
        return [
          { label: 'My review queue', onClick: () => window.history.back() },
          { label: table ? `${table.catalog}.${table.schema}.${table.table}` : tableKey },
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
