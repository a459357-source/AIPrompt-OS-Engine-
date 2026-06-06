import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-game-primary/50 focus:ring-offset-2 focus:ring-offset-game-bg',
  {
    variants: {
      variant: {
        default: 'border-game-border bg-game-surface text-game-text hover:bg-game-border',
        primary: 'border-game-primary/30 bg-game-primary/15 text-game-primary',
        accent: 'border-game-accent/30 bg-game-accent/15 text-game-accent',
        success: 'border-game-success/30 bg-game-success/15 text-game-success',
        warning: 'border-game-warning/30 bg-game-warning/15 text-game-warning',
        danger: 'border-game-danger/30 bg-game-danger/15 text-game-danger',
        secret: 'border-game-secret/50 bg-game-secret/30 text-game-accent',
        outline: 'border-game-border bg-transparent text-game-muted',
      },
      size: {
        default: 'px-2.5 py-0.5 text-xs',
        sm: 'px-2 py-0.5 text-[10px]',
        lg: 'px-3 py-1 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  removable?: boolean
  onRemove?: () => void
}

function Badge({ className, variant, size, removable, onRemove, children, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant, size }), className)} {...props}>
      {children}
      {removable && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove?.() }}
          className="ml-1 rounded-full opacity-60 hover:opacity-100 transition-opacity text-[10px] leading-none"
        >
          ×
        </button>
      )}
    </div>
  )
}

export { Badge, badgeVariants }
