import { NavLink, Outlet, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Image, Map, Clapperboard, Bug, Users, Play, Compass } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { usePageShell } from '@/components/layout/usePageShell'
import { useVisualStatus } from '@/hooks/useVisualStatus'
import { useNarrativeMode } from '@/hooks/useNarrativeMode'
import { cn } from '@/lib/utils'

const EXPLORE_NAV = [
  { to: '/visual/characters', icon: Users, label: '角色' },
  { to: '/visual/world', icon: Map, label: '世界' },
  { to: '/visual/events', icon: Clapperboard, label: '事件' },
  { to: '/visual/debug', icon: Bug, label: '调试' },
] as const

const NARRATIVE_NAV = [
  { to: '/visual/narrative', icon: Play, label: '入口' },
] as const

export default function VisualLayout() {
  usePageShell({ hideShellPanels: true })
  const location = useLocation()
  const navigate = useNavigate()
  const status = useVisualStatus()
  const { mode, setMode, loading: modeLoading } = useNarrativeMode()

  const isNarrativePath = location.pathname.includes('/visual/narrative')
  const uiMode = isNarrativePath ? 'narrative' : (mode || 'explore')

  if (location.pathname === '/visual' || location.pathname === '/visual/') {
    return <Navigate to="/visual/characters" replace />
  }

  const toggleMode = async (next: 'explore' | 'narrative') => {
    await setMode(next)
    if (next === 'narrative') {
      navigate('/visual/narrative')
    } else if (isNarrativePath) {
      navigate('/visual/characters')
    }
  }

  const nav = uiMode === 'narrative'
    ? [...NARRATIVE_NAV, ...EXPLORE_NAV.filter((n) => n.to === '/visual/events')]
    : EXPLORE_NAV

  return (
    <div className="h-full flex flex-col gap-3 p-4 overflow-hidden">
      <div className="flex items-start justify-between gap-3 shrink-0 flex-wrap">
        <SectionHeader
          icon={Image}
          title="视觉世界"
          subtitle={uiMode === 'narrative'
            ? '叙事模式 · 进入节点并做出选择（V6.6）'
            : '探索模式 · 只读展示 Identity / Registry / Cache（V6.5）'}
        />
        <div className="flex items-center gap-2 shrink-0 mt-1">
          {status && (
            <Badge variant="outline" className="font-neural-mono text-[10px]">
              {status.provider}
            </Badge>
          )}
          <div className="flex rounded-md border border-neural-cyan/20 overflow-hidden">
            <Button
              type="button"
              size="sm"
              variant={uiMode === 'explore' ? 'default' : 'ghost'}
              className="h-7 px-2 text-xs rounded-none gap-1"
              disabled={modeLoading}
              onClick={() => void toggleMode('explore')}
            >
              <Compass className="w-3 h-3" />
              探索
            </Button>
            <Button
              type="button"
              size="sm"
              variant={uiMode === 'narrative' ? 'default' : 'ghost'}
              className="h-7 px-2 text-xs rounded-none gap-1"
              disabled={modeLoading}
              onClick={() => void toggleMode('narrative')}
            >
              <Play className="w-3 h-3" />
              叙事
            </Button>
          </div>
        </div>
      </div>

      <nav className="flex flex-wrap gap-1 shrink-0 border-b border-neural-cyan/10 pb-2">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
              isActive
                ? 'bg-neural-cyan/10 text-neural-cyan border border-neural-cyan/30'
                : 'text-game-muted hover:text-game-text hover:bg-neural-glass/40',
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="flex-1 min-h-0 overflow-hidden">
        <Outlet />
      </div>
    </div>
  )
}
