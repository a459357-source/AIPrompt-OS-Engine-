import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { GlassPanel } from '@/components/neural/GlassPanel'

interface InspectorPanelProps {
  title?: string
  children: ReactNode
  className?: string
  footer?: ReactNode
  /** 标题栏显示收起按钮，由父组件控制侧栏显隐 */
  collapsible?: boolean
  onCollapse?: () => void
  collapseLabel?: string
}

export function InspectorPanel({
  title,
  children,
  className,
  footer,
  collapsible,
  onCollapse,
  collapseLabel = '收起',
}: InspectorPanelProps) {
  return (
    <GlassPanel padding="none" className={cn('flex flex-col h-full overflow-hidden', className)}>
      {title && (
        <div className="px-4 py-3 border-b border-neural-cyan/10 shrink-0 flex items-center justify-between gap-2">
          <h3 className="font-neural-display text-sm text-neural-cyan tracking-wide min-w-0 truncate">{title}</h3>
          {collapsible && onCollapse && (
            <button
              type="button"
              onClick={onCollapse}
              title={collapseLabel}
              aria-label={collapseLabel}
              className="shrink-0 p-1 rounded-md text-game-muted hover:text-neural-cyan hover:bg-neural-cyan/10 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-4">{children}</div>
      {footer && (
        <div className="px-4 py-3 border-t border-neural-cyan/10 shrink-0">{footer}</div>
      )}
    </GlassPanel>
  )
}
