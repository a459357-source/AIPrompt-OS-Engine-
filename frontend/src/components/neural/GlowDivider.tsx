import { cn } from '@/lib/utils'

interface GlowDividerProps {
  className?: string
  label?: string
}

export function GlowDivider({ className, label }: GlowDividerProps) {
  return (
    <div className={cn('flex items-center gap-3 my-4', className)}>
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-neural-cyan/40 to-transparent" />
      {label && (
        <span className="text-[10px] font-neural-mono text-neural-cyan/60 uppercase tracking-widest">
          {label}
        </span>
      )}
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-neural-violet/40 to-transparent" />
    </div>
  )
}
