import { useEffect } from 'react'
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

export function usePageShell({
  navItems = [],
  activeNavId = null,
  inspector = null,
  leftPanel = null,
  showLeftPanel = true,
  showRightPanel = true,
  hideShellPanels = false,
}: UsePageShellOptions) {
  const shell = useNeuralShell()

  useEffect(() => {
    shell.setNavItems(navItems)
    shell.setShowLeftPanel(showLeftPanel)
    shell.setShowRightPanel(showRightPanel)
    shell.setHideShellPanels(hideShellPanels)
    return () => shell.resetShell()
  }, [showLeftPanel, showRightPanel, hideShellPanels])

  useEffect(() => {
    shell.setNavItems(navItems)
  }, [navItems])

  useEffect(() => {
    shell.setActiveNavId(activeNavId)
  }, [activeNavId])

  useEffect(() => {
    shell.setInspector(inspector)
  }, [inspector])

  useEffect(() => {
    shell.setLeftPanel(leftPanel)
  }, [leftPanel])

  return shell
}
