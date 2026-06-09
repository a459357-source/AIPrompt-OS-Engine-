import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { StatusToast } from '@/components/StatusToast'
import { InspectorPanel } from '@/components/layout/InspectorPanel'
import { usePageShell } from '@/components/layout/usePageShell'
import { GlassPanel } from '@/components/neural/GlassPanel'
import { getGameState, startGameOnce, nextTurn, getHistory, getGameGenSettings, updateGameGenSettings, formatFetchError, cancelGeneration, getGenerationStatus, waitForGameReady, supplementLore, type HistoryTurn, type GameGenSettings, type ContentWeights, type ObjectivesGameData } from '@/lib/api'
import { logger } from '@/lib/logger'
import { parseOptionEffects, parseGameOption, formatOptionStatusMetrics } from '@/lib/relationHints'
import { useAppSettings } from '@/hooks/useAppSettings'
import { getSettings, saveSettings, clampAutoAdvanceRounds, AUTO_ADVANCE_ROUND_OPTIONS, MAX_WIDTH_OPTIONS, storyMaxWidthCSSValue } from '@/lib/settings'
import { dispatchAdultModeChange, dispatchAdultThemeChange, dispatchVisualThemeChange, getAdultRelationLevel, applyUiTheme, VISUAL_THEME_OPTIONS, VISUAL_THEME_LABELS, CONTENT_PREFERENCES_SAVED, ADULT_MODE_EVENT, type AdultThemeId, type VisualThemeId } from '@/lib/theme'
import { t, tTheme } from '@/lib/i18n'
import { dedupeCharactersByName } from '@/lib/characters'
import { cn } from '@/lib/utils'
import { suggestsAdultModeForOptions, suggestsAdultModeForText } from '@/lib/adultContentHint'
import { AdultUnlockDialog } from '@/components/AdultUnlockDialog'

function AdultModeSuggestBanner({
  onEnable,
  className,
}: {
  onEnable: () => void
  className?: string
}) {
  return (
    <div className={cn(
      'rounded-md border border-amber-500/35 bg-amber-500/10 px-3 py-2 text-xs text-amber-100/90 flex flex-wrap items-center gap-2',
      className,
    )}>
      <span>
        检测到较明确的成人向内容。建议在顶栏
        <strong className="mx-0.5 font-semibold">❤️ 成人</strong>
        中开启成人模式，以获得更匹配的情节与选项。
      </span>
      <Button
        type="button"
        variant="outline"
        size="xs"
        className="border-amber-500/50 shrink-0"
        onClick={onEnable}
      >
        开启成人模式
      </Button>
    </div>
  )
}

/** Keep in sync with config.py */
const STORY_CHAR_TO_TOKEN = 1.35
const JSON_OUTPUT_OVERHEAD = 3500
const COMPRESS_BASE = 4000
const COMPRESS_STORY_FACTOR = 5

function estimateMaxTokens(length: number, min: number, max: number, outputCap: number) {
  const clamped = Math.max(min, Math.min(max, length))
  return Math.max(1, Math.min(outputCap, Math.floor(clamped * STORY_CHAR_TO_TOKEN + JSON_OUTPUT_OVERHEAD)))
}

function estimateCompressThreshold(length: number, min: number, max: number, contextCap: number) {
  const clamped = Math.max(min, Math.min(max, length))
  const perTurnTokens = Math.floor(clamped * 0.6)
  return Math.max(500, Math.min(contextCap, COMPRESS_BASE + perTurnTokens * COMPRESS_STORY_FACTOR))
}

