import { Link, useLocation } from 'react-router-dom'
import { useState } from 'react'
import {
  Globe, Gamepad2, Users, Activity, Settings, Menu, PanelLeft, PanelRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { ParticleBackground } from '@/components/neural/ParticleBackground'
import { PrivateStoryAtmosphere } from '@/components/neural/PrivateStoryAtmosphere'
import { WorldNavTree } from './WorldNavTree'
import { useNeuralShell } from './NeuralShellContext'
import { useAppSettings } from '@/hooks/useAppSettings'
import { useAdultThemeOptional } from '@/contexts/AdultThemeContext'
import { t, tTheme } from '@/lib/i18n'
import { cn } from '@/lib/utils'

const ROUTE_NAV = [
  { to: '/new', icon: Globe, labelKey: 'nav.worldBuilder', themeKey: true },
  { to: '/game', icon: Gamepad2, labelKey: 'nav.game', themeKey: true },
  { to: '/npcs', icon: Users, labelKey: 'nav.characters', themeKey: true },
  { to: '/dashboard', icon: Activity, labelKey: 'nav.worldState', themeKey: true },
  { to: '/settings', icon: Settings, labelKey: 'nav.settings', themeKey: false },
]

function NeuralTopBar() {
  const location = useLocation()
  const { language } = useAppSettings()
  const adultMode = useAdultThemeOptional()?.adultMode ?? false
  const lang = language as 'zh' | 'en' | 'ja'

  return (
    <header className="shrink-0 h-12 flex items-center justify-between px-4 border-b border-neural-cyan/10 glass-panel rounded-none border-x-0 border-t-0 z-40 transition-colors duration-[800ms]">
      <Link to="/" className="flex items-center gap-2 group">
        <span className="w-2 h-2 rounded-full bg-neural-cyan neural-pulse-dot transition-colors duration-[800ms]" />
        <span className="font-neural-display text-sm font-bold text-neural-cyan neural-text-glow tracking-wider transition-colors duration-[800ms]">
          {tTheme('brand.title', lang, adultMode)}
        </span>
        <span className="hidden sm:inline text-[10px] font-neural-mono text-game-dim group-hover:text-neural-violet transition-colors duration-[800ms]">
          {tTheme('brand.subtitle', lang, adultMode)}
        </span>
      </Link>
      <nav className="hidden lg:flex items-center gap-1">
        {ROUTE_NAV.map(({ to, icon: Icon, labelKey, themeKey }) => {
          const active = location.pathname === to || (to === '/new' && location.pathname === '/')
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-[800ms]',
                active
                  ? 'bg-neural-cyan/10 text-neural-cyan border border-neural-cyan/30'
                  : 'text-game-muted hover:text-game-text hover:bg-neural-glass/50',
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {themeKey ? tTheme(labelKey, lang, adultMode) : tTheme(labelKey, lang, false)}
            </Link>
          )
        })}
      </nav>
    </header>
  )
}

function NeuralDock() {
  const location = useLocation()
  const { language } = useAppSettings()
  const adultMode = useAdultThemeOptional()?.adultMode ?? false
  const lang = language as 'zh' | 'en' | 'ja'

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-50 glass-panel border-x-0 border-b-0 rounded-none safe-area-bottom transition-colors duration-[800ms]">
      <div className="flex items-center justify-around px-1 py-2">
        {ROUTE_NAV.map(({ to, icon: Icon, labelKey, themeKey }) => {
          const active = location.pathname === to || (to === '/new' && location.pathname === '/')
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                'flex flex-col items-center gap-0.5 px-2 py-1 rounded-lg min-w-0 transition-colors duration-[800ms]',
                active ? 'text-neural-cyan' : 'text-game-dim',
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[9px] leading-none truncate max-w-[56px]">
                {themeKey ? tTheme(labelKey, lang, adultMode) : tTheme(labelKey, lang, false)}
              </span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}

interface NeuralShellProps {
  children: React.ReactNode
}

export function NeuralShell({ children }: NeuralShellProps) {
  const {
    layout: {
      navItems,
      activeNavId,
      showLeftPanel,
      showRightPanel,
      hideShellPanels,
    },
    slots: { inspector, leftPanel },
    setActiveNavId,
  } = useNeuralShell()
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)

  const hasSidePanels = !hideShellPanels && (navItems.length > 0 || leftPanel)
  const hasInspector = !hideShellPanels && showRightPanel

  return (
    <div className="h-screen flex flex-col overflow-hidden relative">
      <ParticleBackground />
      <PrivateStoryAtmosphere />
      <NeuralTopBar />
      <div className="flex-1 flex min-h-0 relative z-10 pb-14 lg:pb-0">
        {/* Desktop left panel */}
        {hasSidePanels && showLeftPanel && (
          <aside className="hidden md:flex flex-col w-60 shrink-0 border-r border-neural-cyan/10 glass-panel rounded-none border-y-0 border-l-0 overflow-hidden">
            {leftPanel || (
              <WorldNavTree
                items={navItems}
                activeId={activeNavId}
                onSelect={setActiveNavId}
                className="flex-1 overflow-y-auto"
              />
            )}
          </aside>
        )}

        {/* Mobile left sheet */}
        {hasSidePanels && showLeftPanel && (
          <Sheet open={leftOpen} onOpenChange={setLeftOpen}>
            <SheetTrigger className="md:hidden absolute top-2 left-2 z-20">
              <Button variant="ghost" size="icon" className="glass-panel h-8 w-8">
                <PanelLeft className="w-4 h-4 text-neural-cyan" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 glass-panel border-neural-cyan/20 p-0">
              <SheetHeader className="p-4 border-b border-neural-cyan/10">
                <SheetTitle className="font-neural-display text-neural-cyan text-sm">Navigation</SheetTitle>
              </SheetHeader>
              {leftPanel || (
                <WorldNavTree
                  items={navItems}
                  activeId={activeNavId}
                  onSelect={(id) => { setActiveNavId(id); setLeftOpen(false) }}
                />
              )}
            </SheetContent>
          </Sheet>
        )}

        {/* Center canvas */}
        <main className="flex-1 min-w-0 min-h-0 overflow-hidden relative">
          {children}
        </main>

        {/* Desktop right inspector */}
        {hasInspector && inspector && (
          <aside className="hidden md:flex flex-col w-96 shrink-0 border-l border-neural-cyan/10 overflow-hidden">
            {inspector}
          </aside>
        )}

        {/* Mobile right sheet */}
        {hasInspector && inspector && (
          <Sheet open={rightOpen} onOpenChange={setRightOpen}>
            <SheetTrigger className="md:hidden absolute top-2 right-2 z-20">
              <Button variant="ghost" size="icon" className="glass-panel h-8 w-8">
                <PanelRight className="w-4 h-4 text-neural-cyan" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-96 max-w-[92vw] glass-panel border-neural-cyan/20 p-0">
              {inspector}
            </SheetContent>
          </Sheet>
        )}

        {/* Mobile menu fallback when no page nav */}
        {!hasSidePanels && (
          <Sheet>
            <SheetTrigger className="md:hidden absolute top-2 left-2 z-20">
              <Button variant="ghost" size="icon" className="glass-panel h-8 w-8">
                <Menu className="w-4 h-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 glass-panel">
              <SheetHeader>
                <SheetTitle className="font-neural-display text-neural-cyan">{t('brand.title')}</SheetTitle>
              </SheetHeader>
            </SheetContent>
          </Sheet>
        )}
      </div>
      <NeuralDock />
    </div>
  )
}
