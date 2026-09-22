import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Icon, Avatar } from '../components'
import { useAppStore } from '../store/useAppStore'

export interface BreadcrumbItem {
  label: string
  onClick?: () => void
}

interface AppTopBarProps {
  breadcrumb?: BreadcrumbItem[]
}

export function AppTopBar({ breadcrumb }: AppTopBarProps) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const queryClient = useQueryClient()
  const currentUser = useAppStore(s => s.currentUser)
  const role = useAppStore(s => s.role)
  const isAdmin = useAppStore(s => s.isAdmin)
  const isMockMode = useAppStore(s => s.isMockMode)
  const allMockUsers = useAppStore(s => s.allMockUsers)
  const setRole = useAppStore(s => s.setRole)
  const switchMockUser = useAppStore(s => s.switchMockUser)

  if (!currentUser) {
    // Render a minimal header while identity loads to preserve layout
    return (
      <header style={{
        height: 56, background: '#fff', borderBottom: '1px solid var(--db-gray-lines)',
        display: 'flex', alignItems: 'center', padding: '0 20px', gap: 16, flexShrink: 0,
      }} />
    )
  }

  return (
    <header style={{
      height: 56, background: '#fff', borderBottom: '1px solid var(--db-gray-lines)',
      display: 'flex', alignItems: 'center', padding: '0 20px', gap: 16, flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 6, background: 'var(--db-navy-800)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff',
        }}>
          <Icon name="flag" size={15} color="#FF5F46" />
        </div>
        <div style={{ whiteSpace: 'nowrap' }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--db-navy-800)', lineHeight: 1.1 }}>
            Data Classification Review App
          </div>
        </div>
      </div>

      <div style={{ width: 1, height: 24, background: 'var(--db-gray-lines)', margin: '0 8px' }} />

      {breadcrumb && breadcrumb.length > 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, fontSize: 13,
          color: 'var(--db-gray-text)', whiteSpace: 'nowrap', overflow: 'hidden',
          textOverflow: 'ellipsis', flex: '0 1 auto', minWidth: 0,
        }}>
          {breadcrumb.map((b, i) => (
            <span key={b.label ?? i} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <span
                onClick={b.onClick}
                style={{
                  color: i === breadcrumb.length - 1 ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
                  fontWeight: i === breadcrumb.length - 1 ? 500 : 400,
                  cursor: b.onClick ? 'pointer' : 'default',
                  overflow: 'hidden', textOverflow: 'ellipsis',
                }}
              >
                {b.label}
              </span>
              {i < breadcrumb.length - 1 && (
                <span style={{ color: 'var(--db-navy-400)', flexShrink: 0 }}>/</span>
              )}
            </span>
          ))}
        </div>
      )}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 14 }}>
        {isAdmin && (
          <div style={{
            display: 'inline-flex', background: 'var(--db-oat-medium)',
            borderRadius: 999, padding: 3, gap: 0,
          }}>
            {[
              { id: 'steward' as const, label: 'Steward view', icon: 'user' },
              { id: 'admin' as const, label: 'Admin view', icon: 'users' },
            ].map(opt => (
              <button key={opt.id} onClick={() => setRole(opt.id)} style={{
                display: 'inline-flex', alignItems: 'center', gap: 7, whiteSpace: 'nowrap',
                border: 0, background: role === opt.id ? '#fff' : 'transparent',
                color: role === opt.id ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
                padding: '6px 14px', borderRadius: 999, cursor: 'pointer',
                fontFamily: 'var(--font-sans)', fontWeight: 500, fontSize: 12.5,
                boxShadow: role === opt.id ? 'var(--shadow-xs)' : 'none',
                transition: 'all var(--dur-fast) var(--ease-out)',
              }}>
                <Icon name={opt.icon} size={13} />
                {opt.label}
              </button>
            ))}
          </div>
        )}

        <div style={{ width: 1, height: 24, background: 'var(--db-gray-lines)' }} />

        <div style={{ position: 'relative' }}>
          <button
            onClick={() => { if (isMockMode) setPickerOpen(!pickerOpen) }}
            style={{
              display: 'flex', alignItems: 'center', gap: 9, whiteSpace: 'nowrap',
              background: 'transparent', border: 0, padding: '4px 6px',
              cursor: isMockMode ? 'pointer' : 'default',
              borderRadius: 6, transition: 'background var(--dur-fast)',
            }}
            onMouseEnter={e => { if (isMockMode) (e.currentTarget as HTMLButtonElement).style.background = 'var(--db-oat-medium)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
          >
            <Avatar initials={currentUser.initials} color={currentUser.accent} size={30} />
            <div style={{ lineHeight: 1.15, textAlign: 'left' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--db-navy-800)' }}>{currentUser.name}</span>
                {isAdmin && (
                  <span style={{
                    fontSize: 9, padding: '1px 6px', borderRadius: 3,
                    background: 'var(--db-navy-800)', color: '#fff', fontWeight: 600,
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                  }}>Admin</span>
                )}
              </div>
              {currentUser.team && (
                <div style={{ fontSize: 10.5, color: 'var(--db-gray-text)' }}>{currentUser.team}</div>
              )}
            </div>
            {isMockMode && <Icon name="chevDown" size={13} color="var(--db-gray-text)" />}
          </button>

          {isMockMode && pickerOpen && allMockUsers.length > 0 && (
            <>
              <div
                onClick={() => setPickerOpen(false)}
                style={{ position: 'fixed', inset: 0, zIndex: 50 }}
              />
              <div style={{
                position: 'absolute', top: 'calc(100% + 6px)', right: 0,
                background: '#fff', border: '1px solid var(--db-gray-lines)',
                borderRadius: 8, boxShadow: 'var(--shadow-lg)', width: 280,
                zIndex: 51, padding: 4,
              }}>
                <div style={{
                  fontSize: 10.5, color: 'var(--db-gray-text)', textTransform: 'uppercase',
                  letterSpacing: '0.08em', fontWeight: 500, padding: '8px 12px 6px',
                }}>
                  Switch user · mock mode only
                </div>
                <div style={{
                  padding: '0 12px 8px', fontSize: 10.5, color: 'var(--db-gray-text)', lineHeight: 1.4,
                }}>
                  In production, the user is determined by the Databricks workspace login — there is no picker.
                </div>
                {allMockUsers.map(u => (
                  <button
                    key={u.id}
                    onClick={() => {
                      switchMockUser(u.id)
                      setPickerOpen(false)
                      queryClient.invalidateQueries()
                    }}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 10px',
                      background: u.id === currentUser.id ? 'var(--db-oat-medium)' : 'transparent',
                      border: 0, borderRadius: 5, cursor: 'pointer', textAlign: 'left',
                    }}
                    onMouseEnter={e => {
                      if (u.id !== currentUser.id) {
                        (e.currentTarget as HTMLButtonElement).style.background = 'var(--db-oat-light)'
                      }
                    }}
                    onMouseLeave={e => {
                      if (u.id !== currentUser.id) {
                        (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                      }
                    }}
                  >
                    <Avatar initials={u.initials} color={u.accent} size={26} fontSize={11} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 12.5, color: 'var(--db-navy-800)', fontWeight: 500 }}>
                          {u.name}
                        </span>
                        {u.isAdmin && (
                          <span style={{
                            fontSize: 8.5, padding: '1px 5px', borderRadius: 3,
                            background: 'var(--db-navy-800)', color: '#fff', fontWeight: 600,
                            textTransform: 'uppercase', letterSpacing: '0.06em',
                          }}>Admin</span>
                        )}
                      </div>
                      {u.email && (
                        <div style={{ fontSize: 10.5, color: 'var(--db-gray-text)' }}>{u.email}</div>
                      )}
                    </div>
                    {u.id === currentUser.id && (
                      <Icon name="check" size={13} color="var(--db-green-700)" />
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
