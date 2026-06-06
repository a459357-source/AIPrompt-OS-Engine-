import * as React from 'react'
import { cn } from '@/lib/utils'

const Sheet = ({ open, onOpenChange, children }: {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: React.ReactNode
}) => {
  return (
    <div data-sheet-root="">
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<{ 'data-sheet-open'?: boolean; 'data-sheet-onopenchange'?: (open: boolean) => void }>, {
            'data-sheet-open': open,
            'data-sheet-onopenchange': onOpenChange,
          })
        }
        return child
      })}
    </div>
  )
}

interface SheetTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  'data-sheet-open'?: boolean
  'data-sheet-onopenchange'?: (open: boolean) => void
}

const SheetTrigger = React.forwardRef<HTMLDivElement, SheetTriggerProps>(
  ({ className, ...props }, ref) => {
    const onOpen = (props as Record<string, unknown>)['data-sheet-onopenchange'] as ((open: boolean) => void) | undefined
    const isOpen = (props as Record<string, unknown>)['data-sheet-open'] as boolean | undefined

    return (
      <div
        ref={ref}
        className={cn('cursor-pointer', className)}
        onClick={() => onOpen?.(!isOpen)}
        {...props}
      />
    )
  }
)
SheetTrigger.displayName = 'SheetTrigger'

interface SheetContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: 'left' | 'right' | 'top' | 'bottom'
  'data-sheet-open'?: boolean
  'data-sheet-onopenchange'?: (open: boolean) => void
}

const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
  ({ className, children, side = 'right', ...props }, ref) => {
    const isOpen = (props as Record<string, unknown>)['data-sheet-open'] as boolean | undefined
    const onOpen = (props as Record<string, unknown>)['data-sheet-onopenchange'] as ((open: boolean) => void) | undefined

    if (!isOpen) return null

    const sideClasses = {
      left: 'left-0 top-0 h-full w-80 border-r animate-in slide-in-from-left',
      right: 'right-0 top-0 h-full w-80 border-l animate-in slide-in-from-right',
      top: 'top-0 left-0 w-full h-80 border-b animate-in slide-in-from-top',
      bottom: 'bottom-0 left-0 w-full h-80 border-t animate-in slide-in-from-bottom',
    }

    return (
      <>
        <div
          className="fixed inset-0 z-50 bg-black/50"
          onClick={() => onOpen?.(false)}
        />
        <div
          ref={ref}
          className={cn(
            'fixed z-50 bg-game-card border-game-border shadow-xl p-6 overflow-auto',
            sideClasses[side],
            className
          )}
          {...props}
        >
          <button
            onClick={() => onOpen?.(false)}
            className="absolute right-4 top-4 text-game-muted hover:text-game-text text-lg"
          >
            ✕
          </button>
          {children}
        </div>
      </>
    )
  }
)
SheetContent.displayName = 'SheetContent'

const SheetHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col space-y-1.5 pb-4', className)} {...props} />
)
SheetHeader.displayName = 'SheetHeader'

const SheetTitle = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('text-lg font-bold text-game-accent', className)} {...props} />
)
SheetTitle.displayName = 'SheetTitle'

const SheetDescription = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('text-sm text-game-muted', className)} {...props} />
)
SheetDescription.displayName = 'SheetDescription'

export { Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription }
