import { useEffect, useLayoutEffect, useRef } from 'react'
import { useNeuralShell, type NavTreeItem } from './NeuralShellContext'

interface UsePageShellOptions {
  navItems?: NavTreeItem[]
  activeNavId?: string | null
  onNavSelect?: (id: string) => void
  inspector?: React.ReactNode
  leftPanel?: React.ReactNode
  showLeftPanel?: boolean
  showRightPanel?: boolean
  hideShellPanels?: boolean
}

/** Stable default — never inline `[]` in parameter defaults (new ref every render). */
const EMPTY_NAV: NavTreeItem[] = []

export function usePageShell({
  navItems = EMPTY_NAV,
  activeNavId = null,
  inspector = null,
  leftPanel = null,
  showLeftPanel = true,
  showRightPanel = true,
  hideShellPanels = false,
}: UsePageShellOptions) {
  const shell = useNeuralShell()
  const shellRef = useRef(shell)
  shellRef.current = shell

  const inspectorRef = useRef(inspector)
  const leftPanelRef = useRef(leftPanel)
  const navItemsRef = useRef(navItems)
  inspectorRef.current = inspector
  leftPanelRef.current = leftPanel
  navItemsRef.current = navItems

  useLayoutEffect(() => {
    const s = shellRef.current
    s.setNavItems(navItemsRef.current)
    s.setActiveNavId(activeNavId)
    s.setInspector(inspectorRef.current)
    s.setLeftPanel(leftPanelRef.current)
    s.setShowLeftPanel(showLeftPanel)
    s.setShowRightPanel(showRightPanel)
    s.setHideShellPanels(hideShellPanels)
  })

  useEffect(() => {
    return () => shellRef.current.resetShell()
  }, [])

  return shell
}
