import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Separator } from '@/components/ui/separator'
import { StatusToast } from '@/components/StatusToast'
import { getGameState, startGame, nextTurn, getHistory, getGameGenSettings, updateGameGenSettings, type HistoryTurn, type GameGenSettings } from '@/lib/api'
import { logger } from '@/lib/logger'
import { parseRelationHints } from '@/lib/relationHints'


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

function RelationChips({ text }: { text: string }) {
  const hints = parseRelationHints(text)
  if (!hints.length) return null
  return (
    <div className="flex flex-wrap gap-1.5 ml-5 mt-1">
      {hints.map((h, j) => (
        <span
          key={j}
          className={`inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded border ${
            h.tone === 'up'
              ? 'border-game-success/40 text-game-success bg-game-success/10'
              : h.tone === 'down'
                ? 'border-game-danger/40 text-game-danger bg-game-danger/10'
                : h.tone === 'new'
                  ? 'border-game-accent/40 text-game-accent bg-game-accent/10'
                  : 'border-game-border text-game-muted'
          }`}
        >
          <span>{h.icon}</span>
          <span>{h.name}</span>
          {h.tone !== 'new' && (
            <span className="text-game-dim">{h.metricLabel}</span>
          )}
          {h.tone !== 'new' && (
            <span className="font-bold tabular-nums">
              {h.delta > 0 ? '+' : ''}{h.delta}
            </span>
          )}
        </span>
      ))}
    </div>
  )
}

