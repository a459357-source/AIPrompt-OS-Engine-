import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem } from '@/components/ui/command'

type TagColor = 'primary' | 'accent' | 'secret' | 'success' | 'warning'

interface TagInputProps {
  value: string[]
  onChange: (tags: string[]) => void
  presets: string[]
  placeholder?: string
  color?: TagColor
  maxTags?: number
  /** 侧栏等窄布局：隐藏底部快捷预设 chips，仅用输入框 + 下拉 */
  compact?: boolean
}

const colorVariantMap: Record<TagColor, 'primary' | 'accent' | 'secret' | 'success' | 'warning'> = {
  primary: 'primary',
  accent: 'accent',
  secret: 'secret',
  success: 'success',
  warning: 'warning',
}

export function TagInput({
  value,
  onChange,
  presets,
  placeholder = '输入后回车添加…',
  color = 'primary',
  maxTags = 20,
  compact = false,
}: TagInputProps) {
  const [input, setInput] = useState('')
  const [showCommand, setShowCommand] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const valueRef = useRef(value)
  valueRef.current = value

  const add = (tag: string) => {
    const t = tag.trim()
    const current = valueRef.current
    if (t && !current.includes(t) && current.length < maxTags) {
      onChange([...current, t])
    }
    setInput('')
    setShowCommand(false)
  }

  const remove = (idx: number) => {
    onChange(valueRef.current.filter((_, i) => i !== idx))
  }

  const filteredPresets = presets.filter(
    (p) => !value.includes(p) && p.toLowerCase().includes(input.toLowerCase())
  )

  // Close command on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowCommand(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={containerRef} className="space-y-2">
      {/* Selected tags */}
      <div className="flex flex-wrap gap-1.5 min-h-[28px]">
        <AnimatePresence>
          {value.map((tag, i) => (
            <motion.div
              key={`${tag}-${i}`}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <Badge
                variant={colorVariantMap[color]}
                removable
                onRemove={() => remove(i)}
                className="cursor-pointer"
              >
                {tag}
              </Badge>
            </motion.div>
          ))}
        </AnimatePresence>
        {value.length === 0 && (
          <span className="text-xs text-game-dim self-center">{placeholder}</span>
        )}
      </div>

      {/* Input + search */}
      <div className="relative">
        <div className="flex gap-1.5">
          <Input
            value={input}
            onChange={(e) => { setInput(e.target.value); setShowCommand(true) }}
            onFocus={() => setShowCommand(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (filteredPresets.length > 0 && input) {
                  add(filteredPresets[0])
                } else if (input.trim()) {
                  add(input)
                }
              }
              if (e.key === 'Backspace' && !input && value.length > 0) {
                remove(value.length - 1)
              }
            }}
            placeholder={value.length > 0 ? '继续添加…' : placeholder}
            className="h-8 text-xs"
          />
        </div>

        {/* Command dropdown */}
        {showCommand && input && filteredPresets.length > 0 && (
          <div className="absolute z-10 top-full mt-1 w-full">
            <Command className="max-h-40 shadow-lg">
              <CommandList>
                <CommandGroup heading={`匹配 ${filteredPresets.length} 个`}>
                  {filteredPresets.slice(0, 12).map((p) => (
                    <CommandItem key={p} onSelect={() => add(p)} className="text-xs">
                      <span className="text-game-dim">+</span> {p}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </div>
        )}
      </div>

      {/* Quick presets */}
      {!compact && !input && presets.length > 0 && (
        <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
          {presets.filter((p) => !value.includes(p)).slice(0, 20).map((p) => (
            <button
              key={p}
              type="button"
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); add(p) }}
              className="inline-flex items-center rounded-full border border-game-border bg-transparent text-game-muted px-2.5 py-0.5 text-xs font-medium hover:bg-game-primary/10 hover:text-game-primary hover:border-game-primary/30 transition-colors"
            >
              + {p}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
