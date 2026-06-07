import { useState, useEffect, useCallback, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion } from 'framer-motion'
import { logger } from '@/lib/logger'
import {
  getEngineSettings,
  saveEngineSettings,
  getAppSettings,
  clearApiKey,
  resetGame,
  listSaves,
  saveGameSlot,
  loadGameSlot,
  downloadStoryExport,
  checkHealth,
  shutdownServer,
  type SaveSlotInfo,
} from '@/lib/api'
import {
  loadSettings,
  saveSettings,
  DEFAULTS,
  type AppSettings,
  FONT_SIZE_OPTIONS,
  LINE_HEIGHT_OPTIONS,
  MAX_WIDTH_OPTIONS,
  normalizeMaxWidth,
  FONT_FAMILY_LABELS,
  BG_THEME_LABELS,
  AUTO_ADVANCE_ROUND_OPTIONS,
} from '@/lib/settings'
import { t } from '@/lib/i18n'
import { useAppSettings } from '@/hooks/useAppSettings'
import { usePageShell } from '@/components/layout/usePageShell'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { Settings as SettingsIcon } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// ── Zod Schema ──
const settingsSchema = z.object({
  fontSize: z.number(),
  lineHeight: z.number(),
  fontFamily: z.string(),
  maxWidth: z.number(),
  bgTheme: z.string(),
  paragraphSpacing: z.string(),
  autoAdvance: z.boolean(),
  autoAdvanceRounds: z.number().min(1).max(50),
  autoSaveInterval: z.number(),
  maxSaveSlots: z.number(),
  exportFormat: z.string(),
  autoExport: z.string(),
  animations: z.boolean(),
  sidebarDefault: z.string(),
  charPanelPosition: z.string(),
  language: z.string(),
})

type SettingsForm = z.infer<typeof settingsSchema>

// ── Option helper ──
function SelectRow({
  label,
  value,
  options,
  onChange,
  labels,
}: {
  label: string
  value: string | number
  options: readonly (string | number | { value: string | number; label: string })[]
  onChange: (v: string | number) => void
  labels?: Record<string, string>
}) {
  const optionValues = new Set(
    options.map((opt) =>
      String(typeof opt === 'object' && opt !== null && 'value' in opt ? opt.value : opt),
    ),
  )
  const safeValue = optionValues.has(String(value))
    ? String(value)
    : (optionValues.size > 0 ? String(value) : undefined)

  return (
    <div className="flex items-center justify-between gap-4">
      <Label className="text-sm text-game-muted shrink-0">{label}</Label>
      <Select
        value={safeValue && optionValues.has(safeValue) ? safeValue : undefined}
        onValueChange={(v) => onChange(isNaN(Number(v)) ? v : Number(v))}
      >
        <SelectTrigger className="w-[140px] h-8 text-xs">
          <SelectValue placeholder="请选择" />
        </SelectTrigger>
        <SelectContent>
          {options.map((opt) => {
            const v = typeof opt === 'object' && opt !== null && 'value' in opt ? opt.value : opt
            const l = typeof opt === 'object' && opt !== null && 'label' in opt ? opt.label : String(opt)
            return (
              <SelectItem key={String(v)} value={String(v)} className="text-xs">
                {labels?.[String(v)] ?? l}
              </SelectItem>
            )
          })}
        </SelectContent>
      </Select>
    </div>
  )
}

