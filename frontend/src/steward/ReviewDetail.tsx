import { useState, useMemo } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { Icon, TagPill, ConfidencePill, Btn, AssetPath, Spinner, SamplesStatus } from '../components'
import { api } from '../store/api'
import { useAppStore } from '../store/useAppStore'
import {
  ALL_TAGS,
  type Proposal,
  type DecisionPatch,
  type DecisionStatus,
  type TableSamplesResult,
} from '../store/types'
import { ProposeColumnTagsSection } from './ProposeColumnTagsSection'

interface ReviewDetailProps {
  tableKey: string
  onBack: () => void
}

interface EffectiveDecision {
  status: DecisionStatus
  modifiedTag: string | null
  comment: string | null
}

export function ReviewDetail({ tableKey, onBack }: ReviewDetailProps) {
  const queryClient = useQueryClient()
  const localDecisions = useAppStore(s => s.localDecisions)
  const userProposed = useAppStore(s => s.userProposed)
  const applyLocalDecision = useAppStore(s => s.applyLocalDecision)
  const undoLocalDecision = useAppStore(s => s.undoLocalDecision)
  const clearLocalState = useAppStore(s => s.clearLocalState)

  const { data: tables = [] } = useQuery({
    queryKey: ['tables'],
    queryFn: api.getTables,
  })
  const table = tables.find(t => t.key === tableKey)

  const [catalog, schema, tableName] = tableKey.split('.')

  const { data: columnsData, isFetching: columnsLoading } = useQuery({
    queryKey: ['columns', tableKey],
    queryFn: () => api.getColumns(catalog, schema, tableName),
    enabled: Boolean(catalog && schema && tableName),
  })
  const columns = columnsData?.columns ?? []

  const {
    data: samplesData,
    isFetching: samplesLoading,
    refetch: fetchSamples,
  } = useQuery({
    queryKey: ['tableSamples', tableKey],
    queryFn: () => api.getTableSamples(catalog, schema, tableName, columns.map(c => c.column)),
    enabled: false,
  })

  const proposals: Proposal[] = useMemo(() => {
    if (!table) return []
    return table.proposals
  }, [table])

  const [submitError, setSubmitError] = useState<string | null>(null)

  const submitMutation = useMutation({
    mutationFn: async (patches: DecisionPatch[]) => api.postDecisions(patches),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tables'] })
      queryClient.invalidateQueries({ queryKey: ['proposals'] })
      clearLocalState()
      setSubmitError(null)
    },
    onError: (err: Error) => {
      setSubmitError(err.message ?? 'Failed to submit decisions')
    },
  })

  if (!table) {
    return (
      <div style={{
        flex: 1, overflow: 'auto', background: 'var(--db-oat-light)',
        padding: '48px 32px', display: 'flex', justifyContent: 'center',
      }}>
        <div style={{
          background: '#fff', border: '1px solid var(--db-gray-lines)',
          borderRadius: 8, padding: 24, color: 'var(--db-gray-text)', fontSize: 13,
        }}>
          Loading table…
        </div>
      </div>
    )
  }

  const effectiveFor = (p: Proposal): EffectiveDecision => {
    const local = localDecisions[p.key]
    if (local) {
      return {
        status: local.status,
        modifiedTag: local.modifiedTag ?? null,
        comment: local.comment ?? null,
      }
    }
    return {
      status: p.status,
      modifiedTag: p.modifiedTag,
      comment: p.comment,
    }
  }

  const decidedCount = proposals.filter(p => effectiveFor(p).status !== 'pending').length
  const total = proposals.length
  const pct = total > 0 ? Math.round((decidedCount / total) * 100) : 0

  const onDecision = (p: Proposal, patch: Partial<DecisionPatch>) => {
    const current = effectiveFor(p)
    const nextStatus = (patch.status ?? current.status) as DecisionStatus
    if (nextStatus === 'pending') {
      undoLocalDecision(p.key)
      return
    }
    applyLocalDecision(p.key, {
      status: nextStatus,
      modifiedTag: patch.modifiedTag !== undefined ? patch.modifiedTag : current.modifiedTag,
      comment: patch.comment !== undefined ? patch.comment : current.comment,
    })
  }

  const onSubmit = () => {
    const patches: DecisionPatch[] = []
    // Existing scanner proposals: any local decision becomes a patch
    for (const p of proposals) {
      const local = localDecisions[p.key]
      if (!local) continue
      // User-added proposals have a synthetic key "{column_key}:{tag}"; extract real column_key
      const columnKey = p.userAdded ? p.key.substring(0, p.key.lastIndexOf(':')) : p.key
      patches.push({
        columnKey,
        status: local.status,
        // For user-added proposals, preserve the original tag as modifiedTag so the backend
        // updates the correct (user_added=true) decision row
        modifiedTag: p.userAdded ? p.classTag : (local.modifiedTag ?? null),
        comment: local.comment ?? null,
        classTag: p.classTag,
        userAdded: p.userAdded ? true : undefined,
      })
    }
    // User-proposed tags become approved patches keyed by column.tag
    for (const [colKey, tags] of Object.entries(userProposed)) {
      // Only submit user-proposed for columns in this table
      if (!colKey.startsWith(tableKey + '.')) continue
      for (const tag of tags) {
        patches.push({
          columnKey: colKey,
          status: 'approved',
          modifiedTag: tag,
          comment: null,
          userAdded: true,
        })
      }
    }
    if (patches.length === 0) return
    submitMutation.mutate(patches)
  }

  const stewardOwner = table.owner

  return (
    <div style={{ flex: 1, overflow: 'auto', background: 'var(--db-oat-light)' }}>
      {/* Header band */}
      <div style={{
        background: '#fff', borderBottom: '1px solid var(--db-gray-lines)',
        padding: '20px 32px',
      }}>
        <button
          onClick={onBack}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent',
            border: 0, padding: 0, cursor: 'pointer', color: 'var(--db-gray-text)',
            fontSize: 12, fontFamily: 'var(--font-sans)', fontWeight: 500, marginBottom: 10,
          }}
        >
          <Icon name="arrowLeft" size={13} /> Back to queue
        </button>
        <div style={{
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
          gap: 24, flexWrap: 'wrap',
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, flexWrap: 'wrap',
            }}>
              <Icon name="table" size={20} color="var(--db-navy-600)" />
              <AssetPath catalog={table.catalog} schema={table.schema} table={table.table} size={20} />
            </div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 14, fontSize: 12.5,
              color: 'var(--db-gray-text)', flexWrap: 'wrap',
            }}>
              <span>{table.totalCols} columns · {table.proposalCount} proposals</span>
              <span style={{ width: 3, height: 3, borderRadius: '50%', background: 'var(--db-navy-300)' }} />
              <span>Last scan {table.lastScan}</span>
              <span style={{ width: 3, height: 3, borderRadius: '50%', background: 'var(--db-navy-300)' }} />
              <span>Steward <span style={{ color: 'var(--db-navy-800)', fontWeight: 500 }}>{stewardOwner}</span></span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
            <div style={{ minWidth: 200 }}>
              <div style={{
                display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4,
              }}>
                <span style={{ color: 'var(--db-gray-text)' }}>Review progress</span>
                <span style={{
                  fontFamily: 'var(--font-mono)', color: 'var(--db-navy-800)', fontWeight: 500,
                }}>{decidedCount} / {total}</span>
              </div>
              <div style={{ height: 6, background: 'var(--db-oat-medium)', borderRadius: 3 }}>
                <div style={{
                  width: `${pct}%`, height: '100%', background: 'var(--db-green-700)',
                  borderRadius: 3, transition: 'width 320ms var(--ease-out)',
                }} />
              </div>
            </div>
            <Btn variant="ghost" size="sm">
              <Icon name="download" size={13} /> Export
            </Btn>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
              <Btn
                variant="secondary" size="sm"
                onClick={onSubmit}
                disabled={
                  submitMutation.isPending ||
                  (Object.keys(localDecisions).length === 0 && Object.keys(userProposed).length === 0)
                }
              >
                {submitMutation.isPending ? 'Submitting…' : 'Submit decisions'}
              </Btn>
              {submitError && (
                <span style={{ fontSize: 11, color: 'var(--db-lava-700)' }}>{submitError}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '24px 32px 48px' }}>
        {columnsData && (
          <div style={{ marginBottom: 16 }}>
            <div style={{
              fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
              letterSpacing: '0.06em', fontWeight: 500, marginBottom: 6,
            }}>Table description</div>
            {columnsData.metadataDenied ? (
              <div style={{ fontSize: 12.5, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
                Ask to admins to grant BROWSE permission to allow you to see object metadata.
              </div>
            ) : columnsData.tableDescription ? (
              <div style={{ fontSize: 13, color: 'var(--db-navy-800)', lineHeight: 1.5 }}>
                {columnsData.tableDescription}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
                No description available
              </div>
            )}
          </div>
        )}

        <div style={{
          marginBottom: 14, display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', gap: 12, flexWrap: 'wrap',
        }}>
          <h3 style={{
            fontSize: 16, fontWeight: 500, color: 'var(--db-navy-800)',
            margin: 0, letterSpacing: '-0.005em',
          }}>Proposals to review</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Btn
              variant="ghost" size="sm"
              onClick={() => fetchSamples()}
              disabled={columnsLoading || columns.length === 0 || samplesLoading}
            >
              <Icon name="eye" size={13} /> {samplesLoading ? 'Fetching samples…' : 'Get samples'}
            </Btn>
            {samplesLoading && <Spinner size={13} />}
            {samplesData?.denied && (
              <span style={{ fontSize: 12, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
                You don't have permission to see samples for this table.
              </span>
            )}
          </div>
        </div>

        <ProposalsTable
          proposals={proposals}
          effectiveFor={effectiveFor}
          onDecision={onDecision}
          samplesData={samplesData}
          samplesLoading={samplesLoading}
        />

        <ProposeColumnTagsSection
          columns={columns}
          columnsLoading={columnsLoading}
          samplesData={samplesData}
          samplesLoading={samplesLoading}
          tableTags={columnsData?.tableTags ?? []}
          tableTagsDenied={columnsData?.tableTagsDenied ?? false}
          metadataDenied={columnsData?.metadataDenied ?? false}
          columnTagsDenied={columnsData?.columnTagsDenied ?? false}
        />
      </div>
    </div>
  )
}

// ─────────────────────────── Proposals table ───────────────────────────

interface ProposalsTableProps {
  proposals: Proposal[]
  effectiveFor: (p: Proposal) => EffectiveDecision
  onDecision: (p: Proposal, patch: Partial<DecisionPatch>) => void
  samplesData: TableSamplesResult | undefined
  samplesLoading: boolean
}

function ProposalsTable({
  proposals, effectiveFor, onDecision, samplesData, samplesLoading,
}: ProposalsTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())
  const grid = '24px minmax(140px, 1.4fr) minmax(160px, 1fr) 64px 116px'

  if (proposals.length === 0) {
    return (
      <div style={{
        background: '#fff', border: '1px dashed var(--db-gray-lines)', borderRadius: 8,
        padding: 32, textAlign: 'center', color: 'var(--db-gray-text)', fontSize: 13,
      }}>
        No classification proposals for this table.
      </div>
    )
  }

  return (
    <div style={{
      background: '#fff', border: '1px solid var(--db-gray-lines)',
      borderRadius: 8, overflow: 'hidden',
    }}>
      <div style={{
        display: 'grid', gridTemplateColumns: grid, alignItems: 'center', gap: 12,
        padding: '12px 16px', background: 'var(--db-oat-medium)',
        borderBottom: '1px solid var(--db-gray-lines)',
        fontSize: 10.5, fontWeight: 500, color: 'var(--db-gray-text)',
        textTransform: 'uppercase', letterSpacing: '0.06em',
      }}>
        <div></div>
        <div>Column</div>
        <div>Proposed tag</div>
        <div>Conf.</div>
        <div style={{ textAlign: 'right' }}>Decision</div>
      </div>

      {proposals.map(p => {
        const eff = effectiveFor(p)
        const isOpen = expanded.has(p.key)
        const rowBg =
          eff.status === 'approved' ? 'rgba(158, 214, 196, 0.12)'
          : eff.status === 'rejected' ? 'rgba(250, 191, 186, 0.18)'
          : eff.status === 'modified' ? 'rgba(186, 225, 252, 0.18)'
          : '#fff'

        const displayedTag = eff.status === 'modified' && eff.modifiedTag ? eff.modifiedTag : p.classTag

        return (
          <div key={p.key}>
            <div style={{
              display: 'grid', gridTemplateColumns: grid, gap: 12, alignItems: 'center',
              padding: '12px 16px', borderTop: '1px solid var(--db-gray-lines)',
              background: rowBg, transition: 'background var(--dur-fast)',
            }}>
              <button
                onClick={() => {
                  const n = new Set(expanded)
                  if (n.has(p.key)) n.delete(p.key); else n.add(p.key)
                  setExpanded(n)
                }}
                style={{
                  background: 'transparent', border: 0, cursor: 'pointer',
                  color: 'var(--db-gray-text)', padding: 4, display: 'flex',
                }}
                title={isOpen ? 'Collapse' : 'Expand'}
              >
                <Icon name={isOpen ? 'chevDown' : 'chev'} size={14} />
              </button>

              <div style={{ minWidth: 0, overflow: 'hidden' }}>
                <div style={{
                  fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--db-navy-800)',
                  fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>{p.column}</div>
                <div style={{ fontSize: 11, color: 'var(--db-gray-text)', marginTop: 2 }}>
                  {p.dataType}
                  {p.frequency != null && (
                    <>
                      {' · '}
                      <span style={{ fontFamily: 'var(--font-mono)' }}>
                        {(p.frequency * 100).toFixed(1)}%
                      </span>
                      {' match'}
                    </>
                  )}
                  {p.userAdded && (
                    <>
                      {' · '}
                      <span style={{ color: 'var(--db-blue-700)', fontWeight: 500 }}>
                        proposed by steward
                      </span>
                    </>
                  )}
                </div>
              </div>

              <div style={{ minWidth: 0 }}>
                <TagPill tag={displayedTag} size="sm" />
                {p.userAdded && (
                  <div style={{
                    fontSize: 9.5, color: 'var(--db-blue-700)', marginTop: 4, fontWeight: 500,
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                  }}>
                    <Icon name="plus" size={9} stroke={2.5} /> User-added
                  </div>
                )}
                {eff.status === 'modified' && eff.modifiedTag && eff.modifiedTag !== p.classTag && (
                  <div style={{
                    fontSize: 10, color: 'var(--db-gray-text)', marginTop: 4,
                    fontFamily: 'var(--font-mono)',
                  }}>was: {p.classTag}</div>
                )}
              </div>

              <div><ConfidencePill level={p.confidence} /></div>

              <IconActions
                status={eff.status}
                onSet={(next) => {
                  if (next === eff.status) {
                    onDecision(p, { status: 'pending' })
                  } else if (next === 'modified') {
                    onDecision(p, {
                      status: 'modified',
                      modifiedTag: eff.modifiedTag ?? p.classTag,
                    })
                  } else {
                    onDecision(p, { status: next })
                  }
                }}
              />
            </div>

            {isOpen && (
              <div style={{
                borderTop: '1px solid var(--db-gray-lines)',
                padding: '16px 24px 18px 48px', background: 'var(--db-oat-light)',
              }}>
                <div style={{
                  display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 280px', gap: 24,
                }}>
                  <div style={{ minWidth: 0 }}>
                    <SamplesStatus samplesData={samplesData} samplesLoading={samplesLoading} column={p.column} />
                  </div>
                  <div>
                    <div style={{
                      fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
                      letterSpacing: '0.06em', fontWeight: 500, marginBottom: 8,
                    }}>Modify tag</div>
                    <select
                      value={eff.modifiedTag ?? p.classTag}
                      onChange={e => onDecision(p, {
                        status: 'modified', modifiedTag: e.target.value,
                      })}
                      style={{
                        width: '100%', padding: '7px 10px', fontFamily: 'var(--font-mono)',
                        fontSize: 12, border: '1px solid var(--db-gray-lines)',
                        borderRadius: 6, background: '#fff',
                      }}
                    >
                      {ALL_TAGS.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <div style={{
                      fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
                      letterSpacing: '0.06em', fontWeight: 500, marginTop: 14, marginBottom: 6,
                    }}>Comment</div>
                    <textarea
                      value={eff.comment ?? ''}
                      onChange={e => onDecision(p, { comment: e.target.value })}
                      placeholder="Add context for this decision…"
                      style={{
                        width: '100%', minHeight: 60, padding: '7px 10px',
                        fontFamily: 'var(--font-sans)', fontSize: 12,
                        border: '1px solid var(--db-gray-lines)', borderRadius: 6,
                        background: '#fff', resize: 'vertical',
                      }}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─────────────────────────── Action icons ───────────────────────────

interface IconActionsProps {
  status: DecisionStatus
  onSet: (next: DecisionStatus) => void
}

function IconActions({ status, onSet }: IconActionsProps) {
  const items: {
    id: Exclude<DecisionStatus, 'pending'>
    icon: string
    label: string
    activeBg: string
    activeFg: string
  }[] = [
    { id: 'approved', icon: 'check', label: 'Approve', activeBg: '#9ED6C4', activeFg: '#095A35' },
    { id: 'modified', icon: 'edit',  label: 'Modify',  activeBg: '#BAE1FC', activeFg: '#04355D' },
    { id: 'rejected', icon: 'x',     label: 'Reject',  activeBg: '#FABFBA', activeFg: '#801C17' },
  ]

  return (
    <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
      {items.map(it => {
        const active = status === it.id
        return (
          <button
            key={it.id}
            title={it.label}
            onClick={() => onSet(it.id)}
            style={{
              width: 32, height: 30,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              borderRadius: 6,
              background: active ? it.activeBg : '#fff',
              color: active ? it.activeFg : 'var(--db-navy-800)',
              border: `1px solid ${active ? it.activeBg : 'var(--db-gray-lines)'}`,
              cursor: 'pointer',
              transition: 'all var(--dur-fast) var(--ease-out)',
            }}
            onMouseEnter={e => {
              if (!active) (e.currentTarget as HTMLButtonElement).style.background = 'var(--db-oat-medium)'
            }}
            onMouseLeave={e => {
              if (!active) (e.currentTarget as HTMLButtonElement).style.background = '#fff'
            }}
          >
            <Icon name={it.icon} size={14} stroke={2.2} color={active ? it.activeFg : 'var(--db-navy-800)'} />
          </button>
        )
      })}
    </div>
  )
}
