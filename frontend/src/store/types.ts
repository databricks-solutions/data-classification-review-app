export const TAG_META: Record<string, { label: string; short: string; color: string; bg: string }> = {
  'class.name':          { label: 'Name',         short: 'Name',   color: '#1B3139', bg: '#EEEDE9' },
  'class.email_address': { label: 'Email address', short: 'Email',  color: '#1B3139', bg: '#EEEDE9' },
  'class.phone_number':  { label: 'Phone number',  short: 'Phone',  color: '#1B3139', bg: '#EEEDE9' },
  'class.location':      { label: 'Location',      short: 'Loc.',   color: '#1B3139', bg: '#EEEDE9' },
  'class.address':       { label: 'Address',       short: 'Addr.',  color: '#1B3139', bg: '#EEEDE9' },
  'class.ssn':           { label: 'SSN',           short: 'SSN',    color: '#1B3139', bg: '#EEEDE9' },
  'class.credit_card':   { label: 'Credit card',   short: 'Card',   color: '#1B3139', bg: '#EEEDE9' },
  'class.date_of_birth': { label: 'Date of birth', short: 'DOB',    color: '#1B3139', bg: '#EEEDE9' },
  'class.ip_address':    { label: 'IP address',    short: 'IP',     color: '#1B3139', bg: '#EEEDE9' },
  'class.gender':        { label: 'Gender',        short: 'Gender', color: '#1B3139', bg: '#EEEDE9' },
  'class.bank_account':  { label: 'Bank account',  short: 'Bank',   color: '#1B3139', bg: '#EEEDE9' },
}

export const ALL_TAGS = Object.keys(TAG_META)

export type ClassificationStatus = 'pending' | 'approved' | 'rejected' | 'modified' | 'applied'
export type DecisionStatus = ClassificationStatus | 'steward_added' | 'steward_removed' | 'scope_added' | 'scope_removed' | 'role_granted' | 'role_revoked'

export const ADMIN_STATUSES = new Set<string>([
  'steward_added', 'steward_removed', 'scope_added', 'scope_removed', 'role_granted', 'role_revoked',
])
export function isAdminEvent(status: string): boolean {
  return ADMIN_STATUSES.has(status)
}

export type PrincipalKind = 'user' | 'group'
export type AssignmentScope = 'catalog' | 'schema' | 'table'
export type AppRole = 'steward' | 'admin'

export const STATUS_STYLE: Record<string, { label: string; bg: string; color: string }> = {
  pending:  { label: 'Pending',  bg: '#FFDB96', color: '#7D5319' },
  approved: { label: 'Approved', bg: '#9ED6C4', color: '#095A35' },
  rejected: { label: 'Rejected', bg: '#FABFBA', color: '#801C17' },
  modified: { label: 'Modified', bg: '#BAE1FC', color: '#04355D' },
  applied:  { label: 'Applied',  bg: '#EEEDE9', color: '#1B3139' },
  steward_added:   { label: 'Steward added',   bg: '#9ED6C4', color: '#095A35' },
  steward_removed: { label: 'Steward removed', bg: '#FABFBA', color: '#801C17' },
  scope_added:     { label: 'Scope added',     bg: '#9ED6C4', color: '#095A35' },
  scope_removed:   { label: 'Scope removed',   bg: '#FABFBA', color: '#801C17' },
  role_granted:    { label: 'Admin granted',   bg: '#9ED6C4', color: '#095A35' },
  role_revoked:    { label: 'Admin revoked',   bg: '#FABFBA', color: '#801C17' },
}

export interface Principal {
  id: string
  name: string
  email?: string
  kind: PrincipalKind
  initials: string
  accent: string
  team?: string
  members?: number
  isAdmin: boolean
  assignmentCount?: number
}

export interface PrincipalSearchResult {
  id: string
  name: string
  email?: string
  kind: PrincipalKind
  initials: string
  accent: string
  members?: number
}

export interface Proposal {
  key: string                      // catalog.schema.table.column
  catalog: string
  schemaName: string
  table: string
  column: string
  dataType: string
  tableKey: string                 // catalog.schema.table
  classTag: string
  confidence: 'HIGH' | 'LOW' | null
  frequency: number | null
  latestDetectedTime?: string
  owner: string                    // steward email
  status: DecisionStatus
  modifiedTag: string | null
  comment: string | null
  reviewer: string | null
  decidedAt: string | null
  userAdded?: boolean
  appliedAt?: string | null
}

export interface TableSummary {
  key: string                      // catalog.schema.table
  catalog: string
  schema: string
  table: string
  owner: string
  lastScan: string
  totalCols: number
  proposalCount: number
  pending: number
  approved: number
  rejected: number
  modified: number
  highConf: number
  lowConf: number
  proposals: Proposal[]
}

export interface ColumnDetail {
  catalog: string
  schemaName: string
  table: string
  column: string
  dataType: string
  tableKey: string
  owner: string
  existingTags: string[]           // already applied in UC
  classTag: string | null          // from classification results
  confidence: 'HIGH' | 'LOW' | null
  frequency: number | null
  columnDescription: string | null
}

export interface ColumnsResponse {
  columns: ColumnDetail[]
  tableDescription: string | null
  tableTags: string[]
  metadataDenied: boolean
  tableTagsDenied: boolean
  columnTagsDenied: boolean
}

export interface ColumnSamples {
  column: string
  samples: string[]
}

export interface TableSamplesResult {
  columns: ColumnSamples[]
  denied: boolean
}

export interface DecisionPatch {
  columnKey: string
  status: DecisionStatus
  modifiedTag?: string | null
  comment?: string | null
  userAdded?: boolean
  classTag?: string | null
}

export interface AuditEntry {
  id?: string
  columnKey: string
  catalog: string
  schemaName: string
  table: string
  column: string
  status: Exclude<DecisionStatus, 'pending'>
  classTag: string
  modifiedTag: string | null
  comment: string | null
  reviewer: string
  decidedAt: string
}

export interface StewardAssignment {
  id: string
  principal: string
  principalKind: PrincipalKind
  scope: AssignmentScope
  catalog: string
  schemaName?: string
  tableName?: string
}

export interface ApplyTagsResult {
  applied: number
  skipped: number
  errors: { columnKey: string; error: string }[]
}

export interface TagConfig {
  key: string
  enabled: boolean
  description?: string
  allowedValues?: string[]
}

export interface TagRefreshResult {
  added: number
  addedEnabled: number
  addedDisabled: number
  total: number
}

export interface TagPatchResult {
  key: string
  enabled: boolean
  activeProposals: number
}

export interface MeResponse {
  id: string
  name: string
  email?: string
  initials: string
  accent: string
  team?: string
  isAdmin: boolean
  isMockMode: boolean
  allUsers?: Principal[]           // only present in mock mode
}
