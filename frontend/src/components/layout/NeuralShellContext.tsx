import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

export interface NavTreeItem {
  id: string
  label: string
  icon?: ReactNode
  children?: NavTreeItem[]
}

export interface NeuralShellLayout {
  navItems: NavTreeItem[]
  activeNavId: string | null
  showLeftPanel: boolean
  showRightPanel: boolean
  hideShellPanels: boolean
}

export interface NeuralShellSlots {
  inspector: ReactNode | null
  leftPanel: ReactNode | null
}

export interface PageShellSync extends Partial<NeuralShellLayout>, Partial<NeuralShellSlots> {
  onNavSelect?: (id: string) => void
}

interface PageShellActions {
  syncPageShell: (patch: PageShellSync) => void
  resetShell: () => void
}

interface NeuralShellDisplay {
  layout: NeuralShellLayout
  slots: NeuralShellSlots
  paintTick: number
  setActiveNavId: (id: string | null) => void
}

const defaultLayout: NeuralShellLayout = {
  navItems: [],
  activeNavId: null,
  showLeftPanel: true,
  showRightPanel: true,
  hideShellPanels: false,
}

const defaultSlots: NeuralShellSlots = {
  inspector: null,
  leftPanel: null,
}

function navItemsEqual(a: NavTreeItem[], b: NavTreeItem[]) {
  if (a === b) return true
  if (a.length !== b.length) return false
  return a.every((item, i) => item.id === b[i]?.id)
}

function layoutEqual(a: NeuralShellLayout, b: NeuralShellLayout) {
  return (
    a.activeNavId === b.activeNavId
    && a.showLeftPanel === b.showLeftPanel
    && a.showRightPanel === b.showRightPanel
    && a.hideShellPanels === b.hideShellPanels
    && navItemsEqual(a.navItems, b.navItems)
  )
}

const PageShellActionsContext = createContext<PageShellActions | null>(null)
const NeuralShellDisplayContext = createContext<NeuralShellDisplay | null>(null)

export function NeuralShellProvider({ children }: { children: ReactNode }) {
  const [layout, setLayout] = useState<NeuralShellLayout>(defaultLayout)
  const [paintTick, setPaintTick] = useState(0)
  const slotsRef = useRef<NeuralShellSlots>({ ...defaultSlots })
  const onNavSelectRef = useRef<((id: string) => void) | undefined>(undefined)

  const bumpPaint = useCallback(() => {
    setPaintTick((t) => t + 1)
  }, [])

  const syncPageShell = useCallback((patch: PageShellSync) => {
    if (patch.onNavSelect !== undefined) {
      onNavSelectRef.current = patch.onNavSelect
    }

    let slotsChanged = false
    if (patch.inspector !== undefined && !Object.is(slotsRef.current.inspector, patch.inspector)) {
      slotsRef.current.inspector = patch.inspector
      slotsChanged = true
    }
    if (patch.leftPanel !== undefined && !Object.is(slotsRef.current.leftPanel, patch.leftPanel)) {
      slotsRef.current.leftPanel = patch.leftPanel
      slotsChanged = true
    }

    let layoutChanged = false
    setLayout((prev) => {
      const nextLayout: NeuralShellLayout = {
        navItems: patch.navItems ?? prev.navItems,
        activeNavId: patch.activeNavId !== undefined ? patch.activeNavId : prev.activeNavId,
        showLeftPanel: patch.showLeftPanel ?? prev.showLeftPanel,
        showRightPanel: patch.showRightPanel ?? prev.showRightPanel,
        hideShellPanels: patch.hideShellPanels ?? prev.hideShellPanels,
      }
      if (layoutEqual(prev, nextLayout)) return prev
      layoutChanged = true
      return nextLayout
    })

    if (slotsChanged) bumpPaint()
  }, [bumpPaint])

  const setActiveNavId = useCallback((id: string | null) => {
    setLayout((prev) => {
      if (prev.activeNavId === id) return prev
      return { ...prev, activeNavId: id }
    })
    if (id) onNavSelectRef.current?.(id)
  }, [])

  const resetShell = useCallback(() => {
    onNavSelectRef.current = undefined
    slotsRef.current = { ...defaultSlots }
    setLayout(defaultLayout)
    bumpPaint()
  }, [bumpPaint])

  const actions = useMemo(
    () => ({ syncPageShell, resetShell }),
    [syncPageShell, resetShell],
  )

  const display = useMemo(
    () => ({
      layout,
      slots: slotsRef.current,
      paintTick,
      setActiveNavId,
    }),
    [layout, paintTick, setActiveNavId],
  )

  return (
    <PageShellActionsContext.Provider value={actions}>
      <NeuralShellDisplayContext.Provider value={display}>
        {children}
      </NeuralShellDisplayContext.Provider>
    </PageShellActionsContext.Provider>
  )
}

/** Pages: sync shell slots without subscribing to shell display updates. */
export function usePageShellActions() {
  const ctx = useContext(PageShellActionsContext)
  if (!ctx) throw new Error('usePageShellActions must be used within NeuralShellProvider')
  return ctx
}

/** NeuralShell layout component only. */
export function useNeuralShell() {
  const ctx = useContext(NeuralShellDisplayContext)
  if (!ctx) throw new Error('useNeuralShell must be used within NeuralShellProvider')
  return ctx
}

export function useNeuralShellOptional() {
  return useContext(NeuralShellDisplayContext)
}
