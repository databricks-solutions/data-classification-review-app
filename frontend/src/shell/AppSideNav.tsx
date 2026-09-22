import { useNavigate, useLocation } from 'react-router-dom'
import { Icon } from '../components'
import { useAppStore } from '../store/useAppStore'

interface NavItem {
  id: string
  path: string
  icon: string
  label: string
  badge?: number
}

interface AppSideNavProps {
  pendingCount: number
  adminPendingCount: number
}

export function AppSideNav({ pendingCount, adminPendingCount }: AppSideNavProps) {
  const role = useAppStore(s => s.role)
  const navigate = useNavigate()
  const location = useLocation()

  const stewardItems: NavItem[] = [
    { id: 'inbox',    path: '/inbox',   icon: 'inbox', label: 'My review queue', badge: pendingCount },
    { id: 'decided', path: '/decided', icon: 'audit', label: 'Decided' },
    { id: 'guide',   path: '/guide',   icon: 'info',  label: 'Review guide' },
  ]

  const adminItems: NavItem[] = [
    { id: 'overview', path: '/overview', icon: 'chart',    label: 'Overview' },
    { id: 'assets',   path: '/assets',   icon: 'table',    label: 'All assets', badge: adminPendingCount },
    { id: 'apply',    path: '/apply',    icon: 'upload',   label: 'Apply tags' },
    { id: 'tags',     path: '/tags',     icon: 'tag',      label: 'Tags' },
    { id: 'audit',    path: '/audit',    icon: 'audit',    label: 'Audit log' },
    { id: 'stewards', path: '/stewards', icon: 'users',    label: 'Stewards' },
  ]

  const items = role === 'admin' ? adminItems : stewardItems

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + '/')

  return (
    <aside style={{
      width: 220, background: '#fff', borderRight: '1px solid var(--db-gray-lines)',
      display: 'flex', flexDirection: 'column', flexShrink: 0, padding: '18px 12px 12px',
    }}>
      <div style={{
        fontSize: 10.5, color: 'var(--db-gray-text)',
        textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 500,
        padding: '0 8px 10px',
      }}>
        {role === 'admin' ? 'Administration' : 'Review'}
      </div>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        {items.map(it => {
          const active = isActive(it.path)
          return (
            <button
              key={it.id}
              onClick={() => navigate(it.path)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
                borderRadius: 5, border: 0, cursor: 'pointer',
                background: active ? 'var(--db-oat-medium)' : 'transparent',
                color: active ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
                fontFamily: 'var(--font-sans)', fontWeight: active ? 500 : 400, fontSize: 13,
                textAlign: 'left', position: 'relative',
              }}
            >
              <Icon name={it.icon} size={15} />
              <span style={{ flex: 1 }}>{it.label}</span>
              {it.badge ? (
                <span style={{
                  background: 'var(--db-lava-600)', color: '#fff',
                  fontSize: 10, fontWeight: 600, padding: '1px 7px',
                  borderRadius: 999, minWidth: 18, textAlign: 'center',
                }}>{it.badge}</span>
              ) : null}
            </button>
          )
        })}
      </nav>

    </aside>
  )
}