// ── Main Page ──
export default function Settings() {
  const navigate = useNavigate()
  const { language } = useAppSettings()
  const lang = language as 'zh' | 'en' | 'ja'
  const [saved, setSaved] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [apiKeyMasked, setApiKeyMasked] = useState('')
  const [model, setModel] = useState('deepseek-chat')
  const [streamEnabled, setStreamEnabled] = useState(true)
  const [maxContextMsgs, setMaxContextMsgs] = useState(20)
  const [autoCompress, setAutoCompress] = useState(true)

  const defaultValues = loadSettings()
  const form = useForm<SettingsForm>({
    resolver: zodResolver(settingsSchema),
    defaultValues,
  })

  const { watch, setValue } = form
  const values = watch()

  // Persist on change
  const persist = useCallback((key: keyof AppSettings, value: unknown) => {
    saveSettings({ [key]: value } as Partial<AppSettings>)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }, [])

  const setAndPersist = useCallback((key: keyof SettingsForm, value: unknown) => {
    setValue(key, value as never, { shouldDirty: true })
    persist(key as keyof AppSettings, value)
  }, [setValue, persist])

  const skipWatchRef = useRef(true)

  // Sync all changes（不依赖 isDirty 闭包，避免首次改最大宽度等不保存）
  useEffect(() => {
    const sub = form.watch((data) => {
      if (skipWatchRef.current) {
        skipWatchRef.current = false
        return
      }
      if (data) {
        saveSettings(data as Partial<AppSettings>)
        setSaved(true)
        const t = setTimeout(() => setSaved(false), 1500)
        return () => clearTimeout(t)
      }
    })
    return () => sub.unsubscribe()
  }, [form])

  // 旧版 maxWidth（如 800）迁移到合法选项并写回
  useEffect(() => {
    const s = loadSettings()
    const normalized = normalizeMaxWidth(s.maxWidth)
    if (normalized !== s.maxWidth) {
      saveSettings({ maxWidth: normalized })
    }
    if (values.maxWidth !== normalized) {
      setValue('maxWidth', normalized)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // API settings — refetch when entering settings or tab refocus (sync max_tokens after game page edits)
  const location = useLocation()
  const loadEngineSettings = useCallback(() => {
    getEngineSettings()
      .then((data) => {
        if (data.api_key_masked) setApiKeyMasked(data.api_key_masked)
        setModel(data.model)
        setStreamEnabled(data.stream)
        setMaxContextMsgs(data.max_context_messages)
        setAutoCompress(data.auto_compress)
      })
      .catch((e) => logger.error('Settings', 'Load engine settings failed', { error: String(e) }))
  }, [])

  useEffect(() => {
    loadEngineSettings()
  }, [location.pathname, loadEngineSettings])

  useEffect(() => {
    getAppSettings()
      .then((data) => {
        if (!data) return
        setValue('autoSaveInterval', data.auto_save_interval)
        setValue('maxSaveSlots', data.max_save_slots)
        setValue('exportFormat', data.export_format)
        setValue('autoExport', data.auto_export)
      })
      .catch((e) => logger.warn('Settings', 'Load app settings failed', { error: String(e) }))
  }, [setValue])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') loadEngineSettings()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [loadEngineSettings])

  useEffect(() => {
    const onSettingsChanged = () => loadEngineSettings()
    window.addEventListener('promptos:settings-changed', onSettingsChanged)
    return () => window.removeEventListener('promptos:settings-changed', onSettingsChanged)
  }, [loadEngineSettings])

  const [apiSaving, setApiSaving] = useState(false)
  const [apiSaved, setApiSaved] = useState(false)
  const [apiClearing, setApiClearing] = useState(false)
  const [apiCleared, setApiCleared] = useState(false)
  const [apiError, setApiError] = useState('')
  const [resetting, setResetting] = useState(false)
  const [dataError, setDataError] = useState('')
  const [saves, setSaves] = useState<SaveSlotInfo[]>([])
  const [savesLoading, setSavesLoading] = useState(false)
  const [slotBusy, setSlotBusy] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportSuccess, setExportSuccess] = useState(false)
  const [healthOk, setHealthOk] = useState<boolean | null>(null)
  const [shuttingDown, setShuttingDown] = useState(false)

  const refreshSaves = useCallback(async () => {
    setSavesLoading(true)
    try {
      const list = await listSaves()
      setSaves(list)
    } catch (e) {
      logger.warn('Settings', 'Load saves failed', { error: String(e) })
    }
    setSavesLoading(false)
  }, [])

  useEffect(() => {
    refreshSaves()
  }, [refreshSaves, values.maxSaveSlots])

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const h = await checkHealth()
        if (!cancelled) setHealthOk(h.status === 'ok')
      } catch {
        if (!cancelled) setHealthOk(false)
      }
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const manualSlots = Array.from({ length: values.maxSaveSlots }, (_, i) => `slot${i + 1}`)

  const getSlotMeta = (slot: string) => saves.find((s) => s.slot === slot)

  const handleSaveSlot = useCallback(async (slot: string) => {
    if (!confirm(`确定将当前进度保存到 ${slot}？`)) return
    setSlotBusy(slot)
    setDataError('')
    setSaveSuccess('')
    try {
      await saveGameSlot(slot)
      await refreshSaves()
      setSaveSuccess(`${slot} 已保存`)
      setTimeout(() => setSaveSuccess(''), 2500)
    } catch (e) {
      setDataError((e as Error).message || String(e))
    }
    setSlotBusy(null)
  }, [refreshSaves])

  const handleLoadSlot = useCallback(async (slot: string) => {
    const meta = getSlotMeta(slot)
    if (!meta) {
      setDataError(`存档槽 ${slot} 为空`)
      return
    }
    if (!confirm(`确定从 ${slot} 读档？\n回合 ${meta.turn} · ${meta.scene || '未知场景'}\n当前未保存进度将丢失。`)) return
    setSlotBusy(slot)
    setDataError('')
    try {
      await loadGameSlot(slot)
      navigate('/game')
    } catch (e) {
      setDataError((e as Error).message || String(e))
    }
    setSlotBusy(null)
  }, [navigate, saves])

  const handleExport = useCallback(async () => {
    setExporting(true)
    setDataError('')
    setExportSuccess(false)
    try {
      await downloadStoryExport()
      setExportSuccess(true)
      setTimeout(() => setExportSuccess(false), 2500)
    } catch (e) {
      setDataError((e as Error).message || String(e))
    }
    setExporting(false)
  }, [])

  const handleShutdown = useCallback(async () => {
    if (!confirm('确定要关闭后端服务？\n游戏将无法继续直到重新启动。')) return
    if (!confirm('再次确认：关闭后需重新运行「启动.bat」。')) return
    setShuttingDown(true)
    setDataError('')
    try {
      await shutdownServer()
      setHealthOk(false)
    } catch (e) {
      setDataError((e as Error).message || String(e))
    }
    setShuttingDown(false)
  }, [])

  const handleResetGame = useCallback(async () => {
    if (!confirm('确定要重置当前游戏进度？\n\n将恢复到创建故事时的初始状态（回合、历史、章节输出会清空），此操作不可撤销。')) return
    setResetting(true)
    setDataError('')
    try {
      await resetGame()
      navigate('/game')
    } catch (e) {
      const msg = (e as Error).message || String(e)
      setDataError(msg)
      logger.error('Settings', 'Reset game failed', { error: msg })
    }
    setResetting(false)
  }, [navigate])

  const saveApiKey = useCallback(async () => {
    setApiSaving(true)
    setApiSaved(false)
    setApiError('')
    try {
      const data = await saveEngineSettings({
        apiKey: apiKey || undefined,
        model,
        stream: streamEnabled,
        maxContextMsgs,
        autoCompress,
      })
      if (data.api_key_masked) setApiKeyMasked(data.api_key_masked)
      setApiKey('')
      setApiSaved(true)
      setSaved(true)
      setTimeout(() => { setSaved(false); setApiSaved(false) }, 2500)
    } catch (e) {
      const msg = (e as Error).message || String(e)
      setApiError(msg)
      logger.error('Settings', 'Save API failed', { error: msg })
    }
    setApiSaving(false)
  }, [apiKey, model, streamEnabled, maxContextMsgs, autoCompress])

  const clearStoredApiKey = useCallback(async () => {
    if (!confirm('确定要清除本机已保存的 API Key？清除后需重新填写才能调用 AI。')) return
    setApiClearing(true)
    setApiError('')
    setApiCleared(false)
    try {
      const data = await clearApiKey()
      setApiKey('')
      setApiKeyMasked(data.api_key_masked || '')
      setApiCleared(true)
      window.dispatchEvent(new Event('promptos:apikey-cleared'))
      setTimeout(() => setApiCleared(false), 2500)
    } catch (e) {
      const msg = (e as Error).message || String(e)
      setApiError(msg)
      logger.error('Settings', 'Clear API key failed', { error: msg })
    }
    setApiClearing(false)
  }, [])

  usePageShell({
    navItems: [
      { id: 'reading', label: t('settings.reading', lang) },
      { id: 'data', label: t('settings.data', lang) },
      { id: 'ui', label: t('settings.ui', lang) },
      { id: 'api', label: t('settings.api', lang) },
    ],
    activeNavId: 'reading',
    hideShellPanels: false,
  })

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6 space-y-6 max-w-3xl">
      <SectionHeader
        icon={SettingsIcon}
        title={t('settings.title', lang)}
        subtitle="Neural Interface · 系统配置"
        status={saved ? 'active' : 'idle'}
      />
      <div className="flex justify-end">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: saved ? 1 : 0 }}
        >
          <Badge variant="success" size="sm">✅ 已保存</Badge>
        </motion.div>
      </div>

      <Accordion type="multiple" defaultValue={['reading', 'data', 'ui', 'api']} className="space-y-3">
        {/* ── Reading ── */}
        <AccordionItem value="reading" asChild>
          <Card>
            <AccordionTrigger className="px-5 py-3.5 hover:no-underline">
              <span className="font-bold text-sm flex items-center gap-2">
                <span>📖</span> {t('settings.reading', lang)}
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <CardContent className="space-y-4 pt-2">
                <SelectRow label="字体大小" value={values.fontSize} options={FONT_SIZE_OPTIONS} onChange={(v) => setAndPersist('fontSize', v as number)} />
                <SelectRow label="行高" value={values.lineHeight} options={LINE_HEIGHT_OPTIONS} onChange={(v) => setAndPersist('lineHeight', v as number)} />
                <SelectRow label="正文字体" value={values.fontFamily} options={['system', 'serif', 'sans', 'kai']} onChange={(v) => setAndPersist('fontFamily', v as string)} labels={FONT_FAMILY_LABELS} />
                <SelectRow label="最大宽度" value={normalizeMaxWidth(values.maxWidth)} options={MAX_WIDTH_OPTIONS} onChange={(v) => setAndPersist('maxWidth', v as number)} />
                <SelectRow label="背景色调" value={values.bgTheme} options={['dark', 'sepia', 'gray']} onChange={(v) => setAndPersist('bgTheme', v as string)} labels={BG_THEME_LABELS} />
                <SelectRow label="段落间距" value={values.paragraphSpacing} options={['compact', 'standard', 'relaxed']} onChange={(v) => setAndPersist('paragraphSpacing', v as string)} labels={{ compact: '紧凑', standard: '标准', relaxed: '宽松' }} />

                {/* Live preview */}
                <Card className="bg-game-bg border-game-border">
                  <CardContent className="p-4 text-sm" style={{
                    fontSize: `var(--story-font-size)`,
                    lineHeight: `var(--story-line-height)`,
                    fontFamily: `var(--story-font-family)`,
                    maxWidth: `var(--story-max-width)`,
                  }}>
                    <p style={{ marginBottom: 'var(--story-paragraph-spacing)' }}>
                      「有时候，一个选择就足以改变一切。」
                    </p>
                    <p>少女微微一笑，伸手拨开了被风吹乱的刘海，目光穿过窗外的樱花，仿佛在凝视遥远的记忆。</p>
                  </CardContent>
                </Card>
              </CardContent>
            </AccordionContent>
          </Card>
        </AccordionItem>

        {/* ── Data ── */}
        <AccordionItem value="data" asChild>
          <Card>
            <AccordionTrigger className="px-5 py-3.5 hover:no-underline">
              <span className="font-bold text-sm flex items-center gap-2">
                <span>💾</span> {t('settings.data', lang)}
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <CardContent className="space-y-4 pt-2">
                <SelectRow
                  label="自动保存间隔"
                  value={values.autoSaveInterval}
                  options={[30, 60, 300, 0]}
                  onChange={(v) => setValue('autoSaveInterval', v as number)}
                  labels={{ 30: '30秒', 60: '1分钟', 300: '5分钟', 0: '关闭' }}
                />
                <SelectRow label="最大存档数" value={values.maxSaveSlots} options={[3, 5, 10]} onChange={(v) => setValue('maxSaveSlots', v as number)} />
                <SelectRow
                  label="导出格式"
                  value={values.exportFormat}
                  options={['markdown', 'text', 'html']}
                  onChange={(v) => setValue('exportFormat', v as string)}
                  labels={{ markdown: 'Markdown', text: '纯文本', html: 'HTML' }}
                />
                <SelectRow
                  label="自动导出"
                  value={values.autoExport}
                  options={['off', 'turn', 'chapter']}
                  onChange={(v) => setValue('autoExport', v as string)}
                  labels={{ off: '关闭', turn: '每轮', chapter: '每章' }}
                />
                <p className="text-xs text-game-dim">
                  自动保存间隔控制引擎 autosave 频率；自动导出写入 <code className="text-game-muted">output/exports/</code>。
                </p>
                <Separator />
                <div className="space-y-2">
                  <Label className="text-sm text-game-muted">游戏进度</Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full text-game-danger border-game-danger/40 hover:bg-game-danger/10"
                    onClick={handleResetGame}
                    disabled={resetting}
                  >
                    {resetting ? '⏳ 重置中…' : '🔄 重置游戏进度'}
                  </Button>
                  <p className="text-[11px] text-game-dim">
                    从 <code className="text-game-muted">world_init.json</code> 恢复初始状态，清空当前回合与历史；世界观设定（world_pack）不变。
                  </p>
                  {dataError && (
                    <p className="text-xs text-game-danger rounded-md border border-game-danger/30 bg-game-danger/10 px-3 py-2">
                      {dataError}
                    </p>
                  )}
                </div>
                <p className="text-[11px] text-game-dim">
                  引擎每回合仍会自动 autosave；手动槽位与 autosave 独立存储。
                </p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <Label className="text-sm text-game-muted">手动存档</Label>
                    <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={refreshSaves} disabled={savesLoading}>
                      {savesLoading ? '刷新中…' : '🔄 刷新'}
                    </Button>
                  </div>
                  {saveSuccess && (
                    <p className="text-xs text-game-success">{saveSuccess}</p>
                  )}
                  <div className="space-y-2">
                    {manualSlots.map((slot) => {
                      const meta = getSlotMeta(slot)
                      const busy = slotBusy === slot
                      return (
                        <div key={slot} className="rounded-md border border-game-border/60 bg-game-bg/30 px-3 py-2 space-y-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-medium text-game-muted">{slot}</span>
                            {meta ? (
                              <span className="text-[10px] text-game-dim truncate">
                                回合 {meta.turn} · {meta.scene || '—'} · {meta.saved_at?.slice(0, 16).replace('T', ' ')}
                              </span>
                            ) : (
                              <span className="text-[10px] text-game-dim">空槽</span>
                            )}
                          </div>
                          <div className="flex gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="flex-1 h-7 text-xs"
                              onClick={() => handleSaveSlot(slot)}
                              disabled={busy || savesLoading}
                            >
                              {busy ? '…' : '💾 存档'}
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="flex-1 h-7 text-xs"
                              onClick={() => handleLoadSlot(slot)}
                              disabled={busy || savesLoading || !meta}
                            >
                              {busy ? '…' : '📂 读档'}
                            </Button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm text-game-muted">Obsidian 导出</Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full"
                    onClick={handleExport}
                    disabled={exporting}
                  >
                    {exporting ? '⏳ 导出中…' : exportSuccess ? '✅ 已下载' : '📓 导出完整叙事'}
                  </Button>
                  <p className="text-[11px] text-game-dim">
                    下载 Markdown 文件，可导入 Obsidian 等笔记软件。
                  </p>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm text-game-muted">后端服务</Label>
                  <div className="flex items-center gap-2 text-xs">
                    <span
                      className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                        healthOk === null ? 'bg-game-dim animate-pulse' : healthOk ? 'bg-game-success' : 'bg-game-danger'
                      }`}
                    />
                    <span className="text-game-muted">
                      {healthOk === null ? '检测中…' : healthOk ? '已连接' : '未连接'}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="w-full text-game-danger border-game-danger/40 hover:bg-game-danger/10"
                    onClick={handleShutdown}
                    disabled={shuttingDown}
                  >
                    {shuttingDown ? '⏳ 关闭中…' : '⏻ 关闭后端服务'}
                  </Button>
                  <p className="text-[11px] text-game-dim">
                    关闭后需重新运行启动脚本；开发模式下 Vite 代理也会失效。
                  </p>
                </div>
              </CardContent>
            </AccordionContent>
          </Card>
        </AccordionItem>

        {/* ── UI ── */}
        <AccordionItem value="ui" asChild>
          <Card>
            <AccordionTrigger className="px-5 py-3.5 hover:no-underline">
              <span className="font-bold text-sm flex items-center gap-2">
                <span>🎨</span> {t('settings.ui', lang)}
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <CardContent className="space-y-4 pt-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm text-game-muted">自动推进</Label>
                  <Switch
                    checked={values.autoAdvance}
                    onCheckedChange={(v) => setValue('autoAdvance', v)}
                  />
                </div>
                {values.autoAdvance && (
                  <SelectRow
                    label="推进轮数"
                    value={values.autoAdvanceRounds}
                    options={[...AUTO_ADVANCE_ROUND_OPTIONS]}
                    onChange={(v) => setValue('autoAdvanceRounds', v as number)}
                  />
                )}
                <p className="text-xs text-game-dim">
                  开启后游戏页选项区上方可开关、调整轮数；5 秒后自动选 A，可暂停/继续，每轮成功生成后扣减剩余轮数。
                </p>
                <div className="flex items-center justify-between">
                  <Label className="text-sm text-game-muted">动画效果</Label>
                  <Switch
                    checked={values.animations}
                    onCheckedChange={(v) => setValue('animations', v)}
                  />
                </div>
                <SelectRow
                  label="快捷设置默认展开"
                  value={values.sidebarDefault}
                  options={['expanded', 'collapsed']}
                  onChange={(v) => setValue('sidebarDefault', v as string)}
                  labels={{ expanded: '展开', collapsed: '折叠' }}
                />
                <p className="text-xs text-game-dim -mt-2">
                  控制游戏页 ⚡ 快捷设置面板的初始折叠状态（不影响角色状态面板）。
                </p>
                <SelectRow
                  label="角色面板位置"
                  value={values.charPanelPosition}
                  options={['right', 'bottom', 'hidden']}
                  onChange={(v) => setValue('charPanelPosition', v as string)}
                  labels={{ right: '右侧', bottom: '底部', hidden: '隐藏' }}
                />
                <SelectRow
                  label="语言"
                  value={values.language}
                  options={['zh', 'en', 'ja']}
                  onChange={(v) => setValue('language', v as string)}
                  labels={{ zh: '中文', en: 'English', ja: '日本語' }}
                />
              </CardContent>
            </AccordionContent>
          </Card>
        </AccordionItem>

        {/* ── API ── */}
        <AccordionItem value="api" asChild>
          <Card>
            <AccordionTrigger className="px-5 py-3.5 hover:no-underline">
              <span className="font-bold text-sm flex items-center gap-2">
                <span>🔑</span> {t('settings.api', lang)}
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <CardContent className="space-y-4 pt-2">
                <p className="text-xs text-game-dim rounded-md border border-game-border/60 bg-game-bg/50 px-3 py-2">
                  与首次启动弹窗写入同一 <code className="text-game-muted">data/apikey.json</code>；清除后弹窗会再次出现。
                </p>
                <div className="space-y-1.5">
                  <Label>DeepSeek API Key</Label>
                  <Input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-xxxxxxxxxxxxxxxx"
                    className="font-mono"
                  />
                  {apiKeyMasked && (
                    <p className="text-xs text-game-success">✅ 已配置 ({apiKeyMasked})</p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label>模型</Label>
                  <Select value={model} onValueChange={setModel}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="deepseek-chat">V4-Flash（快速）</SelectItem>
                      <SelectItem value="deepseek-reasoner">V4-Pro（深度思考）</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <p className="text-xs text-game-dim rounded-md border border-game-border/60 bg-game-bg/50 px-3 py-2">
                  生成相关参数（字数、温度、选项数、视角、文风等）请在<strong className="text-game-muted">游戏页 → ⚡ 快捷设置</strong>中调整。
                </p>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <Label>📡 流式输出</Label>
                    <p className="text-xs text-game-dim">逐字显示 AI 回复（SSE，默认开启）</p>
                  </div>
                  <Switch checked={streamEnabled} onCheckedChange={setStreamEnabled} />
                </div>
                <Separator />
                <p className="text-xs text-game-accent font-medium">💬 上下文管理</p>
                <div className="space-y-1.5">
                  <Label>上下文消息上限</Label>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Input
                      type="number"
                      min={4}
                      max={100}
                      step={2}
                      value={maxContextMsgs}
                      onChange={(e) => setMaxContextMsgs(parseInt(e.target.value) || 20)}
                      className="w-24"
                    />
                    <span className="text-xs text-game-dim">保留最近 N 条对话（4–100）</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>🗜️ 自动压缩</Label>
                    <p className="text-xs text-game-dim">历史过长时自动摘要</p>
                  </div>
                  <Switch checked={autoCompress} onCheckedChange={setAutoCompress} />
                </div>
                {apiError && (
                  <p className="text-xs text-game-danger rounded-md border border-game-danger/30 bg-game-danger/10 px-3 py-2">
                    {apiError}
                  </p>
                )}
                <Button variant={apiSaved ? 'success' : 'success'} className="w-full" onClick={saveApiKey} disabled={apiSaving || apiClearing}>
                  {apiSaving ? '⏳ 保存中…' : apiSaved ? '✅ 已保存' : '💾 保存 API 设置'}
                </Button>
                {apiKeyMasked && (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full text-game-danger border-game-danger/40 hover:bg-game-danger/10"
                    onClick={clearStoredApiKey}
                    disabled={apiSaving || apiClearing}
                  >
                    {apiClearing ? '⏳ 清除中…' : apiCleared ? '✅ 已清除' : '🗑️ 清除已存 API Key'}
                  </Button>
                )}
              </CardContent>
            </AccordionContent>
          </Card>
        </AccordionItem>
      </Accordion>

      {/* Reset */}
      <div className="text-center pb-8">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-xs text-game-dim hover:text-game-danger"
          onClick={() => {
            if (confirm('恢复所有设置为默认值？')) {
              saveSettings({ ...DEFAULTS })
              Object.entries(DEFAULTS).forEach(([key, val]) => {
                setValue(key as keyof SettingsForm, val as never)
              })
              import('@/lib/api').then(({ updateAppSettings }) =>
                updateAppSettings({
                  autoSaveInterval: DEFAULTS.autoSaveInterval,
                  maxSaveSlots: DEFAULTS.maxSaveSlots,
                  exportFormat: DEFAULTS.exportFormat,
                  autoExport: DEFAULTS.autoExport,
                }).catch(() => {}),
              )
            }
          }}
        >
          恢复默认设置
        </Button>
      </div>
    </div>
  )
}
