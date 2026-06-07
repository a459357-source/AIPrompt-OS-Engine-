import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Heart, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { useContentPreferences } from '@/hooks/useContentPreferences'
import { cn } from '@/lib/utils'

function WeightSlider({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string
  value: number
  disabled: boolean
  onChange: (v: number) => void
}) {
  return (
    <div className="flex items-center gap-2 w-full">
      <span className="text-[11px] text-game-muted w-8 tabular-nums">{label}</span>
      <Slider
        value={[value]}
        min={0}
        max={100}
        step={1}
        disabled={disabled}
        onValueChange={([v]) => onChange(v)}
        className="flex-1 min-w-0"
      />
      <span className="text-[11px] text-game-text w-8 text-right tabular-nums">{value}</span>
    </div>
  )
}

export function AdultContentControls() {
  const location = useLocation()
  const onGamePage = location.pathname === '/game'
  const {
    loading,
    saving,
    adultMode,
    adultProfileOptions,
    adultProfileLabels,
    adultProfileDescriptions,
    adultTheme,
    adultThemeOptions,
    adultThemeLabels,
    visualTheme,
    visualThemeOptions,
    visualThemeLabels,
    expressionStyle,
    expressionStyleOptions,
    expressionStyleLabels,
    contentWeights,
    activeAdultProfile,
    savePreferences,
  } = useContentPreferences()

  const [open, setOpen] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  if (loading) return null

  return (
    <div ref={panelRef} className="relative flex items-center gap-1.5 shrink-0">
      <button
        type="button"
        className={cn(
          'flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all duration-[800ms] border',
          adultMode
            ? 'border-pink-500/40 bg-pink-500/10 text-pink-200'
            : 'border-transparent text-game-muted hover:text-game-text hover:bg-neural-glass/50',
        )}
        onClick={() => savePreferences({ adultMode: !adultMode }, true)}
        title="成人内容模式"
      >
        <Heart className={cn('w-3.5 h-3.5', adultMode && 'fill-pink-400/80 text-pink-300')} />
        <span className="hidden sm:inline">成人</span>
        <span className="hidden md:inline text-[10px] opacity-80">{adultMode ? '开' : '关'}</span>
      </button>

      {adultMode && (
        <button
          type="button"
          className="flex items-center gap-0.5 px-1.5 py-1 rounded-md text-[10px] text-game-muted hover:text-game-text hover:bg-neural-glass/50 transition-colors"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          偏好
          <ChevronDown className={cn('w-3 h-3 transition-transform', open && 'rotate-180')} />
        </button>
      )}

      {saving && (
        <span className="text-[9px] text-game-dim hidden sm:inline">保存中</span>
      )}

      {open && adultMode && (
        <div className="absolute top-full right-0 mt-1.5 z-[60] w-[min(92vw,22rem)] max-h-[min(70vh,32rem)] overflow-y-auto rounded-lg glass-panel-opaque shadow-2xl p-3 space-y-3">
          <div className="private-mode-banner rounded-lg border px-3 py-2 space-y-1 bg-game-surface/90">
            <p className="text-xs font-semibold text-game-accent">🌙 私人故事模式</p>
            <p className="text-[10px] text-game-muted">人物关系 · 情感发展 · 亲密互动</p>
          </div>

          {onGamePage && (
            <div className="text-[10px] text-game-dim px-1">
              模拟页「沉浸阅读」仍在 ⚡ 快捷设置中
            </div>
          )}

          <div className="space-y-2">
            <Label className="text-xs text-game-muted">内容倾向</Label>
            <div className="flex flex-col gap-1.5">
              {adultProfileOptions.map((profileId) => (
                <button
                  key={profileId}
                  type="button"
                  onClick={() => savePreferences({ adultProfile: profileId }, true)}
                  className={cn(
                    'text-left rounded-lg border px-2.5 py-2 transition-colors bg-game-surface/80',
                    activeAdultProfile === profileId
                      ? 'border-game-accent bg-game-accent/15'
                      : 'border-game-border/60 hover:border-game-accent/40',
                  )}
                >
                  <span className="text-xs font-medium text-game-text">
                    {adultProfileLabels[profileId] || profileId}
                  </span>
                  {adultProfileDescriptions[profileId] && (
                    <p className="text-[10px] text-game-muted mt-0.5">
                      {adultProfileDescriptions[profileId]}
                    </p>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs text-game-muted">表达风格</Label>
            <div className="flex flex-wrap gap-1">
              {expressionStyleOptions.map((opt) => (
                <Button
                  key={opt}
                  type="button"
                  size="xs"
                  variant={expressionStyle === opt ? 'primary' : 'ghost'}
                  onClick={() => savePreferences({ expressionStyle: opt }, true)}
                >
                  {expressionStyleLabels[opt] || opt}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs text-game-muted">视觉主题</Label>
            <div className="flex flex-wrap gap-1">
              {visualThemeOptions.map((themeId) => (
                <Button
                  key={themeId}
                  type="button"
                  size="xs"
                  variant={visualTheme === themeId ? 'primary' : 'ghost'}
                  onClick={() => savePreferences({ visualTheme: themeId }, true)}
                >
                  {visualThemeLabels[themeId] || themeId}
                </Button>
              ))}
            </div>
            <div className={cn(
              'flex flex-wrap gap-1 transition-opacity',
              visualTheme === 'desire' ? 'opacity-100' : 'opacity-40 pointer-events-none',
            )}>
              {adultThemeOptions.map((themeId) => (
                <Button
                  key={themeId}
                  type="button"
                  size="xs"
                  variant={adultTheme === themeId ? 'primary' : 'ghost'}
                  disabled={visualTheme !== 'desire'}
                  onClick={() => savePreferences({ adultTheme: themeId }, true)}
                >
                  {adultThemeLabels[themeId] || themeId}
                </Button>
              ))}
            </div>
          </div>

          <div>
            <button
              type="button"
              className="flex items-center gap-1 text-xs text-game-muted hover:text-game-accent py-1"
              onClick={() => setAdvancedOpen((v) => !v)}
            >
              <span>{advancedOpen ? '▼' : '▶'}</span>
              <span>高级 · 内容权重</span>
              {!activeAdultProfile && (
                <Badge variant="outline" size="sm" className="text-[9px] ml-1">自定义</Badge>
              )}
            </button>
            {advancedOpen && (
              <div className="mt-2 space-y-2 pl-1">
                <WeightSlider
                  label="剧情"
                  value={contentWeights.story}
                  disabled={false}
                  onChange={(v) => {
                    const remaining = 100 - v
                    const ratio = contentWeights.romance + contentWeights.adult || 1
                    const newRomance = Math.round(remaining * contentWeights.romance / ratio)
                    savePreferences({ contentWeights: { story: v, romance: newRomance, adult: remaining - newRomance } })
                  }}
                />
                <WeightSlider
                  label="感情"
                  value={contentWeights.romance}
                  disabled={false}
                  onChange={(v) => {
                    const remaining = 100 - v
                    const ratio = contentWeights.story + contentWeights.adult || 1
                    const newStory = Math.round(remaining * contentWeights.story / ratio)
                    savePreferences({ contentWeights: { story: newStory, romance: v, adult: remaining - newStory } })
                  }}
                />
                <WeightSlider
                  label="成人"
                  value={contentWeights.adult}
                  disabled={false}
                  onChange={(v) => {
                    const remaining = 100 - v
                    const ratio = contentWeights.story + contentWeights.romance || 1
                    const newStory = Math.round(remaining * contentWeights.story / ratio)
                    savePreferences({ contentWeights: { story: newStory, romance: remaining - newStory, adult: v } })
                  }}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
