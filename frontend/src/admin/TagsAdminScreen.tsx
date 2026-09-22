import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../store/api'
import type { TagConfig } from '../store/types'
import { Icon, Btn, Spinner, TagPill } from '../components'

export function TagsAdminScreen() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [pendingToggle, setPendingToggle] = useState<TagConfig | null>(null)
  const [activeProposalsCount, setActiveProposalsCount] = useState(0)

  const { data: tags = [], isLoading } = useQuery({
    queryKey: ['tags'],
    queryFn: () => api.getTags(),
  })

  const [refreshToast, setRefreshToast] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    setRefreshing(true)
    setRefreshToast(null)
    try {
      const result = await api.refreshTags()
      await queryClient.invalidateQueries({ queryKey: ['tags'] })
      if (result.added === 0) {
        setRefreshToast('Tag list is up to date')
      } else {
        setRefreshToast(
          `${result.added} new tag${result.added > 1 ? 's' : ''} added ` +
          `(${result.addedEnabled} enabled, ${result.addedDisabled} disabled)`
        )
      }
    } catch {
      setRefreshToast('Failed to fetch tags from Databricks. Check warehouse connectivity.')
    } finally {
      setRefreshing(false)
      setTimeout(() => setRefreshToast(null), 5000)
    }
  }

  const patchMutation = useMutation({
    mutationFn: ({ key, enabled, force }: { key: string; enabled: boolean; force: boolean }) =>
      api.patchTag(key, enabled, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] })
    },
  })

  const handleToggle = async (tag: TagConfig) => {
    if (tag.enabled) {
      const result = await patchMutation.mutateAsync({ key: tag.key, enabled: false, force: false })
      if (result.activeProposals > 0) {
        setActiveProposalsCount(result.activeProposals)
        setPendingToggle(tag)
      }
    } else {
      patchMutation.mutate({ key: tag.key, enabled: true, force: false })
    }
  }

  const handleConfirmDisable = () => {
    if (pendingToggle) {
      patchMutation.mutate({ key: pendingToggle.key, enabled: false, force: true })
      setPendingToggle(null)
    }
  }

  const q = search.toLowerCase()
  const filtered = tags.filter(t => t.key.toLowerCase().includes(q))
  const databricksTags = filtered.filter(t => t.key.startsWith('class.')).sort((a, b) => a.key.localeCompare(b.key))
  const customTags = filtered.filter(t => !t.key.startsWith('class.')).sort((a, b) => a.key.localeCompare(b.key))

  return (
    <div style={{ padding: '28px 32px', maxWidth: 820 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--db-navy-800)', margin: 0 }}>
          Governed Tags
        </h1>
        <Btn variant="ghost" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? <Spinner size={13} /> : <Icon name="refresh" size={13} />}
          {refreshing ? 'Refreshing…' : 'Refresh tag list'}
        </Btn>
      </div>

      {/* Toast */}
      {refreshToast && (
        <div style={{
          marginBottom: 16, padding: '10px 14px', borderRadius: 6,
          background: refreshToast.startsWith('Failed') ? '#FABFBA' : '#9ED6C4',
          color: refreshToast.startsWith('Failed') ? '#801C17' : '#095A35',
          fontSize: 13,
        }}>
          {refreshToast}
        </div>
      )}

      {/* Search */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 6,
        padding: '7px 12px', marginBottom: 20,
      }}>
        <Icon name="search" size={14} color="var(--db-gray-text)" />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search tags…"
          style={{
            border: 'none', outline: 'none', flex: 1,
            fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--db-navy-800)',
            background: 'transparent',
          }}
        />
        {search && (
          <button onClick={() => setSearch('')} style={{
            border: 'none', background: 'transparent', cursor: 'pointer', padding: 2,
            color: 'var(--db-gray-text)', display: 'flex',
          }}>
            <Icon name="x" size={13} />
          </button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--db-gray-text)', fontSize: 13 }}>
          <Spinner size={14} /> Loading tags…
        </div>
      ) : tags.length === 0 ? (
        <div style={{
          padding: '32px 20px', textAlign: 'center',
          color: 'var(--db-gray-text)', fontSize: 13,
          border: '1px dashed var(--db-gray-lines)', borderRadius: 8,
        }}>
          No tags found. Click "Refresh tag list" to load governed tags from your Databricks instance.
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ color: 'var(--db-gray-text)', fontSize: 13, padding: '16px 0' }}>
          No tags match your search.
        </div>
      ) : (
        <div style={{ background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 8, overflow: 'hidden' }}>
          <TableHeader />
          {databricksTags.length > 0 && (
            <TagGroup title="Databricks reserved tags" tags={databricksTags} onToggle={handleToggle} />
          )}
          {customTags.length > 0 && (
            <TagGroup
              title="Custom tags"
              tags={customTags}
              onToggle={handleToggle}
              borderTop={databricksTags.length > 0}
            />
          )}
        </div>
      )}

      {/* Warning modal */}
      {pendingToggle && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#fff', borderRadius: 10, padding: '24px 28px',
            width: 420, boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: 'var(--db-navy-800)' }}>
              Disable tag?
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: 13, color: 'var(--db-gray-text)', lineHeight: 1.6 }}>
              Disabling <TagPill tag={pendingToggle.key} size="sm" /> will hide it from stewards'
              tag pickers. <strong style={{ color: 'var(--db-navy-800)' }}>
                {activeProposalsCount} existing proposal{activeProposalsCount > 1 ? 's' : ''}
              </strong> using this tag will remain unchanged. Continue?
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Btn variant="ghost" onClick={() => setPendingToggle(null)}>Cancel</Btn>
              <Btn variant="danger" onClick={handleConfirmDisable}>Disable tag</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const COL_WIDTHS = '44px 220px 1fr 200px'

