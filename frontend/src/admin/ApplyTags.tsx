import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Icon, Pill, TagPill, StatusPill, Btn, AssetPath, FilterChip } from '../components'
import { api } from '../store/api'
import type { Proposal, ApplyTagsResult } from '../store/types'

export function ApplyTags() {
  const queryClient = useQueryClient()

  const { data: proposals = [], isLoading, isError } = useQuery({
    queryKey: ['proposals'],
    queryFn: () => api.getProposals(),
  })

  const [catalogFilter, setCatalogFilter] = useState('')
  const [schemaFilter, setSchemaFilter] = useState('')
  const [tableFilter, setTableFilter] = useState('')
  const [showApplied, setShowApplied] = useState(false)
  const [applyResult, setApplyResult] = useState<string | null>(null)
  const [applyHasErrors, setApplyHasErrors] = useState(false)

  // Cascading: changing catalog resets schema + table; changing schema resets table
  useEffect(() => {
    setSchemaFilter('')
    setTableFilter('')
  }, [catalogFilter])

  useEffect(() => {
    setTableFilter('')
  }, [schemaFilter])

  // Universe: approved, modified, and applied proposals
  const allApproved = useMemo<Proposal[]>(
    () => proposals.filter(p => p.status === 'approved' || p.status === 'modified' || p.status === 'applied'),
    [proposals],
  )

  // Cascading filter options
  const catalogs = useMemo(
    () => [...new Set(allApproved.map(p => p.catalog))],
    [allApproved],
  )

  const schemas = useMemo(() => {
    const scope = catalogFilter
      ? allApproved.filter(p => p.catalog === catalogFilter)
      : allApproved
    return [...new Set(scope.map(p => p.schemaName))]
  }, [allApproved, catalogFilter])

  const tables = useMemo(() => {
    const scope = allApproved.filter(p =>
      (!catalogFilter || p.catalog === catalogFilter) &&
      (!schemaFilter || p.schemaName === schemaFilter),
    )
    return [...new Set(scope.map(p => p.table))]
  }, [allApproved, catalogFilter, schemaFilter])

  // Currently in-scope proposals (scope filters only, before applied toggle)
  const scopeFiltered = useMemo(
    () =>
      allApproved.filter(p => {
        if (catalogFilter && p.catalog !== catalogFilter) return false
        if (schemaFilter && p.schemaName !== schemaFilter) return false
        if (tableFilter && p.table !== tableFilter) return false
        return true
      }),
    [allApproved, catalogFilter, schemaFilter, tableFilter],
  )

  const pending = useMemo(() => scopeFiltered.filter(p => p.status !== 'applied'), [scopeFiltered])
  const alreadyApplied = useMemo(() => scopeFiltered.filter(p => p.status === 'applied'), [scopeFiltered])

  // What's actually shown in the list
  const filtered = useMemo(
    () => showApplied ? scopeFiltered : pending,
    [scopeFiltered, pending, showApplied],
  )

  // Group filtered proposals by table
  const byTable = useMemo(() => {
    const groups: Record<string, Proposal[]> = {}
    for (const p of filtered) {
      if (!groups[p.tableKey]) groups[p.tableKey] = []
      groups[p.tableKey].push(p)
    }
    return groups
  }, [filtered])

  const hasScopeFilter = !!(catalogFilter || schemaFilter || tableFilter)

  const applyMutation = useMutation({
    mutationFn: ({ columnKeys, classTags }: { columnKeys: string[]; classTags: Record<string, string> }) =>
      api.applyTags(columnKeys, classTags),
    onSuccess: (r: ApplyTagsResult) => {
      const msg = `Applied ${r.applied} · Skipped ${r.skipped}${r.errors.length > 0 ? ` · ${r.errors.length} errors` : ''}`
      setApplyResult(msg)
      setApplyHasErrors(r.errors.length > 0)
      queryClient.invalidateQueries({ queryKey: ['proposals'] })
    },
    onError: () => {
      setApplyResult('Failed to apply tags. Please try again.')
      setApplyHasErrors(true)
    },
  })

  const onApply = () => {
    setApplyResult(null)
    setApplyHasErrors(false)
    const toApply = pending
    const classTags: Record<string, string> = {}
    for (const p of toApply) classTags[p.key] = p.classTag
    applyMutation.mutate({ columnKeys: toApply.map(p => p.key), classTags })
  }

  const clearScope = () => {
    setCatalogFilter('')
    setSchemaFilter('')
    setTableFilter('')
  }

  if (isLoading) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-sans)', color: 'var(--db-gray-text)',
      }}>
        Loading…
      </div>
    )
  }

  if (isError) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-sans)', color: 'var(--db-lava-600)',
      }}>
        Failed to load proposals. Please refresh.
      </div>
    )
  }

  return (
    <div style={{
      flex: 1, overflow: 'auto', background: 'var(--db-oat-light)',
      padding: '28px 32px 48px',
    }}>
      <div style={{ maxWidth: 1100 }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          marginBottom: 24, gap: 16, flexWrap: 'wrap',
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{
              fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
              letterSpacing: '0.08em', fontWeight: 500, marginBottom: 6,
            }}>
              Apply tags
            </div>
            <h1 style={{
              fontSize: 26, fontWeight: 500, letterSpacing: '-0.018em',
              color: 'var(--db-navy-800)', margin: 0,
            }}>
              Apply approved tags
            </h1>
            <div style={{ fontSize: 13, color: 'var(--db-gray-text)', marginTop: 6 }}>
              {pending.length > 0
                ? `${pending.length} tag${pending.length === 1 ? '' : 's'} ready to apply${alreadyApplied.length > 0 ? ` · ${alreadyApplied.length} already applied` : ''}.`
                : alreadyApplied.length > 0
                  ? `All tags applied · ${alreadyApplied.length} in scope.`
                  : 'No approved tags in the selected scope.'}
            </div>
          </div>
          <Btn
            variant="primary"
            size="lg"
            disabled={pending.length === 0 || applyMutation.isPending}
            onClick={onApply}
          >
            <Icon name="upload" size={14} color="#fff" />
            {applyMutation.isPending ? 'Applying…' : `Apply ${pending.length} tag${pending.length === 1 ? '' : 's'}`}
          </Btn>
        </div>

        {/* Apply result banner */}
        {applyResult && (
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)',
            borderLeft: `3px solid ${applyHasErrors ? 'var(--db-lava-600)' : 'var(--db-green-700)'}`,
            borderRadius: 6,
            padding: '10px 14px', marginBottom: 14,
            fontSize: 13, color: 'var(--db-navy-800)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            {applyHasErrors
              ? <Icon name="x" size={14} color="var(--db-lava-600)" />
              : <Icon name="check" size={14} color="var(--db-green-700)" />}
            <span style={{ flex: 1 }}>{applyResult}</span>
            <button
              onClick={() => setApplyResult(null)}
              style={{
                background: 'transparent', border: 0, padding: 2, cursor: 'pointer',
                color: 'var(--db-gray-text)', display: 'flex',
              }}
              aria-label="Dismiss"
            >
              <Icon name="x" size={14} />
            </button>
          </div>
        )}

        {/* Scope filter bar */}
        <div style={{
          background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 8,
          padding: '12px 16px', marginBottom: 16,
        }}>
          {/* Row 1: scope chips */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 11, fontWeight: 500, color: 'var(--db-gray-text)',
              textTransform: 'uppercase', letterSpacing: '0.08em',
            }}>
              Scope
            </span>
            <FilterChip
              label="Catalog"
              value={catalogFilter}
              onChange={setCatalogFilter}
              options={[
                { value: '', label: 'All catalogs' },
                ...catalogs.map(c => ({ value: c, label: c })),
              ]}
            />
            <FilterChip
              label="Schema"
              value={schemaFilter}
              onChange={setSchemaFilter}
              options={[
                { value: '', label: 'All schemas' },
                ...schemas.map(s => ({ value: s, label: s })),
              ]}
            />
            <FilterChip
              label="Table"
              value={tableFilter}
              onChange={setTableFilter}
              options={[
                { value: '', label: 'All tables' },
                ...tables.map(t => ({ value: t, label: t })),
              ]}
            />
            {hasScopeFilter && (
              <button
                onClick={clearScope}
                style={{
                  background: 'transparent', border: 0, color: 'var(--db-lava-700)',
                  fontSize: 12, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Clear scope
              </button>
            )}
          </div>
          {/* Row 2: show applied toggle + stats */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10 }}>
            <button
              onClick={() => setShowApplied(v => !v)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                background: showApplied ? 'var(--db-oat-medium)' : 'transparent',
                border: '1px solid var(--db-gray-lines)', borderRadius: 999,
                padding: '4px 12px', cursor: 'pointer', fontSize: 12,
                color: showApplied ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
                fontFamily: 'var(--font-sans)', fontWeight: showApplied ? 500 : 400,
              }}
            >
              <Icon name="check" size={12} color={showApplied ? 'var(--db-green-700)' : 'var(--db-gray-text)'} stroke={2.5} />
              Show applied
            </button>
            <span style={{ fontSize: 12, color: 'var(--db-gray-text)' }}>
              {pending.length} pending · {alreadyApplied.length} applied · {allApproved.length} total
            </span>
          </div>
        </div>

        {/* Groups */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {Object.entries(byTable).map(([tk, props]) => {
            const tablePending = props.filter(p => p.status !== 'applied').length
            const tableApplied = props.filter(p => p.status === 'applied').length
            return (
              <div
                key={tk}
                style={{
                  background: '#fff', border: '1px solid var(--db-gray-lines)',
                  borderRadius: 8, overflow: 'hidden',
                }}
              >
                <div style={{
                  padding: '12px 18px', background: 'var(--db-oat-light)',
                  borderBottom: '1px solid var(--db-gray-lines)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Icon name="table" size={15} color="var(--db-navy-600)" />
                    <AssetPath
                      catalog={props[0].catalog}
                      schema={props[0].schemaName}
                      table={props[0].table}
                      size={13}
                    />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {tableApplied > 0 && (
                      <Pill bg="#E8F5F0" color="#095A35">
                        {tableApplied} applied
                      </Pill>
                    )}
                    {tablePending > 0 && (
                      <Pill bg="#9ED6C4" color="#095A35">
                        {tablePending} ready
                      </Pill>
                    )}
                  </div>
                </div>
                <div style={{ padding: 4 }}>
                  {props.map(p => (
                    <div
                      key={p.key}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '180px 1fr auto auto',
                        alignItems: 'center',
                        padding: '8px 14px', borderRadius: 4,
                        opacity: p.status === 'applied' ? 0.6 : 1,
                      }}
                    >
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 12.5,
                        color: 'var(--db-navy-800)', fontWeight: 500,
                      }}>
                        {p.column}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {p.modifiedTag && <TagPill tag={p.classTag} size="sm" />}
                        {p.modifiedTag && (
                          <span style={{ color: 'var(--db-gray-text)', fontSize: 12 }}>→</span>
                        )}
                        <TagPill tag={p.modifiedTag || p.classTag} size="sm" />
                      </div>
                      <StatusPill status={p.status} />
                      {p.status === 'applied'
                        ? <Icon name="check" size={13} color="var(--db-green-700)" />
                        : <span style={{ width: 13 }} />}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
          {filtered.length === 0 && (
            <div style={{
              background: '#fff', border: '1px dashed var(--db-gray-lines)',
              borderRadius: 8, padding: 40, textAlign: 'center',
              color: 'var(--db-gray-text)', fontSize: 13,
            }}>
              {showApplied ? 'No approved or applied tags in the selected scope.' : 'No pending tags to apply in the selected scope.'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
