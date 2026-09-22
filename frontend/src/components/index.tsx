import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { TAG_META, STATUS_STYLE, type DecisionStatus, type TableSamplesResult } from '../store/types'

// ── Icon ─────────────────────────────────────────────────────────────────────

const ICON_PATHS: Record<string, string> = {
  // nav
  inbox: 'M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z',
  table: 'M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18',
  chart: 'M3 3v18h18M7 14l4-4 4 4 5-5',
  audit: 'M9 12l2 2 4-4M21 12c0 4.5-3.5 8.5-9 9-5.5-.5-9-4.5-9-9 0-4 3.5-8 9-9 5.5 1 9 5 9 9z',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
  // workspace rail
  home: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2h-4v-7H10v7H6a2 2 0 0 1-2-2V9z',
  workspace: 'M3 7h18M3 12h18M3 17h18',
  catalog: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  notebook: 'M4 4h12a2 2 0 0 1 2 2v14H6a2 2 0 0 1-2-2V4zM4 4v16',
  sql: 'M4 6c0-1.1 3.6-2 8-2s8 .9 8 2-3.6 2-8 2-8-.9-8-2zM4 6v6c0 1.1 3.6 2 8 2s8-.9 8-2V6M4 12v6c0 1.1 3.6 2 8 2s8-.9 8-2v-6',
  bot: 'M8 4h8a4 4 0 0 1 4 4v8a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8a4 4 0 0 1 4-4zM9 11v1M15 11v1M9 16h6',
  dash: 'M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z',
  job: 'M4 5h16v3H4zM4 11h16v3H4zM4 17h10v3H4z',
  compute: 'M5 3h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM8 21h8M12 17v4',
  apps: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  // ui
  search: 'M21 21l-5-5M3 11a8 8 0 1 0 16 0 8 8 0 0 0-16 0z',
  bell: 'M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9zM10 21a2 2 0 0 0 4 0',
  check: 'M5 13l4 4 10-10',
  x: 'M18 6L6 18M6 6l12 12',
  edit: 'M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z',
  comment: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
  chev: 'M9 6l6 6-6 6',
  chevDown: 'M6 9l6 6 6-6',
  chevUp: 'M18 15l-6-6-6 6',
  plus: 'M12 5v14M5 12h14',
  filter: 'M22 3H2l8 9.5V19l4 2v-8.5L22 3z',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  arrowLeft: 'M19 12H5M11 6l-6 6 6 6',
  eye: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  eyeOff: 'M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a17.92 17.92 0 0 1 4.27-5.06m5.43-1.81A10.43 10.43 0 0 1 12 4c7 0 11 8 11 8a17.78 17.78 0 0 1-3.06 4.24M9.9 4.24A9.12 9.12 0 0 1 12 4M1 1l22 22M14.12 14.12a3 3 0 1 1-4.24-4.24',
  user: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2',
  tag: 'M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01',
  upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12',
  play: 'M5 3l14 9-14 9V3z',
  sparkle: 'M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z',
  download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3',
  refresh: 'M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15',
  info: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01',
  list: 'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z',
  columns: 'M9 3H4a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h5V3zM20 3h-5v18h5a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1z',
  db: 'M12 8c5 0 9-1.5 9-3.5S17 1 12 1 3 2.5 3 4.5 7 8 12 8zM3 4.5v15c0 2 4 3.5 9 3.5s9-1.5 9-3.5v-15M3 12c0 2 4 3.5 9 3.5s9-1.5 9-3.5',
  flag: 'M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7',
  spark: 'M12 3l2 7 7 2-7 2-2 7-2-7-7-2 7-2z',
  // tags taxonomy
  pii: 'M9 12l2 2 4-4M21 12c0 4.5-3.5 8.5-9 9-5.5-.5-9-4.5-9-9 0-4 3.5-8 9-9 5.5 1 9 5 9 9z',
  sortDesc: 'M3 6h13M3 12h9M3 18h5M14 14l4 4 4-4M18 8v10',
  moreH: 'M5 12a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM12 12a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM19 12a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
  minus: 'M5 12h14',
  'user-plus': 'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M8.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM20 8v6M23 11h-6',
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  'trash-2': 'M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6',
}

interface IconProps {
  name: string
  size?: number
  color?: string
  stroke?: number
  style?: CSSProperties
}

