import { useEffect, useLayoutEffect, useRef } from 'react'
import { usePageShellActions, type NavTreeItem } from './NeuralShellContext'

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
  onNavSelect,
  inspector = null,
  leftPanel = null,
  showLeftPanel = true,
  showRightPanel = true,
  hideShellPanels = false,
}: UsePageShellOptions) {
  const { syncPageShell, resetShell } = usePageShellActions()

  const patchRef = useRef({
    navItems,
    activeNavId,
    onNavSelect,
    inspector,
    leftPanel,
    showLeftPanel,
    showRightPanel,
    hideShellPanels,
  })
  patchRef.current = {
    navItems,
    activeNavId,
    onNavSelect,
    inspector,
    leftPanel,
    showLeftPanel,
    showRightPanel,
    hideShellPanels,
  }

  useLayoutEffect(() => {
    syncPageShell(patchRef.current)
  })

  useEffect(() => () => resetShell(), [resetShell])

  return { syncPageShell, resetShell }
}