function AffectionBar({ value }: { value: number; name?: string }) {
  // 防御 NaN / undefined / 负数（避免 '█'.repeat(NaN) 崩溃）
  const safe = Number.isFinite(value) ? Math.max(0, Math.min(100, Math.round(value))) : 50
  // 双向条：左5格=敌意(红)，右5格=好感(绿)，50%为中性
  const hostility = Math.max(0, Math.min(5, Math.round((50 - safe) / 10)))  // 0~5 红色
  const affection = Math.max(0, Math.min(5, Math.round((safe - 50) / 10)))  // 0~5 绿色
  const neutral = 10 - hostility - affection  // 中间灰色
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

export default function Game() {
  const [story, setStory] = useState('')
  const [options, setOptions] = useState<string[]>([])
  const [turn, setTurn] = useState(0)
  const [status, setStatus] = useState('SETUP')
  const [scene, setScene] = useState('')
  const [characters, setCharacters] = useState<CharInfo[]>([])
  const [factions, setFactions] = useState<FactionInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [choosing, setChoosing] = useState(false)
  const [customInput, setCustomInput] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)
  const [charPanelOpen, setCharPanelOpen] = useState(false)
  const [showConsequences, setShowConsequences] = useState(true)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [history, setHistory] = useState<HistoryTurn[]>([])
  const [storyLength, setStoryLength] = useState(1000)
  const [storyLengthMin, setStoryLengthMin] = useState(300)
  const [storyLengthMax, setStoryLengthMax] = useState(213333)
  const [storyLengthRecommended, setStoryLengthRecommended] = useState(1000)
  const [maxTokens, setMaxTokens] = useState(1800)
  const [maxOutputTokens, setMaxOutputTokens] = useState(384000)
  const [contextTokens, setContextTokens] = useState(1000000)
  const [temperature, setTemperature] = useState(0.8)
  const [topP, setTopP] = useState(0.9)
  const [compressThreshold, setCompressThreshold] = useState(4000)
  const [genSettingsOpen, setGenSettingsOpen] = useState(true)
  const [genSettingsSaved, setGenSettingsSaved] = useState(false)
  const storyScrollRef = useRef<HTMLDivElement>(null)
  const genSettingsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingGenPatchRef = useRef<{
    storyLength?: number
    temperature?: number
    topP?: number
    compressThreshold?: number
  }>({})

  const applyTurnData = useCallback((data: {
    story: string
    options?: string[]
    state: Record<string, unknown>
  }) => {
    setStory(data.story)
    setOptions(data.options || [])
    const st = data.state
    setTurn((st.turn as number) || 1)
    setStatus((st.status as string) || 'SETUP')
    setScene((st.scene as string) || '')
    const chars = st.characters as Record<string, CharInfo> | undefined
    if (chars) {
      setCharacters(Object.values(chars).map((c) => ({
        ...c,
        affection: c.affection ?? c.trust_pct ?? 50,
      })))
    }
    const factionsData = st.factions as FactionInfo[] | undefined
    if (factionsData) setFactions(factionsData)
  }, [])

  const loadGame = useCallback(async () => {
    setLoading(true)
    setError('')
    logger.info('Game', 'Loading game state...')
    try {
      const data = await getGameState()
      if (data.error) { setError(data.error); setLoading(false); return }

      if (data.not_started) {
        logger.info('Game', 'Game not started — calling startGame()')
        const started = await startGame()
        if (started.error || !started.story) {
          setError(started.error || '开篇生成失败')
          setLoading(false)
          return
        }
        applyTurnData({
          story: started.story,
          options: started.options,
          state: started.state as Record<string, unknown>,
        })
        logger.info('Game', 'Opening scene generated')
        setLoading(false)
        return
      }

      applyTurnData({
        story: data.story,
        options: data.options,
        state: data.state as Record<string, unknown>,
      })
      logger.info('Game', `Loaded: turn=${(data.state as Record<string, unknown>).turn}`)
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('Game', 'Load failed', { error: msg })
      setError(msg)
    }
    setLoading(false)
  }, [applyTurnData])

  useEffect(() => { loadGame() }, [loadGame])

  const applyGenSettings = useCallback((data: GameGenSettings) => {
    setStoryLength(data.story_length)
    setStoryLengthMin(data.min)
    setStoryLengthMax(data.max)
    setStoryLengthRecommended(data.recommended)
    setMaxTokens(data.max_tokens)
    setMaxOutputTokens(data.max_output_tokens)
    setContextTokens(data.context_tokens)
    setTemperature(data.temperature)
    setTopP(data.top_p)
    setCompressThreshold(data.compress_threshold)
  }, [])

  useEffect(() => {
    getGameGenSettings()
      .then(applyGenSettings)
      .catch((e) => logger.warn('Game', 'Load gen settings failed', { error: String(e) }))
  }, [applyGenSettings])

  const queueGenSettingsSave = useCallback((patch: {
    storyLength?: number
    temperature?: number
    topP?: number
    compressThreshold?: number
  }) => {
    if (patch.storyLength != null) {
      const clamped = Math.max(storyLengthMin, Math.min(storyLengthMax, patch.storyLength))
      setStoryLength(clamped)
      patch.storyLength = clamped
    }
    if (patch.temperature != null) setTemperature(patch.temperature)
    if (patch.topP != null) setTopP(patch.topP)
    if (patch.compressThreshold != null) {
      const clamped = Math.max(500, Math.min(contextTokens, patch.compressThreshold))
      setCompressThreshold(clamped)
      patch.compressThreshold = clamped
    }

    pendingGenPatchRef.current = { ...pendingGenPatchRef.current, ...patch }
    if (genSettingsTimerRef.current) clearTimeout(genSettingsTimerRef.current)
    genSettingsTimerRef.current = setTimeout(async () => {
      const pending = pendingGenPatchRef.current
      pendingGenPatchRef.current = {}
      try {
        const saved = await updateGameGenSettings(pending)
        applyGenSettings(saved)
        setGenSettingsSaved(true)
        setTimeout(() => setGenSettingsSaved(false), 1500)
      } catch (e) {
        logger.error('Game', 'Save gen settings failed', { error: String(e) })
      }
    }, 600)
  }, [storyLengthMin, storyLengthMax, contextTokens, applyGenSettings])

  useEffect(() => () => {
    if (genSettingsTimerRef.current) clearTimeout(genSettingsTimerRef.current)
  }, [])

  const currentStoryChars = story.replace(/\s/g, '').length

  // 新正文生成后滚回顶部，方便从开头阅读
  useEffect(() => {
    if (!story) return
    const el = storyScrollRef.current
    if (!el) return
    requestAnimationFrame(() => { el.scrollTop = 0 })
  }, [turn, story])

  const handleChoice = useCallback(async (choice: string) => {
    setChoosing(true)
    logger.info('Game', `Choice: ${choice}`)
    try {
      const data = await nextTurn(choice)
      if (data.error) { setError(data.error); setChoosing(false); return }
      setStory(data.story)
      setOptions(data.options || [])
      setTurn(data.state.turn)
      setStatus(data.state.status)
      setScene(data.state.scene)
      const chars = data.state.characters as Record<string, CharInfo> | undefined
      if (chars) setCharacters(Object.values(chars).map((c) => ({
        ...c,
        affection: c.affection ?? c.trust_pct ?? 50,
      })))
      const factionsData = data.state.factions as FactionInfo[] | undefined
      if (factionsData) setFactions(factionsData)
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('Game', 'Choice failed', { error: msg })
      // Detect truncation errors and add settings link
      if (msg.includes('截断') || msg.includes('Token') || msg.includes('unparseable')) {
        setError(`${msg}。建议前往设置调高「AI 最大 Token」。`)
      } else {
        setError(msg)
      }
    }
    setChoosing(false)
  }, [])

  const hasGame = !loading && !error && story.length > 0

  // Shared character + faction list component
  const StatusList = () => (
    <div className="space-y-4">
      {/* Characters */}
      {characters.length === 0 && factions.length === 0 && (
        <p className="text-xs text-game-dim text-center py-4">暂无数据</p>
      )}
      {characters.map((c) => (
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
          {c.relation && <p className="text-xs text-game-muted">{c.relation}</p>}
          {/* 主角对自己没有好感度，只显示 NPC 对主角的好感 */}
          {c.tier !== '主角' && (
            <AffectionBar value={c.affection ?? 50} />
          )}
          <Separator />
        </div>
      ))}

      {/* Factions */}
      {factions.length > 0 && characters.length > 0 && (
        <p className="text-xs text-game-dim font-bold pt-2">🏛️ 势力</p>
      )}
      {factions.map((f) => (
        <div key={`f-${f.name}`} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{f.name}</span>
            <Badge variant="outline" size="sm" className={f.attitude_label === '敌对' ? 'border-red-500/50 text-red-400' : f.attitude_label === '同盟' ? 'border-green-500/50 text-green-400' : ''}>
              {f.attitude_label}
            </Badge>
          </div>
          {f.role && <p className="text-xs text-game-muted">{f.role}</p>}
          <div className="flex items-center gap-2">
            <AffectionBar value={(f.reputation ?? 0.5) * 100} />
            <span className="text-xs text-game-dim tabular-nums">{Math.round((f.reputation ?? 0.5) * 100)}%</span>
          </div>
          {/* Inter-faction attitudes (top 3) — safe guarded against missing data */}
          {(f.attitudes || []).filter(a => Math.abs((a.attitude ?? 0.5) - 0.5) >= 0.15).slice(0, 3).map(a => (
            <div key={a.target} className="flex items-center gap-1 text-[10px]">
              <span className="text-game-dim">→ {a.target}</span>
              <span className={a.label === '敌对' || a.label === '冷淡' ? 'text-red-400' : a.label === '同盟' || a.label === '友好' ? 'text-green-400' : 'text-game-muted'}>
                {a.label}
              </span>
            </div>
          ))}
          <Separator />
        </div>
      ))}
    </div>
  )

  return (
    <div className="w-full">
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
        <div className="flex gap-0" style={{ height: 'calc(100vh - 80px)' }}>
          {/* Main content */}
          <div className="flex-1 min-w-0 flex flex-col">
            {/* Top status bar */}
            <div className="flex items-center justify-between gap-3 flex-wrap shrink-0">
              <div className="flex items-center gap-2 text-sm">
                <Badge variant="primary">📖 第 {turn} 轮</Badge>
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

              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1 text-game-muted hover:text-game-text"
                  onClick={async () => {
                    setHistoryOpen(true)
                    const data = await getHistory()
                    if (!data.error) setHistory(data.turns)
                  }}
                >
                  📜 回顾
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1.5 text-game-muted hover:text-game-text"
                  onClick={() => setCharPanelOpen(!charPanelOpen)}
                >
                  📊 状态
                  {(characters.length > 0 || factions.length > 0) && (
                    <Badge variant="accent" size="sm" className="ml-0.5">{characters.length + factions.length}</Badge>
                  )}
                </Button>
              </div>
            </div>

            {/* Generating indicator — fixed, always visible */}
            {choosing && (
              <div className="shrink-0 flex items-center justify-center gap-2 py-3 bg-game-accent/10 border border-game-accent/30 rounded-lg text-sm text-game-accent animate-pulse">
                <span className="inline-block w-3.5 h-3.5 border-2 border-game-accent/30 border-t-game-accent rounded-full animate-spin" />
                AI 正在生成下一段剧情…
              </div>
            )}

            {/* Story — scrollable */}
            <div ref={storyScrollRef} className="flex-1 overflow-y-auto min-h-0 space-y-3">
            <Card className="border-game-border/70 bg-game-bg/40">
              <button
                type="button"
                className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-game-primary/5 transition-colors"
                onClick={() => setGenSettingsOpen((v) => !v)}
              >
                <span className="text-sm font-medium text-game-muted">⚡ 生成快捷设置</span>
                <span className="text-xs text-game-dim flex items-center gap-2">
                  {genSettingsSaved && <span className="text-game-success">已保存</span>}
                  <span>{genSettingsOpen ? '收起 ▲' : '展开 ▼'}</span>
                </span>
              </button>
              {genSettingsOpen && (
                <CardContent className="pt-0 pb-3 px-4">
                  <QuickGenRow
                    label="目标字数"
                    hint="每轮正文目标长度，修改后下一轮生成生效"
                  >
                    <Input
                      type="number"
                      min={storyLengthMin}
                      max={storyLengthMax}
                      step={100}
                      value={storyLength}
                      disabled={choosing}
                      onChange={(e) => queueGenSettingsSave({ storyLength: parseInt(e.target.value, 10) || storyLengthRecommended })}
                      className="w-24 h-8 text-sm"
                    />
                    <button
                      type="button"
                      disabled={choosing}
                      onClick={() => queueGenSettingsSave({ storyLength: storyLengthRecommended })}
                      className="text-xs text-game-accent hover:underline disabled:opacity-50"
                    >
                      建议 {storyLengthRecommended.toLocaleString()}
                    </button>
                    <Badge variant="outline" size="sm" className="tabular-nums">当前 {currentStoryChars} 字</Badge>
                  </QuickGenRow>
                  <QuickGenRow
                    label="最大 Token"
                    hint={`AI 单次回复上限，随字数自动匹配；官方最大 ${maxOutputTokens.toLocaleString()}`}
                  >
                    <Badge variant="outline" size="sm" className="tabular-nums">{maxTokens.toLocaleString()}</Badge>
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
                    hint={`对话 token 超过此值时触发压缩；范围 500–${contextTokens.toLocaleString()}`}
                  >
                    <Input
                      type="number"
                      min={500}
                      max={contextTokens}
                      step={500}
                      value={compressThreshold}
                      disabled={choosing}
                      onChange={(e) => queueGenSettingsSave({ compressThreshold: parseInt(e.target.value, 10) || 4000 })}
                      className="w-28 h-8 text-sm"
                    />
                  </QuickGenRow>
                </CardContent>
              )}
            </Card>
            <Card>
              <CardContent className="pt-4 md:px-8">
                <p className="text-sm font-medium text-game-muted mb-4">📖 正文</p>
                <motion.div key={turn} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
                  {story.split('\n').filter(Boolean).map((paragraph, i) => (
                    <motion.p key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                      className="text-game-text leading-relaxed text-[17px] mb-5"
                    >
                      {paragraph}
                    </motion.p>
                  ))}
                </motion.div>
              </CardContent>
            </Card>
            </div>{/* end scrollable area */}

            {/* Choices — fixed at bottom */}
            <div className="shrink-0 border-t border-game-border bg-game-bg/95 backdrop-blur-sm pt-3 pb-1">
            <AnimatePresence>
              {options.length > 0 && (
                <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-game-muted font-medium">🎯 做出你的选择</p>
                    <div className="flex items-center gap-2">
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
                  {options.map((choice, i) => {
                    // Parse "行动 → 可能发展 | 态度 | 人际影响"
                    const parts = choice.split(/\s*[→]\s*/)
                    const action = parts[0] || choice
                    const rest = parts.slice(1).join(' → ')
                    const segments = rest.split(/\s*\|\s*/)
                    const consequence = segments[0] || ''
                    const attitude = segments[1] || ''
                    const relation = segments[2] || ''
                    return (
                      <Button key={`${turn}-${i}`} variant="outline" disabled={choosing}
                        onClick={() => handleChoice(String.fromCharCode(65 + i))}
                        className="w-full justify-start text-left h-auto py-3 px-4 hover:bg-game-primary/10 hover:border-game-primary/50 transition-all"
                      >
                        <div className="flex flex-col gap-1 min-w-0">
                          <div className="flex items-start gap-2 flex-wrap">
                            <span className="text-game-accent font-bold shrink-0 mt-0.5">{String.fromCharCode(65 + i)}.</span>
                            <span className="text-base font-medium text-game-text">{action}</span>
                            {showConsequences && attitude && (
                              <Badge variant="accent" size="sm" className="shrink-0 text-[10px]">{attitude.trim()}</Badge>
                            )}
                          </div>
                          {showConsequences && consequence && (
                            <p className="text-sm text-game-muted ml-5 pl-0.5">{consequence.trim()}</p>
                          )}
                          {relation && <RelationChips text={relation} />}
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
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            </div>

          </div>

          {/* Character side panel — inline, pushes content */}
          {charPanelOpen && (
            <div className="w-64 shrink-0 border-l border-game-border bg-game-card p-4 overflow-auto max-h-[calc(100vh-64px)] sticky top-14">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-game-accent">📊 状态</h3>
                <button onClick={() => setCharPanelOpen(false)} className="text-game-muted hover:text-game-text">✕</button>
              </div>
              <StatusList />
            </div>
          )}
        </div>
      )}

      {/* ── History Dialog ── */}
      {historyOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-12 px-4">
          <div className="fixed inset-0 bg-black/70" onClick={() => setHistoryOpen(false)} />
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
                <button onClick={() => setHistoryOpen(false)} className="text-game-muted hover:text-game-text text-lg px-1">✕</button>
              </div>
            </div>

            {/* Content */}
            <div className="overflow-y-auto p-5 space-y-6 flex-1">
              {history.length === 0 ? (
                <p className="text-game-muted text-center py-8">暂无剧情记录</p>
              ) : (
                history.map((h, i) => (
                  <div key={i} className="space-y-2">
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
                      const choiceText = isLetter && h.options[idx] ? h.options[idx].split('→')[0].trim() : h.choice
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
    </div>
  )
}
