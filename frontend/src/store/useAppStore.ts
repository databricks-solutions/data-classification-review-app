import { create } from 'zustand'
import type { Principal, DecisionPatch, AppRole } from './types'

// Admins can toggle between "Admin view" and "Steward view" (AppTopBar). That
// choice must survive a page refresh, so it's mirrored to sessionStorage —
// otherwise setIdentity() below would always reset an admin back to 'admin'
// on reload, kicking them out of any steward-only route they were viewing.
const VIEW_ROLE_KEY = 'view_role'

function loadStoredViewRole(): AppRole | null {
  const stored = sessionStorage.getItem(VIEW_ROLE_KEY)
  return stored === 'admin' || stored === 'steward' ? stored : null
}

interface AppState {
  currentUser: Principal | null
  role: AppRole
  isAdmin: boolean
  isMockMode: boolean
  allMockUsers: Principal[]

  localDecisions: Record<string, DecisionPatch>   // columnKey → patch
  userProposed: Record<string, string[]>           // columnKey → tag[]

  setIdentity: (user: Principal, isMockMode: boolean, allUsers?: Principal[]) => void
  setRole: (role: AppRole) => void
  applyLocalDecision: (columnKey: string, patch: Omit<DecisionPatch, 'columnKey'>) => void
  undoLocalDecision: (columnKey: string) => void
  toggleUserTag: (columnKey: string, tag: string) => void
  removeUserTag: (columnKey: string, tag: string) => void
  clearLocalState: () => void
  switchMockUser: (userId: string) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  currentUser: null,
  role: 'steward',
  isAdmin: false,
  isMockMode: false,
  allMockUsers: [],
  localDecisions: {},
  userProposed: {},

  setIdentity: (user, isMockMode, allUsers = []) => {
    if (isMockMode) localStorage.setItem('mock_user_id', user.id)
    set({
      currentUser: user,
      isAdmin: user.isAdmin,
      role: user.isAdmin ? (loadStoredViewRole() ?? 'admin') : 'steward',
      isMockMode,
      allMockUsers: allUsers,
    })
  },

  setRole: (role) => {
    sessionStorage.setItem(VIEW_ROLE_KEY, role)
    set({ role })
  },

  applyLocalDecision: (columnKey, patch) =>
    set(s => ({
      localDecisions: { ...s.localDecisions, [columnKey]: { columnKey, ...patch } },
    })),

  undoLocalDecision: (columnKey) =>
    set(s => {
      const next = { ...s.localDecisions }
      delete next[columnKey]
      return { localDecisions: next }
    }),

  toggleUserTag: (columnKey, tag) =>
    set(s => {
      const cur = s.userProposed[columnKey] ?? []
      const next = cur.includes(tag) ? cur.filter(t => t !== tag) : [...cur, tag]
      const proposed = { ...s.userProposed }
      if (next.length === 0) delete proposed[columnKey]
      else proposed[columnKey] = next
      return { userProposed: proposed }
    }),

  removeUserTag: (columnKey, tag) =>
    set(s => {
      const cur = s.userProposed[columnKey] ?? []
      const next = cur.filter(t => t !== tag)
      const proposed = { ...s.userProposed }
      if (next.length === 0) delete proposed[columnKey]
      else proposed[columnKey] = next
      return { userProposed: proposed }
    }),

  clearLocalState: () => set({ localDecisions: {}, userProposed: {} }),

  switchMockUser: (userId) => {
    localStorage.setItem('mock_user_id', userId)
    const user = get().allMockUsers.find(u => u.id === userId)
    if (user) {
      set({
        currentUser: user,
        isAdmin: user.isAdmin,
        role: user.isAdmin ? 'admin' : 'steward',
        localDecisions: {},
        userProposed: {},
      })
    }
  },
}))
