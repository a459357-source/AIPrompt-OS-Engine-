import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import type { Character } from '@/lib/types'
import { useAdultThemeOptional } from '@/contexts/AdultThemeContext'
import { getAdultRelationLevel } from '@/lib/theme'

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
  const adultMode = useAdultThemeOptional()?.adultMode ?? false
  const affinity = trustPct ?? c.trust_pct ?? 50

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
    >
      <Card className={`overflow-hidden border-neural-cyan/20 ${isMain ? 'border-neural-magenta/40 bg-neural-magenta/5 glass-panel-glow' : 'glass-panel'} ${className || ''}`}>
        {/* ── V6.7: Character portrait (enlarged) ── */}
        {c.image_url ? (
          <div className="relative w-full h-48 overflow-hidden bg-neural-void/60 border-b border-game-border/30">
            <img src={c.image_url} alt={c.name || ''} className="w-full h-full object-cover" loading="lazy" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent pointer-events-none" />
          </div>
        ) : (
          <div className="w-full h-24 overflow-hidden bg-neural-void/40 border-b border-game-border/20 flex items-center justify-center">
            <span className="text-game-dim text-3xl select-none">🎭</span>
          </div>
        )}
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

          {!isMain && (() => {
            if (adultMode) {
              const level = getAdultRelationLevel(affinity)
              return (
                <div className="adult-relation-panel">
                  <span className="text-[10px] text-game-muted">关系</span>
                  <div className="adult-relation-bar mt-1">
                    <div
                      className="adult-relation-bar-fill"
                      style={{ width: `${affinity}%`, backgroundColor: level.color }}
                    />
                  </div>
                  <span className="adult-relation-label mt-1 block" style={{ color: level.color }}>
                    {level.label}
                  </span>
                </div>
              )
            }
            const isHostile = affinity < 50
            const barWidth = Math.abs(affinity - 50) * 2
            const barColor = isHostile ? '#da3633' : '#3fb950'
            const label = affinity <= 35 ? '敌视' : affinity <= 45 ? '疏远' : affinity >= 65 ? '信赖' : affinity >= 55 ? '友好' : '中立'
            const labelColor = affinity <= 35 ? 'text-game-danger' : affinity <= 45 ? 'text-game-warning' : affinity >= 65 ? 'text-game-success' : 'text-game-muted'
            return (
              <div>
                <span className="text-[10px] text-game-muted">关系</span>
                <div className="flex items-center gap-2 mt-0.5">
                  <div className="flex-1 h-2 bg-game-border rounded-full overflow-hidden relative">
                    <div className="absolute inset-0 flex items-center justify-center" style={{ zIndex: 0 }}>
                      <div className="h-full w-px bg-game-border/50" />
                    </div>
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
