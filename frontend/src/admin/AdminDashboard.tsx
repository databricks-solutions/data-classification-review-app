import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { Icon, Pill, TagPill, Btn, Avatar, FilterChip } from '../components'
import { api } from '../store/api'
import type { Principal, ProvisioningStatus } from '../store/types'

function KpiTile({ label, value, sub, valueColor }: {
  label: string; value: string | number; sub?: string; valueColor?: string
}) {
  return (
    <div style={{
      background: '#fff', border: '1px solid var(--db-gray-lines)',
      borderRadius: 8, padding: '16px 18px',
    }}>
      <div style={{
        fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em',
        color: 'var(--db-gray-text)', fontWeight: 500, marginBottom: 6,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 30, fontWeight: 500,
        color: valueColor ?? 'var(--db-navy-800)',
        letterSpacing: '-0.018em',
        fontVariantNumeric: 'tabular-nums',
      }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 11.5, color: 'var(--db-gray-text)', marginTop: 4 }}>
          {sub}
        </div>
      )}
    </div>
  )
}


const SETUP_STEP_LABEL: Record<NonNullable<ProvisioningStatus['step']>, string> = {
  view: 'Creating the classification view',
  synced_table: 'Creating the Lakebase synced table',
  pipeline: 'Waiting for the synced-table pipeline',
  job: 'Creating the sync job',
}

/** Classification setup (the app SP's startup provisioning) isn't ready yet. */
function isSetupIncomplete(p: ProvisioningStatus | undefined): p is ProvisioningStatus {
  return !!p && p.state !== 'ready' && p.state !== 'disabled'
}

function SetupBanner({ status, onRetry, retrying }: {
  status: ProvisioningStatus
  onRetry: () => void
  retrying: boolean
}) {
  const inProgress = status.state === 'running' || status.state === 'pending'
  const stepLabel = status.step ? SETUP_STEP_LABEL[status.step] : null
  const title = inProgress
    ? `Setting up classification data${stepLabel ? ` — ${stepLabel.toLowerCase()}…` : '…'}`
    : status.state === 'not_configured'
      ? 'Classification setup is not configured'
      : `Classification setup failed${stepLabel ? ` while ${stepLabel.toLowerCase()}` : ''}`
  const tone = inProgress
    ? { border: 'var(--info-bg)', icon: 'var(--info)' }
    : { border: 'var(--danger-bg)', icon: 'var(--danger)' }
  return (
    <div role={inProgress ? 'status' : 'alert'} style={{
      display: 'flex', gap: 12, alignItems: 'flex-start',
      background: 'var(--db-white)', border: `1px solid ${tone.border}`,
      borderLeft: `4px solid ${tone.icon}`, borderRadius: 8,
      padding: '14px 18px', marginBottom: 20, fontFamily: 'var(--font-sans)',
      textAlign: 'left', width: '100%', maxWidth: 1280, boxSizing: 'border-box',
    }}>
      <Icon name="info" size={18} color={tone.icon} style={{ marginTop: 1 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--db-navy-800)' }}>{title}</div>
        {inProgress ? (
          <div style={{ fontSize: 13, color: 'var(--db-gray-text)', marginTop: 4 }}>
            Proposals appear once the first sync completes. This can take several minutes.
          </div>
        ) : (
          <>
            {status.hint && (
              <div style={{ fontSize: 13, color: 'var(--db-navy-800)', marginTop: 6 }}>{status.hint}</div>
            )}
            {status.servicePrincipal && (
              <div style={{ fontSize: 12, color: 'var(--db-gray-text)', marginTop: 6 }}>
                App service principal: <code style={{ fontFamily: 'var(--font-mono)' }}>{status.servicePrincipal}</code>
              </div>
            )}
            {status.error && (
              <pre style={{
                fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--danger)',
                background: 'var(--db-oat-light)', borderRadius: 6, padding: '8px 10px',
                margin: '8px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                maxHeight: 160, overflow: 'auto',
              }}>{status.error}</pre>
            )}
            <div style={{ fontSize: 12, color: 'var(--db-gray-text)', marginTop: 6 }}>
              After granting the missing permissions, click Retry setup.
              {status.updatedAt && ` Last attempt: ${new Date(status.updatedAt).toLocaleString()}.`}
            </div>
          </>
        )}
      </div>
      {!inProgress && (
        <Btn onClick={onRetry} disabled={retrying} style={{ flexShrink: 0 }}>
          <Icon name="refresh" size={13} /> Retry setup
        </Btn>
      )}
    </div>
  )
}

