import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import type { Character } from '@/lib/types'

interface CharacterCardProps {
  character: Character & { id?: string }
  index: number
  isMain?: boolean
  onRemove?: () => void
  className?: string
}

export function CharacterCard({ character, index, isMain, onRemove, className }: CharacterCardProps) {
  const c = character

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
    >
      <Card className={`overflow-hidden ${isMain ? 'border-game-accent/50 bg-game-accent/[0.03]' : ''} ${className || ''}`}>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <Badge variant={isMain ? 'accent' : 'success'} size="sm">
              {isMain ? '⭐ 主角' : '👤 NPC'}
            </Badge>
            {!isMain && onRemove && (
              <button
                type="button"
                onClick={onRemove}
                className="text-game-dim hover:text-game-danger transition-colors text-sm px-1"
              >
                ✕
              </button>
            )}
          </div>
          <CardTitle className="text-base mt-1">
            {c.name || '未命名角色'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Priority: relationship > goal > secret > personality > appearance */}
          {c.relationship && c.relationship.length > 0 && (
            <div>
              <span className="text-[10px] text-game-muted">关系</span>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {c.relationship.map((r, i) => (
                  <Badge key={i} variant="accent" size="sm">{r}</Badge>
                ))}
              </div>
            </div>
          )}

          {c.goal && (
            <div>
              <span className="text-[10px] text-game-muted">目标</span>
              <p className="text-xs text-game-text mt-0.5">{c.goal}</p>
            </div>
          )}

          {c.secret && (
            <div>
              <span className="text-[10px] text-game-accent">🔒 秘密</span>
              <p className="text-xs text-game-accent/80 mt-0.5 bg-game-secret/10 rounded px-2 py-1">{c.secret}</p>
            </div>
          )}

          {c.personality_tags && c.personality_tags.length > 0 && (
            <div>
              <span className="text-[10px] text-game-muted">性格</span>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {c.personality_tags.map((t, i) => (
                  <Badge key={i} variant="primary" size="sm">{t}</Badge>
                ))}
              </div>
            </div>
          )}

          {c.appearance && (
            <div>
              <span className="text-[10px] text-game-muted">外貌</span>
              <p className="text-xs text-game-dim mt-0.5">{c.appearance}</p>
            </div>
          )}

          {c.role_tags && c.role_tags.length > 0 && (
            <div>
              <span className="text-[10px] text-game-muted">身份</span>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {c.role_tags.map((t, i) => (
                  <Badge key={i} variant="outline" size="sm">{t}</Badge>
                ))}
              </div>
            </div>
          )}

          <Separator className="my-1" />

          {/* Affinity visual bar */}
          {c.relationship && c.relationship.length > 0 && (
            <div>
              <span className="text-[10px] text-game-muted">好感度</span>
              <div className="flex items-center gap-2 mt-0.5">
                <div className="flex-1 h-2 bg-game-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-game-primary to-game-accent rounded-full transition-all"
                    style={{ width: `${Math.min(100, 30 + (c.relationship.length * 15))}%` }}
                  />
                </div>
                <span className="text-[10px] text-game-muted tabular-nums">
                  {Math.min(100, 30 + (c.relationship.length * 15))}%
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
