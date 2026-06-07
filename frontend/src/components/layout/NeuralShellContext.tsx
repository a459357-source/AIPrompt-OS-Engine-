import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

export interface NavTreeItem {
  id: string
  label: string
  icon?: ReactNode
  children?: NavTreeItem[]
}

export interface NeuralShellState {
  navItems: NavTreeItem[]
  activeNavId: string | null
  inspector: ReactNode | null
  leftPanel: ReactNode | null
  showLeftPanel: boolean
  showRightPanel: boolean
  hideShellPanels: boolean
}

interface NeuralShellContextValue extends NeuralShellState {
  setNavItems: (items: NavTreeItem[]) => void
  setActiveNavId: (id: string | null) => void
  setInspector: (content: ReactNode | null) => void
  setLeftPanel: (content: ReactNode | null) => void
  setShowLeftPanel: (show: boolean) => void
  setShowRightPanel: (show: boolean) => void
  setHideShellPanels: (hide: boolean) => void
  resetShell: () => void
}

const defaultState: NeuralShellState = {
  navItems: [],
  activeNavId: null,
  inspector: null,
  leftPanel: null,
  showLeftPanel: true,
  showRightPanel: true,
  hideShellPanels: false,
}

function navItemsEqual(a: NavTreeItem[], b: NavTreeItem[]) {
  if (a === b) return true
  if (a.length !== b.length) return false
  return a.every((item, i) => item.id === b[i]?.id)
}

const NeuralShellContext = createContext<NeuralShellContextValue | null>(null)

export function NeuralShellProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<NeuralShellState>(defaultState)

  const setNavItems = useCallback((items: NavTreeItem[]) => {
    setState((s) => (navItemsEqual(s.navItems, items) ? s : { ...s, navItems: items }))
  }, [])

  const setActiveNavId = useCallback((id: string | null) => {
    setState((s) => (s.activeNavId === id ? s : { ...s, activeNavId: id }))
  }, [])

  const setInspector = useCallback((content: ReactNode | null) => {
    setState((s) => (Object.is(s.inspector, content) ? s : { ...s, inspector: content }))
  }, [])

  const setLeftPanel = useCallback((content: ReactNode | null) => {
    setState((s) => (Object.is(s.leftPanel, content) ? s : { ...s, leftPanel: content }))
  }, [])

  const setShowLeftPanel = useCallback((show: boolean) => {
    setState((s) => (s.showLeftPanel === show ? s : { ...s, showLeftPanel: show }))
  }, [])

  const setShowRightPanel = useCallback((show: boolean) => {
    setState((s) => (s.showRightPanel === show ? s : { ...s, showRightPanel: show }))
  }, [])

  const setHideShellPanels = useCallback((hide: boolean) => {
    setState((s) => (s.hideShellPanels === hide ? s : { ...s, hideShellPanels: hide }))
  }, [])

  const resetShell = useCallback(() => {
    setState(defaultState)
  }, [])

  return (
    <NeuralShellContext.Provider
      value={{
        ...state,
        setNavItems,
        setActiveNavId,
        setInspector,
        setLeftPanel,
        setShowLeftPanel,
        setShowRightPanel,
        setHideShellPanels,
        resetShell,
      }}
    >
      {children}
    </NeuralShellContext.Provider>
  )
}

export function useNeuralShell() {
  const ctx = useContext(NeuralShellContext)
  if (!ctx) throw new Error('useNeuralShell must be used within NeuralShellProvider')
  return ctx
}

export function useNeuralShellOptional() {
  return useContext(NeuralShellContext)
}