export function AdminDashboard() {
  const [catalogFilter, setCatalogFilter] = useState<string>('')

  const { data: stats, isLoading, isError, error } = useQuery({
    queryKey: ['proposals', 'stats', catalogFilter],
    queryFn: () => api.getOverviewStats(catalogFilter || undefined),
    placeholderData: keepPreviousData,
  })
  const { data: facets } = useQuery({
    queryKey: ['proposals', 'facets', '', ''],
    queryFn: () => api.getProposalFacets(),
  })
  const catalogs = facets?.catalogs ?? []

  const metrics = useMemo(() => {
    const s = stats ?? {
      total: 0, approved: 0, rejected: 0, modified: 0, pending: 0, applied: 0,
      approvalRate: 0, tableCount: 0, byCatalog: [], byTag: [], byOwner: [],
    }
    // KPI "pending" keeps its old meaning: everything not approved/rejected/modified.
    return { ...s, pending: s.total - s.approved - s.rejected - s.modified }
  }, [stats])
  const tableCount = metrics.tableCount

  const { data: stewards = [] } = useQuery<Principal[]>({
    queryKey: ['stewards'],
    queryFn: api.getStewards,
  })

  const stewardLookup = useMemo(() => {
    const m = new Map<string, Principal>()
    for (const s of stewards) m.set(s.id, s)
    return m
  }, [stewards])

  const pendingPct = metrics.total > 0
    ? Math.round((metrics.pending / metrics.total) * 100)
    : 0

  const tagMax = metrics.byTag.length > 0
    ? Math.max(...metrics.byTag.map(t => t.total))
    : 1

  const queryClient = useQueryClient()

  const { data: sync } = useQuery({
    queryKey: ['syncStatus'],
    queryFn: api.getSyncStatus,
    refetchInterval: (query) => (query.state.data?.running ? 3000 : false),
  })

  const refresh = useMutation({
    mutationFn: api.refreshSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syncStatus'] })
      queryClient.invalidateQueries({ queryKey: ['proposals'] })
      queryClient.invalidateQueries({ queryKey: ['tables'] })
    },
  })

  // Reload proposals when a sync — or the setup that runs the first sync — finishes.
  const wasRunning = useRef(false)
  useEffect(() => {
    const running = !!sync?.running
    if (wasRunning.current && !running) {
      queryClient.invalidateQueries({ queryKey: ['proposals'] })
      queryClient.invalidateQueries({ queryKey: ['tables'] })
    }
    wasRunning.current = running
  }, [sync?.running, queryClient])

  const setup = isSetupIncomplete(sync?.provisioning) ? sync.provisioning : null
  const refreshLabel = setup
    ? (sync?.running ? 'Setting up…' : 'Retry setup')
    : (sync?.running ? 'Syncing…' : 'Refresh')
  const setupBanner = setup && (
    <SetupBanner status={setup} onRetry={() => refresh.mutate()}
      retrying={!!sync?.running || refresh.isPending} />
  )

  if (isLoading) return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-sans)', color: 'var(--db-gray-text)' }}>Loading…</div>
  if (isError) {
    const is503 = (error as any)?.status === 503
    if (is503) return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, fontFamily: 'var(--font-sans)', padding: '28px 32px' }}>
        {setupBanner}
        {!setup && <>
          <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--db-navy-800)' }}>Classification sync pending</div>
          <div style={{ fontSize: 13, color: 'var(--db-gray-text)', maxWidth: 360, textAlign: 'center' }}>No synced data yet. Click Refresh to trigger the first sync.</div>
          <Btn onClick={() => refresh.mutate()} disabled={!!sync?.running || refresh.isPending}>
            {refreshLabel}
          </Btn>
        </>}
      </div>
    )
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, fontFamily: 'var(--font-sans)', padding: '28px 32px' }}>
        {setupBanner}
        <div style={{ color: 'var(--db-lava-600)' }}>Failed to load data. Please refresh.</div>
      </div>
    )
  }

  return (
    <div style={{
      flex: 1, overflow: 'auto', background: 'var(--db-oat-light)',
      padding: '28px 32px 48px',
    }}>
      <div style={{ maxWidth: 1280 }}>
        {setupBanner}
        {/* Header band */}
        <div style={{
          display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
          marginBottom: 28, gap: 24, flexWrap: 'wrap',
        }}>
          <div style={{ minWidth: 0, flex: '1 1 auto' }}>
            <div style={{
              fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
              letterSpacing: '0.08em', fontWeight: 500, marginBottom: 6,
            }}>
              Administration
            </div>
            <h1 style={{
              fontSize: 30, fontWeight: 500, letterSpacing: '-0.018em',
              color: 'var(--db-navy-800)', margin: 0,
            }}>
              Classification overview
            </h1>
            <p style={{ fontSize: 14, color: 'var(--db-gray-text)', marginTop: 8 }}>
              All catalogs, all stewards, all decisions. Approved tags can be
              committed to Unity Catalog from the Apply tags screen.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 4 }}>
              <span style={{ fontSize: 12, color: 'var(--db-gray-text)' }}>
                Last synced: {sync?.lastSyncEnd ? new Date(sync.lastSyncEnd).toLocaleString() : '—'}
              </span>
              <Btn onClick={() => refresh.mutate()} disabled={!!sync?.running || refresh.isPending}>
                {refreshLabel}
              </Btn>
            </div>
            <FilterChip
              label="Catalog"
              value={catalogFilter}
              onChange={setCatalogFilter}
              options={[
                { value: '', label: 'All catalogs' },
                ...catalogs.map(c => ({ value: c, label: c })),
              ]}
            />
            <Btn variant="ghost" size="sm">
              <Icon name="download" size={13} /> Export report
            </Btn>
          </div>
        </div>

        {/* KPI tile grid */}
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 16,
        }}>
          <KpiTile
            label="Total proposals"
            value={metrics.total}
            sub={`across ${tableCount} tables`}
          />
          <KpiTile
            label="Pending review"
            value={metrics.pending}
            sub={metrics.total > 0 ? `${pendingPct}% of total` : undefined}
            valueColor="var(--db-lava-600)"
          />
          <KpiTile
            label="Approved"
            value={metrics.approved}
            sub="ready to apply"
            valueColor="var(--db-green-700)"
          />
          <KpiTile
            label="Modified"
            value={metrics.modified}
            sub="adjusted by stewards"
            valueColor="var(--db-blue-700)"
          />
          <KpiTile
            label="Avg approval rate"
            value={`${metrics.approvalRate}%`}
            sub="of decided"
          />
        </div>

        {/* Coverage by catalog + Top tags */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14,
        }}>
          {/* Catalog breakdown */}
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)',
            borderRadius: 8, overflow: 'hidden',
          }}>
            <div style={{
              padding: '14px 18px', borderBottom: '1px solid var(--db-gray-lines)',
              fontSize: 13, fontWeight: 500, color: 'var(--db-navy-800)',
            }}>
              Coverage by catalog
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--db-oat-light)' }}>
                  {['Catalog', 'Tables', 'Proposals', 'Pending', 'Decided', 'Progress'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '8px 16px',
                      fontSize: 10.5, textTransform: 'uppercase',
                      letterSpacing: '0.06em', color: 'var(--db-gray-text)', fontWeight: 500,
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metrics.byCatalog.map(c => {
                  const decided = c.approved + c.rejected + c.modified
                  const pct = c.total > 0 ? Math.round((decided / c.total) * 100) : 0
                  return (
                    <tr key={c.catalog} style={{ borderTop: '1px solid var(--db-gray-lines)' }}>
                      <td style={{
                        padding: '12px 16px', fontFamily: 'var(--font-mono)',
                        fontSize: 12.5, color: 'var(--db-navy-800)', fontWeight: 500,
                      }}>
                        {c.catalog}
                      </td>
                      <td style={{
                        padding: '12px 16px', fontFamily: 'var(--font-mono)',
                        fontSize: 12.5, color: 'var(--db-navy-800)',
                      }}>
                        {c.tables}
                      </td>
                      <td style={{
                        padding: '12px 16px', fontFamily: 'var(--font-mono)',
                        fontSize: 12.5, color: 'var(--db-navy-800)',
                      }}>
                        {c.total}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        {c.pending > 0 ? (
                          <Pill bg="#FFDB96" color="#7D5319" dot>{c.pending}</Pill>
                        ) : (
                          <span style={{ color: 'var(--db-gray-text)', fontSize: 12 }}>0</span>
                        )}
                      </td>
                      <td style={{
                        padding: '12px 16px', fontFamily: 'var(--font-mono)',
                        fontSize: 12.5, color: 'var(--db-navy-800)',
                      }}>
                        {decided}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{
                            flex: 1, height: 5, background: 'var(--db-oat-medium)',
                            borderRadius: 3, maxWidth: 140,
                          }}>
                            <div style={{
                              width: `${pct}%`, height: '100%',
                              background: pct === 100 ? 'var(--db-green-700)' : 'var(--db-navy-600)',
                              borderRadius: 3,
                            }} />
                          </div>
                          <span style={{
                            fontFamily: 'var(--font-mono)', fontSize: 11.5,
                            color: 'var(--db-gray-text)', minWidth: 32, textAlign: 'right',
                          }}>
                            {pct}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {metrics.byCatalog.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{
                      padding: 24, textAlign: 'center',
                      color: 'var(--db-gray-text)', fontSize: 12.5,
                    }}>
                      No catalogs in scope.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Top tags list */}
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)',
            borderRadius: 8, padding: '14px 18px',
          }}>
            <div style={{
              fontSize: 13, fontWeight: 500, color: 'var(--db-navy-800)', marginBottom: 14,
            }}>
              Top detected tags
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[...metrics.byTag].sort((a, b) => b.total - a.total).map(t => (
                <div key={t.tag}>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: 4,
                  }}>
                    <TagPill tag={t.tag} size="sm" />
                    <span style={{
                      fontFamily: 'var(--font-mono)', fontSize: 12,
                      color: 'var(--db-navy-800)', fontWeight: 500,
                    }}>
                      {t.total}
                    </span>
                  </div>
                  <div style={{
                    display: 'flex', height: 5, borderRadius: 3,
                    overflow: 'hidden', background: 'var(--db-oat-medium)',
                  }}>
                    <div style={{ width: `${(t.approved / tagMax) * 100}%`, background: 'var(--db-green-700)' }}
                         title={`${t.approved} approved`} />
                    <div style={{ width: `${(t.modified / tagMax) * 100}%`, background: 'var(--db-blue-700)' }}
                         title={`${t.modified} modified`} />
                    <div style={{ width: `${(t.rejected / tagMax) * 100}%`, background: 'var(--db-lava-700)' }}
                         title={`${t.rejected} rejected`} />
                    <div style={{ width: `${(t.pending / tagMax) * 100}%`, background: 'var(--db-yellow-600)' }}
                         title={`${t.pending} pending`} />
                  </div>
                </div>
              ))}
              {metrics.byTag.length === 0 && (
                <div style={{ color: 'var(--db-gray-text)', fontSize: 12.5 }}>
                  No tags in scope.
                </div>
              )}
            </div>
            <div style={{
              display: 'flex', gap: 14, marginTop: 16, paddingTop: 12,
              borderTop: '1px solid var(--db-gray-lines)',
              fontSize: 11, color: 'var(--db-gray-text)', flexWrap: 'wrap',
            }}>
              {([
                ['Approved', 'var(--db-green-700)'],
                ['Modified', 'var(--db-blue-700)'],
                ['Rejected', 'var(--db-lava-700)'],
                ['Pending', 'var(--db-yellow-600)'],
              ] as const).map(([l, c]) => (
                <span key={l} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: c }} />
                  {l}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Steward leaderboard */}
        <div style={{ marginTop: 14 }}>
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)',
            borderRadius: 8, padding: '14px 18px',
          }}>
            <div style={{
              fontSize: 13, fontWeight: 500, color: 'var(--db-navy-800)', marginBottom: 14,
            }}>
              Stewards
            </div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14,
            }}>
              {metrics.byOwner.map(o => {
                const s = stewardLookup.get(o.owner)
                if (!s) return null
                const decided = o.approved + o.rejected + o.modified
                const pct = o.total > 0 ? Math.round((decided / o.total) * 100) : 0
                return (
                  <div key={o.owner} style={{
                    display: 'flex', gap: 12, alignItems: 'flex-start',
                    padding: '10px 12px', background: 'var(--db-oat-light)', borderRadius: 6,
                  }}>
                    <Avatar initials={s.initials} color={s.accent} size={32} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontSize: 12.5, fontWeight: 500, color: 'var(--db-navy-800)',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {s.name}
                      </div>
                      <div style={{
                        fontSize: 11, color: 'var(--db-gray-text)', marginTop: 1,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {(s.team ?? '').replace('Data Governance · ', '')}
                      </div>
                      <div style={{
                        display: 'flex', gap: 8, marginTop: 6,
                        fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--db-gray-text)',
                      }}>
                        <span>
                          <span style={{ color: 'var(--db-lava-600)', fontWeight: 600 }}>
                            {o.pending}
                          </span> pending
                        </span>
                        <span>
                          <span style={{ color: 'var(--db-green-700)', fontWeight: 600 }}>
                            {decided}
                          </span> done
                        </span>
                      </div>
                      <div style={{
                        height: 4, background: 'var(--db-oat-medium)',
                        borderRadius: 2, marginTop: 6,
                      }}>
                        <div style={{
                          width: `${pct}%`, height: '100%',
                          background: 'var(--db-green-700)', borderRadius: 2,
                        }} />
                      </div>
                    </div>
                  </div>
                )
              })}
              {metrics.byOwner.length === 0 && (
                <div style={{
                  gridColumn: '1 / -1', color: 'var(--db-gray-text)',
                  fontSize: 12.5, padding: 16, textAlign: 'center',
                }}>
                  No stewards have activity in scope.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
