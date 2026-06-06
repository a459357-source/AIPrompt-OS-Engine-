import * as React from 'react'
import { cn } from '@/lib/utils'

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'flex min-h-[80px] w-full rounded-md border border-game-border bg-game-bg px-3 py-2 text-sm text-game-text shadow-sm transition-colors',
          'placeholder:text-game-dim',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-game-primary/50 focus-visible:border-game-primary',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = 'Textarea'

export { Textarea }
