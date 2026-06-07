import { cn } from '@/lib/utils'
import type { NavTreeItem } from './NeuralShellContext'

interface WorldNavTreeProps {
  items: NavTreeItem[]
  activeId: string | null
  onSelect: (id: string) => void
  className?: string
}

function NavItem({
  item,
  activeId,
  onSelect,
  depth = 0,
}: {
  item: NavTreeItem
  activeId: string | null
  onSelect: (id: string) => void
  depth?: number
}) {
  const active = activeId === item.id
  return (
    <div>
      <button
        type="button"
        onClick={() => onSelect(item.id)}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-all rounded-md',
          'border border-transparent',
          active
            ? 'bg-neural-cyan/10 text-neural-cyan border-neural-cyan/30 shadow-[0_0_12px_rgba(0,240,255,0.1)]'
            : 'text-game-muted hover:text-game-text hover:bg-neural-glass/50',
          depth > 0 && 'ml-3 text-xs',
        )}
      >
        {item.icon && <span className="shrink-0 opacity-80">{item.icon}</span>}
        <span className="truncate font-medium">{item.label}</span>
        {active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-neural-cyan neural-pulse-dot" />}
      </button>
      {item.children?.map((child) => (
        <NavItem key={child.id} item={child} activeId={activeId} onSelect={onSelect} depth={depth + 1} />
      ))}
    </div>
  )
}

export function WorldNavTree({ items, activeId, onSelect, className }: WorldNavTreeProps) {
  return (
    <nav className={cn('flex flex-col gap-0.5 p-2', className)} aria-label="World navigation">
      {items.map((item) => (
        <NavItem key={item.id} item={item} activeId={activeId} onSelect={onSelect} />
      ))}
    </nav>
  )
}
