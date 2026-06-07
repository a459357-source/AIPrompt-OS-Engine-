import * as React from 'react'
import { cn } from '@/lib/utils'

interface GlassPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: boolean
  opaque?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddingMap = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-5',
}

export function GlassPanel({
  className,
  glow = false,
  opaque = false,
  padding = 'md',
  children,
  ...props
}: GlassPanelProps) {
  return (
    <div
      className={cn(
        opaque ? 'glass-panel-opaque' : 'glass-panel',
        'rounded-lg',
        glow && 'glass-panel-glow',
        paddingMap[padding],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
