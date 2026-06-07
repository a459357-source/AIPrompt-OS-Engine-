import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SectionHeaderProps {
  icon?: LucideIcon
  title: string
  subtitle?: string
  status?: 'active' | 'idle' | 'warning'
  className?: string
}

const statusColors = {
  active: 'bg-neural-cyan neural-pulse-dot',
  idle: 'bg-game-dim',
  warning: 'bg-game-warning',
}

export function SectionHeader({
  icon: Icon,
  title,
  subtitle,
  status = 'idle',
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn('flex items-start gap-3 mb-4', className)}>
      {Icon && (
        <div className="p-2 rounded-lg glass-panel border-neural-cyan/20">
          <Icon className="w-5 h-5 text-neural-cyan" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="font-neural-display text-lg font-semibold text-neural-cyan neural-text-glow truncate">
            {title}
          </h2>
          <span className={cn('w-2 h-2 rounded-full shrink-0', statusColors[status])} />
        </div>
        {subtitle && (
          <p className="text-sm text-game-muted mt-0.5">{subtitle}</p>
        )}
      </div>
    </div>
  )
}
