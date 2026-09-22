import { useMemo, useRef, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Icon, Pill, Btn, Avatar, AssetPath, SearchableSelect } from '../components'
import { api } from '../store/api'
import { AddStewardDialog } from './AddStewardDialog'
import type {
  Principal, StewardAssignment, AssignmentScope, TableSummary,
} from '../store/types'

type KindFilter = 'all' | 'user' | 'group'

export function StewardsAdminScreen() {
  const queryClient = useQueryClient()

  const { data: principals = [], isLoading } = useQuery<Principal[]>({
    queryKey: ['stewards'],
    queryFn: api.getStewards,
  })

  const { data: tables = [] } = useQuery<TableSummary[]>({
    queryKey: ['tables'],
    queryFn: api.getTables,
  })

  const [filter, setFilter] = useState('')
  const [kindFilter, setKindFilter] = useState<KindFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showAddStewardDialog, setShowAddStewardDialog] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const removeMutation = useMutation({
    mutationFn: (id: string) => api.deleteAssignment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assignments', selected?.id] })
      queryClient.invalidateQueries({ queryKey: ['stewards'] })
      queryClient.invalidateQueries({ queryKey: ['tables'] })
    },
    onError: () => setError('Failed to remove assignment'),
  })

  const removePrincipalMutation = useMutation({
    mutationFn: (id: string) => api.deleteSteward(id),
    onSuccess: () => {
      setSelectedId(null)
      queryClient.invalidateQueries({ queryKey: ['stewards'] })
      queryClient.invalidateQueries({ queryKey: ['tables'] })
    },
    onError: () => setError('Failed to remove steward'),
  })

  const filteredPrincipals = useMemo(() => {
    const q = filter.toLowerCase().trim()
    return principals.filter(p => {
      if (kindFilter !== 'all' && p.kind !== kindFilter) return false
      if (q && !p.name.toLowerCase().includes(q)) return false
      return true
    })
  }, [principals, filter, kindFilter])

  const selected = useMemo(() => {
    if (selectedId) return principals.find(p => p.id === selectedId) ?? null
    return filteredPrincipals[0] ?? principals[0] ?? null
  }, [principals, filteredPrincipals, selectedId])

  const { data: assignments = [] } = useQuery<StewardAssignment[]>({
    queryKey: ['assignments', selected?.id],
    queryFn: () => api.getAssignments(selected!.id),
    enabled: !!selected,
  })

  return (
    <div style={{
      flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column',
      background: 'var(--db-oat-light)',
    }}>
      <div style={{ padding: '28px 32px 16px', flexShrink: 0 }}>
        <div style={{
          display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          gap: 16, flexWrap: 'wrap',
        }}>
          <div>
            <div style={{
              fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
              letterSpacing: '0.08em', fontWeight: 500, marginBottom: 6,
            }}>
              Administration
            </div>
            <h1 style={{
              fontSize: 26, fontWeight: 500, letterSpacing: '-0.018em',
              color: 'var(--db-navy-800)', margin: 0,
            }}>
              Stewards
            </h1>
            <div style={{ fontSize: 13, color: 'var(--db-gray-text)', marginTop: 6 }}>
              Assign users and groups as data stewards on Unity Catalog assets, at any level — catalog, schema, or table.
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="secondary" size="sm" onClick={() => setShowAddStewardDialog(true)}>
              <Icon name="user" size={13} /> Add steward
            </Btn>
            <Btn variant="primary" size="sm" onClick={() => setShowAddDialog(true)} disabled={!selected}>
              <Icon name="plus" size={13} color="#fff" /> New assignment
            </Btn>
          </div>
        </div>
      </div>

      <div style={{
        flex: 1, minHeight: 0, padding: '0 32px 32px',
        display: 'grid', gridTemplateColumns: '320px 1fr', gap: 14,
      }}>
        {/* Left — principal list */}
        <div style={{
          background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 8,
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}>
          <div style={{
            padding: 12, borderBottom: '1px solid var(--db-gray-lines)',
            display: 'flex', flexDirection: 'column', gap: 10,
          }}>
            <div style={{ position: 'relative' }}>
              <Icon
                name="search" size={14} color="var(--db-gray-text)"
                style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }}
              />
              <input
                value={filter}
                onChange={e => setFilter(e.target.value)}
                placeholder="Filter by user or group…"
                style={{
                  width: '100%', padding: '7px 10px 7px 32px',
                  background: 'var(--db-oat-light)',
                  border: '1px solid var(--db-gray-lines)', borderRadius: 6,
                  fontSize: 12.5, outline: 'none', boxSizing: 'border-box',
                  fontFamily: 'var(--font-sans)',
                }}
              />
            </div>
            <div style={{
              display: 'flex', background: 'var(--db-oat-medium)', borderRadius: 999, padding: 2,
            }}>
              {([
                { v: 'all', l: 'All' },
                { v: 'user', l: 'Users' },
                { v: 'group', l: 'Groups' },
              ] as { v: KindFilter; l: string }[]).map(opt => (
                <button
                  key={opt.v}
                  onClick={() => setKindFilter(opt.v)}
                  style={{
                    flex: 1, padding: '5px 8px', border: 0,
                    background: kindFilter === opt.v ? '#fff' : 'transparent',
                    color: kindFilter === opt.v ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
                    borderRadius: 999, fontWeight: 500, fontSize: 11.5, cursor: 'pointer',
                    boxShadow: kindFilter === opt.v ? 'var(--shadow-xs)' : 'none',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  {opt.l}
                </button>
              ))}
            </div>
          </div>
          <div style={{ flex: 1, overflow: 'auto' }}>
            {isLoading && (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--db-gray-text)', fontSize: 12.5 }}>
                Loading…
              </div>
            )}
            {!isLoading && filteredPrincipals.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--db-gray-text)', fontSize: 12.5 }}>
                No matches.
              </div>
            )}
            {filteredPrincipals.map(p => {
              const active = p.id === selected?.id
              return (
                <button
                  key={p.id}
                  onClick={() => setSelectedId(p.id)}
                  style={{
                    width: '100%', textAlign: 'left', padding: '11px 14px',
                    border: 0, background: active ? 'var(--db-oat-medium)' : 'transparent',
                    borderTop: '1px solid var(--db-gray-lines)',
                    borderLeft: active ? '3px solid var(--db-lava-600)' : '3px solid transparent',
                    display: 'flex', alignItems: 'center', gap: 11, cursor: 'pointer',
                    fontFamily: 'var(--font-sans)',
                  }}
                >
                  <Avatar initials={p.initials} color={p.accent} size={32} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{
                        fontSize: 13, color: 'var(--db-navy-800)', fontWeight: 500,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1,
                      }}>
                        {p.name}
                      </span>
                      {p.kind === 'group' && (
                        <span style={{
                          fontSize: 9.5, padding: '1px 6px', borderRadius: 4,
                          background: 'var(--db-navy-300)', color: 'var(--db-navy-800)',
                          fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em',
                        }}>
                          Group
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--db-gray-text)', marginTop: 2 }}>
                      {p.kind === 'user' ? (p.email ?? '') : ''}
                    </div>
                  </div>
                  <span style={{
                    fontSize: 11, color: 'var(--db-gray-text)', fontFamily: 'var(--font-mono)',
                  }}>
                    {p.assignmentCount ?? 0}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Right — detail */}
        {selected ? (
          <StewardDetailPanel
            principal={selected}
            assignments={assignments}
            tables={tables}
            onAddRequest={() => setShowAddDialog(true)}
            onRemove={(id) => removeMutation.mutate(id)}
            onRemovePrincipal={() => removePrincipalMutation.mutate(selected.id)}
            error={error}
            onClearError={() => setError(null)}
            onSetError={setError}
          />
        ) : (
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--db-gray-text)', fontSize: 13,
          }}>
            Select a steward to see their assignments.
          </div>
        )}
      </div>

      {showAddStewardDialog && (
        <AddStewardDialog onClose={() => setShowAddStewardDialog(false)} />
      )}

      {showAddDialog && selected && (
        <NewAssignmentDialog
          principal={selected}
          tables={tables}
          onClose={() => setShowAddDialog(false)}
          onCreate={async (payload) => {
            await api.postAssignment(payload)
            queryClient.invalidateQueries({ queryKey: ['assignments', selected.id] })
            queryClient.invalidateQueries({ queryKey: ['stewards'] })
            queryClient.invalidateQueries({ queryKey: ['tables'] })
            setShowAddDialog(false)
          }}
        />
      )}
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Detail panel
// ────────────────────────────────────────────────────────────────────────────