export function Icon({ name, size = 16, color = 'currentColor', stroke = 1.6, style }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }}>
      <path d={ICON_PATHS[name] ?? ICON_PATHS['inbox']} />
    </svg>
  )
}

// ── Pill ──────────────────────────────────────────────────────────────────────

interface PillProps {
  children: ReactNode
  bg?: string
  color?: string
  dot?: boolean
  style?: CSSProperties
}

export function Pill({ children, bg = '#EEEDE9', color = '#1B3139', dot, style }: PillProps) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontSize: 11, fontWeight: 500, padding: '3px 9px',
      borderRadius: 999, background: bg, color, lineHeight: 1.3,
      fontFamily: 'var(--font-sans)', ...style,
    }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />}
      {children}
    </span>
  )
}

// ── StatusPill ────────────────────────────────────────────────────────────────

export function StatusPill({ status }: { status: DecisionStatus }) {
  const s = STATUS_STYLE[status]
  return <Pill bg={s.bg} color={s.color} dot>{s.label}</Pill>
}

// ── ConfidencePill ────────────────────────────────────────────────────────────

export function ConfidencePill({ level }: { level: 'HIGH' | 'LOW' | null }) {
  if (level === 'HIGH') return (
    <Pill bg="#EEEDE9" color="#1B3139" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.04em' }}>HIGH</Pill>
  )
  if (level === 'LOW') return (
    <Pill bg="#FFDB96" color="#7D5319" style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.04em' }}>LOW</Pill>
  )
  return null
}

// ── TagPill ───────────────────────────────────────────────────────────────────

export function TagPill({ tag, size = 'md' }: { tag: string; size?: 'sm' | 'md' }) {
  const meta = TAG_META[tag] ?? { color: '#1B3139', bg: '#EEEDE9' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--font-mono)', fontSize: size === 'sm' ? 10 : 11,
      padding: size === 'sm' ? '2px 8px' : '3px 10px',
      borderRadius: 4, background: meta.bg, color: meta.color, fontWeight: 500,
    }}>
      <span style={{ width: 4, height: 4, borderRadius: '50%', background: meta.color, flexShrink: 0 }} />
      {tag}
    </span>
  )
}

// ── Btn ───────────────────────────────────────────────────────────────────────

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'plain' | 'danger' | 'success'
type BtnSize = 'sm' | 'md' | 'lg'

const BTN_SIZE: Record<BtnSize, CSSProperties> = {
  sm: { padding: '5px 10px', fontSize: 12, gap: 5 },
  md: { padding: '7px 14px', fontSize: 13, gap: 6 },
  lg: { padding: '9px 18px', fontSize: 14, gap: 8 },
}

const BTN_VARIANT: Record<BtnVariant, CSSProperties> = {
  primary:   { background: 'var(--db-lava-600)',  color: '#fff', border: 'none' },
  secondary: { background: 'var(--db-navy-800)',  color: '#fff', border: 'none' },
  ghost:     { background: 'transparent', color: 'var(--db-navy-800)', border: '1px solid var(--db-gray-lines)' },
  plain:     { background: 'transparent', color: 'var(--db-navy-800)', border: 'none' },
  danger:    { background: 'transparent', color: 'var(--db-lava-700)', border: '1px solid var(--db-lava-300)' },
  success:   { background: 'var(--db-green-700)', color: '#fff', border: 'none' },
}

const BTN_HOVER: Record<BtnVariant, string> = {
  primary:   'var(--db-lava-700)',
  secondary: 'var(--db-navy-900)',
  ghost:     'var(--db-oat-medium)',
  plain:     'var(--db-oat-medium)',
  danger:    '#FABFBA',
  success:   '#095A35',
}

interface BtnProps {
  children: ReactNode
  variant?: BtnVariant
  size?: BtnSize
  onClick?: () => void
  disabled?: boolean
  title?: string
  style?: CSSProperties
  type?: 'button' | 'submit' | 'reset'
}