function TableHeader() {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: COL_WIDTHS,
      padding: '8px 16px', background: 'var(--db-oat-medium)',
      borderBottom: '1px solid var(--db-gray-lines)',
      fontSize: 10.5, fontWeight: 500, color: 'var(--db-gray-text)',
      textTransform: 'uppercase', letterSpacing: '0.08em',
      alignItems: 'center', gap: 12,
    }}>
      <div />
      <div>Tag</div>
      <div>Description</div>
      <div>Allowed values</div>
    </div>
  )
}

function TagGroup({
  title, tags, onToggle, borderTop = false, showHeader = false,
}: {
  title: string
  tags: TagConfig[]
  onToggle: (tag: TagConfig) => void
  borderTop?: boolean
  showHeader?: boolean
}) {
  return (
    <div style={{ borderTop: borderTop ? '1px solid var(--db-gray-lines)' : undefined }}>
      <div style={{
        padding: '8px 16px', background: 'var(--db-oat-light)',
        fontSize: 10.5, fontWeight: 600, color: 'var(--db-navy-800)',
        textTransform: 'uppercase', letterSpacing: '0.08em',
        borderBottom: '1px solid var(--db-gray-lines)',
      }}>
        {title}
      </div>
      {showHeader && <TableHeader />}
      {tags.map(tag => <TagRow key={tag.key} tag={tag} onToggle={onToggle} />)}
    </div>
  )
}

function TagRow({ tag, onToggle }: { tag: TagConfig; onToggle: (tag: TagConfig) => void }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: COL_WIDTHS,
      alignItems: 'start', gap: 12,
      padding: '10px 16px', borderTop: '1px solid var(--db-gray-lines)',
      opacity: tag.enabled ? 1 : 0.5,
      transition: 'opacity 0.15s',
    }}>
      {/* Toggle */}
      <div style={{ display: 'flex', alignItems: 'center', paddingTop: 2 }}>
        <button
          onClick={() => onToggle(tag)}
          title={tag.enabled ? 'Disable tag' : 'Enable tag'}
          style={{
            width: 36, height: 20, borderRadius: 999, border: 'none', cursor: 'pointer',
            background: tag.enabled ? 'var(--db-green-700)' : 'var(--db-gray-lines)',
            position: 'relative', transition: 'background 0.15s', flexShrink: 0,
            padding: 0,
          }}
        >
          <span style={{
            position: 'absolute', top: 3, left: tag.enabled ? 18 : 3,
            width: 14, height: 14, borderRadius: '50%', background: '#fff',
            transition: 'left 0.15s', display: 'block',
          }} />
        </button>
      </div>

      {/* Tag name */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <TagPill tag={tag.key} size="sm" />
      </div>

      {/* Description */}
      <div style={{ fontSize: 12, color: 'var(--db-gray-text)', lineHeight: 1.5 }}>
        {tag.description || '—'}
      </div>

      {/* Allowed values */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {tag.allowedValues && tag.allowedValues.length > 0 ? (
          tag.allowedValues.map(v => (
            <span key={v} style={{
              fontFamily: 'var(--font-mono)', fontSize: 10, padding: '2px 7px',
              borderRadius: 4, background: 'var(--db-oat-medium)',
              color: 'var(--db-navy-800)', fontWeight: 500,
            }}>{v}</span>
          ))
        ) : (
          <span style={{ fontSize: 12, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>Any</span>
        )}
      </div>
    </div>
  )
}
