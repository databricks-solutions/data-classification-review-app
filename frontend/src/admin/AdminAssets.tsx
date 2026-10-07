import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  Icon, Btn, Avatar, TagPill, StatusPill, ConfidencePill, FilterChip,
} from '../components'
import { api } from '../store/api'
import { useDebounced } from '../store/useDebounced'
import type { Principal, ProposalQuery } from '../store/types'

const GRID_COLUMNS = '0.9fr 1.1fr 1.3fr 1.1fr 1.1fr 80px 1.1fr 110px 90px'

export function AdminAssets() {
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [catalogFilter, setCatalogFilter] = useState('')
  const [schemaFilter, setSchemaFilter] = useState('')
  const [tagFilter, setTagFilter] = useState('')
  const [stewardFilter, setStewardFilter] = useState('')
  const [confidenceFilter, setConfidenceFilter] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const search = useDebounced(searchText.trim())

  // Cascade: reset schema when catalog changes
  useEffect(() => { setSchemaFilter('') }, [catalogFilter])

  // Reset to first page whenever filters or page size change
  useEffect(() => { setPage(1) }, [
    search, statusFilter, catalogFilter, schemaFilter,
    tagFilter, stewardFilter, confidenceFilter, pageSize,
  ])

  const query: ProposalQuery = {
    search: search || undefined,
    status: statusFilter || undefined,
    catalog: catalogFilter || undefined,
    schema: schemaFilter || undefined,
    tag: tagFilter || undefined,
    steward: stewardFilter || undefined,
    confidence: confidenceFilter || undefined,
    page, pageSize,
  }
  const { data: pageData, isLoading, isError, error } = useQuery({
    queryKey: ['proposals', 'page', query],
    queryFn: () => api.listProposals(query),
    placeholderData: keepPreviousData,
  })
  const { data: facets } = useQuery({
    queryKey: ['proposals', 'facets', catalogFilter, ''],
    queryFn: () => api.getProposalFacets({ catalog: catalogFilter || undefined }),
    placeholderData: keepPreviousData,
  })
  const { data: stats } = useQuery({
    queryKey: ['proposals', 'stats', ''],
    queryFn: () => api.getOverviewStats(),
  })
  const { data: stewards = [] } = useQuery<Principal[]>({
    queryKey: ['stewards'],
    queryFn: api.getStewards,
  })

  const catalogs = facets?.catalogs ?? []
  const schemas = facets?.schemas ?? []
  const tagOpts = facets?.tags ?? []
  const stewardOpts = facets?.stewards ?? []

  const stewardLookup = useMemo(() => {
    const m = new Map<string, Principal>()
    for (const s of stewards) m.set(s.id, s)
    return m
  }, [stewards])

  const rows = pageData?.items ?? []
  const filteredTotal = pageData?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(filteredTotal / pageSize))

  if (isLoading) return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-sans)', color: 'var(--db-gray-text)' }}>Loading…</div>
  if (isError) {
    const is503 = (error as any)?.status === 503
    if (is503) return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, fontFamily: 'var(--font-sans)' }}>
        <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--db-navy-800)' }}>Classification sync pending</div>
        <div style={{ fontSize: 13, color: 'var(--db-gray-text)', maxWidth: 360, textAlign: 'center' }}>No synced data yet. Go to the Overview tab and click Refresh to trigger the first sync.</div>
      </div>
    )
    return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-sans)', color: 'var(--db-lava-600)' }}>Failed to load data. Please refresh.</div>
  }

  return (
    <div style={{
      flex: 1, overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      background: 'var(--db-oat-light)',
    }}>
      {/* Header band */}
      <div style={{ padding: '24px 32px 16px' }}>
        <div style={{
          display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          marginBottom: 20, gap: 16, flexWrap: 'wrap',
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
              All classification proposals
            </h1>
            <div style={{ fontSize: 13, color: 'var(--db-gray-text)', marginTop: 6 }}>
              {filteredTotal} of {stats?.total ?? filteredTotal} columns shown
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="ghost" size="sm">
              <Icon name="download" size={13} /> Export
            </Btn>
          </div>
        </div>

        {/* Filter bar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ position: 'relative', maxWidth: 420 }}>
            <Icon
              name="search" size={14} color="var(--db-gray-text)"
              style={{
                position: 'absolute', left: 10, top: '50%',
                transform: 'translateY(-50%)',
              }}
            />
            <input
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              placeholder="Search columns, tables, tags…"
              style={{
                width: '100%', padding: '8px 12px 8px 32px', background: '#fff',
                border: '1px solid var(--db-gray-lines)', borderRadius: 6,
                fontSize: 13, fontFamily: 'var(--font-sans)', outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <FilterChip
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: '', label: 'All' },
                { value: 'pending', label: 'Pending' },
                { value: 'approved', label: 'Approved' },
                { value: 'modified', label: 'Modified' },
                { value: 'rejected', label: 'Rejected' },
              ]}
            />
            <FilterChip
              label="Catalog"
              value={catalogFilter}
              onChange={setCatalogFilter}
              options={[
                { value: '', label: 'All' },
                ...catalogs.map(c => ({ value: c, label: c })),
              ]}
            />
            <FilterChip
              label="Schema"
              value={schemaFilter}
              onChange={setSchemaFilter}
              options={[
                { value: '', label: 'All' },
                ...schemas.map(s => ({ value: s, label: s })),
              ]}
            />
            <FilterChip
              label="Tag"
              value={tagFilter}
              onChange={setTagFilter}
              options={[
                { value: '', label: 'All' },
                ...tagOpts.map(t => ({ value: t, label: t })),
              ]}
            />
            <FilterChip
              label="Steward"
              value={stewardFilter}
              onChange={setStewardFilter}
              options={[
                { value: '', label: 'All' },
                ...stewardOpts.map(o => ({
                  value: o,
                  label: stewardLookup.get(o)?.name ?? o,
                })),
              ]}
            />
            <FilterChip
              label="Confidence"
              value={confidenceFilter}
              onChange={setConfidenceFilter}
              options={[
                { value: '', label: 'All' },
                { value: 'HIGH', label: 'High' },
                { value: 'LOW', label: 'Low' },
                { value: 'NONE', label: 'No confidence' },
              ]}
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 32px' }}>
        {filteredTotal === 0 ? (
          <div style={{
            background: '#fff', border: '1px dashed var(--db-gray-lines)',
            borderRadius: 8, padding: 40, textAlign: 'center',
            color: 'var(--db-gray-text)', fontSize: 13,
          }}>
            No proposals match the current filters.
          </div>
        ) : (
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)',
            borderRadius: 8, overflow: 'hidden',
          }}>
            {/* Header row */}
            <div style={{
              display: 'grid', gridTemplateColumns: GRID_COLUMNS,
              padding: '10px 16px', background: 'var(--db-oat-medium)',
              borderBottom: '1px solid var(--db-gray-lines)',
              fontSize: 10.5, fontWeight: 500, color: 'var(--db-gray-text)',
              textTransform: 'uppercase', letterSpacing: '0.06em', gap: 10,
            }}>
              <div>Catalog</div>
              <div>Schema</div>
              <div>Table</div>
              <div>Column</div>
              <div>Proposed tag</div>
              <div>Conf.</div>
              <div>Steward</div>
              <div>Status</div>
              <div>Decided</div>
            </div>
            {rows.map(p => {
              const s = stewardLookup.get(p.owner)
              const decided = p.decidedAt ? p.decidedAt.slice(0, 10) : '—'
              return (
                <div key={p.key} style={{
                  display: 'grid', gridTemplateColumns: GRID_COLUMNS,
                  alignItems: 'center', padding: '11px 16px',
                  borderTop: '1px solid var(--db-gray-lines)', gap: 10,
                }}>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12.5,
                    color: 'var(--db-gray-text)', overflow: 'hidden',
                    textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }} title={p.catalog}>
                    {p.catalog}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12.5,
                    color: 'var(--db-gray-text)', overflow: 'hidden',
                    textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }} title={p.schemaName}>
                    {p.schemaName}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12.5,
                    color: 'var(--db-navy-800)', fontWeight: 500,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }} title={p.table}>
                    {p.table}
                  </span>
                  <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 12.5,
                    color: 'var(--db-navy-800)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }} title={p.column}>
                    {p.column}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <TagPill tag={p.modifiedTag || p.classTag} size="sm" />
                  </div>
                  <div>
                    <ConfidencePill level={p.confidence} />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                    {s ? (
                      <>
                        <Avatar initials={s.initials} color={s.accent} size={22} fontSize={9.5} />
                        <span style={{
                          fontSize: 12, color: 'var(--db-navy-800)',
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                        }}>
                          {s.name}
                        </span>
                      </>
                    ) : (
                      <span style={{ fontSize: 12, color: 'var(--db-gray-text)' }}>{p.owner}</span>
                    )}
                  </div>
                  <div>
                    <StatusPill status={p.status} />
                  </div>
                  <span style={{
                    fontSize: 11, color: 'var(--db-gray-text)',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    {decided}
                  </span>
                </div>
              )
            })}
          </div>
        )}

        {/* Pagination bar */}
        {filteredTotal > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 0', gap: 12, flexWrap: 'wrap',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: 'var(--db-gray-text)', fontFamily: 'var(--font-sans)' }}>
                Rows per page:
              </span>
              <select
                value={pageSize}
                onChange={e => setPageSize(Number(e.target.value))}
                style={{
                  border: '1px solid var(--db-gray-lines)', borderRadius: 6,
                  padding: '4px 8px', fontSize: 12, fontFamily: 'var(--font-sans)',
                  background: '#fff', color: 'var(--db-navy-800)', cursor: 'pointer', outline: 'none',
                }}
              >
                {[25, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 12, color: 'var(--db-gray-text)', fontFamily: 'var(--font-sans)' }}>
                {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, filteredTotal)} of {filteredTotal}
              </span>
              <Btn variant="ghost" size="sm" onClick={() => setPage(p => p - 1)} disabled={page === 1} title="Previous page">
                <Icon name="arrowLeft" size={13} />
              </Btn>
              <Btn variant="ghost" size="sm" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages} title="Next page">
                <Icon name="arrow" size={13} />
              </Btn>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
