import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Icon, TagPill, Avatar, AssetPath, FilterChip } from '../components'
import { api } from '../store/api'
import type { AuditEntry, Principal } from '../store/types'
import { isAdminEvent } from '../store/types'

interface AuditLogProps {
  hideFilters?: boolean
  reviewerFilter?: string
}

type DateFilter = '' | '24h' | '7d' | '30d'

const STATUS_ICON: Record<'approved' | 'rejected' | 'modified' | 'applied', { icon: string; color: string; verb: string }> = {
  approved: { icon: 'check',  color: 'var(--db-green-700)',  verb: 'approved' },
  rejected: { icon: 'x',      color: 'var(--db-lava-700)',   verb: 'rejected' },
  modified: { icon: 'edit',   color: 'var(--db-blue-700)',   verb: 'modified' },
  applied:  { icon: 'tag',    color: 'var(--db-navy-600)',   verb: 'applied'  },
}

export function AuditLog({ hideFilters, reviewerFilter }: AuditLogProps) {
  const { data: decisions = [], isLoading, isError } = useQuery({
    queryKey: ['decisions', reviewerFilter ?? ''],
    queryFn: () => api.getDecisions(reviewerFilter ? { reviewer: reviewerFilter } : undefined),
  })

  const { data: stewards = [] } = useQuery<Principal[]>({
    queryKey: ['stewards'],
    queryFn: api.getStewards,
  })

  const principalMap = useMemo(() => {
    const m = new Map<string, Principal>()
    for (const s of stewards) m.set(s.id, s)
    return m
  }, [stewards])

  const [localUserFilter, setLocalUserFilter] = useState('')
  const [dateFilter, setDateFilter] = useState<DateFilter>('')

  type TypeFilter = 'all' | 'classification' | 'admin'
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')

  // Distinct reviewers visible in the data
  const reviewerOpts = useMemo(
    () => [...new Set(decisions.map(d => d.reviewer).filter(Boolean))],
    [decisions],
  )

  const filteredDecisions = useMemo(() => {
    if (hideFilters) return decisions
    const now = Date.now()
    const cutoff = dateFilter === '24h' ? now - 86_400_000
                : dateFilter === '7d'  ? now - 7 * 86_400_000
                : dateFilter === '30d' ? now - 30 * 86_400_000
                : null
    return decisions.filter(d => {
      if (typeFilter === 'classification' && isAdminEvent(d.status)) return false
      if (typeFilter === 'admin' && !isAdminEvent(d.status)) return false
      if (localUserFilter && d.reviewer !== localUserFilter) return false
      if (cutoff !== null) {
        const t = Date.parse((d.decidedAt || '').replace(' ', 'T'))
        if (!isNaN(t) && t < cutoff) return false
      }
      return true
    })
  }, [decisions, hideFilters, typeFilter, localUserFilter, dateFilter])

  const hasFilter = !!(localUserFilter || dateFilter || typeFilter !== 'all')

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
        Failed to load audit log. Please refresh.
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
        <div style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
            letterSpacing: '0.08em', fontWeight: 500, marginBottom: 6,
          }}>
            {hideFilters ? 'Review history' : 'Administration'}
          </div>
          <h1 style={{
            fontSize: 26, fontWeight: 500, letterSpacing: '-0.018em',
            color: 'var(--db-navy-800)', margin: 0,
          }}>
            {hideFilters ? 'My decisions' : 'Audit log'}
          </h1>
          <div style={{ fontSize: 13, color: 'var(--db-gray-text)', marginTop: 6 }}>
            {hideFilters
              ? 'Every decision you’ve made, in order.'
              : 'Actions executed by stewards and admins.'}
          </div>
        </div>

        {/* Filter bar */}
        {!hideFilters && (
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 8,
            padding: '10px 16px', marginBottom: 14,
            display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
          }}>
            <span style={{
              fontSize: 11, fontWeight: 500, color: 'var(--db-gray-text)',
              textTransform: 'uppercase', letterSpacing: '0.08em',
            }}>
              Filter
            </span>
            <FilterChip
              label="User"
              value={localUserFilter}
              onChange={setLocalUserFilter}
              options={[
                { value: '', label: 'All users' },
                ...reviewerOpts.map(r => ({
                  value: r,
                  label: principalMap.get(r)?.name ?? r,
                })),
              ]}
            />
            <FilterChip
              label="Date"
              value={dateFilter}
              onChange={v => setDateFilter(v as DateFilter)}
              options={[
                { value: '', label: 'All time' },
                { value: '24h', label: 'Last 24 hours' },
                { value: '7d', label: 'Last 7 days' },
                { value: '30d', label: 'Last 30 days' },
              ]}
            />
            <FilterChip
              label="Type"
              value={typeFilter}
              onChange={v => setTypeFilter(v as TypeFilter)}
              options={[
                { value: 'all',            label: 'All events' },
                { value: 'classification', label: 'Classification' },
                { value: 'admin',          label: 'Admin' },
              ]}
            />
            {hasFilter && (
              <button
                onClick={() => { setLocalUserFilter(''); setDateFilter(''); setTypeFilter('all') }}
                style={{
                  background: 'transparent', border: 0, color: 'var(--db-lava-700)',
                  fontSize: 12, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Clear
              </button>
            )}
            <div style={{
              marginLeft: 'auto', fontSize: 12, color: 'var(--db-gray-text)',
            }}>
              {filteredDecisions.length} of {decisions.length} event{decisions.length === 1 ? '' : 's'}
            </div>
          </div>
        )}

        {/* Feed */}
        {filteredDecisions.length === 0 ? (
          <div style={{
            background: '#fff', border: '1px dashed var(--db-gray-lines)',
            borderRadius: 8, padding: 40, textAlign: 'center',
            color: 'var(--db-gray-text)', fontSize: 13,
          }}>
            {decisions.length === 0
              ? 'No decisions recorded yet.'
              : 'No decisions match the current filters.'}
          </div>
        ) : (
          <div style={{
            background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 8,
            display: 'flex', flexDirection: 'column',
          }}>
            {filteredDecisions.map((entry, i) => (
              <AuditEntryRow
                key={entry.id ?? `${entry.columnKey}-${entry.decidedAt}-${i}`}
                entry={entry}
                steward={principalMap.get(entry.reviewer)}
                isFirst={i === 0}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function AuditEntryRow({
  entry, steward, isFirst,
}: {
  entry: AuditEntry
  steward: Principal | undefined
  isFirst: boolean
}) {
  const meta = STATUS_ICON[entry.status as keyof typeof STATUS_ICON] ?? STATUS_ICON.approved
  const name = steward?.name ?? entry.reviewer
  const initials = steward?.initials ?? entry.reviewer.slice(0, 2).toUpperCase()
  const accent = steward?.accent ?? 'var(--db-navy-600)'

  const ADMIN_STATUS_META: Record<string, { icon: string; color: string }> = {
    steward_added:   { icon: 'user-plus', color: 'var(--db-green-700)' },
    steward_removed: { icon: 'trash-2',   color: 'var(--db-lava-700)' },
    scope_added:     { icon: 'plus',      color: 'var(--db-green-700)' },
    scope_removed:   { icon: 'minus',     color: 'var(--db-lava-700)' },
    role_granted:    { icon: 'shield',    color: 'var(--db-green-700)' },
    role_revoked:    { icon: 'shield',    color: 'var(--db-lava-700)' },
  }

  if (isAdminEvent(entry.status)) {
    const adminMeta = ADMIN_STATUS_META[entry.status] ?? { icon: 'shield', color: 'var(--db-navy-600)' }
    return (
      <div style={{
        display: 'flex', gap: 12, padding: '14px 18px',
        borderTop: isFirst ? 0 : '1px solid var(--db-gray-lines)',
      }}>
        <div style={{ position: 'relative', width: 44, flexShrink: 0 }}>
          <Avatar initials={initials} color={accent} size={32} />
          <div style={{
            position: 'absolute', bottom: -2, left: 18,
            width: 14, height: 14, borderRadius: '50%', background: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: `1.5px solid ${adminMeta.color}`,
          }}>
            <Icon name={adminMeta.icon} size={9} color={adminMeta.color} stroke={2.4} />
          </div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, color: 'var(--db-navy-800)' }}>
            <span style={{ fontWeight: 500 }}>{name}</span>{' '}{entry.comment}
          </div>
        </div>
        <div style={{
          fontSize: 11, color: 'var(--db-gray-text)',
          whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)',
        }}>
          {entry.decidedAt}
        </div>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', gap: 12, padding: '14px 18px',
      borderTop: isFirst ? 0 : '1px solid var(--db-gray-lines)',
    }}>
      {/* Avatar with status badge */}
      <div style={{ position: 'relative', width: 44, flexShrink: 0 }}>
        <Avatar initials={initials} color={accent} size={32} />
        <div style={{
          position: 'absolute', bottom: -2, left: 18,
          width: 14, height: 14, borderRadius: '50%', background: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: `1.5px solid ${meta.color}`,
        }}>
          <Icon name={meta.icon} size={9} color={meta.color} stroke={2.4} />
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: 'var(--db-navy-800)' }}>
          <span style={{ fontWeight: 500 }}>{name}</span>{' '}
          {meta.verb} tag{' '}
          <TagPill tag={entry.classTag ?? entry.modifiedTag} size="sm" />
          {entry.modifiedTag && entry.classTag && (
            <>
              {' '}
              <span style={{ color: 'var(--db-gray-text)' }}>→</span>{' '}
              <TagPill tag={entry.modifiedTag} size="sm" />
            </>
          )}{' '}
          on{' '}
          <AssetPath
            catalog={entry.catalog}
            schema={entry.schemaName}
            table={entry.table}
            column={entry.column}
            size={12}
          />
        </div>
        {entry.comment && (
          <div style={{
            fontSize: 12, color: 'var(--db-navy-800)', marginTop: 8,
            padding: '12px 14px', background: 'var(--db-oat-light)',
            borderRadius: 5, borderLeft: '2px solid var(--db-navy-400)',
            fontStyle: 'italic',
          }}>
            “{entry.comment}”
          </div>
        )}
      </div>

      {/* Timestamp */}
      <div style={{
        fontSize: 11, color: 'var(--db-gray-text)',
        whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)',
      }}>
        {entry.decidedAt}
      </div>
    </div>
  )
}
