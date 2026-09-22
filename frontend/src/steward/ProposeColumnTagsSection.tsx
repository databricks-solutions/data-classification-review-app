import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Icon, TagPill, Btn, Spinner, SamplesStatus } from '../components'
import { api } from '../store/api'
import { useAppStore } from '../store/useAppStore'
import { type ColumnDetail, type TagConfig, type TableSamplesResult } from '../store/types'

const GRID = '24px minmax(180px, 1.4fr) 110px minmax(220px, 1.6fr) 120px'

interface ProposeColumnTagsSectionProps {
  columns: ColumnDetail[]
  columnsLoading: boolean
  samplesData: TableSamplesResult | undefined
  samplesLoading: boolean
  tableTags: string[]
  tableTagsDenied: boolean
  metadataDenied: boolean
  columnTagsDenied: boolean
}

export function ProposeColumnTagsSection({
  columns, columnsLoading, samplesData, samplesLoading, tableTags, tableTagsDenied, metadataDenied, columnTagsDenied,
}: ProposeColumnTagsSectionProps) {
  const userProposed = useAppStore(s => s.userProposed)
  const toggleUserTag = useAppStore(s => s.toggleUserTag)
  const removeUserTag = useAppStore(s => s.removeUserTag)
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set())

  const { data: enabledTagConfigs = [], isError: tagsError, isLoading: tagsLoading } = useQuery({
    queryKey: ['tags', 'enabled'],
    queryFn: () => api.getTags(true),
    staleTime: 5 * 60_000,
  })

  return (
    <div style={{ marginTop: 40 }}>
      <div style={{ marginBottom: 14 }}>
        <h3 style={{
          fontSize: 16, fontWeight: 500, color: 'var(--db-navy-800)',
          margin: 0, letterSpacing: '-0.005em',
        }}>
          Propose column tags
        </h3>
      </div>

      <div style={{
        background: '#fff', border: '1px solid var(--db-gray-lines)',
        borderRadius: 8, overflow: 'hidden',
      }}>
        <div style={{
          padding: '10px 16px', borderBottom: '1px solid var(--db-gray-lines)',
          display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
        }}>
          <span style={{
            fontSize: 10.5, fontWeight: 500, color: 'var(--db-gray-text)',
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>Table tags</span>
          {(tableTagsDenied || metadataDenied) ? (
            <span style={{ fontSize: 11.5, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
              Ask to admins to grant BROWSE permission to allow you to see object metadata.
            </span>
          ) : tableTags.length === 0 ? (
            <span style={{ fontSize: 11.5, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>No tags applied</span>
          ) : tableTags.map(t => <TagPill key={t} tag={tagDisplayKey(t)} size="sm" />)}
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: GRID,
          alignItems: 'center', gap: 12,
          padding: '10px 16px', background: 'var(--db-oat-medium)',
          borderBottom: '1px solid var(--db-gray-lines)',
          fontSize: 10.5, fontWeight: 500, color: 'var(--db-gray-text)',
          textTransform: 'uppercase', letterSpacing: '0.06em',
        }}>
          <div></div>
          <div>Column</div>
          <div>Type</div>
          <div>Tags</div>
          <div style={{ textAlign: 'right' }}>Propose</div>
        </div>

        {columnsLoading ? (
          <div style={{
            padding: '20px 16px', display: 'flex', alignItems: 'center', gap: 8,
            color: 'var(--db-gray-text)', fontSize: 12.5,
            borderTop: '1px solid var(--db-gray-lines)',
          }}>
            <Spinner size={14} /> Loading columns…
          </div>
        ) : columns.map(c => {
          const colKey = `${c.catalog}.${c.schemaName}.${c.table}.${c.column}`
          const userTags = userProposed[colKey] ?? []
          const detectedTag = c.classTag
          const existing = c.existingTags ?? []

          return (
            <ColumnRow
              key={colKey}
              column={c}
              userTags={userTags}
              detectedTag={detectedTag}
              existingTags={existing}
              availableTags={enabledTagConfigs}
              tagsLoading={tagsLoading}
              tagsError={tagsError}
              isOpen={expanded.has(colKey)}
              onToggleExpand={() => {
                const n = new Set(expanded)
                if (n.has(colKey)) n.delete(colKey); else n.add(colKey)
                setExpanded(n)
              }}
              samplesData={samplesData}
              samplesLoading={samplesLoading}
              metadataDenied={metadataDenied}
              columnTagsDenied={columnTagsDenied}
              onToggleTag={(tag) => toggleUserTag(colKey, tag)}
              onRemoveTag={(tag) => removeUserTag(colKey, tag)}
            />
          )
        })}
      </div>
    </div>
  )
}

interface ColumnRowProps {
  column: ColumnDetail
  userTags: string[]
  detectedTag: string | null
  existingTags: string[]
  availableTags: TagConfig[]
  tagsLoading: boolean
  tagsError: boolean
  isOpen: boolean
  onToggleExpand: () => void
  samplesData: TableSamplesResult | undefined
  samplesLoading: boolean
  metadataDenied: boolean
  columnTagsDenied: boolean
  onToggleTag: (tag: string) => void
  onRemoveTag: (tag: string) => void
}

// Extract display key from "key=value" or plain "key"
function tagDisplayKey(tagStr: string): string {
  const idx = tagStr.indexOf('=')
  return idx > 0 ? tagStr.substring(0, idx) : tagStr
}

function ColumnRow({
  column: c, userTags, detectedTag, existingTags, availableTags,
  tagsLoading, tagsError, isOpen, onToggleExpand, samplesData, samplesLoading, metadataDenied, columnTagsDenied,
  onToggleTag, onRemoveTag,
}: ColumnRowProps) {
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!dropdownOpen) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [dropdownOpen])

  useEffect(() => {
    if (!dropdownOpen) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setDropdownOpen(false) }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [dropdownOpen])

  const lockedTags: { tag: string; key: string }[] = []
  for (const t of existingTags) lockedTags.push({ tag: t, key: `existing:${t}` })
  if (detectedTag && !existingTags.includes(detectedTag)) {
    lockedTags.push({ tag: detectedTag, key: `detected:${detectedTag}` })
  }

  const hasAnyTag = lockedTags.length > 0 || userTags.length > 0

  return (
    <div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: GRID,
        alignItems: 'center', gap: 12,
        padding: '12px 16px', borderTop: '1px solid var(--db-gray-lines)',
      }}>
        <button
          onClick={onToggleExpand}
          style={{
            background: 'transparent', border: 0, cursor: 'pointer',
            color: 'var(--db-gray-text)', padding: 4, display: 'flex',
          }}
          title={isOpen ? 'Collapse' : 'Expand'}
        >
          <Icon name={isOpen ? 'chevDown' : 'chev'} size={14} />
        </button>

        <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 12.5, color: 'var(--db-navy-800)',
        fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{c.column}</div>

      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--db-gray-text)',
      }}>{c.dataType}</div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
        {!hasAnyTag && (
          columnTagsDenied ? (
            <span style={{ fontSize: 11.5, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
              Ask to admins to grant BROWSE permission to allow you to see object metadata.
            </span>
          ) : (
            <span style={{ fontSize: 11.5, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
              No tags
            </span>
          )
        )}
        {lockedTags.map(({ tag, key }) => (
          <span key={key} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <TagPill tag={tag} size="sm" />
          </span>
        ))}
        {userTags.map(tag => (
          <span key={`user:${tag}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <TagPill tag={tagDisplayKey(tag)} size="sm" />
            <button
              onClick={() => onRemoveTag(tag)}
              title="Remove this tag"
              style={{
                background: 'transparent', border: 0, padding: 2, cursor: 'pointer',
                color: 'var(--db-gray-text)', display: 'inline-flex',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--db-lava-700)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--db-gray-text)' }}
            >
              <Icon name="x" size={11} stroke={2.4} />
            </button>
          </span>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', position: 'relative' }} ref={containerRef}>
        <Btn
          variant={dropdownOpen ? 'secondary' : 'ghost'}
          size="sm"
          onClick={() => setDropdownOpen(o => !o)}
        >
          <Icon name="plus" size={12} color={dropdownOpen ? '#fff' : 'currentColor'} /> Add tag
        </Btn>

        {dropdownOpen && (
          <TagPickerDropdown
            availableTags={availableTags}
            userTags={userTags}
            detectedTag={detectedTag}
            tagsLoading={tagsLoading}
            tagsError={tagsError}
            onToggleTag={onToggleTag}
          />
        )}
        </div>
      </div>

      {isOpen && (
        <div style={{
          borderTop: '1px solid var(--db-gray-lines)',
          padding: '16px 24px 18px 48px', background: 'var(--db-oat-light)',
        }}>
          <SamplesStatus samplesData={samplesData} samplesLoading={samplesLoading} column={c.column}
            description={c.columnDescription} descriptionDenied={metadataDenied} />
        </div>
      )}
    </div>
  )
}

function TagPickerDropdown({
  availableTags, userTags, detectedTag, tagsLoading, tagsError, onToggleTag,
}: {
  availableTags: TagConfig[]
  userTags: string[]
  detectedTag: string | null
  tagsLoading: boolean
  tagsError: boolean
  onToggleTag: (tag: string) => void
}) {
  const [search, setSearch] = useState('')
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { if (!tagsLoading && !tagsError) inputRef.current?.focus() }, [tagsLoading, tagsError])

  const q = search.toLowerCase()
  const filtered = q
    ? availableTags.filter(t => t.key.toLowerCase().includes(q))
    : availableTags

  // Selected tag keys (strip "=value" suffix for lookup)
  const selectedKeys = new Set(userTags.map(tagDisplayKey))

  return (
    <div style={{
      position: 'absolute', top: '100%', right: 0, marginTop: 4,
      width: 300, zIndex: 100,
      background: '#fff', border: '1px solid var(--db-gray-lines)',
      borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
      overflow: 'hidden',
    }}>
      {/* Search — hidden when no tags to search */}
      {!tagsError && !tagsLoading && availableTags.length > 0 && <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', borderBottom: '1px solid var(--db-gray-lines)',
      }}>
        <Icon name="search" size={13} color="var(--db-gray-text)" />
        <input
          ref={inputRef}
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search tags…"
          style={{
            flex: 1, border: 'none', outline: 'none', fontSize: 12.5,
            fontFamily: 'var(--font-sans)', color: 'var(--db-navy-800)',
            background: 'transparent',
          }}
        />
        {search && (
          <button
            onMouseDown={e => { e.preventDefault(); setSearch('') }}
            style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 0, display: 'flex', color: 'var(--db-gray-text)' }}
          >
            <Icon name="x" size={12} />
          </button>
        )}
      </div>}

      {/* Tag list */}
      <div style={{ maxHeight: 300, overflowY: 'auto' }}>
        {tagsLoading ? (
          <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--db-gray-text)' }}>
            <Spinner size={13} /> Loading tags…
          </div>
        ) : tagsError ? (
          <div style={{ padding: '12px 14px', fontSize: 12, color: 'var(--db-lava-700)' }}>
            Unable to load tags. Contact your admin to ensure tags are configured.
          </div>
        ) : availableTags.length === 0 ? (
          <div style={{ padding: '12px 14px', fontSize: 12, color: 'var(--db-gray-text)' }}>
            No tags are enabled. Ask your admin to configure available tags in the Tags section.
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: '12px 14px', fontSize: 12, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
            No tags match your search.
          </div>
        ) : filtered.map(tc => {
          const isDetected = detectedTag === tc.key
          const isSelected = selectedKeys.has(tc.key)
          const hasValues = !!(tc.allowedValues && tc.allowedValues.length > 0)
          const isExpanded = expandedKey === tc.key
          const selectedValue = userTags.find(t => tagDisplayKey(t) === tc.key && t.includes('='))?.split('=')[1]
          const rowBg = isSelected ? 'var(--db-oat-light)' : 'transparent'

          return (
            <div key={tc.key}>
              <button
                onMouseDown={e => e.preventDefault()}
                onClick={() => {
                  if (isDetected) return
                  if (hasValues) {
                    setExpandedKey(isExpanded ? null : tc.key)
                  } else {
                    onToggleTag(tc.key)
                  }
                }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  width: '100%', padding: '8px 12px', border: 'none',
                  background: rowBg, cursor: isDetected ? 'default' : 'pointer', textAlign: 'left',
                }}
                onMouseEnter={e => { if (!isDetected) (e.currentTarget as HTMLButtonElement).style.background = 'var(--db-oat-medium)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = rowBg }}
              >
                <span style={{
                  width: 14, height: 14, borderRadius: 3, flexShrink: 0,
                  border: isSelected ? 'none' : '1.5px solid var(--db-gray-lines)',
                  background: isSelected ? 'var(--db-lava-600)' : 'transparent',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {isSelected && <Icon name="check" size={9} color="#fff" stroke={3} />}
                </span>
                <TagPill tag={tc.key} size="sm" />
                {selectedValue && (
                  <span style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)',
                    background: 'var(--db-oat-medium)', padding: '1px 6px',
                    borderRadius: 3, color: 'var(--db-navy-800)',
                  }}>{selectedValue}</span>
                )}
                {isDetected && (
                  <span style={{
                    marginLeft: 'auto', fontSize: 9, color: 'var(--db-gray-text)',
                    textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500,
                  }}>detected</span>
                )}
                {hasValues && !isDetected && (
                  <Icon name={isExpanded ? 'chevDown' : 'chev'} size={12}
                    color="var(--db-gray-text)" style={{ marginLeft: 'auto' }} />
                )}
              </button>

              {/* Value sub-rows for constrained tags */}
              {hasValues && isExpanded && (
                <div style={{ background: 'var(--db-oat-light)', borderTop: '1px solid var(--db-gray-lines)' }}>
                  {tc.allowedValues!.map(val => {
                    const tagVal = `${tc.key}=${val}`
                    const isValSelected = userTags.includes(tagVal)
                    return (
                      <button
                        key={val}
                        onMouseDown={e => e.preventDefault()}
                        onClick={() => {
                          // Replace any existing value selection for this key
                          const prev = userTags.find(t => tagDisplayKey(t) === tc.key)
                          if (prev && prev !== tagVal) onToggleTag(prev)
                          onToggleTag(tagVal)
                          setExpandedKey(null)
                        }}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          width: '100%', padding: '7px 12px 7px 36px', border: 'none',
                          background: isValSelected ? '#E8F0FE' : 'transparent',
                          cursor: 'pointer', textAlign: 'left',
                        }}
                        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--db-oat-medium)' }}
                        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = isValSelected ? '#E8F0FE' : 'transparent' }}
                      >
                        <span style={{
                          width: 12, height: 12, borderRadius: '50%', flexShrink: 0,
                          border: isValSelected ? 'none' : '1.5px solid var(--db-gray-lines)',
                          background: isValSelected ? 'var(--db-lava-600)' : 'transparent',
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          {isValSelected && <Icon name="check" size={8} color="#fff" stroke={3} />}
                        </span>
                        <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--db-navy-800)' }}>
                          {val}
                        </span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div style={{
        padding: '6px 12px', borderTop: '1px solid var(--db-gray-lines)',
        fontSize: 11, color: 'var(--db-gray-text)',
      }}>
        {userTags.length > 0
          ? `${userTags.length} tag${userTags.length > 1 ? 's' : ''} selected`
          : 'Click to select tags'}
      </div>
    </div>
  )
}
