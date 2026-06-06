import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

interface AIButtonProps {
  loading?: boolean
  error?: string | null
  onClick: () => void
  onAccept?: () => void
  onUndo?: () => void
  onCopy?: () => void
  onEdit?: () => void
  children: string
  /** Whether generated content is available for actions */
  hasGenerated?: boolean
}

export function AIButton({
  loading,
  error,
  onClick,
  onAccept,
  onUndo,
  onCopy,
  onEdit,
  children,
  hasGenerated,
}: AIButtonProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    onCopy?.()
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* Main generate button */}
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant={error ? 'outline' : 'glow'}
              size="xs"
              disabled={loading}
              onClick={onClick}
              className="gap-1.5"
            >
              {loading ? (
                <span className="inline-block w-3 h-3 border-2 border-game-primary/30 border-t-game-primary rounded-full animate-spin" />
              ) : error ? (
                <span>🔄</span>
              ) : (
                <span>✨</span>
              )}
              {loading ? '生成中…' : error ? `重试${children}` : `AI${children}`}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {loading ? 'AI 正在生成内容…' : '点击 AI 生成此内容'}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      {/* Error message */}
      <AnimatePresence>
        {error && (
          <motion.span
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            className="text-[11px] text-game-danger"
            title={error}
          >
            {error.length > 24 ? error.slice(0, 22) + '…' : error}
          </motion.span>
        )}
      </AnimatePresence>

      {/* Action buttons (shown after generation) */}
      <AnimatePresence>
        {hasGenerated && !loading && !error && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="flex gap-1"
          >
            {onAccept && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="button" variant="ghost" size="xs" onClick={onAccept} className="text-game-success">
                      ✓
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>确认采用</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            {onUndo && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="button" variant="ghost" size="xs" onClick={onUndo} className="text-game-warning">
                      ↩
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>撤销</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            {onEdit && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="button" variant="ghost" size="xs" onClick={onEdit} className="text-game-muted">
                      ✎
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>编辑</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            {onCopy && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button type="button" variant="ghost" size="xs" onClick={handleCopy} className="text-game-muted">
                      {copied ? '✓' : '📋'}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{copied ? '已复制' : '复制'}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
