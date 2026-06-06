import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-game-bg disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-game-primary text-white hover:bg-game-primary/80 shadow-sm',
        destructive: 'bg-game-danger text-white hover:bg-game-danger/80 shadow-sm',
        outline: 'border border-game-border bg-transparent text-game-text hover:bg-game-surface hover:text-game-primary',
        secondary: 'bg-game-surface text-game-text hover:bg-game-border',
        ghost: 'text-game-muted hover:bg-game-surface hover:text-game-text',
        link: 'text-game-primary underline-offset-4 hover:underline',
        accent: 'bg-game-accent/20 text-game-accent border border-game-accent/30 hover:bg-game-accent/30',
        success: 'bg-game-success/20 text-game-success border border-game-success/30 hover:bg-game-success/30',
        glow: 'bg-game-primary/15 text-game-primary border border-game-primary/30 hover:bg-game-primary/25 shadow-[0_0_12px_var(--color-game-primary)]/20',
        primary: 'bg-game-primary/20 text-game-primary border border-game-primary/40 hover:bg-game-primary/30',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-10 rounded-md px-6 text-base',
        icon: 'h-9 w-9',
        xs: 'h-7 rounded-md px-2 text-xs gap-1',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
