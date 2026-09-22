import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Icon, Pill, TagPill, Btn, AssetPath } from '../components'
import { api } from '../store/api'
import { useAppStore } from '../store/useAppStore'
import type { TableSummary } from '../store/types'

interface StewardInboxProps {
  onOpenTable: (tableKey: string) => void
}

export function StewardInbox({ onOpenTable }: StewardInboxProps) {
  const [showAll, setShowAll] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCatalog, setFilterCatalog] = useState('')
  const [filterSchema, setFilterSchema] = useState('')
  const currentUser = useAppStore(s => s.currentUser)

  const { data: allTables = [], isLoading } = useQuery({
    queryKey: ['tables'],
    queryFn: api.getTables,
  })

  const { data: myAssignments = [] } = useQuery({
    queryKey: ['assignments', currentUser?.id],
    queryFn: () => api.getAssignments(currentUser!.id),
    enabled: !!currentUser,
  })

  const myTables = allTables.filter(t =>
    myAssignments.some(a => {
      if (a.catalog !== t.catalog) return false
      if (a.scope === 'catalog') return true
      if (a.scope === 'schema') return a.schemaName === t.schema
      return a.schemaName === t.schema && a.tableName === t.table
    })
  )

  const catalogs = useMemo(() => [...new Set(myTables.map(t => t.catalog))].sort(), [myTables])
  const schemas = useMemo(() => {
    const src = filterCatalog ? myTables.filter(t => t.catalog === filterCatalog) : myTables
    return [...new Set(src.map(t => t.schema))].sort()
  }, [myTables, filterCatalog])

  const visible = useMemo(() => {
    let result = showAll ? myTables : myTables.filter(t => t.pending > 0)
    if (filterCatalog) result = result.filter(t => t.catalog === filterCatalog)
    if (filterSchema) result = result.filter(t => t.schema === filterSchema)
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      result = result.filter(t =>
        t.table.toLowerCase().includes(q) ||
        t.schema.toLowerCase().includes(q) ||
        t.catalog.toLowerCase().includes(q) ||
        t.proposals.some(p => p.column.toLowerCase().includes(q))
      )
    }
    return result
  }, [myTables, showAll, filterCatalog, filterSchema, searchQuery])

  const totalPending = myTables.reduce((s, t) => s + t.pending, 0)
  const totalProposals = myTables.reduce((s, t) => s + (t.proposalCount ?? t.proposals.length), 0)
  const allReviewed = myTables.length > 0 && totalPending === 0
  const hasFilters = searchQuery.trim() !== '' || filterCatalog !== '' || filterSchema !== ''

  return (
    <div style={{
      flex: 1, overflow: 'auto', background: 'var(--db-oat-light)', padding: '28px 32px 48px',
    }}>
      <div style={{ maxWidth: 1200 }}>
        <div style={{
          display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          marginBottom: 28, gap: 20, flexWrap: 'wrap',
        }}>
          <div>
            <div style={{
              fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
              letterSpacing: '0.08em', fontWeight: 500, marginBottom: 6,
            }}>
              My review queue
            </div>
            <h1 style={{
              fontSize: 30, fontWeight: 500, letterSpacing: '-0.018em',
              color: 'var(--db-navy-800)', margin: 0,
            }}>
              {totalPending > 0 ? (
                <>
                  {totalPending} column tags{' '}
                  <span style={{ color: 'var(--db-gray-text)', fontWeight: 400 }}>need your review</span>
                </>
              ) : (
                "You’re all caught up"
              )}
            </h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 0,
              background: 'var(--db-oat-medium)', borderRadius: 999, padding: 3,
            }}>
              {[
                { v: false, l: 'Pending only', n: totalPending },
                { v: true,  l: 'All tables',   n: myTables.length },
              ].map(opt => (
                <button
                  key={String(opt.v)}
                  onClick={() => setShowAll(opt.v)}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 7,
                    padding: '6px 14px', border: 0, borderRadius: 999, cursor: 'pointer',
                    background: showAll === opt.v ? '#fff' : 'transparent',
                    color: showAll === opt.v ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
                    fontFamily: 'var(--font-sans)', fontWeight: 500, fontSize: 12.5,
                    boxShadow: showAll === opt.v ? 'var(--shadow-xs)' : 'none',
                  }}
                >
                  {opt.l}
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 11,
                    color: showAll === opt.v ? 'var(--db-gray-text)' : 'var(--db-navy-400)',
                  }}>{opt.n}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Search & filter bar */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, flexWrap: 'wrap',
        }}>
          <div style={{ position: 'relative', flex: '1 1 220px', minWidth: 0 }}>
            <Icon
              name="search" size={14} color="var(--db-gray-text)"
              style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
            />
            <input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search tables or columns…"
              style={{
                width: '100%', boxSizing: 'border-box',
                paddingLeft: 32, paddingRight: searchQuery ? 28 : 10, paddingTop: 7, paddingBottom: 7,
                border: '1px solid var(--db-gray-lines)', borderRadius: 6,
                fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--db-navy-800)',
                background: '#fff', outline: 'none',
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer', padding: 2,
                  color: 'var(--db-gray-text)', lineHeight: 1,
                }}
              >
                ×
              </button>
            )}
          </div>
          <select
            value={filterCatalog}
            onChange={e => { setFilterCatalog(e.target.value); setFilterSchema('') }}
            style={{
              padding: '7px 10px', border: '1px solid var(--db-gray-lines)', borderRadius: 6,
              fontFamily: 'var(--font-sans)', fontSize: 13, color: filterCatalog ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
              background: '#fff', cursor: 'pointer', outline: 'none', flexShrink: 0,
            }}
          >
            <option value="">All catalogs</option>
            {catalogs.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select
            value={filterSchema}
            onChange={e => setFilterSchema(e.target.value)}
            disabled={schemas.length === 0}
            style={{
              padding: '7px 10px', border: '1px solid var(--db-gray-lines)', borderRadius: 6,
              fontFamily: 'var(--font-sans)', fontSize: 13, color: filterSchema ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
              background: '#fff', cursor: schemas.length > 0 ? 'pointer' : 'default', outline: 'none', flexShrink: 0,
            }}
          >
            <option value="">All schemas</option>
            {schemas.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          {hasFilters && (
            <button
              onClick={() => { setSearchQuery(''); setFilterCatalog(''); setFilterSchema('') }}
              style={{
                padding: '7px 12px', border: '1px solid var(--db-gray-lines)', borderRadius: 6,
                fontFamily: 'var(--font-sans)', fontSize: 12.5, color: 'var(--db-gray-text)',
                background: '#fff', cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap',
              }}
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Summary strip */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 28,
        }}>
          {[
            { l: 'Tables assigned',   v: myTables.length, col: 'var(--db-navy-800)' },
            { l: 'Pending decisions', v: totalPending,    col: 'var(--db-lava-600)' },
            { l: 'Total proposals',   v: totalProposals,  col: 'var(--db-navy-800)' },
          ].map((k) => (
            <div key={k.l} style={{
              background: '#fff', border: '1px solid var(--db-gray-lines)',
              borderRadius: 8, padding: '14px 18px',
            }}>
              <div style={{
                fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
                letterSpacing: '0.06em', fontWeight: 500,
              }}>{k.l}</div>
              <div style={{
                fontSize: 28, fontWeight: 500, color: k.col, marginTop: 6, letterSpacing: '-0.015em',
              }}>{k.v}</div>
            </div>
          ))}
        </div>

        {/* Section heading */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
          fontSize: 12, fontWeight: 500, color: 'var(--db-gray-text)',
          textTransform: 'uppercase', letterSpacing: '0.08em',
        }}>
          {showAll ? 'All my tables' : 'Tables to review'}
          {hasFilters && (
            <span style={{ fontWeight: 400, textTransform: 'none', color: 'var(--db-navy-400)', letterSpacing: 0 }}>
              — {visible.length} of {showAll ? myTables.length : myTables.filter(t => t.pending > 0).length}
            </span>
          )}
          <span style={{ flex: 1, height: 1, background: 'var(--db-gray-lines)' }} />
        </div>

        {visible.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {visible.map(t => (
              <TableCard key={t.key} t={t} onOpen={() => onOpenTable(t.key)} />
            ))}
          </div>
        ) : (
          <div style={{
            background: '#fff', border: '1px dashed var(--db-gray-lines)', borderRadius: 8,
            padding: 40, textAlign: 'center', color: 'var(--db-gray-text)',
          }}>
            {isLoading ? (
              <div style={{ fontSize: 13 }}>Loading…</div>
            ) : hasFilters ? (
              <div style={{ fontSize: 13 }}>No tables match your search or filters.</div>
            ) : allReviewed ? (
              <>
                <Icon name="check" size={24} color="var(--db-green-700)" stroke={2.2} />
                <div style={{ marginTop: 10, fontSize: 14, color: 'var(--db-navy-800)', fontWeight: 500 }}>
                  Every assigned table is reviewed.
                </div>
                <div style={{ fontSize: 12.5, marginTop: 4 }}>
                  Switch to "All tables" to see reviewed ones too.
                </div>
              </>
            ) : (
              <div style={{ fontSize: 13 }}>No assigned tables.</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function TableCard({ t, onOpen }: { t: TableSummary; onOpen: () => void }) {
  const tags = Array.from(new Set(t.proposals.map(p => p.classTag)))
  return (
    <div
      onClick={onOpen}
      style={{
        background: '#fff', border: '1px solid var(--db-gray-lines)',
        borderRadius: 10, padding: '18px 22px',
        display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, alignItems: 'center',
        cursor: 'pointer', transition: 'all var(--dur-base) var(--ease-out)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--db-navy-400)'
        e.currentTarget.style.boxShadow = 'var(--shadow-md)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--db-gray-lines)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
          <Icon name="table" size={16} color="var(--db-navy-600)" />
          <AssetPath catalog={t.catalog} schema={t.schema} table={t.table} size={14} />
          {t.pending > 0 ? (
            <Pill bg="#FFDB96" color="#7D5319" dot>{t.pending} pending</Pill>
          ) : (
            <Pill bg="#9ED6C4" color="#095A35" dot>Reviewed</Pill>
          )}
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 16, marginTop: 10,
          fontSize: 12, color: 'var(--db-gray-text)', flexWrap: 'wrap',
        }}>
          <span>{t.totalCols} columns scanned</span>
          <span style={{ width: 3, height: 3, borderRadius: '50%', background: 'var(--db-navy-300)' }} />
          <span>{t.proposalCount} tag proposals</span>
          <span style={{ width: 3, height: 3, borderRadius: '50%', background: 'var(--db-navy-300)' }} />
          <span>Last scan {t.lastScan}</span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
          {tags.map(tag => <TagPill key={tag} tag={tag} size="sm" />)}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Btn variant="primary" size="md">
          Review <Icon name="arrow" size={13} color="#fff" />
        </Btn>
      </div>
    </div>
  )
}
