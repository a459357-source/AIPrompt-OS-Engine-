import * as React from 'react'
import { cn } from '@/lib/utils'

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'flex min-h-[80px] w-full rounded-md border border-neural-cyan/15 bg-neural-glass/80 backdrop-blur-sm px-3 py-2 text-sm text-game-text shadow-sm transition-colors',
          'placeholder:text-game-dim',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neural-cyan/40 focus-visible:border-neural-cyan/50',
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
