import type {
  Proposal, TableSummary, ColumnsResponse, DecisionPatch,
  AuditEntry, StewardAssignment, Principal, PrincipalSearchResult, ApplyTagsResult, MeResponse,
  TagConfig, TagRefreshResult, TagPatchResult, TableSamplesResult,
} from './types'

const BASE = '/api'

function getMockUserHeader(): Record<string, string> {
  const id = localStorage.getItem('mock_user_id')
  return id ? { 'X-Mock-User': id } : {}
}

// FastAPI/Pydantic returns snake_case; convert all response keys to camelCase.
function snakeToCamel(key: string): string {
  return key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
}

function transformKeys(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(transformKeys)
  if (obj !== null && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [snakeToCamel(k), transformKeys(v)])
    )
  }
  return obj
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...getMockUserHeader(),
      ...(init?.headers as Record<string, string> | undefined),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  const json = await res.json()
  return transformKeys(json) as T
}

// Convert camelCase request body keys to snake_case for the FastAPI backend.
function camelToSnake(key: string): string {
  return key.replace(/([A-Z])/g, (c) => `_${c.toLowerCase()}`)
}

function toSnakeKeys(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(toSnakeKeys)
  if (obj !== null && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [camelToSnake(k), toSnakeKeys(v)])
    )
  }
  return obj
}

function bodyOf(data: unknown): string {
  return JSON.stringify(toSnakeKeys(data))
}

function qs(params: Record<string, string | undefined>): string {
  const p = new URLSearchParams(
    Object.entries(params).filter((e): e is [string, string] => e[1] !== undefined && e[1] !== '')
  )
  return p.size ? `?${p}` : ''
}

export const api = {
  getMe: () => req<MeResponse>('/me'),

  getProposals: (p?: { catalog?: string; schema?: string; table?: string; owner?: string }) =>
    req<Proposal[]>(`/proposals${qs(p ?? {})}`),

  getTables: () => req<TableSummary[]>('/tables'),

  getColumns: (catalog: string, schema: string, table: string) =>
    req<ColumnsResponse>(`/tables/${catalog}/${schema}/${table}/columns`),

  getTableSamples: (catalog: string, schema: string, table: string, columns: string[]) =>
    req<TableSamplesResult>(
      `/tables/${catalog}/${schema}/${table}/samples?${columns.map(c => `columns=${encodeURIComponent(c)}`).join('&')}`
    ),

  postDecisions: (patches: DecisionPatch[]) =>
    req<{ saved: number }>('/decisions', { method: 'POST', body: bodyOf(patches) }),

  getDecisions: (p?: { reviewer?: string; since?: string }) =>
    req<AuditEntry[]>(`/decisions${qs(p ?? {})}`),

  applyTags: (columnKeys: string[], classTags: Record<string, string>) =>
    req<ApplyTagsResult>('/apply-tags', {
      method: 'POST',
      body: JSON.stringify({ column_keys: columnKeys, class_tags: classTags }),
    }),

  getStewards: () => req<Principal[]>('/stewards'),

  getAssignments: (id: string) =>
    req<StewardAssignment[]>(`/stewards/${encodeURIComponent(id)}/assignments`),

  postAssignment: (a: Omit<StewardAssignment, 'id'>) =>
    req<StewardAssignment>('/stewards/assignments', { method: 'POST', body: bodyOf(a) }),

  deleteAssignment: (id: string) =>
    req<void>(`/stewards/assignments/${id}`, { method: 'DELETE' }),

  patchSteward: (id: string, patch: { isAdmin: boolean }) =>
    req<Principal>(`/stewards/${encodeURIComponent(id)}`, {
      method: 'PATCH', body: bodyOf({ isAdmin: patch.isAdmin }),
    }),

  deleteSteward: (id: string) =>
    req<void>(`/stewards/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  searchStewards: (q: string, kind: 'user' | 'group' | 'all' = 'all') =>
    req<PrincipalSearchResult[]>(`/stewards/search?q=${encodeURIComponent(q)}&kind=${kind}`),

  postSteward: (p: PrincipalSearchResult) =>
    req<Principal>('/stewards', { method: 'POST', body: bodyOf(p) }),

  getTags: (enabledOnly?: boolean) =>
    req<TagConfig[]>(`/tags${enabledOnly ? '?enabled_only=true' : ''}`),

  refreshTags: () =>
    req<TagRefreshResult>('/tags/refresh', { method: 'POST' }),

  patchTag: (key: string, enabled: boolean, force = false) =>
    req<TagPatchResult>(`/tags/${encodeURIComponent(key)}`, {
      method: 'PATCH',
      body: bodyOf({ enabled, force }),
    }),
}
