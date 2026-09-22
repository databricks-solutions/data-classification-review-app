import { useRef, useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Icon, Avatar, Btn, Pill } from '../components'
import { api } from '../store/api'
import type { PrincipalSearchResult } from '../store/types'

type KindFilter = 'all' | 'user' | 'group'

interface Props {
  onClose: () => void
}

export function AddStewardDialog({ onClose }: Props) {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [kind, setKind] = useState<KindFilter>('all')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set())
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  // Debounce search input by 300ms.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300)
    return () => clearTimeout(t)
  }, [q])

  const { data: results = [], isFetching, isError } = useQuery<PrincipalSearchResult[]>({
    queryKey: ['stewards-search', debouncedQ, kind],
    queryFn: () => api.searchStewards(debouncedQ, kind),
    enabled: debouncedQ.length >= 2,
    staleTime: 30_000,
  })

  const addMutation = useMutation({
    mutationFn: (p: PrincipalSearchResult) => api.postSteward(p),
    onSuccess: (_, p) => {
      setAddedIds(prev => new Set([...prev, p.id]))
      queryClient.invalidateQueries({ queryKey: ['stewards'] })
    },
  })

  const kindOptions: { v: KindFilter; l: string }[] = [
    { v: 'all', l: 'All' },
    { v: 'user', l: 'Users' },
    { v: 'group', l: 'Groups' },
  ]

  return (
    <div
      onClick={onClose}
      onKeyDown={e => { if (e.key === 'Escape') onClose() }}
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
        aria-label="Add steward"
        tabIndex={-1}
        style={{
          background: '#fff', borderRadius: 12, padding: 24, width: 520,
          boxShadow: 'var(--shadow-xl)', maxHeight: '80vh', overflow: 'hidden',
          display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-sans)', outline: 'none',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 18, fontWeight: 500, margin: 0, color: 'var(--db-navy-800)' }}>
            Add steward
          </h3>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 0, padding: 4, cursor: 'pointer', color: 'var(--db-gray-text)' }}
            aria-label="Close"
          >
            <Icon name="x" size={16} />
          </button>
        </div>

        {/* Search + kind filter */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Icon name="search" size={14} color="var(--db-gray-text)"
              style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
            <input
              ref={inputRef}
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="Search by name or email…"
              style={{
                width: '100%', paddingLeft: 32, paddingRight: 10, paddingTop: 8, paddingBottom: 8,
                border: '1px solid var(--db-gray-lines)', borderRadius: 6, fontSize: 13,
                fontFamily: 'var(--font-sans)', outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ display: 'inline-flex', background: 'var(--db-oat-medium)', borderRadius: 999, padding: 3, gap: 0 }}>
            {kindOptions.map(opt => (
              <button
                key={opt.v}
                onClick={() => setKind(opt.v)}
                style={{
                  padding: '4px 10px', border: 0, borderRadius: 999, fontSize: 12, cursor: 'pointer',
                  background: kind === opt.v ? '#fff' : 'transparent',
                  color: kind === opt.v ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
                  fontFamily: 'var(--font-sans)', fontWeight: kind === opt.v ? 500 : 400,
                  boxShadow: kind === opt.v ? '0 1px 3px rgba(0,0,0,0.12)' : 'none',
                }}
              >
                {opt.l}
              </button>
            ))}
          </div>
        </div>

        {/* Results list */}
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {debouncedQ.length < 2 && (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--db-gray-text)', fontSize: 13 }}>
              Type at least 2 characters to search
            </div>
          )}
          {debouncedQ.length >= 2 && isFetching && (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--db-gray-text)', fontSize: 13 }}>
              Searching…
            </div>
          )}
          {debouncedQ.length >= 2 && isError && (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--db-lava-600)', fontSize: 13 }}>
              Search failed — check that you have SCIM read permissions
            </div>
          )}
          {debouncedQ.length >= 2 && !isFetching && !isError && results.length === 0 && (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--db-gray-text)', fontSize: 13 }}>
              No results found
            </div>
          )}
          {results.map(p => {
            const alreadyAdded = addedIds.has(p.id)
            return (
              <div
                key={p.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 4px', borderBottom: '1px solid var(--db-gray-lines)',
                }}
              >
                <Avatar initials={p.initials} color={p.accent} size={32} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--db-navy-800)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    {p.name}
                    <Pill bg={p.kind === 'group' ? '#BAE1FC' : '#EEEDE9'} color="var(--db-navy-800)">
                      {p.kind === 'group' ? 'Group' : 'User'}
                    </Pill>
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--db-gray-text)', marginTop: 1 }}>
                    {p.kind === 'user' ? (p.email ?? p.id) : `${p.members ?? 0} members`}
                  </div>
                </div>
                <Btn
                  variant={alreadyAdded ? 'ghost' : 'secondary'}
                  size="sm"
                  disabled={alreadyAdded || addMutation.isPending}
                  onClick={() => !alreadyAdded && addMutation.mutate(p)}
                >
                  {alreadyAdded ? <><Icon name="check" size={12} /> Added</> : 'Add'}
                </Btn>
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div style={{ paddingTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
          <Btn variant="ghost" onClick={onClose}>Done</Btn>
        </div>
      </div>
    </div>
  )
}
