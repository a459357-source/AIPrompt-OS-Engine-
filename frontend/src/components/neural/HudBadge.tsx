import * as React from 'react'
import { cn } from '@/lib/utils'

interface HudBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'cyan' | 'magenta' | 'violet' | 'success' | 'warning' | 'danger'
  size?: 'sm' | 'md'
}

const variantStyles = {
  cyan: 'border-neural-cyan/40 bg-neural-cyan/10 text-neural-cyan',
  magenta: 'border-neural-magenta/40 bg-neural-magenta/10 text-neural-magenta',
  violet: 'border-neural-violet/40 bg-neural-violet/10 text-neural-violet',
  success: 'border-game-success/40 bg-game-success/10 text-game-success',
  warning: 'border-game-warning/40 bg-game-warning/10 text-game-warning',
  danger: 'border-game-danger/40 bg-game-danger/10 text-game-danger',
}

export function HudBadge({
  className,
  variant = 'cyan',
  size = 'sm',
  children,
  ...props
}: HudBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center font-neural-mono uppercase tracking-wider border',
        'clip-path-[polygon(8px_0,100%_0,calc(100%-8px)_100%,0_100%)]',
        size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs',
        variantStyles[variant],
        className,
      )}
      style={{
        clipPath: 'polygon(6px 0, 100% 0, calc(100% - 6px) 100%, 0 100%)',
      }}
      {...props}
    >
      {children}
    </span>
  )
}
