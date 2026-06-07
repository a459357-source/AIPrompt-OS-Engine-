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
  trustPct?: number   // 覆盖character.trust_pct，用于NPC页面传入真实数据
}

export function CharacterCard({ character, index, isMain, onRemove, className, trustPct }: CharacterCardProps) {
  const c = character
  // 使用传入的 trustPct 或 character 自带的 trust_pct（默认 50）
  const affinity = trustPct ?? c.trust_pct ?? 50

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
    >
      <Card className={`overflow-hidden border-neural-cyan/20 ${isMain ? 'border-neural-magenta/40 bg-neural-magenta/5 glass-panel-glow' : 'glass-panel'} ${className || ''}`}>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 flex-wrap">
              <Badge variant={isMain ? 'accent' : 'success'} size="sm">
                {isMain ? '⭐ 主角' : '👤 NPC'}
              </Badge>
              {(c as { faction?: string }).faction && (
                <Badge variant="warning" size="sm">🏛️ {(c as { faction?: string }).faction}</Badge>
              )}
            </div>
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

          {/* Affinity — bidirectional bar: 左红(敌意) 右绿(好感)，50%中性 */}
          {!isMain && (() => {
            const isHostile = affinity < 50
            const barWidth = Math.abs(affinity - 50) * 2  // 0~100
            const barColor = isHostile ? '#da3633' : '#3fb950'
            const label = affinity <= 35 ? '敌视' : affinity <= 45 ? '疏远' : affinity >= 65 ? '信赖' : affinity >= 55 ? '友好' : '中立'
            const labelColor = affinity <= 35 ? 'text-game-danger' : affinity <= 45 ? 'text-game-warning' : affinity >= 65 ? 'text-game-success' : 'text-game-muted'
            return (
              <div>
                <span className="text-[10px] text-game-muted">关系</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <div className="flex-1 h-2 bg-game-border rounded-full overflow-hidden relative">
                    {/* center line at 50% */}
                    <div className="absolute inset-0 flex items-center justify-center" style={{ zIndex: 0 }}>
                      <div className="h-full w-px bg-game-border/50" />
                    </div>
                    {/* filled bar — grows from center */}
                    <div
                      className="h-full rounded-full transition-all absolute top-0"
                      style={{
                        width: barWidth > 0 ? `${barWidth}%` : '0',
                        [isHostile ? 'right' : 'left']: '50%',
                        background: barColor,
                        zIndex: 1,
                      }}
                    />
                  </div>
                  <span className={`text-[10px] tabular-nums ${labelColor}`}>
                    {affinity}% {label}
                  </span>
                </div>
              </div>
            )
          })()}
        </CardContent>
      </Card>
    </motion.div>
  )
}
