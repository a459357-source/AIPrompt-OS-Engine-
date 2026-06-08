import { NavLink, Outlet, Navigate, useLocation } from 'react-router-dom'
import { Image, Map, Clapperboard, Bug, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { usePageShell } from '@/components/layout/usePageShell'
import { useVisualStatus } from '@/hooks/useVisualStatus'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/visual/characters', icon: Users, label: '角色' },
  { to: '/visual/world', icon: Map, label: '世界' },
  { to: '/visual/events', icon: Clapperboard, label: '事件' },
  { to: '/visual/debug', icon: Bug, label: '调试' },
] as const

export default function VisualLayout() {
  usePageShell({ hideShellPanels: true })
  const location = useLocation()
  const status = useVisualStatus()

  if (location.pathname === '/visual' || location.pathname === '/visual/') {
    return <Navigate to="/visual/characters" replace />
  }

  return (
    <div className="h-full flex flex-col gap-3 p-4 overflow-hidden">
      <div className="flex items-start justify-between gap-3 shrink-0">
        <SectionHeader
          icon={Image}
          title="视觉世界"
          subtitle="只读查询终端 · 展示 Identity / Registry / Cache（V6.5）"
        />
        {status && (
          <Badge variant="outline" className="font-neural-mono text-[10px] shrink-0 mt-2">
            {status.provider} · read-only
          </Badge>
        )}
      </div>

      <nav className="flex flex-wrap gap-1 shrink-0 border-b border-neural-cyan/10 pb-2">
        {NAV.map(({ to, icon: Icon, label }) => (
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