interface DerivedAssignment extends StewardAssignment {
  coveredTables: string[]      // "catalog.schema.table"
  proposalCount: number
  pending: number
}

function StewardDetailPanel({
  principal, assignments, tables, onAddRequest, onRemove, onRemovePrincipal, error, onClearError, onSetError,
}: {
  principal: Principal
  assignments: StewardAssignment[]
  tables: TableSummary[]
  onAddRequest: () => void
  onRemove: (id: string) => void
  onRemovePrincipal: () => void
  error: string | null
  onClearError: () => void
  onSetError: (msg: string) => void
}) {
  const queryClient = useQueryClient()

  const derived = useMemo<DerivedAssignment[]>(() => {
    return assignments.map(a => {
      const matches = tables.filter(t => {
        if (t.catalog !== a.catalog) return false
        if (a.scope !== 'catalog' && t.schema !== a.schemaName) return false
        if (a.scope === 'table' && t.table !== a.tableName) return false
        return true
      })
      const coveredTables = matches.map(t => `${t.catalog}.${t.schema}.${t.table}`)
      const proposalCount = matches.reduce((s, t) => s + (t.proposalCount ?? t.proposals.length), 0)
      const pending = matches.reduce((s, t) => s + t.pending, 0)
      return { ...a, coveredTables, proposalCount, pending }
    })
  }, [assignments, tables])

  const totalProposals = derived.reduce((s, a) => s + a.proposalCount, 0)
  const totalPending = derived.reduce((s, a) => s + a.pending, 0)
  const tableCount = new Set(derived.flatMap(a => a.coveredTables)).size

  const isUser = principal.kind === 'user'
  const [showConfirmRemove, setShowConfirmRemove] = useState(false)

  const toggleAdmin = useMutation({
    mutationFn: (isAdmin: boolean) => api.patchSteward(principal.id, { isAdmin }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stewards'] })
    },
    onError: () => onSetError('Failed to update admin role'),
  })

  return (
    <div style={{
      background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 8,
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '18px 22px', borderBottom: '1px solid var(--db-gray-lines)',
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <Avatar initials={principal.initials} color={principal.accent} size={44} fontSize={16} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <h2 style={{
              fontSize: 19, fontWeight: 500, margin: 0, color: 'var(--db-navy-800)',
            }}>
              {principal.name}
            </h2>
            {principal.kind === 'group' && (
              <Pill bg="var(--db-navy-300)" color="var(--db-navy-800)" style={{ fontSize: 10 }}>
                Group
              </Pill>
            )}
            {principal.isAdmin && (
              <span style={{
                fontSize: 9.5, padding: '2px 7px', borderRadius: 3,
                background: 'var(--db-navy-800)', color: '#fff', fontWeight: 600,
                textTransform: 'uppercase', letterSpacing: '0.06em',
              }}>
                Admin role
              </span>
            )}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--db-gray-text)', marginTop: 3 }}>
            {principal.kind === 'user'
              ? `${principal.email ?? ''}${principal.team ? ` · ${principal.team}` : ''}`
              : `${principal.members ?? 0} members`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 24 }}>
          <StatTiny label="Assignments" v={derived.length} />
          <StatTiny label="Tables in scope" v={tableCount} />
          <StatTiny label="Proposals" v={totalProposals} />
          <StatTiny label="Pending" v={totalPending} accent="var(--db-lava-600)" />
        </div>
        <Btn variant="ghost" size="sm" onClick={() => setShowConfirmRemove(true)}
          style={{ color: 'var(--db-lava-600)', flexShrink: 0 }}>
          <Icon name="trash-2" size={13} /> Remove
        </Btn>
      </div>

      {/* Admin role toggle */}
      {isUser && (
        <div style={{
          padding: '12px 22px', borderBottom: '1px solid var(--db-gray-lines)',
          background: 'var(--db-oat-light)',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <Icon name="users" size={15} color="var(--db-navy-600)" />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12.5, color: 'var(--db-navy-800)', fontWeight: 500 }}>
              Admin role
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--db-gray-text)', marginTop: 1 }}>
              Admins can view all catalogs, apply approved tags, and switch into the admin view.
            </div>
          </div>
          <button
            onClick={() => toggleAdmin.mutate(!principal.isAdmin)}
            disabled={toggleAdmin.isPending}
            style={{
              position: 'relative', width: 38, height: 22, borderRadius: 999,
              background: principal.isAdmin ? 'var(--db-green-700)' : 'var(--db-navy-300)',
              border: 0, cursor: toggleAdmin.isPending ? 'wait' : 'pointer',
              transition: 'background var(--dur-fast)',
              opacity: toggleAdmin.isPending ? 0.7 : 1,
            }}
            aria-label="Toggle admin role"
          >
            <span style={{
              position: 'absolute', top: 2, left: principal.isAdmin ? 18 : 2,
              width: 18, height: 18, borderRadius: '50%', background: '#fff',
              transition: 'left var(--dur-fast) var(--ease-out)',
              boxShadow: '0 1px 3px rgba(0,0,0,0.18)',
            }} />
          </button>
        </div>
      )}

      {/* Body — assignments list */}
      <div style={{ flex: 1, overflow: 'auto', padding: 22 }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 12,
        }}>
          <h3 style={{
            fontSize: 13, fontWeight: 500, color: 'var(--db-navy-800)', margin: 0,
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            Assigned scopes
          </h3>
          <Btn variant="ghost" size="sm" onClick={onAddRequest}>
            <Icon name="plus" size={12} /> Add scope
          </Btn>
        </div>

        {error && (
          <div style={{
            fontSize: 12, color: 'var(--db-lava-600)', marginBottom: 10,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <Icon name="x" size={12} color="var(--db-lava-600)" />
            <span>{error}</span>
            <button
              onClick={onClearError}
              style={{
                background: 'transparent', border: 0, padding: 0, cursor: 'pointer',
                color: 'var(--db-lava-600)', fontSize: 11, marginLeft: 4,
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        {derived.length === 0 ? (
          <div style={{
            padding: 30, textAlign: 'center', background: 'var(--db-oat-light)',
            borderRadius: 8, border: '1px dashed var(--db-gray-lines)',
            color: 'var(--db-gray-text)', fontSize: 13,
          }}>
            No assignments yet. Click <strong>Add scope</strong> to make {principal.name} a steward on a catalog, schema, or table.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {derived.map(a => (
              <AssignmentRow key={a.id} assignment={a} onRemove={() => onRemove(a.id)} />
            ))}
          </div>
        )}
      </div>

      {showConfirmRemove && (
        <div
          onClick={() => setShowConfirmRemove(false)}
          onKeyDown={e => { if (e.key === 'Escape') setShowConfirmRemove(false) }}
          tabIndex={-1}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(11,32,38,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            style={{
              background: '#fff', borderRadius: 12, padding: 28, width: 400,
              boxShadow: 'var(--shadow-xl)', fontFamily: 'var(--font-sans)',
            }}
          >
            <h3 style={{ fontSize: 17, fontWeight: 500, margin: '0 0 8px', color: 'var(--db-navy-800)' }}>
              Remove {principal.name}?
            </h3>
            <p style={{ fontSize: 13, color: 'var(--db-gray-text)', margin: '0 0 22px', lineHeight: 1.5 }}>
              This will remove <strong>{principal.name}</strong> as a steward and delete all their scope assignments. This cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Btn variant="ghost" onClick={() => setShowConfirmRemove(false)}>Cancel</Btn>
              <Btn
                variant="primary"
                onClick={() => { setShowConfirmRemove(false); onRemovePrincipal() }}
                style={{ background: 'var(--db-lava-600)', borderColor: 'var(--db-lava-600)' }}
              >
                Remove
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatTiny({ label, v, accent }: { label: string; v: number; accent?: string }) {
  return (
    <div style={{ textAlign: 'right' }}>
      <div style={{
        fontSize: 10, color: 'var(--db-gray-text)', textTransform: 'uppercase',
        letterSpacing: '0.06em', fontWeight: 500,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 18, fontWeight: 500, color: accent ?? 'var(--db-navy-800)',
        letterSpacing: '-0.01em', lineHeight: 1.1, marginTop: 2,
      }}>
        {v}
      </div>
    </div>
  )
}

const SCOPE_STYLES: Record<AssignmentScope, { label: string; bg: string; fg: string; icon: string }> = {
  catalog: { label: 'Catalog', bg: '#143D4A', fg: '#fff', icon: 'db' },
  schema:  { label: 'Schema',  bg: '#1B5162', fg: '#fff', icon: 'columns' },
  table:   { label: 'Table',   bg: '#618794', fg: '#fff', icon: 'table' },
}

function AssignmentRow({
  assignment, onRemove,
}: {
  assignment: DerivedAssignment
  onRemove: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const sty = SCOPE_STYLES[assignment.scope]
  const scopePath =
    assignment.scope === 'catalog'
      ? assignment.catalog
      : assignment.scope === 'schema'
        ? `${assignment.catalog}.${assignment.schemaName ?? ''}`
        : `${assignment.catalog}.${assignment.schemaName ?? ''}.${assignment.tableName ?? ''}`

  return (
    <div style={{
      border: '1px solid var(--db-gray-lines)', borderRadius: 8,
      overflow: 'hidden', background: '#fff',
    }}>
      <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 6, background: sty.bg, color: sty.fg,
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <Icon name={sty.icon} size={15} color={sty.fg} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
            <span style={{
              fontSize: 10.5, fontWeight: 500, color: 'var(--db-gray-text)',
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>
              {sty.label} scope
            </span>
            {assignment.pending > 0 && (
              <Pill bg="#FFDB96" color="#7D5319" style={{ fontSize: 10 }}>
                {assignment.pending} pending
              </Pill>
            )}
          </div>
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 13,
            color: 'var(--db-navy-800)', fontWeight: 500,
          }}>
            {scopePath}
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--db-gray-text)', textAlign: 'right' }}>
          <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--db-navy-800)', fontWeight: 500 }}>
            {assignment.coveredTables.length} table{assignment.coveredTables.length === 1 ? '' : 's'}
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', marginTop: 2 }}>
            {assignment.proposalCount} proposals
          </div>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          title={expanded ? 'Collapse' : 'View covered tables'}
          style={{
            background: 'transparent', border: '1px solid var(--db-gray-lines)',
            padding: 6, borderRadius: 6, cursor: 'pointer',
            color: 'var(--db-gray-text)', display: 'flex',
          }}
        >
          <Icon name={expanded ? 'chevDown' : 'chev'} size={14} />
        </button>
        <button
          onClick={onRemove}
          title="Remove assignment"
          style={{
            background: 'transparent', border: '1px solid var(--db-gray-lines)',
            padding: 6, borderRadius: 6, cursor: 'pointer',
            color: 'var(--db-gray-text)', display: 'flex',
          }}
        >
          <Icon name="x" size={14} />
        </button>
      </div>
      {expanded && assignment.coveredTables.length > 0 && (
        <div style={{
          borderTop: '1px solid var(--db-gray-lines)', padding: 12,
          background: 'var(--db-oat-light)',
        }}>
          <div style={{
            fontSize: 10.5, color: 'var(--db-gray-text)', textTransform: 'uppercase',
            letterSpacing: '0.06em', fontWeight: 500, marginBottom: 8,
          }}>
            Covered tables
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {assignment.coveredTables.map(tk => {
              const [c, s, tt] = tk.split('.')
              return (
                <div
                  key={tk}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '6px 10px', background: '#fff', borderRadius: 4,
                    border: '1px solid var(--db-gray-lines)',
                  }}
                >
                  <Icon name="table" size={13} color="var(--db-navy-600)" />
                  <AssetPath catalog={c} schema={s} table={tt} size={12} />
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// New Assignment Dialog
// ────────────────────────────────────────────────────────────────────────────

function NewAssignmentDialog({
  principal, tables, onClose, onCreate,
}: {
  principal: Principal
  tables: TableSummary[]
  onClose: () => void
  onCreate: (payload: Omit<StewardAssignment, 'id'>) => void
}) {
  const catalogs = useMemo(
    () => [...new Set(tables.map(t => t.catalog))].sort(),
    [tables],
  )

  const [scope, setScope] = useState<AssignmentScope>('table')
  const [catalog, setCatalog] = useState<string>(catalogs[0] ?? '')
  const [schema, setSchema] = useState<string>('')
  const [tbl, setTbl] = useState<string>('')

  const schemas = useMemo(
    () => [...new Set(tables.filter(t => t.catalog === catalog).map(t => t.schema))].sort(),
    [tables, catalog],
  )

  const tableList = useMemo(
    () => [...new Set(tables.filter(t => t.catalog === catalog && t.schema === schema).map(t => t.table))].sort(),
    [tables, catalog, schema],
  )

  const isValid =
    !!catalog &&
    (scope === 'catalog' || !!schema) &&
    (scope !== 'table' || !!tbl)

  const dialogRef = useRef<HTMLDivElement>(null)
  useEffect(() => { dialogRef.current?.focus() }, [])

  const handleCreate = () => {
    if (!isValid) return
    const payload: Omit<StewardAssignment, 'id'> = {
      principal: principal.id,
      principalKind: principal.kind,
      scope,
      catalog,
    }
    if (scope !== 'catalog') payload.schemaName = schema
    if (scope === 'table') payload.tableName = tbl
    onCreate(payload)
  }

  return (
    <div
      onClick={onClose}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
      tabIndex={-1}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(11,32,38,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      }}
    >
      <div
        ref={dialogRef}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="New steward assignment"
        tabIndex={-1}
        style={{
          background: '#fff', borderRadius: 12, padding: 24, width: 540,
          boxShadow: 'var(--shadow-xl)',
          fontFamily: 'var(--font-sans)', outline: 'none',
        }}
      >
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 18,
        }}>
          <h3 style={{ fontSize: 18, fontWeight: 500, margin: 0, color: 'var(--db-navy-800)' }}>
            New steward assignment
          </h3>
          <button
            onClick={onClose}
            style={{
              background: 'transparent', border: 0, padding: 4, cursor: 'pointer',
              color: 'var(--db-gray-text)',
            }}
            aria-label="Close"
          >
            <Icon name="x" size={16} />
          </button>
        </div>

        {/* Assign to (read-only — pre-filled to selected principal) */}
        <DialogLabel>Assign to</DialogLabel>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px',
          border: '1px solid var(--db-gray-lines)', borderRadius: 6,
          background: 'var(--db-oat-light)', marginBottom: 16,
        }}>
          <Avatar initials={principal.initials} color={principal.accent} size={28} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--db-navy-800)' }}>
              {principal.name}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--db-gray-text)', marginTop: 1 }}>
              {principal.kind === 'user'
                ? (principal.email ?? '')
                : `Group · ${principal.members ?? 0} members`}
            </div>
          </div>
        </div>

        {/* Scope picker */}
        <DialogLabel>Scope</DialogLabel>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14,
        }}>
          {([
            { v: 'catalog' as const, l: 'Catalog', d: 'Every table in a catalog' },
            { v: 'schema'  as const, l: 'Schema',  d: 'Every table in a schema' },
            { v: 'table'   as const, l: 'Table',   d: 'A single table' },
          ]).map(opt => (
            <button
              key={opt.v}
              onClick={() => setScope(opt.v)}
              style={{
                padding: '10px 12px', textAlign: 'left',
                border: scope === opt.v
                  ? '1.5px solid var(--db-lava-600)'
                  : '1px solid var(--db-gray-lines)',
                borderRadius: 6,
                background: scope === opt.v ? 'var(--db-oat-light)' : '#fff',
                cursor: 'pointer', fontFamily: 'var(--font-sans)',
              }}
            >
              <div style={{
                fontSize: 12.5, fontWeight: 500, color: 'var(--db-navy-800)', marginBottom: 2,
              }}>
                {opt.l}
              </div>
              <div style={{ fontSize: 11, color: 'var(--db-gray-text)' }}>
                {opt.d}
              </div>
            </button>
          ))}
        </div>

        {/* Path selectors */}
        <DialogLabel>Catalog</DialogLabel>
        <SearchableSelect
          value={catalog}
          onChange={v => { setCatalog(v); setSchema(''); setTbl('') }}
          options={catalogs.map(c => ({ value: c, label: c }))}
          placeholder="No catalogs available"
        />

        {scope !== 'catalog' && (
          <>
            <DialogLabel style={{ marginTop: 12 }}>Schema</DialogLabel>
            <SearchableSelect
              value={schema}
              onChange={v => { setSchema(v); setTbl('') }}
              options={schemas.map(s => ({ value: s, label: s }))}
              placeholder="Choose a schema…"
            />
          </>
        )}

        {scope === 'table' && (
          <>
            <DialogLabel style={{ marginTop: 12 }}>Table</DialogLabel>
            <SearchableSelect
              value={tbl}
              onChange={setTbl}
              options={tableList.map(t => ({ value: t, label: t }))}
              placeholder="Choose a table…"
              disabled={!schema}
            />
          </>
        )}

        <div style={{
          display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 22,
        }}>
          <Btn variant="ghost" onClick={onClose}>Cancel</Btn>
          <Btn variant="primary" onClick={handleCreate} disabled={!isValid}>
            Create assignment
          </Btn>
        </div>
      </div>
    </div>
  )
}

function DialogLabel({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 500, color: 'var(--db-gray-text)',
      textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6,
      ...(style ?? {}),
    }}>
      {children}
    </div>
  )
}