export function Btn({ children, variant = 'ghost', size = 'md', onClick, disabled, title, style, type = 'button' }: BtnProps) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: 6, cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'var(--font-sans)', fontWeight: 500,
        transition: 'all var(--dur-base) var(--ease-out)',
        opacity: disabled ? 0.5 : 1, whiteSpace: 'nowrap',
        ...BTN_SIZE[size], ...BTN_VARIANT[variant], ...style,
      }}
      onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = BTN_HOVER[variant] }}
      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = String(BTN_VARIANT[variant].background) }}
    >
      {children}
    </button>
  )
}

// ── AssetPath ─────────────────────────────────────────────────────────────────

export function AssetPath({ catalog, schema, table, column, size = 13 }: {
  catalog: string; schema: string; table: string; column?: string; size?: number
}) {
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: size, color: 'var(--db-navy-800)', whiteSpace: 'nowrap' }}>
      <span style={{ color: 'var(--db-gray-text)' }}>
        {catalog}<span style={{ margin: '0 1px', color: 'var(--db-navy-400)' }}>.</span>
        {schema}<span style={{ margin: '0 1px', color: 'var(--db-navy-400)' }}>.</span>
      </span>
      <span>{table}</span>
      {column && (
        <span style={{ color: 'var(--db-navy-400)' }}>
          .<span style={{ color: 'var(--db-navy-800)' }}>{column}</span>
        </span>
      )}
    </span>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────────────

export function Spinner({ size = 16, color = 'var(--db-gray-text)' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={2.2} strokeLinecap="round"
      style={{ animation: 'spin 0.75s linear infinite', flexShrink: 0 }}>
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  )
}

// ── Avatar ────────────────────────────────────────────────────────────────────

export function Avatar({ initials, color = '#FF3621', size = 28, fontSize }: {
  initials: string; color?: string; size?: number; fontSize?: number
}) {
  return (
    <div style={{
      width: size, height: size, borderRadius: 999, background: color, color: '#fff',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 600, fontSize: fontSize ?? Math.round(size * 0.42),
      letterSpacing: 0.2, flexShrink: 0,
    }}>
      {initials}
    </div>
  )
}

// ── SearchableSelect ──────────────────────────────────────────────────────────

