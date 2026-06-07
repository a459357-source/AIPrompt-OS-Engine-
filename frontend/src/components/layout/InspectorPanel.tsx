import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { GlassPanel } from '@/components/neural/GlassPanel'

interface InspectorPanelProps {
  title?: string
  children: ReactNode
  className?: string
  footer?: ReactNode
}

export function InspectorPanel({ title, children, className, footer }: InspectorPanelProps) {
  return (
    <GlassPanel padding="none" className={cn('flex flex-col h-full overflow-hidden', className)}>
      {title && (
        <div className="px-4 py-3 border-b border-neural-cyan/10 shrink-0">
          <h3 className="font-neural-display text-sm text-neural-cyan tracking-wide">{title}</h3>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-4">{children}</div>
      {footer && (
        <div className="px-4 py-3 border-t border-neural-cyan/10 shrink-0">{footer}</div>
      )}
    </GlassPanel>
  )
}