function parseDraftLength(draft: string, fallback: number) {
  const parsed = parseInt(draft, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

function countStoryChars(text: string) {
  return text.replace(/\s/g, '').length
}

import { storyTargetBounds, storyLengthRangeLabel } from '@/lib/storyLength'

interface CharInfo {
  name: string
  role: string
  relation: string
  level: string
  affection?: number
  trust_pct?: number
  tier?: string
  faction?: string
}

interface FactionInfo {
  name: string
  role: string
  reputation_pct: number
  reputation: number
  attitude_label: string
  flags: string[]
  attitudes: { target: string; attitude: number; label: string; flags: string[] }[]
  controlledTerritories?: string[]
  subordinateOrganizations?: string[]
  keyAssets?: string[]
  power?: { military: number; economic: number; political: number; technology: number }
}

interface GameVisuals {
  characters: { name: string; image_url: string }[]
  factions: { name: string; image_url: string }[]
  scene: { scene_id?: string; image_url: string } | null
}

interface NarrativeNode {
  event_id: string
  context: string
  characters: { name: string }[]
  choices: { choice_id: string; text: string; target_event_id: string; tone: string }[]
}

function OptionEffectsInline({
  effects,
  effectText,
  attitude,
}: {
  effects: ReturnType<typeof parseOptionEffects> | null
  effectText: string
  attitude: string
}) {
  const parsed = effects ?? (effectText.trim() ? parseOptionEffects(effectText) : { hints: [], narrative: [] })
  const metricsLine = [
    formatOptionStatusMetrics(parsed.hints),
    parsed.narrative.filter(Boolean).join(' · '),
  ].filter(Boolean).join(' · ')
  const attitudeText = attitude.trim()

  if (!attitudeText && !metricsLine) {
    if (!effectText.trim()) return null
    return (
      <p className="w-full text-center text-[11px] leading-snug text-game-muted px-1">
        {effectText.trim()}
      </p>
    )
  }

  return (
    <p className="w-full text-center text-[11px] leading-snug text-game-muted px-1">
      {attitudeText && <span className="text-game-accent/90">{attitudeText}</span>}
      {attitudeText && metricsLine && <span className="text-game-dim"> · </span>}
      {metricsLine && <span className="text-game-muted/90">{metricsLine}</span>}
    </p>
  )
}

function resolveHistoryChoice(choice: string, options: string[]): { text: string; isCustom: boolean } {
  const trimmed = choice.trim()
  const idx = trimmed.charCodeAt(0) - 65
  const isLetter = /^[A-Z]$/i.test(trimmed)
  if (isLetter && options[idx]) {
    return { text: parseGameOption(options[idx]).action, isCustom: false }
  }
  return { text: trimmed, isCustom: !isLetter }
}

function AffectionBar({ value, adultMode = false }: { value: number; name?: string; adultMode?: boolean }) {
  const safe = Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : 50

  if (adultMode) {
    const level = getAdultRelationLevel(safe)
    return (
      <div className="space-y-1 adult-relation-panel">
        <div className="adult-relation-bar">
          <div
            className="adult-relation-bar-fill"
            style={{ width: `${safe}%`, backgroundColor: level.color }}
          />
        </div>
        <span className="adult-relation-label" style={{ color: level.color }}>
          {level.label}
        </span>
      </div>
    )
  }

  const hostility = Math.max(0, Math.min(5, Math.round((50 - safe) / 10)))
  const affection = Math.max(0, Math.min(5, Math.round((safe - 50) / 10)))
  const neutral = 10 - hostility - affection
  const label = safe <= 35 ? '敌视' : safe <= 45 ? '疏远' : safe >= 65 ? '信赖' : safe >= 55 ? '友好' : '中立'
  return (
    <span className="text-xs tracking-[2px] select-none leading-none">
      <span className="text-game-danger">{'█'.repeat(hostility)}</span>
      <span className="text-game-dim">{'░'.repeat(neutral)}</span>
      <span className="text-game-success">{'█'.repeat(affection)}</span>
      <span className="text-game-muted ml-1">{label}</span>
    </span>
  )
}

function GameStatusList({
  characters,
  factions,
  adultMode,
  visuals,
}: {
  characters: CharInfo[]
  factions: FactionInfo[]
  adultMode: boolean
  visuals: GameVisuals
}) {
  const visualByChar = new Map(visuals.characters.map(v => [v.name, v.image_url]))
  const visualByFaction = new Map(visuals.factions.map(v => [v.name, v.image_url]))
  return (
    <div className="space-y-4">
      {characters.length === 0 && factions.length === 0 && (
        <p className="text-xs text-game-dim text-center py-4">暂无数据</p>
      )}
      {characters.map((c) => {
        const img = visualByChar.get(c.name)
        return (
        <div key={`c-${c.name}`} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              {c.name}
              {c.tier === '主角' && <span className="text-game-accent text-xs ml-1">⭐</span>}
              {c.tier === '核心' && <span className="text-game-primary text-xs ml-1">◆</span>}
            </span>
            <div className="flex items-center gap-1">
              {c.faction && (
                <Badge variant="warning" size="sm">🏛️ {c.faction}</Badge>
              )}
              <Badge variant="outline" size="sm">{c.role}</Badge>
            </div>
          </div>
          {img && (
            <div className="w-full rounded-md overflow-hidden border border-game-border/50 bg-neural-void/60">
              <img src={img} alt={c.name} className="w-full max-h-56 object-contain object-top" loading="lazy" />
            </div>
          )}
          {c.relation && <p className="text-xs text-game-muted">{c.relation}</p>}
          {c.tier !== '主角' && (
            <AffectionBar value={c.affection ?? 50} adultMode={adultMode} />
          )}
          <Separator />
        </div>
        )
      })}

      {factions.length > 0 && characters.length > 0 && (
        <p className="text-xs text-game-dim font-bold pt-2">🏛️ 势力</p>
      )}
      {factions.map((f) => {
        const fImg = visualByFaction.get(f.name)
        const attitudes = (f.attitudes || [])
          .filter(a => Math.abs((a.attitude ?? 0.5) - 0.5) >= 0.15)
          .slice(0, 3)
        return (
        <div key={`f-${f.name}`} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {fImg ? (
                <div className="w-8 h-8 rounded-md overflow-hidden border border-game-border/50 shrink-0 bg-neural-void/60">
                  <img src={fImg} alt={f.name} className="w-full h-full object-cover" loading="lazy" />
                </div>
              ) : (
                <div className="w-8 h-8 rounded-md border border-dashed border-game-border/30 shrink-0 bg-neural-void/40 flex items-center justify-center">
                  <span className="text-game-dim text-xs">🏛</span>
                </div>
              )}
              <span className="text-sm font-medium">{f.name}</span>
            </div>
            <Badge variant="outline" size="sm" className={f.attitude_label === '敌对' ? 'border-red-500/50 text-red-400' : f.attitude_label === '同盟' ? 'border-green-500/50 text-green-400' : ''}>
              {f.attitude_label}
            </Badge>
          </div>
          {f.role && <p className="text-xs text-game-muted">{f.role}</p>}
          <div className="flex items-center gap-2">
            <AffectionBar value={(f.reputation ?? 0.5) * 100} adultMode={adultMode} />
            <span className="text-xs text-game-dim tabular-nums">{Math.round((f.reputation ?? 0.5) * 100)}%</span>
          </div>
          {attitudes.map(a => {
            const labelColor = a.label === '敌对' || a.label === '冷淡'
              ? 'text-red-400'
              : a.label === '同盟' || a.label === '友好'
                ? 'text-green-400'
                : 'text-game-muted'
            return (
              <div key={a.target} className="flex items-center gap-1 text-[10px]">
                <span className="text-game-dim">→ {a.target}</span>
                <span className={labelColor}>{a.label}</span>
              </div>
            )
          })}
          <Separator />
        </div>
        )
      })}
    </div>
  )
}

function GenFieldHint({ children }: { children: React.ReactNode }) {
  return <span className="text-[11px] text-game-dim/90 leading-snug">{children}</span>
}

function QuickGenRow({ label, children, hint }: { label: string; children: React.ReactNode; hint: string }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[5.5rem_1fr] gap-x-3 gap-y-1 items-center py-1.5 border-b border-game-border/40 last:border-0">
      <Label className="text-xs text-game-muted whitespace-nowrap">{label}</Label>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 min-w-0">
        {children}
        <GenFieldHint>{hint}</GenFieldHint>
      </div>
    </div>
  )
}

/** 遮盖游戏主区域，不挡顶部/底部导航（z-30 < 导航 z-40/z-50） */
function GameBusyOverlay({ message }: { message: string }) {
  return (
    <div
      className="fixed inset-x-0 top-12 bottom-16 z-30 flex items-center justify-center md:bottom-0 md:top-11"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="absolute inset-0 bg-black/55 backdrop-blur-[1px] pointer-events-auto" aria-hidden />
      <div className="relative flex flex-col items-center gap-3 rounded-lg border border-game-border bg-game-card/95 px-10 py-8 shadow-2xl pointer-events-none">
        <span className="inline-block h-9 w-9 animate-spin rounded-full border-2 border-game-accent/30 border-t-game-accent" />
        <span className="text-sm text-game-text">{message}</span>
      </div>
    </div>
  )
}

export default function Game() {
  const appSettings = useAppSettings()
  const [story, setStory] = useState('')
  const [options, setOptions] = useState<string[]>([])
  const [turn, setTurn] = useState(0)
  const [status, setStatus] = useState('SETUP')
  const [scene, setScene] = useState('')
  const [characters, setCharacters] = useState<CharInfo[]>([])
  const [factions, setFactions] = useState<FactionInfo[]>([])
  const [objectives, setObjectives] = useState<ObjectivesGameData>({ main: [], side: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [choosing, setChoosing] = useState(false)
  const [genProgress, setGenProgress] = useState('')
  const [genStoryChars, setGenStoryChars] = useState(0)
  const [customInput, setCustomInput] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [showConsequences, setShowConsequences] = useState(true)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [visuals, setVisuals] = useState<GameVisuals>({ characters: [], factions: [], scene: null })
  const [narrativeNode, setNarrativeNode] = useState<NarrativeNode | null>(null)
  const [supplementOpen, setSupplementOpen] = useState(false)
  const [supplementText, setSupplementText] = useState('')
  const [supplementLoading, setSupplementLoading] = useState(false)
  const [supplementError, setSupplementError] = useState('')
  const [supplementSuccess, setSupplementSuccess] = useState('')
  const [supplementAdultHint, setSupplementAdultHint] = useState(false)
  const [history, setHistory] = useState<HistoryTurn[]>([])
  const [historyFocusTurn, setHistoryFocusTurn] = useState<number | null>(null)
  const [historyError, setHistoryError] = useState('')
  const [historyLoading, setHistoryLoading] = useState(false)
  const [viewingTurn, setViewingTurn] = useState<number | null>(null)
  const [timelineCache, setTimelineCache] = useState<HistoryTurn[]>([])
  const [timelineLoading, setTimelineLoading] = useState(false)
  const [storyLength, setStoryLength] = useState(1000)
  const [storyLengthMin, setStoryLengthMin] = useState(300)
  const [storyLengthMax, setStoryLengthMax] = useState(281851)
  const [storyLengthRecommended, setStoryLengthRecommended] = useState(1000)
  const [storyLengthDraft, setStoryLengthDraft] = useState('1000')
  const [maxTokens, setMaxTokens] = useState(1800)
  const [maxOutputTokens, setMaxOutputTokens] = useState(384000)
  const [contextTokens, setContextTokens] = useState(1000000)
  const [temperature, setTemperature] = useState(0.8)
  const [topP, setTopP] = useState(0.9)
  const [compressThreshold, setCompressThreshold] = useState(4000)
  const [compressThresholdDraft, setCompressThresholdDraft] = useState('4000')
  const [optionCount, setOptionCount] = useState(4)
  const [narrativePov, setNarrativePov] = useState('auto')
  const [stylePreference, setStylePreference] = useState('balanced')
  const [repetitionCheck, setRepetitionCheck] = useState('standard')
  const [adultMode, setAdultMode] = useState(false)
  const [adultUnlocked, setAdultUnlocked] = useState(false)
  const [adultUnlockOpen, setAdultUnlockOpen] = useState(false)
  const [adultUnlockError, setAdultUnlockError] = useState('')
  const [adultUnlockSaving, setAdultUnlockSaving] = useState(false)
  const [adultProfile, setAdultProfile] = useState('balanced')
  const [adultProfileOptions, setAdultProfileOptions] = useState<string[]>(['story_first', 'balanced', 'adult_first'])
  const [adultProfileLabels, setAdultProfileLabels] = useState<Record<string, string>>({})
  const [adultProfileDescriptions, setAdultProfileDescriptions] = useState<Record<string, string>>({})
  const [adultTheme, setAdultTheme] = useState<AdultThemeId>('deep_purple')
  const [visualTheme, setVisualTheme] = useState<VisualThemeId>('desire')
  const [adultThemeOptions, setAdultThemeOptions] = useState<string[]>([])
  const [adultThemeLabels, setAdultThemeLabels] = useState<Record<string, string>>({})
  const [visualThemeOptions, setVisualThemeOptions] = useState<string[]>([...VISUAL_THEME_OPTIONS])
  const [visualThemeLabels, setVisualThemeLabels] = useState<Record<string, string>>({ ...VISUAL_THEME_LABELS })
  const [expressionStyle, setExpressionStyle] = useState('light_novel')
  const [expressionStyleOptions, setExpressionStyleOptions] = useState<string[]>(['literary', 'romantic', 'light_novel', 'direct'])
  const [expressionStyleLabels, setExpressionStyleLabels] = useState<Record<string, string>>({})
  const [contentWeights, setContentWeights] = useState<ContentWeights>({ story: 40, romance: 30, adult: 30 })
  const [presetWeights, setPresetWeights] = useState<Record<string, ContentWeights>>({})
  const [readingMode, setReadingMode] = useState(false)
  const [relationPanelOpen, setRelationPanelOpen] = useState(true)
  const [genSettingsOpen, setGenSettingsOpen] = useState(() => {
    const saved = localStorage.getItem('promptos_gen_settings_open')
    return saved === 'true'
  })
  // persist quick settings toggle
  useEffect(() => {
    localStorage.setItem('promptos_gen_settings_open', String(genSettingsOpen))
  }, [genSettingsOpen])
  const [genSettingsSaved, setGenSettingsSaved] = useState(false)
  const [genSettingsSaving, setGenSettingsSaving] = useState(false)
  const [genSettingsSaveError, setGenSettingsSaveError] = useState('')
  const [optionsRegenerated, setOptionsRegenerated] = useState(false)
  const storyScrollRef = useRef<HTMLDivElement>(null)
  const storyEndRef = useRef<HTMLDivElement>(null)
  const skipScrollTopRef = useRef(false)
  const genSettingsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const genSettingsSavedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const optionsRegenTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve())
  const mountedRef = useRef(true)
  const loadSeqRef = useRef(0)
  const typewriterBufRef = useRef('')
  const typewriterTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const flushTypewriter = useCallback(() => {
    if (typewriterTimerRef.current) return
    typewriterTimerRef.current = setInterval(() => {
      const buf = typewriterBufRef.current
      if (!buf.length) {
        if (typewriterTimerRef.current) clearInterval(typewriterTimerRef.current)
        typewriterTimerRef.current = null
        return
      }
      const ch = buf[0]
      typewriterBufRef.current = buf.slice(1)
      setStory((prev) => prev + ch)
      setGenStoryChars((n) => n + (/\s/.test(ch) ? 0 : 1))
    }, 18)
  }, [])

  const appendStoryDelta = useCallback((delta: string) => {
    if (!mountedRef.current || !delta) return
    if (appSettings.typewriterEffect) {
      typewriterBufRef.current += delta
      flushTypewriter()
    } else {
      setStory((prev) => prev + delta)
      setGenStoryChars((n) => n + countStoryChars(delta))
    }
  }, [appSettings.typewriterEffect, flushTypewriter])

  const resetStreamStory = useCallback(() => {
    typewriterBufRef.current = ''
    if (typewriterTimerRef.current) {
      clearInterval(typewriterTimerRef.current)
      typewriterTimerRef.current = null
    }
    if (mountedRef.current) {
      setStory('')
      setGenStoryChars(0)
    }
  }, [])
  const streamGenerationStartedRef = useRef(false)
  const autoAdvanceDelaySec = 5
  const pendingGenPatchRef = useRef<{
    storyLength?: number
    temperature?: number
    topP?: number
    compressThreshold?: number
    optionCount?: number
    narrativePov?: string
    stylePreference?: string
    repetitionCheck?: string
    adultMode?: boolean
    adultProfile?: string
    adultTheme?: string
    visualTheme?: string
    expressionStyle?: string
    contentWeights?: ContentWeights
  }>({})
  const [autoAdvancePaused, setAutoAdvancePaused] = useState(true)
  const [autoAdvanceRemaining, setAutoAdvanceRemaining] = useState(0)
  const [autoAdvanceCountdown, setAutoAdvanceCountdown] = useState(autoAdvanceDelaySec)
  const [openingPending, setOpeningPending] = useState(false)
  const persistGenSettingsBeforeTurnRef = useRef<(() => Promise<void>) | null>(null)

  const applyTurnData = useCallback((data: {
    story: string
    options?: string[]
    state: Record<string, unknown>
    visuals?: GameVisuals
    narrative_node?: NarrativeNode
  }) => {
    setViewingTurn(null)
    setStory(data.story)
    setOptions(data.options || [])
    if ((data.options?.length ?? 0) > 0) setOpeningPending(false)
    const st = data.state
    setTurn((st.turn as number) || 1)
    setStatus((st.status as string) || 'SETUP')
    setScene((st.scene as string) || '')
    const chars = st.characters as Record<string, CharInfo> | undefined
    if (chars) {
      setCharacters(dedupeCharactersByName(Object.values(chars).map((c) => ({
        ...c,
        affection: c.affection ?? c.trust_pct ?? 50,
      }))))
    }
    const factionsData = st.factions as FactionInfo[] | undefined
    if (factionsData) setFactions(factionsData)
    const objData = st.objectives as ObjectivesGameData | undefined
    if (objData) setObjectives(objData)
    if (data.visuals) setVisuals(data.visuals)
    if (data.narrative_node) setNarrativeNode(data.narrative_node)
  }, [])

  const loadGame = useCallback(async () => {
    const loadSeq = ++loadSeqRef.current
    setLoading(true)
    setError('')
    logger.info('Game', 'Loading game state...')
    try {
      const data = await getGameState()
      if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
      if (data.error) { setError(data.error); setLoading(false); return }

      if (data.not_started) {
        const gen = await getGenerationStatus()
        if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
        if (gen.active && gen.story) {
          logger.info('Game', 'Opening generation in flight — waiting')
          setOpeningPending(true)
          setStory(gen.story)
          setLoading(false)
          try {
            const ready = await waitForGameReady()
            if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
            skipScrollTopRef.current = true
            applyTurnData(ready)
            setOpeningPending(false)
          } catch (e) {
            if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
            logger.warn('Game', 'Opening wait timeout — clearing stale generation')
            await cancelGeneration()
            setOpeningPending(true)
            setStory('')
            setError('')
            // fall through to startGameOnce below
          }
          if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
          const recheck = await getGameState()
          if (!recheck.not_started && recheck.story) {
            skipScrollTopRef.current = true
            applyTurnData({
              story: recheck.story,
              options: recheck.options,
              state: recheck.state as Record<string, unknown>,
              visuals: recheck.visuals,
              narrative_node: recheck.narrative_node,
            })
            setOpeningPending(false)
            return
          }
        }

        logger.info('Game', 'Game not started — calling startGameOnce()')
        setOpeningPending(true)
        setStory('')
        await persistGenSettingsBeforeTurnRef.current?.()
        if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
        let firstDelta = false
        const started = await startGameOnce({
          onStoryDelta: (delta) => {
            appendStoryDelta(delta)
            if (!firstDelta && mountedRef.current) {
              firstDelta = true
              setLoading(false)
            }
          },
          onStoryReset: resetStreamStory,
          onProgress: (phase) => {
            if (mountedRef.current) setGenProgress(phase)
          },
        })
        if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
        if (started.error || !started.story) {
          setError(started.error || '开篇生成失败')
          setLoading(false)
          return
        }
        skipScrollTopRef.current = true
        applyTurnData({
          story: started.story,
          options: started.options,
          state: started.state as unknown as Record<string, unknown>,
          visuals: started.visuals,
          narrative_node: started.narrative_node,
        })
        setOpeningPending(false)
        logger.info('Game', 'Opening scene ready')
        setLoading(false)
        return
      }

      applyTurnData({
        story: data.story,
        options: data.options,
        state: data.state as Record<string, unknown>,
        visuals: data.visuals,
        narrative_node: data.narrative_node,
      })
      logger.info('Game', `Loaded: turn=${(data.state as Record<string, unknown>).turn}`)
    } catch (e) {
      if (loadSeq !== loadSeqRef.current || !mountedRef.current) return
      const msg = formatFetchError(e)
      logger.error('Game', 'Load failed', { error: msg })
      setError(msg)
    }
    if (loadSeq === loadSeqRef.current && mountedRef.current) setLoading(false)
  }, [applyTurnData, appendStoryDelta, resetStreamStory])

  useEffect(() => { loadGame() }, [loadGame])

  const applyGenSettings = useCallback((data: GameGenSettings) => {
    setStoryLength(data.story_length)
    setStoryLengthDraft(String(data.story_length))
    setStoryLengthMin(data.min)
    setStoryLengthMax(data.max)
    setStoryLengthRecommended(data.recommended)
    setMaxTokens(data.max_tokens)
    setMaxOutputTokens(data.max_output_tokens)
    setContextTokens(data.context_tokens)
    setTemperature(data.temperature)
    setTopP(data.top_p)
    setCompressThreshold(data.compress_threshold)
    setCompressThresholdDraft(String(data.compress_threshold))
    setOptionCount(data.option_count)
    setNarrativePov(data.narrative_pov)
    setStylePreference(data.style_preference)
    setRepetitionCheck(data.repetition_check)
    setAdultMode(data.adult_mode)
    setAdultUnlocked(!!data.adult_unlocked)
    dispatchAdultModeChange(data.adult_mode)
    setAdultProfile(data.adult_profile)
    setAdultProfileOptions(data.adult_profile_options)
    setAdultProfileLabels(data.adult_profile_labels)
    setAdultProfileDescriptions(data.adult_profile_descriptions)
    const themeId = (data.adult_theme || 'deep_purple') as AdultThemeId
    setAdultTheme(themeId)
    setAdultThemeOptions(data.adult_theme_options)
    setAdultThemeLabels(data.adult_theme_labels)
    setVisualThemeOptions(data.visual_theme_options?.length ? data.visual_theme_options : [...VISUAL_THEME_OPTIONS])
    setVisualThemeLabels({ ...VISUAL_THEME_LABELS, ...(data.visual_theme_labels ?? {}) })
    setVisualTheme((prev) => {
      const apiVisual = data.visual_theme
      const next: VisualThemeId =
        apiVisual === 'adult' || apiVisual === 'desire' ? apiVisual : prev
      if (data.adult_mode) {
        applyUiTheme(next, themeId)
        dispatchAdultThemeChange(themeId)
        dispatchVisualThemeChange(next)
      } else {
        applyUiTheme('normal')
      }
      return next
    })
    setExpressionStyle(data.expression_style)
    setExpressionStyleOptions(data.expression_style_options)
    setExpressionStyleLabels(data.expression_style_labels)
    setContentWeights(data.content_weights)
    setPresetWeights(data.preset_weights)
  }, [])

  useEffect(() => {
    getGameGenSettings()
      .then(applyGenSettings)
      .catch((e) => logger.warn('Game', 'Load gen settings failed', { error: String(e) }))
  }, [applyGenSettings])

  useEffect(() => {
    if (!adultMode && readingMode) setReadingMode(false)
  }, [adultMode, readingMode])

  useEffect(() => {
    const onPrefsSaved = (e: Event) => {
      const detail = (e as CustomEvent<{ options?: string[]; options_regenerated?: boolean }>).detail
      if (detail?.options?.length) setOptions(detail.options)
      getGameGenSettings().then(applyGenSettings).catch(() => {})
    }
    const onAdultMode = (e: Event) => {
      const mode = !!(e as CustomEvent<{ adultMode: boolean }>).detail?.adultMode
      setAdultMode(mode)
    }
    window.addEventListener(CONTENT_PREFERENCES_SAVED, onPrefsSaved)
    window.addEventListener(ADULT_MODE_EVENT, onAdultMode)
    return () => {
      window.removeEventListener(CONTENT_PREFERENCES_SAVED, onPrefsSaved)
      window.removeEventListener(ADULT_MODE_EVENT, onAdultMode)
    }
  }, [applyGenSettings])

  const markGenSettingsSaved = useCallback(() => {
    setGenSettingsSaveError('')
    setGenSettingsSaved(true)
    if (genSettingsSavedTimerRef.current) clearTimeout(genSettingsSavedTimerRef.current)
    genSettingsSavedTimerRef.current = setTimeout(() => setGenSettingsSaved(false), 2000)
  }, [])

  const normalizeGenPatch = useCallback((patch: {
    storyLength?: number
    temperature?: number
    topP?: number
    compressThreshold?: number
    optionCount?: number
    narrativePov?: string
    stylePreference?: string
    repetitionCheck?: string
    adultMode?: boolean
    adultProfile?: string
    adultTheme?: string
    visualTheme?: string
    expressionStyle?: string
    contentWeights?: ContentWeights
  }) => {
    const next = { ...patch }
    if (next.storyLength != null) {
      const clamped = Math.max(storyLengthMin, Math.min(storyLengthMax, next.storyLength))
      next.storyLength = clamped
      const matchedTokens = estimateMaxTokens(clamped, storyLengthMin, storyLengthMax, maxOutputTokens)
      const matchedCompress = estimateCompressThreshold(clamped, storyLengthMin, storyLengthMax, contextTokens)
      setStoryLength(clamped)
      setMaxTokens(matchedTokens)
      setCompressThreshold(matchedCompress)
      setCompressThresholdDraft(String(matchedCompress))
      next.compressThreshold = matchedCompress
    }
    if (next.temperature != null) setTemperature(next.temperature)
    if (next.topP != null) setTopP(next.topP)
    if (next.compressThreshold != null && next.storyLength == null) {
      const clamped = Math.max(500, Math.min(contextTokens, next.compressThreshold))
      setCompressThreshold(clamped)
      setCompressThresholdDraft(String(clamped))
      next.compressThreshold = clamped
    }
    if (next.optionCount != null) {
      const clamped = Math.max(3, Math.min(5, next.optionCount))
      setOptionCount(clamped)
      next.optionCount = clamped
    }
    if (next.narrativePov != null) setNarrativePov(next.narrativePov)
    if (next.stylePreference != null) setStylePreference(next.stylePreference)
    if (next.repetitionCheck != null) setRepetitionCheck(next.repetitionCheck)
    if (next.adultMode != null) {
      setAdultMode(next.adultMode)
      dispatchAdultModeChange(next.adultMode)
      if (next.adultMode) applyUiTheme(visualTheme as VisualThemeId, adultTheme)
      else applyUiTheme('normal')
    }
    if (next.adultProfile != null) {
      setAdultProfile(next.adultProfile)
      const preset = presetWeights[next.adultProfile]
      if (preset) {
        setContentWeights({ ...preset })
        next.contentWeights = { ...preset }
      }
    }
    if (next.adultTheme != null) {
      const themeId = next.adultTheme as AdultThemeId
      setAdultTheme(themeId)
      dispatchAdultThemeChange(themeId)
      if (adultMode) applyUiTheme(visualTheme as VisualThemeId, themeId)
    }
    if (next.visualTheme != null) {
      const visualId = next.visualTheme as VisualThemeId
      setVisualTheme(visualId)
      dispatchVisualThemeChange(visualId)
      if (adultMode) applyUiTheme(visualId, adultTheme)
    }
    if (next.expressionStyle != null) setExpressionStyle(next.expressionStyle)
    if (next.contentWeights != null) setContentWeights({ ...next.contentWeights })
    return next
  }, [storyLengthMin, storyLengthMax, contextTokens, maxOutputTokens, adultTheme, visualTheme, presetWeights])

  const flushGenSettings = useCallback(async (silent = false) => {
    const pending = pendingGenPatchRef.current
    pendingGenPatchRef.current = {}
    if (!Object.keys(pending).length) {
      markGenSettingsSaved()
      return
    }
    if (!silent) setGenSettingsSaving(true)
    setGenSettingsSaveError('')
    try {
      logger.info('Game', 'Saving gen settings', pending)
      const saved = await updateGameGenSettings(pending)
      if (saved.options?.length) {
        setOptions(saved.options)
      }
      if (silent) {
        markGenSettingsSaved()
      } else {
        applyGenSettings(saved)
        if (saved.options_regenerated) {
          setOptionsRegenerated(true)
          if (optionsRegenTimerRef.current) clearTimeout(optionsRegenTimerRef.current)
          optionsRegenTimerRef.current = setTimeout(() => setOptionsRegenerated(false), 3000)
        } else if (saved.options_regen_error && pending.adultMode != null) {
          setGenSettingsSaveError(`选项未重生：${saved.options_regen_error}`)
        }
        logger.info('Game', 'Gen settings saved', {
          story_length: saved.story_length,
          max_tokens: saved.max_tokens,
          compress_threshold: saved.compress_threshold,
          options_regenerated: saved.options_regenerated,
        })
        markGenSettingsSaved()
      }
    } catch (e) {
      const msg = formatFetchError(e)
      logger.error('Game', 'Save gen settings failed', { error: msg })
      if (mountedRef.current) setGenSettingsSaveError(msg)
    } finally {
      if (!silent && mountedRef.current) setGenSettingsSaving(false)
    }
  }, [applyGenSettings, markGenSettingsSaved])

  const queueGenSettingsSave = useCallback((patch: {
    storyLength?: number
    temperature?: number
    topP?: number
    compressThreshold?: number
    optionCount?: number
    narrativePov?: string
    stylePreference?: string
    repetitionCheck?: string
    adultMode?: boolean
    adultProfile?: string
    adultTheme?: string
    visualTheme?: string
    expressionStyle?: string
    contentWeights?: ContentWeights
  }, immediate = false, silent = false) => {
    const normalized = normalizeGenPatch(patch)
    pendingGenPatchRef.current = { ...pendingGenPatchRef.current, ...normalized }

    const scheduleFlush = () => {
      saveQueueRef.current = saveQueueRef.current.then(() => flushGenSettings(silent))
    }

    if (genSettingsTimerRef.current) {
      clearTimeout(genSettingsTimerRef.current)
      genSettingsTimerRef.current = null
    }
    if (immediate) {
      scheduleFlush()
      return
    }
    genSettingsTimerRef.current = setTimeout(() => scheduleFlush(), 600)
  }, [normalizeGenPatch, flushGenSettings])

  const enableAdultModeFromHint = useCallback(async () => {
    if (!adultUnlocked) {
      setAdultUnlockError('')
      setAdultUnlockOpen(true)
      return
    }
    try {
      const saved = await updateGameGenSettings({ adultMode: true })
      applyGenSettings(saved)
      if (saved.options?.length) setOptions(saved.options)
      setSupplementAdultHint(false)
    } catch (e) {
      logger.error('Game', 'Enable adult mode from hint failed', { error: String(e) })
    }
  }, [adultUnlocked, applyGenSettings])

  const submitAdultUnlockFromHint = useCallback(async (key: string) => {
    setAdultUnlockSaving(true)
    setAdultUnlockError('')
    try {
      const saved = await updateGameGenSettings({ adultUnlockKey: key, adultMode: true })
      applyGenSettings(saved)
      if (saved.options?.length) setOptions(saved.options)
      setSupplementAdultHint(false)
      setAdultUnlockOpen(false)
    } catch (e) {
      setAdultUnlockError(e instanceof Error ? e.message : '解锁失败')
    } finally {
      setAdultUnlockSaving(false)
    }
  }, [applyGenSettings])

  const optionsSuggestAdult = useMemo(
    () => !adultMode && options.length > 0 && suggestsAdultModeForOptions(options),
    [adultMode, options],
  )

  const supplementInputSuggestAdult = useMemo(
    () => !adultMode && supplementOpen && suggestsAdultModeForText(supplementText),
    [adultMode, supplementOpen, supplementText],
  )

  const customInputSuggestAdult = useMemo(
    () => !adultMode && showCustomInput && suggestsAdultModeForText(customInput),
    [adultMode, showCustomInput, customInput],
  )

  useEffect(() => {
    if (adultMode) setSupplementAdultHint(false)
  }, [adultMode])

  const previewMaxTokens = useMemo(() => {
    const length = parseDraftLength(storyLengthDraft, storyLength)
    return estimateMaxTokens(length, storyLengthMin, storyLengthMax, maxOutputTokens)
  }, [storyLengthDraft, storyLength, storyLengthMin, storyLengthMax, maxOutputTokens])

  const previewCompressThreshold = useMemo(() => {
    const length = parseDraftLength(storyLengthDraft, storyLength)
    return estimateCompressThreshold(length, storyLengthMin, storyLengthMax, contextTokens)
  }, [storyLengthDraft, storyLength, storyLengthMin, storyLengthMax, contextTokens])

  const commitStoryLengthDraft = useCallback(() => {
    const parsed = parseInt(storyLengthDraft, 10)
    if (!Number.isFinite(parsed)) {
      setStoryLengthDraft(String(storyLength))
      return
    }
    const clamped = Math.max(storyLengthMin, Math.min(storyLengthMax, parsed))
    setStoryLengthDraft(String(clamped))
    queueGenSettingsSave({ storyLength: clamped }, true)
  }, [storyLengthDraft, storyLength, storyLengthMin, storyLengthMax, queueGenSettingsSave])

  const persistGenSettingsBeforeTurn = useCallback(async () => {
    if (genSettingsTimerRef.current) {
      clearTimeout(genSettingsTimerRef.current)
      genSettingsTimerRef.current = null
    }
    const parsed = parseInt(storyLengthDraft, 10)
    if (!Number.isFinite(parsed)) return
    const clamped = Math.max(storyLengthMin, Math.min(storyLengthMax, parsed))
    const pending = { ...pendingGenPatchRef.current }
    pendingGenPatchRef.current = {}
    const patch = {
      ...pending,
      storyLength: clamped,
      compressThreshold: estimateCompressThreshold(clamped, storyLengthMin, storyLengthMax, contextTokens),
      adultMode,
      expressionStyle,
      contentWeights,
    }
    try {
      logger.info('Game', 'Sync gen settings before turn', patch)
      const saved = await updateGameGenSettings(patch)
      applyGenSettings(saved)
    } catch (e) {
      logger.error('Game', 'Persist gen settings before turn failed', { error: String(e) })
    }
  }, [
    storyLengthDraft,
    storyLengthMin,
    storyLengthMax,
    contextTokens,
    adultMode,
    expressionStyle,
    contentWeights,
    applyGenSettings,
  ])

  persistGenSettingsBeforeTurnRef.current = persistGenSettingsBeforeTurn

  const closeHistoryReview = useCallback(() => {
    setHistoryOpen(false)
    setHistoryFocusTurn(null)
  }, [])

  const viewTimelineTurn = useCallback(async (n: number) => {
    if (choosing) return
    if (n >= turn) {
      setViewingTurn(null)
      return
    }
    setTimelineLoading(true)
    try {
      let turns = timelineCache
      if (!turns.some((t) => t.turn === n)) {
        const data = await getHistory()
        if (data.error) {
          setError(data.error)
          return
        }
        turns = data.turns
        setTimelineCache(turns)
      }
      if (turns.some((t) => t.turn === n)) {
        setViewingTurn(n)
      }
    } catch (e) {
      setError(formatFetchError(e))
    } finally {
      setTimelineLoading(false)
    }
  }, [choosing, turn, timelineCache])

  const openHistoryReview = useCallback(async (focusTurn?: number) => {
    if (choosing) return
    setHistoryFocusTurn(focusTurn ?? null)
    setHistoryOpen(true)
    setHistoryError('')
    setHistory([])
    setHistoryLoading(true)
    try {
      const data = await getHistory()
      if (data.error) {
        setHistoryError(data.error)
      } else {
        let turns = data.turns
        if (focusTurn != null && focusTurn === turn && story.trim()) {
          const current: HistoryTurn = {
            turn,
            story,
            options,
            choice: '',
            status,
            scene,
          }
          const idx = turns.findIndex((t) => t.turn === turn)
          turns = idx >= 0 ? turns.map((t, i) => (i === idx ? current : t)) : [...turns, current]
        }
        setHistory(turns)
      }
    } catch (e) {
      setHistoryError(formatFetchError(e))
    }
    setHistoryLoading(false)
  }, [choosing, turn, story, options, status, scene])

  const submitSupplement = useCallback(async () => {
    const text = supplementText.trim()
    if (!text || supplementLoading || choosing) return
    setSupplementLoading(true)
    setSupplementError('')
    setSupplementSuccess('')
    setSupplementAdultHint(false)
    try {
      const result = await supplementLore(text)
      if (result.state) {
        skipScrollTopRef.current = true
        applyTurnData({
          story: result.story ?? story,
          options: result.options,
          state: result.state,
        })
      }
      const detail = result.changes?.length ? result.changes.join('；') : ''
      setSupplementSuccess(detail ? `${result.summary ?? '设定已更新'}（${detail}）` : (result.summary ?? '设定已更新'))
      if (result.suggest_adult_mode || suggestsAdultModeForText(text)) {
        setSupplementAdultHint(true)
      }
      setSupplementText('')
    } catch (e) {
      setSupplementError(formatFetchError(e))
    } finally {
      setSupplementLoading(false)
    }
  }, [supplementText, supplementLoading, choosing, applyTurnData, story])

  useEffect(() => {
    if (!historyOpen || historyLoading || historyFocusTurn == null || history.length === 0) return
    const id = `history-turn-${historyFocusTurn}`
    requestAnimationFrame(() => {
      document.getElementById(id)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    })
  }, [historyOpen, historyLoading, historyFocusTurn, history])

  useEffect(() => {
    const parsed = parseInt(storyLengthDraft, 10)
    if (!Number.isFinite(parsed)) return
    const clamped = Math.max(storyLengthMin, Math.min(storyLengthMax, parsed))
    setCompressThresholdDraft(String(estimateCompressThreshold(clamped, storyLengthMin, storyLengthMax, contextTokens)))
  }, [storyLengthDraft, storyLengthMin, storyLengthMax, contextTokens])

  useEffect(() => {
    const parsed = parseInt(storyLengthDraft, 10)
    if (!Number.isFinite(parsed)) return
    const clamped = Math.max(storyLengthMin, Math.min(storyLengthMax, parsed))
    if (clamped === storyLength) return
    const t = setTimeout(() => {
      queueGenSettingsSave({ storyLength: clamped }, true)
    }, 800)
    return () => clearTimeout(t)
  }, [storyLengthDraft, storyLength, storyLengthMin, storyLengthMax, queueGenSettingsSave])

  const commitCompressThresholdDraft = useCallback(() => {
    const parsed = parseInt(compressThresholdDraft, 10)
    if (!Number.isFinite(parsed)) {
      setCompressThresholdDraft(String(compressThreshold))
      return
    }
    const clamped = Math.max(500, Math.min(contextTokens, parsed))
    setCompressThresholdDraft(String(clamped))
    queueGenSettingsSave({ compressThreshold: clamped }, true)
  }, [compressThresholdDraft, compressThreshold, contextTokens, queueGenSettingsSave])

  const handleNumericFieldKeyDown = useCallback((e: React.KeyboardEvent, commit: () => void) => {
    if (e.key === 'Enter') {
      commit()
      ;(e.target as HTMLInputElement).blur()
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (genSettingsTimerRef.current) clearTimeout(genSettingsTimerRef.current)
      if (genSettingsSavedTimerRef.current) clearTimeout(genSettingsSavedTimerRef.current)
      if (optionsRegenTimerRef.current) clearTimeout(optionsRegenTimerRef.current)
    }
  }, [])

  const currentStoryChars = countStoryChars(story)
  const activeStoryTarget = parseDraftLength(storyLengthDraft, storyLength)
  const savedStoryBounds = useMemo(
    () => storyTargetBounds(storyLength, storyLengthMin),
    [storyLength, storyLengthMin],
  )
  const storyLengthGap = currentStoryChars - storyLength
  const storyLengthInRange =
    currentStoryChars >= savedStoryBounds.min && currentStoryChars <= savedStoryBounds.max
  const storyLengthBadgeClass =
    storyLengthInRange
      ? 'border-game-success/40 text-game-success'
      : currentStoryChars > savedStoryBounds.max
        ? 'border-game-danger/40 text-game-danger'
        : 'border-amber-500/40 text-amber-400'

  // 新回合或切换历程回顾时滚回顶部（流式刚结束时跳过，避免闪跳）
  useEffect(() => {
    if (skipScrollTopRef.current) {
      skipScrollTopRef.current = false
      return
    }
    const el = storyScrollRef.current
    if (!el) return
    requestAnimationFrame(() => { el.scrollTop = 0 })
  }, [turn, viewingTurn])

  // 流式生成时跟随滚动到底部（回顾旧轮时不滚动）
  useEffect(() => {
    if (viewingTurn != null) return
    const streaming = choosing || openingPending
    if (!streaming) return
    if (choosing && genProgress === 'building_prompt' && !streamGenerationStartedRef.current) return
    const end = storyEndRef.current
    if (!end) return
    requestAnimationFrame(() => {
      end.scrollIntoView({ block: 'end', behavior: 'auto' })
    })
  }, [story, choosing, openingPending, genProgress, viewingTurn])

  const handleChoice = useCallback(async (choice: string, opts?: { auto?: boolean }) => {
    if (!opts?.auto) setAutoAdvancePaused(true)
    setViewingTurn(null)
    setChoosing(true)
    streamGenerationStartedRef.current = false
    setGenProgress('building_prompt')
    logger.info('Game', `Choice: ${choice}`)
    const streamHandlers = {
      onStoryDelta: (delta: string) => {
        if (!streamGenerationStartedRef.current) {
          streamGenerationStartedRef.current = true
          resetStreamStory()
        }
        appendStoryDelta(delta)
      },
      onStoryReset: () => {
        streamGenerationStartedRef.current = true
        resetStreamStory()
      },
      onProgress: (phase: string) => {
        if (mountedRef.current) setGenProgress(phase)
      },
    }
    try {
      await persistGenSettingsBeforeTurn()
      const data = await nextTurn(choice, streamHandlers)
      if (!mountedRef.current) return
      if (data.error) { setError(data.error); setChoosing(false); return }
      setError('')
      setStory(data.story)
      setOptions(data.options || [])
      skipScrollTopRef.current = true  // 流式输出刚完成，不滚回顶部
      setTurn(data.state.turn)
      setStatus(data.state.status)
      setScene(data.state.scene)
      const chars = data.state.characters as Record<string, CharInfo> | undefined
      if (chars) setCharacters(dedupeCharactersByName(Object.values(chars).map((c) => ({
        ...c,
        affection: c.affection ?? c.trust_pct ?? 50,
      }))))
      const factionsData = data.state.factions as FactionInfo[] | undefined
      if (factionsData) setFactions(factionsData)
      if (data.state.objectives) setObjectives(data.state.objectives)
      if (data.visuals) setVisuals(data.visuals)
      if (data.narrative_node) setNarrativeNode(data.narrative_node)
      void getHistory().then((hist) => {
        if (!hist.error) setTimelineCache(hist.turns)
      })
      if (opts?.auto) {
        setAutoAdvanceRemaining((r) => {
          const next = r - 1
          if (next <= 0) setAutoAdvancePaused(true)
          return Math.max(0, next)
        })
      }
    } catch (e) {
      const msg = formatFetchError(e)
      logger.error('Game', 'Choice failed', { error: msg })
      // Detect truncation errors and add settings link
      if (msg.includes('截断') || msg.includes('Token') || msg.includes('unparseable')) {
        setError(`${msg}。建议在本页展开「⚡ 快捷设置」调高输出 Token。`)
        setGenSettingsOpen(true)
      } else {
        setError(msg)
      }
    }
    if (mountedRef.current) {
      setChoosing(false)
      setGenProgress('')
    }
  }, [persistGenSettingsBeforeTurn, appendStoryDelta, resetStreamStory])

  useEffect(() => {
    setGenSettingsOpen(appSettings.sidebarDefault === 'expanded')
  }, [appSettings.sidebarDefault])

  useEffect(() => {
    if (!appSettings.autoAdvance) {
      setAutoAdvancePaused(true)
      setAutoAdvanceRemaining(0)
      return
    }
    setAutoAdvanceRemaining((r) =>
      r > 0 ? r : clampAutoAdvanceRounds(appSettings.autoAdvanceRounds),
    )
  }, [appSettings.autoAdvance, appSettings.autoAdvanceRounds])

  const autoAdvanceRunning =
    appSettings.autoAdvance
    && !autoAdvancePaused
    && autoAdvanceRemaining > 0
    && options.length > 0
    && !choosing
    && viewingTurn == null

  const isViewingPast = viewingTurn != null && viewingTurn < turn
  const viewingEntry = useMemo(
    () => (viewingTurn != null ? timelineCache.find((t) => t.turn === viewingTurn) : undefined),
    [viewingTurn, timelineCache],
  )
  const displayStory = isViewingPast && viewingEntry ? viewingEntry.story : story
  const activeTimelineTurn = viewingTurn ?? turn

  useEffect(() => {
    if (!autoAdvanceRunning) {
      setAutoAdvanceCountdown(autoAdvanceDelaySec)
      return
    }
    setAutoAdvanceCountdown(autoAdvanceDelaySec)
    const tick = setInterval(() => {
      setAutoAdvanceCountdown((c) => Math.max(0, c - 1))
    }, 1000)
    const timer = setTimeout(() => {
      handleChoice('A', { auto: true })
    }, autoAdvanceDelaySec * 1000)
    return () => {
      clearInterval(tick)
      clearTimeout(timer)
    }
  }, [autoAdvanceRunning, turn, options.length, handleChoice])

  const resumeAutoAdvance = useCallback(() => {
    const rounds = clampAutoAdvanceRounds(appSettings.autoAdvanceRounds)
    setAutoAdvanceRemaining((r) => (r > 0 ? r : rounds))
    setAutoAdvancePaused(false)
  }, [appSettings.autoAdvanceRounds])

  const hasGame = !loading && !error && story.length > 0
  const lang = appSettings.language as 'zh' | 'en' | 'ja'
  const showCharPanel = appSettings.charPanelPosition !== 'hidden'
  const relationPanelTitle = adultMode ? tTheme('nav.characters', lang, true) : t('game.status', lang)
  const storyParagraphStyle = {
    fontSize: 'var(--story-font-size)',
    lineHeight: 'var(--story-line-height)',
    fontFamily: 'var(--story-font-family)',
    marginBottom: 'var(--story-paragraph-spacing)',
  } as const
  const storyContentMaxWidth = storyMaxWidthCSSValue(appSettings.maxWidth)

  const gameLeftPanel = useMemo(() => {
    if (!hasGame || readingMode) return null
    return (
      <div className="p-3 space-y-1 overflow-y-auto h-full">
        <h3 className="text-[10px] font-neural-mono text-neural-cyan uppercase tracking-widest mb-3">
          {tTheme('game.timeline', lang, adultMode)}
        </h3>
        {Array.from({ length: Math.max(turn, 1) }, (_, i) => {
          const n = i + 1
          const isLatest = n === turn && viewingTurn == null
          const isActive = n === activeTimelineTurn
          return (
            <button
              type="button"
              key={n}
              disabled={choosing || timelineLoading}
              onClick={() => void viewTimelineTurn(n)}
              title={n >= turn ? `返回第 ${n} 轮` : `回顾第 ${n} 轮`}
              className={cn(
                'w-full text-left text-xs py-1.5 pl-3 border-l-2 transition-colors rounded-r-md',
                'hover:bg-neural-cyan/5 disabled:opacity-50 disabled:pointer-events-none',
                isActive
                  ? 'border-neural-cyan text-neural-cyan bg-neural-cyan/5'
                  : 'border-game-border/50 text-game-muted hover:text-game-text hover:border-neural-cyan/40',
              )}
            >
              第 {n} 轮{isLatest ? ' ◆' : ''}{viewingTurn === n && n < turn ? ' ·' : ''}
            </button>
          )
        })}
      </div>
    )
  }, [hasGame, readingMode, turn, lang, adultMode, choosing, timelineLoading, viewingTurn, activeTimelineTurn, viewTimelineTurn])

  const gameInspector = useMemo(() => {
    if (!hasGame || !showCharPanel || readingMode) return null
    return (
      <InspectorPanel
        title={relationPanelTitle}
        className={adultMode ? 'adult-relation-inspector' : undefined}
        collapsible
        onCollapse={() => setRelationPanelOpen(false)}
        collapseLabel="收起关系面板"
      >
        <GameStatusList characters={characters} factions={factions} adultMode={adultMode} visuals={visuals} />
      </InspectorPanel>
    )
  }, [hasGame, showCharPanel, readingMode, adultMode, relationPanelTitle, characters, factions])

  usePageShell({
    leftPanel: gameLeftPanel,
    inspector: gameInspector,
    showLeftPanel: !!(hasGame && !readingMode),
    showRightPanel: !!(hasGame && showCharPanel && !readingMode && relationPanelOpen),
    hideShellPanels: !hasGame || readingMode,
  })

  return (
    <div className="w-full h-full">
      <StatusToast
        message={loading ? '正在生成开篇剧情…' : error ? `❌ ${error}` : ''}
        type={loading ? 'loading' : error ? 'error' : 'info'}
      />

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center min-h-[50vh]">
          <motion.div animate={{ opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1.5 }}
            className="text-game-muted text-lg flex items-center gap-3"
          >
            <span className="inline-block w-4 h-4 border-2 border-game-accent/30 border-t-game-accent rounded-full animate-spin" />
            AI 正在生成开篇剧情…
          </motion.div>
        </div>
      )}

      {/* Error */}
      {!loading && error && !story && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center justify-center min-h-[50vh] gap-6 text-center"
        >
          <div className="text-5xl">❌</div>
          <h2 className="text-lg font-bold text-game-danger">出错了</h2>
          <p className="text-game-muted text-sm max-w-md">{error}</p>
          <div className="flex gap-3 flex-wrap justify-center">
            <Button variant="outline" onClick={loadGame}>🔄 重试</Button>
            {error.includes('Token') || error.includes('截断') ? (
              <Button variant="accent" onClick={() => window.location.href = '/settings'}>
                ⚙️ 调整 Token 设置
              </Button>
            ) : (
              <Button variant="glow" onClick={() => window.location.href = '/new'}>✨ 创建新故事</Button>
            )}
          </div>
        </motion.div>
      )}

      {/* Game */}
      {hasGame && (
        <div className={cn('flex gap-0 h-full', readingMode && 'game-reading-mode')}>
          {/* Main content */}
          <div className="flex-1 min-w-0 flex flex-col">
            {/* Top status bar */}
            <div className={cn('shrink-0', readingMode && 'game-chrome-hidden')}>
              <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2 text-sm">
                <Badge variant="primary">📖 第 {isViewingPast && viewingTurn ? viewingTurn : turn} 轮</Badge>
                {isViewingPast && (
                  <Badge variant="outline" size="sm" className="text-game-accent border-game-accent/40">
                    回顾中
                  </Badge>
                )}
                <Badge
                  variant={
                    status === 'TENSION' ? 'warning' :
                    status === 'CLIMAX' ? 'danger' :
                    status === 'COOLDOWN' ? 'success' : 'primary'
                  }
                  size="sm"
                >
                  {status}
                </Badge>
                {scene && <span className="text-game-muted text-xs truncate max-w-[250px]">📍 {scene}</span>}
              </div>

              <div className="flex items-center gap-1 flex-wrap justify-end">
                <div className="hidden md:flex items-center gap-0.5 mr-1">
                  {MAX_WIDTH_OPTIONS.map(({ value, label }) => (
                    <Button
                      key={value}
                      type="button"
                      size="xs"
                      className="text-[11px] px-1.5"
                      variant={appSettings.maxWidth === value ? 'primary' : 'ghost'}
                      disabled={choosing}
                      onClick={() => saveSettings({ maxWidth: value })}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                <div className="flex items-center gap-2 px-1">
                  <span className="text-xs text-game-muted shrink-0">⚡ {t('game.quickSettings', lang)}</span>
                  <Switch
                    checked={genSettingsOpen}
                    disabled={choosing}
                    onCheckedChange={setGenSettingsOpen}
                  />
                  {!genSettingsSaving && genSettingsSaved && (
                    <span className="text-[10px] text-game-success hidden sm:inline">已保存</span>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1 text-game-muted hover:text-game-text"
                  disabled={choosing || supplementLoading}
                  onClick={() => {
                    setSupplementError('')
                    setSupplementSuccess('')
                    setSupplementOpen(true)
                  }}
                >
                  📝 补充设定
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1 text-game-muted hover:text-game-text"
                  disabled={choosing}
                  onClick={() => void openHistoryReview()}
                >
                  📜 回顾
                </Button>
                {showCharPanel && !readingMode && !relationPanelOpen && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1 text-game-muted hover:text-game-text"
                    disabled={choosing}
                    onClick={() => setRelationPanelOpen(true)}
                  >
                    {relationPanelTitle}
                  </Button>
                )}
              </div>
              </div>

              {!isViewingPast && !readingMode && turn > 0 && (objectives.main.length > 0 || objectives.side.length > 0) && (
                <div className="flex flex-col gap-1.5 px-1 py-2 border-b border-game-border/30">
                  <span className="text-[11px] text-game-dim uppercase tracking-wide">🎯 {t('game.objectives', lang)}</span>
                  {objectives.main.map((obj) => (
                    <div key={obj.id} className="flex flex-col gap-0.5 min-w-0">
                      <div className="flex justify-between gap-2 text-xs">
                        <span className="text-game-text truncate font-medium">主线 · {obj.title}</span>
                        <span className="text-game-muted shrink-0">{obj.progress}%</span>
                      </div>
                      <div className="h-1 rounded-full bg-game-border/40 overflow-hidden">
                        <div
                          className="h-full bg-game-accent/80"
                          style={{ width: `${Math.min(100, Math.max(0, obj.progress))}%` }}
                        />
                      </div>
                    </div>
                  ))}
                  {objectives.side.map((obj) => (
                    <div key={obj.id} className="flex justify-between gap-2 text-xs text-game-muted min-w-0">
                      <span className="truncate">支线 · {obj.title}</span>
                      <span className="shrink-0">{obj.progress}%</span>
                    </div>
                  ))}
                  {(objectives.side_extra ?? 0) > 0 && (
                    <span className="text-[11px] text-game-dim">+{objectives.side_extra} 条活跃支线</span>
                  )}
                </div>
              )}
            </div>

            {/* Story — scrollable */}
            <div ref={storyScrollRef} className="flex-1 overflow-y-auto min-h-0 space-y-3">
            {genSettingsOpen && !readingMode && (
              <div className="border border-game-border/70 rounded-lg bg-game-bg/40 px-4 py-3 shrink-0">
                <p className="text-[11px] text-game-dim mb-2 rounded-md border border-game-border/50 bg-game-bg/40 px-2.5 py-1.5">
                  模型与压缩开关在 <strong className="text-game-muted">设置 → API</strong> 中配置
                </p>
                {(genSettingsSaved || genSettingsSaveError) && (
                  <div className="mb-2 text-xs">
                    {genSettingsSaved && (
                      <span className="text-game-success">
                        ✅ 已保存{optionsRegenerated ? '，并已重生本轮选项' : '，下一轮生成生效'}
                      </span>
                    )}
                    {genSettingsSaveError && (
                      <span className="text-game-danger">❌ 保存失败：{genSettingsSaveError}</span>
                    )}
                  </div>
                )}
                <div className="flex md:hidden items-center gap-0.5 mb-3 flex-wrap">
                  {MAX_WIDTH_OPTIONS.map(({ value, label }) => (
                    <Button
                      key={value}
                      type="button"
                      size="xs"
                      className="text-[11px]"
                      variant={appSettings.maxWidth === value ? 'primary' : 'ghost'}
                      disabled={choosing}
                      onClick={() => saveSettings({ maxWidth: value })}
                    >
                      {label}
                    </Button>
                  ))}
                </div>
                  <QuickGenRow
                    label="目标字数"
                    hint="停输约 1 秒保存，选选项前强制同步"
                  >
                    <Input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={storyLengthDraft}
                      disabled={choosing}
                      onChange={(e) => setStoryLengthDraft(e.target.value.replace(/\D/g, ''))}
                      onBlur={commitStoryLengthDraft}
                      onKeyDown={(e) => handleNumericFieldKeyDown(e, commitStoryLengthDraft)}
                      className="w-24 h-8 text-sm tabular-nums"
                    />
                    {storyLength !== storyLengthRecommended && (
                      <button
                        type="button"
                        disabled={choosing}
                        onClick={() => {
                          setStoryLengthDraft(String(storyLengthRecommended))
                          queueGenSettingsSave({ storyLength: storyLengthRecommended }, true)
                        }}
                        className="text-xs text-game-accent hover:underline disabled:opacity-50"
                      >
                        默认 {storyLengthRecommended.toLocaleString()}
                      </button>
                    )}
                    <Badge variant="outline" size="sm" className={`tabular-nums ${storyLengthBadgeClass}`}>
                      当前 {currentStoryChars.toLocaleString()} 字
                      {storyLengthGap !== 0 && (
                        <span className="ml-1 opacity-90">
                          ({storyLengthGap > 0 ? '+' : ''}{storyLengthGap.toLocaleString()})
                        </span>
                      )}
                    </Badge>
                    <span className="text-[11px] text-game-dim basis-full sm:basis-auto">
                      {storyLengthRangeLabel(activeStoryTarget, storyLengthMin)}
                    </span>
                  </QuickGenRow>
                  <QuickGenRow
                    label="最大 Token"
                    hint={`随目标字数自动匹配（当前预览 ${previewMaxTokens.toLocaleString()}，已保存 ${maxTokens.toLocaleString()}）；官方最大 ${maxOutputTokens.toLocaleString()}`}
                  >
                    <Badge variant="outline" size="sm" className="tabular-nums">{previewMaxTokens.toLocaleString()}</Badge>
                    {previewMaxTokens !== maxTokens && (
                      <span className="text-[11px] text-game-accent">→ 保存后 {maxTokens.toLocaleString()}</span>
                    )}
                  </QuickGenRow>
                  <QuickGenRow
                    label="上下文"
                    hint="模型一次能读入的提示+历史总量（官方 1M tokens）"
                  >
                    <Badge variant="outline" size="sm" className="tabular-nums">{contextTokens.toLocaleString()}</Badge>
                  </QuickGenRow>
                  <QuickGenRow
                    label="温度"
                    hint="越高越发散创意，越低越稳定；推荐 0.8–1.0，官方 ≤ 2.0"
                  >
                    <Slider
                      value={[temperature]}
                      min={0.1}
                      max={2.0}
                      step={0.1}
                      disabled={choosing}
                      onValueChange={([v]) => queueGenSettingsSave({ temperature: v })}
                      className="w-32 sm:w-40"
                    />
                    <Badge variant="outline" size="sm">{temperature.toFixed(1)}</Badge>
                  </QuickGenRow>
                  <QuickGenRow
                    label="Top P"
                    hint="核采样范围，越小越保守；推荐 0.9，官方 ≤ 1.0"
                  >
                    <Slider
                      value={[topP]}
                      min={0}
                      max={1}
                      step={0.05}
                      disabled={choosing}
                      onValueChange={([v]) => queueGenSettingsSave({ topP: v })}
                      className="w-32 sm:w-40"
                    />
                    <Badge variant="outline" size="sm">{topP.toFixed(2)}</Badge>
                  </QuickGenRow>
                  <QuickGenRow
                    label="压缩阈值"
                    hint={`历史 token 超此值且「自动压缩」开启时摘要旧轮次（预览 ${previewCompressThreshold.toLocaleString()}）；开关在设置页`}
                  >
                    <Input
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]*"
                      value={compressThresholdDraft}
                      disabled={choosing}
                      onChange={(e) => setCompressThresholdDraft(e.target.value.replace(/\D/g, ''))}
                      onBlur={commitCompressThresholdDraft}
                      onKeyDown={(e) => handleNumericFieldKeyDown(e, commitCompressThresholdDraft)}
                      className="w-28 h-8 text-sm tabular-nums"
                    />
                    {previewCompressThreshold !== compressThreshold && parseDraftLength(storyLengthDraft, storyLength) !== storyLength && (
                      <span className="text-[11px] text-game-accent tabular-nums">联动 {previewCompressThreshold.toLocaleString()}</span>
                    )}
                  </QuickGenRow>
                  <QuickGenRow label="选项数量" hint="每轮 AI 输出的选项个数（3–5）">
                    {[3, 4, 5].map((n) => (
                      <Button
                        key={n}
                        type="button"
                        size="xs"
                        variant={optionCount === n ? 'primary' : 'ghost'}
                        disabled={choosing}
                        onClick={() => queueGenSettingsSave({ optionCount: n }, true)}
                      >
                        {n}
                      </Button>
                    ))}
                  </QuickGenRow>
                  <QuickGenRow label="叙事视角" hint="写入提示词，影响人称与叙述方式">
                    {([
                      { v: 'first', l: '第一人称' },
                      { v: 'third', l: '第三人称' },
                      { v: 'auto', l: '自动' },
                    ] as const).map((o) => (
                      <Button
                        key={o.v}
                        type="button"
                        size="xs"
                        variant={narrativePov === o.v ? 'primary' : 'ghost'}
                        disabled={choosing}
                        onClick={() => queueGenSettingsSave({ narrativePov: o.v }, true)}
                      >
                        {o.l}
                      </Button>
                    ))}
                  </QuickGenRow>
                  <QuickGenRow label="文风" hint="细腻 / 快节奏 / 对话 / 心理 / 均衡">
                    {([
                      { v: 'descriptive', l: '细腻' },
                      { v: 'fast', l: '快' },
                      { v: 'dialogue', l: '对话' },
                      { v: 'psycho', l: '心理' },
                      { v: 'balanced', l: '均衡' },
                    ] as const).map((o) => (
                      <Button
                        key={o.v}
                        type="button"
                        size="xs"
                        className="text-[11px]"
                        variant={stylePreference === o.v ? 'primary' : 'ghost'}
                        disabled={choosing}
                        onClick={() => queueGenSettingsSave({ stylePreference: o.v }, true)}
                      >
                        {o.l}
                      </Button>
                    ))}
                  </QuickGenRow>
                  <QuickGenRow label="重复检测" hint="严格时相似度过高会重试；也影响 FORCE_EVENT 阈值">
                    {([
                      { v: 'strict', l: '严格' },
                      { v: 'standard', l: '标准' },
                      { v: 'loose', l: '宽松' },
                    ] as const).map((o) => (
                      <Button
                        key={o.v}
                        type="button"
                        size="xs"
                        variant={repetitionCheck === o.v ? 'primary' : 'ghost'}
                        disabled={choosing}
                        onClick={() => queueGenSettingsSave({ repetitionCheck: o.v }, true)}
                      >
                        {o.l}
                      </Button>
                    ))}
                  </QuickGenRow>

                  {adultMode && (
                    <QuickGenRow label={tTheme('game.readingMode', lang, false)} hint="隐藏侧栏与快捷设置，聚焦正文阅读">
                      <Switch
                        checked={readingMode}
                        disabled={choosing}
                        onCheckedChange={setReadingMode}
                      />
                      <Badge variant={readingMode ? 'default' : 'outline'} size="sm">
                        {readingMode ? '沉浸中' : '关闭'}
                      </Badge>
                    </QuickGenRow>
                  )}
              </div>
            )}
            {isViewingPast && viewingEntry && (
              <div className="shrink-0 flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-game-accent/30 bg-game-accent/5 text-xs">
                <span className="text-game-muted truncate">
                  今夜历程 · 第 {viewingEntry.turn} 轮
                  {viewingEntry.scene ? ` · ${viewingEntry.scene}` : ''}
                </span>
                <Button type="button" size="xs" variant="ghost" onClick={() => setViewingTurn(null)}>
                  回最新轮
                </Button>
              </div>
            )}
            <Card className={cn('border-neural-cyan/15 glass-panel-glow w-full', adultMode && 'theme-card-enter')}>
              <CardContent
                className={cn('pt-4 pb-6 px-4 md:px-8 w-full mx-auto game-story-focus', readingMode && 'px-6 md:px-12')}
                style={{ maxWidth: storyContentMaxWidth }}
              >
                {visuals.scene?.image_url && !isViewingPast && (
                  <div className="w-full rounded-lg overflow-hidden border border-game-border/30 mb-4">
                    <img src={visuals.scene.image_url} alt={scene} className="w-full max-h-96 object-contain" loading="lazy" />
                  </div>
                )}
                {visuals.characters.length > 0 && !isViewingPast && (
                  <div className="flex flex-wrap justify-center gap-3 mb-4 px-2">
                    {visuals.characters.map((vc) => (
                      <div key={vc.name} className="flex flex-col items-center gap-1">
                        <div className="w-16 h-16 rounded-full overflow-hidden border-2 border-game-accent/40 shadow-lg shadow-game-accent/10">
                          <img src={vc.image_url} alt={vc.name} className="w-full h-full object-cover object-top" loading="lazy" />
                        </div>
                        <span className="text-[10px] text-game-muted text-center leading-tight max-w-[72px] truncate">{vc.name}</span>
                      </div>
                    ))}
                  </div>
                )}
                {narrativeNode?.context && !isViewingPast && (
                  <p className="text-xs text-game-dim italic mb-4 border-l-2 border-game-border/40 pl-3">{narrativeNode.context}</p>
                )}
                {appSettings.animations ? (
                  <motion.div key={viewingTurn ?? turn} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                    {displayStory.split('\n').filter(Boolean).map((paragraph, i) => (
                      <motion.p key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                        className="text-game-text"
                        style={storyParagraphStyle}
                      >
                        {paragraph}
                      </motion.p>
                    ))}
                  </motion.div>
                ) : (
                  <div>
                    {displayStory.split('\n').filter(Boolean).map((paragraph, i) => (
                      <p key={i} className="text-game-text" style={storyParagraphStyle}>
                        {paragraph}
                      </p>
                    ))}
                  </div>
                )}
                {isViewingPast && viewingEntry?.choice && (() => {
                  const { text, isCustom } = resolveHistoryChoice(
                    viewingEntry.choice,
                    viewingEntry.options || [],
                  )
                  return (
                    <div className={cn(
                      'mt-4 border rounded-md px-3 py-2 text-sm',
                      isCustom ? 'bg-game-secret/10 border-game-accent/30' : 'bg-game-surface border-game-border',
                    )}>
                      <span className="text-game-accent font-medium">{isCustom ? '✏️ 已选择（自定义）：' : '👉 已选择：'}</span>
                      <span className="text-game-text">{text}</span>
                    </div>
                  )
                })()}
                {isViewingPast && viewingEntry && !viewingEntry.choice && (
                  <p className="mt-4 text-xs text-game-dim">该轮暂无记录的选择</p>
                )}
                <div ref={storyEndRef} aria-hidden className="h-px shrink-0" />
              </CardContent>
            </Card>

            </div>{/* end scrollable area */}

            {adultMode && readingMode && (
              <div className="flex justify-center py-2 shrink-0">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-game-muted hover:text-game-highlight text-xs"
                  onClick={() => setReadingMode(false)}
                >
                  退出阅读模式
                </Button>
              </div>
            )}

            {/* Choices — fixed at bottom */}
            <div className={cn('shrink-0 border-t border-neural-cyan/15 glass-panel rounded-none border-x-0 pt-3 pb-1', readingMode && 'game-chrome-hidden')}>
            <AnimatePresence>
              {isViewingPast ? (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="px-4 pb-3">
                  <p className="text-sm text-game-muted py-2">
                    正在回顾第 {viewingTurn} 轮，返回最新轮后可继续选择。
                  </p>
                  <Button type="button" variant="outline" size="sm" onClick={() => setViewingTurn(null)}>
                    返回第 {turn} 轮继续
                  </Button>
                </motion.div>
              ) : options.length > 0 ? (
                <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                  {optionsSuggestAdult && (
                    <AdultModeSuggestBanner onEnable={enableAdultModeFromHint} />
                  )}
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex flex-col gap-2 min-w-0 flex-1">
                      <div className="flex items-center gap-3 flex-wrap">
                        <p className="text-sm text-game-muted font-medium shrink-0">🎯 {tTheme('game.choices', lang, adultMode)}</p>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs text-game-muted shrink-0">⚡ 自动推进</span>
                          <Switch
                            checked={appSettings.autoAdvance}
                            disabled={choosing}
                            onCheckedChange={(v) => saveSettings({ autoAdvance: v })}
                          />
                          {appSettings.autoAdvance && (
                            <>
                              <span className="text-xs text-game-dim shrink-0">推进轮数</span>
                              {AUTO_ADVANCE_ROUND_OPTIONS.map((n) => (
                                <Button
                                  key={n}
                                  type="button"
                                  size="xs"
                                  variant={clampAutoAdvanceRounds(appSettings.autoAdvanceRounds) === n ? 'primary' : 'ghost'}
                                  disabled={choosing}
                                  onClick={() => saveSettings({ autoAdvanceRounds: n })}
                                >
                                  {n}
                                </Button>
                              ))}
                            </>
                          )}
                        </div>
                      </div>
                      {appSettings.autoAdvance && (
                        <div className="flex items-center gap-2 flex-wrap pl-0.5">
                          <span className="text-xs text-game-muted tabular-nums">
                            剩余 {autoAdvanceRemaining}/{clampAutoAdvanceRounds(appSettings.autoAdvanceRounds)} 轮
                            {autoAdvanceRunning && (
                              <span className="text-game-accent ml-1">{autoAdvanceCountdown}s 后自动选 A</span>
                            )}
                            {autoAdvanceRemaining <= 0 && !autoAdvanceRunning && (
                              <span className="text-game-dim ml-1">轮数已用尽，点继续可重置</span>
                            )}
                          </span>
                          {autoAdvancePaused || autoAdvanceRemaining <= 0 ? (
                            <Button
                              type="button"
                              variant="outline"
                              size="xs"
                              disabled={choosing}
                              onClick={resumeAutoAdvance}
                            >
                              ▶ 继续自动
                            </Button>
                          ) : (
                            <Button
                              type="button"
                              variant="outline"
                              size="xs"
                              disabled={choosing}
                              onClick={() => setAutoAdvancePaused(true)}
                            >
                              ⏸ 暂停
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap justify-end shrink-0">
                      <span className="text-xs text-game-muted/80 hidden sm:inline">
                        {showConsequences ? 'AI 预测每个选项的剧情发展和好感影响' : '已隐藏剧情推测'}
                      </span>
                      <button
                        onClick={() => setShowConsequences(!showConsequences)}
                        title={showConsequences ? '点击关闭 AI 剧情推测' : '点击开启 AI 剧情推测'}
                        className={`text-xs px-2 py-0.5 rounded-full border transition-colors ${
                          showConsequences
                            ? 'border-game-accent/40 bg-game-accent/10 text-game-accent'
                            : 'border-game-border text-game-dim hover:text-game-muted'
                        }`}
                      >
                        {showConsequences ? '🔮 推测 ON' : '🔮 推测 OFF'}
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1.5 pt-1">
                  {options.map((choice, i) => {
                    const parsed = parseGameOption(choice)
                    const { action, attitude, effectText } = parsed
                    const effects = showConsequences && effectText ? parseOptionEffects(effectText) : null
                    const letter = String.fromCharCode(65 + i)
                    // ── V6: Option character avatars ──
                    const hintedChars = effects?.hints
                      ?.filter((h) => h.kind === 'character' && h.name)
                      .map((h) => h.name) ?? []
                    const visualByChar = new Map(visuals.characters.map((v) => [v.name, v.image_url]))
                    const optionAvatars = [...new Set(hintedChars)]
                      .map((n) => visualByChar.get(n))
                      .filter(Boolean) as string[]
                    return (
                      <Button key={`${turn}-${i}`} variant="neural" disabled={choosing}
                        onClick={() => handleChoice(letter)}
                        className="w-full flex flex-col items-center justify-center text-center h-auto py-2 px-3 transition-all"
                      >
                        <div className="flex w-full flex-col gap-0.5 min-w-0 items-center">
                          <div className="flex gap-2 min-w-0 justify-center text-center w-full items-center">
                            <span className="text-game-accent font-bold shrink-0 text-sm leading-snug">{letter}.</span>
                            <span className="text-sm font-medium text-game-text leading-snug text-center">{action}</span>
                          </div>
                          {optionAvatars.length > 0 && (
                            <div className="flex flex-wrap justify-center gap-1.5 mt-1">
                              {optionAvatars.map((url, j) => (
                                <div key={j} className="w-7 h-7 rounded-full overflow-hidden border border-game-border/40 bg-neural-void/40">
                                  <img src={url} alt="" className="w-full h-full object-cover object-top" loading="lazy" />
                                </div>
                              ))}
                            </div>
                          )}
                          {showConsequences && (
                            <OptionEffectsInline
                              effects={effects}
                              effectText={effectText}
                              attitude={attitude}
                            />
                          )}
                        </div>
                      </Button>
                    )
                  })}

                  {!showCustomInput ? (
                    <Button variant="ghost" size="sm" disabled={choosing}
                      onClick={() => setShowCustomInput(true)}
                      className="w-full text-game-dim hover:text-game-text border border-dashed border-game-border"
                    >
                      ✏️ 自定义输入…
                    </Button>
                  ) : (
                    <div className="space-y-2">
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="flex gap-2">
                        <input value={customInput} onChange={(e) => setCustomInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && customInput.trim()) { handleChoice(customInput.trim()); setCustomInput(''); setShowCustomInput(false) }
                            if (e.key === 'Escape') { setShowCustomInput(false); setCustomInput('') }
                          }}
                          placeholder="输入你想做的事…" disabled={choosing} autoFocus
                          className="flex-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm text-game-text placeholder:text-game-dim focus:outline-none focus:border-game-primary"
                        />
                        <Button variant="accent" size="sm" disabled={choosing || !customInput.trim()}
                          onClick={() => { if (customInput.trim()) { handleChoice(customInput.trim()); setCustomInput(''); setShowCustomInput(false) } }}
                        >确定</Button>
                      </motion.div>
                      {customInputSuggestAdult && (
                        <AdultModeSuggestBanner onEnable={enableAdultModeFromHint} />
                      )}
                    </div>
                  )}
                  </div>
                </motion.div>
              ) : (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="px-4 pb-3 space-y-3">
                  {openingPending || choosing ? (
                    <p className="text-sm text-game-muted flex items-center gap-2 py-2">
                      <span className="inline-block h-4 w-4 border-2 border-game-accent/30 border-t-game-accent rounded-full animate-spin shrink-0" />
                      正在生成选项，请稍候…
                    </p>
                  ) : (
                    <>
                      <p className="text-sm text-game-muted py-1">
                        {turn > 0
                          ? '暂无选项，可直接输入你想做的事继续推进'
                          : '开局尚未完成，请重新加载以生成选项'}
                      </p>
                      <div className="flex gap-2 flex-wrap">
                        <Button variant="outline" size="sm" disabled={choosing} onClick={loadGame}>
                          🔄 重新加载
                        </Button>
                      </div>
                      {turn > 0 && (
                        !showCustomInput ? (
                          <Button variant="ghost" size="sm" disabled={choosing}
                            onClick={() => setShowCustomInput(true)}
                            className="w-full text-game-dim hover:text-game-text border border-dashed border-game-border"
                          >
                            ✏️ 自定义输入…
                          </Button>
                        ) : (
                          <div className="space-y-2">
                            <div className="flex gap-2">
                              <input value={customInput} onChange={(e) => setCustomInput(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' && customInput.trim()) { handleChoice(customInput.trim()); setCustomInput(''); setShowCustomInput(false) }
                                  if (e.key === 'Escape') { setShowCustomInput(false); setCustomInput('') }
                                }}
                                placeholder="输入你想做的事…" disabled={choosing} autoFocus
                                className="flex-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm text-game-text placeholder:text-game-dim focus:outline-none focus:border-game-primary"
                              />
                              <Button variant="accent" size="sm" disabled={choosing || !customInput.trim()}
                                onClick={() => { if (customInput.trim()) { handleChoice(customInput.trim()); setCustomInput(''); setShowCustomInput(false) } }}
                              >确定</Button>
                            </div>
                            {customInputSuggestAdult && (
                              <AdultModeSuggestBanner onEnable={enableAdultModeFromHint} />
                            )}
                          </div>
                        )
                      )}
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            </div>

          </div>

        </div>
      )}

      {/* ── History Dialog ── */}
      {historyOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-12 px-4">
          <div className="fixed inset-0 bg-black/70" onClick={closeHistoryReview} />
          <div className="relative z-50 w-full max-w-2xl max-h-[85vh] bg-game-card border border-game-border rounded-lg shadow-2xl flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-game-border shrink-0">
              <h2 className="text-base font-bold text-game-accent">📜 剧情回顾</h2>
              <div className="flex items-center gap-2">
                {/* Download with options */}
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => {
                    const text = history.map((h) => {
                      const opts = h.options.length > 0 ? '\n选项：\n' + h.options.map((o, i) => `  ${String.fromCharCode(65 + i)}. ${o}`).join('\n') : ''
                      const choice = h.choice ? `\n👉 选择：${h.choice}` : ''
                      return `第${h.turn}轮 [${h.status}] ${h.scene || ''}\n${'─'.repeat(40)}\n${h.story}${choice}${opts}\n`
                    }).join('\n\n')
                    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
                    const a = document.createElement('a')
                    a.href = URL.createObjectURL(blob)
                    a.download = `剧情回顾_含选项.txt`
                    a.click()
                  }}
                >
                  ⬇ 含选项
                </Button>
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => {
                    const text = history.map((h) =>
                      `第${h.turn}轮 [${h.status}] ${h.scene || ''}\n${'─'.repeat(40)}\n${h.story}\n`
                    ).join('\n\n')
                    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
                    const a = document.createElement('a')
                    a.href = URL.createObjectURL(blob)
                    a.download = `剧情回顾_纯正文.txt`
                    a.click()
                  }}
                >
                  ⬇ 纯正文
                </Button>
                <button onClick={closeHistoryReview} className="text-game-muted hover:text-game-text text-lg px-1">✕</button>
              </div>
            </div>

            {/* Content */}
            <div className="overflow-y-auto p-5 space-y-6 flex-1">
              {historyLoading ? (
                <p className="text-game-muted text-center py-8">加载历史记录…</p>
              ) : historyError ? (
                <div className="text-center py-8 space-y-3">
                  <p className="text-game-danger text-sm">{historyError}</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      setHistoryError('')
                      setHistoryLoading(true)
                      try {
                        const data = await getHistory()
                        if (data.error) setHistoryError(data.error)
                        else setHistory(data.turns)
                      } catch (e) {
                        setHistoryError(formatFetchError(e))
                      }
                      setHistoryLoading(false)
                    }}
                  >
                    🔄 重试
                  </Button>
                </div>
              ) : history.length === 0 ? (
                <p className="text-game-muted text-center py-8">暂无剧情记录</p>
              ) : (
                history.map((h, i) => (
                  <div
                    key={h.turn}
                    id={`history-turn-${h.turn}`}
                    className={cn(
                      'space-y-2 scroll-mt-4',
                      historyFocusTurn === h.turn && 'rounded-lg ring-1 ring-game-accent/50 bg-game-accent/5 p-3 -mx-1',
                    )}
                  >
                    <div className="flex items-center gap-2 text-xs text-game-muted">
                      <Badge variant="primary" size="sm">第{h.turn}轮</Badge>
                      <Badge variant="outline" size="sm">{h.status}</Badge>
                      {h.scene && <span>📍 {h.scene}</span>}
                    </div>
                    <div className="text-sm text-game-text leading-relaxed whitespace-pre-wrap">
                      {h.story}
                    </div>
                    {h.choice && (() => {
                      // Resolve choice: if letter, map to option text; otherwise show as custom
                      const idx = h.choice.charCodeAt(0) - 65
                      const isLetter = /^[A-D]$/.test(h.choice)
                      const choiceText = isLetter && h.options[idx]
                        ? parseGameOption(h.options[idx]).action
                        : h.choice
                      const isCustom = !isLetter
                      return (
                        <div className={`border rounded-md px-3 py-2 text-sm ${isCustom ? 'bg-game-secret/10 border-game-accent/30' : 'bg-game-surface border-game-border'}`}>
                          <span className="text-game-accent font-medium">{isCustom ? '✏️ 自定义：' : '👉 选择：'}</span>
                          <span className="text-game-text">{choiceText}</span>
                        </div>
                      )
                    })()}
                    {h.options.length > 0 && !h.choice && (
                      <div className="text-xs text-game-dim space-y-0.5">
                        <span className="text-game-muted">可选项：</span>
                        {h.options.map((o, j) => (
                          <span key={j} className="block ml-3">{String.fromCharCode(65 + j)}. {o.split('→')[0].trim()}</span>
                        ))}
                      </div>
                    )}
                    {i < history.length - 1 && <div className="border-t border-game-border pt-4" />}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Supplement Lore Dialog ── */}
      {supplementOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-12 px-4">
          <div className="fixed inset-0 bg-black/70" onClick={() => !supplementLoading && setSupplementOpen(false)} />
          <div className="relative z-50 w-full max-w-xl bg-game-card border border-game-border rounded-lg shadow-2xl flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-game-border shrink-0">
              <h2 className="text-base font-bold text-game-accent">📝 补充设定</h2>
              <button
                type="button"
                disabled={supplementLoading}
                onClick={() => setSupplementOpen(false)}
                className="text-game-muted hover:text-game-text text-lg px-1 disabled:opacity-40"
              >
                ✕
              </button>
            </div>
            <div className="p-5 space-y-3">
              <p className="text-xs text-game-dim leading-relaxed">
                仅根据您填写的内容提取设定，不会推断未写明的信息。
                入库时<strong className="text-game-muted">优先追加</strong>到已有设定；若与已有内容冲突，以本次补充为准。
              </p>
              <Textarea
                value={supplementText}
                onChange={(e) => setSupplementText(e.target.value)}
                placeholder="例如：艾莉丝其实是邻国间谍；学院禁止夜间外出；后续剧情偏悬疑…"
                rows={8}
                disabled={supplementLoading || choosing}
                className="resize-y min-h-[140px] bg-game-bg/60 border-game-border text-sm"
              />
              {(supplementInputSuggestAdult || supplementAdultHint) && (
                <AdultModeSuggestBanner onEnable={enableAdultModeFromHint} />
              )}
              {supplementError && (
                <p className="text-xs text-game-danger">❌ {supplementError}</p>
              )}
              {supplementSuccess && (
                <p className="text-xs text-game-success">✅ {supplementSuccess}</p>
              )}
              <div className="flex justify-end gap-2 pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={supplementLoading}
                  onClick={() => setSupplementOpen(false)}
                >
                  关闭
                </Button>
                <Button
                  variant="accent"
                  size="sm"
                  disabled={supplementLoading || choosing || !supplementText.trim()}
                  onClick={() => void submitSupplement()}
                >
                  {supplementLoading ? 'AI 分析中…' : '提交分析'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {choosing && (
        <div className="fixed inset-x-0 bottom-16 md:bottom-0 z-40 border-t border-game-border bg-game-card/95 px-4 py-2 flex items-center justify-between gap-3 text-sm">
          <div className="flex items-center gap-2 min-w-0">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-game-accent/30 border-t-game-accent shrink-0" />
            <span className="text-game-muted truncate">
              {genProgress === 'building_prompt' && '构建提示词…'}
              {genProgress === 'generating' && `生成中 · 已 ${genStoryChars} 字`}
              {genProgress === 'continuation' && `续写补偿 · 已 ${genStoryChars} 字`}
              {!genProgress && `生成中 · 已 ${genStoryChars} 字`}
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={() => void cancelGeneration()}>
            取消
          </Button>
        </div>
      )}

      {genSettingsSaving && (
        <GameBusyOverlay message="正在保存快捷设置…" />
      )}

      <AdultUnlockDialog
        open={adultUnlockOpen}
        saving={adultUnlockSaving}
        error={adultUnlockError}
        onClose={() => setAdultUnlockOpen(false)}
        onSubmit={submitAdultUnlockFromHint}
      />
    </div>
  )
}