export function SearchableSelect({ value, onChange, options, placeholder, disabled }: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  placeholder?: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const selectedLabel = options.find(o => o.value === value)?.label ?? ''
  const filtered = query
    ? options.filter(o => o.label.toLowerCase().includes(query.toLowerCase()))
    : options

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0)
  }, [open])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      <div
        onClick={() => { if (!disabled) setOpen(o => !o) }}
        style={{
          padding: '8px 12px', border: '1px solid var(--db-gray-lines)', borderRadius: 6,
          background: disabled ? 'var(--db-oat-medium)' : '#fff',
          cursor: disabled ? 'not-allowed' : 'pointer', userSelect: 'none',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
          fontSize: 13, fontFamily: 'var(--font-sans)',
          color: value ? 'var(--db-navy-800)' : 'var(--db-gray-text)',
          boxSizing: 'border-box',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {value ? selectedLabel : (placeholder ?? 'Select…')}
        </span>
        <Icon name={open ? 'chevUp' : 'chevDown'} size={13} color="var(--db-gray-text)" style={{ flexShrink: 0 }} />
      </div>
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 200,
          background: '#fff', border: '1px solid var(--db-gray-lines)', borderRadius: 6,
          boxShadow: '0 4px 16px rgba(0,0,0,0.12)', overflow: 'hidden',
        }}>
          <div style={{ padding: '7px 8px', borderBottom: '1px solid var(--db-gray-lines)' }}>
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search…"
              style={{
                width: '100%', padding: '5px 8px', fontSize: 12.5,
                border: '1px solid var(--db-gray-lines)', borderRadius: 4,
                fontFamily: 'var(--font-sans)', outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ maxHeight: 220, overflowY: 'auto' }}>
            {filtered.length === 0 ? (
              <div style={{ padding: '10px 12px', fontSize: 12.5, color: 'var(--db-gray-text)' }}>
                No matches
              </div>
            ) : filtered.map(o => (
              <div
                key={o.value}
                onMouseDown={e => { e.preventDefault(); onChange(o.value); setOpen(false); setQuery('') }}
                style={{
                  padding: '8px 12px', cursor: 'pointer', fontSize: 13,
                  fontFamily: 'var(--font-mono)',
                  color: o.value === value ? 'var(--db-lava-600)' : 'var(--db-navy-800)',
                  background: o.value === value ? 'var(--db-oat-light)' : 'transparent',
                  fontWeight: o.value === value ? 500 : 400,
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--db-oat-light)' }}
                onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = o.value === value ? 'var(--db-oat-light)' : 'transparent' }}
              >
                {o.label}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── SamplesBlock / SamplesStatus ───────────────────────────────────────────────

export function SamplesBlock({ samples }: { samples: string[] | undefined }) {
  const items = (samples ?? []).slice(0, 5)
  if (items.length === 0) {
    return (
      <span style={{ fontSize: 12, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
        No samples captured.
      </span>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {items.map((s, i) => (
        <div key={`${i}:${s}`} style={{
          background: 'var(--db-oat-light)', border: '1px solid var(--db-gray-lines)',
          borderRadius: 4, padding: '6px 10px',
          fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--db-navy-800)',
          whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.5,
          maxHeight: 100, overflow: 'hidden', position: 'relative',
        }}>
          {s}
          {s.length > 200 && (
            <div style={{
              position: 'absolute', bottom: 0, left: 0, right: 0, height: 26,
              background: 'linear-gradient(to bottom, transparent, var(--db-oat-light))',
            }} />
          )}
        </div>
      ))}
      {(samples?.length ?? 0) > 5 && (
        <div style={{ fontSize: 11, color: 'var(--db-gray-text)' }}>
          + {(samples?.length ?? 0) - 5} more samples
        </div>
      )}
    </div>
  )
}

// Renders the "Detected samples" heading plus the not-fetched/loading/denied/data
// states shared by every column-level samples display (proposal rows and the
// propose-tags list) so the four-state logic lives in exactly one place.
export function SamplesStatus({ samplesData, samplesLoading, column, description, descriptionDenied }: {
  samplesData: TableSamplesResult | undefined
  samplesLoading: boolean
  column: string
  description?: string | null
  descriptionDenied?: boolean
}) {
  const colSamples = samplesData?.columns.find(c => c.column === column)?.samples
  return (
    <>
      {(description !== undefined || descriptionDenied) && (
        <div style={{ marginBottom: 10 }}>
          <div style={{
            fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
            letterSpacing: '0.06em', fontWeight: 500, marginBottom: 6,
          }}>Column description</div>
          {descriptionDenied ? (
            <div style={{ fontSize: 12, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
              Ask to admins to grant BROWSE permission to allow you to see object metadata.
            </div>
          ) : description ? (
            <div style={{ fontSize: 12.5, color: 'var(--db-navy-800)', lineHeight: 1.5 }}>
              {description}
            </div>
          ) : (
            <div style={{ fontSize: 12.5, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
              No description available
            </div>
          )}
        </div>
      )}
      <div style={{
        fontSize: 11, color: 'var(--db-gray-text)', textTransform: 'uppercase',
        letterSpacing: '0.06em', fontWeight: 500, marginBottom: 8,
      }}>
        Detected samples{samplesData && !samplesData.denied && ` (${(colSamples || []).length})`}
      </div>
      {samplesLoading ? (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--db-gray-text)' }}>
          <Spinner size={13} /> Loading samples…
        </span>
      ) : !samplesData ? (
        <span style={{ fontSize: 12, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
          Click "Get samples" above to load sample values for this table.
        </span>
      ) : samplesData.denied ? (
        <span style={{ fontSize: 12, color: 'var(--db-gray-text)', fontStyle: 'italic' }}>
          You don't have permission to see samples for this table.
        </span>
      ) : (
        <SamplesBlock samples={colSamples} />
      )}
    </>
  )
}

// ── FilterChip ────────────────────────────────────────────────────────────────

export function FilterChip({ label, value, options, onChange }: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (v: string) => void
}) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: '#fff', border: '1px solid var(--db-gray-lines)',
      borderRadius: 999, padding: '5px 10px 5px 12px', fontSize: 12.5,
    }}>
      <span style={{ color: 'var(--db-gray-text)', fontWeight: 500 }}>{label}:</span>
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{ border: 'none', background: 'transparent', fontSize: 12.5,
          fontFamily: 'var(--font-sans)', color: 'var(--db-navy-800)', cursor: 'pointer', outline: 'none' }}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}
