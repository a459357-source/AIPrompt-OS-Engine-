import { useState, useEffect, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { motion } from 'framer-motion'
import { logger } from '@/lib/logger'
import { getEngineSettings, saveEngineSettings, getAppSettings } from '@/lib/api'
import {
  loadSettings,
  saveSettings,
  DEFAULTS,
  type AppSettings,
  FONT_SIZE_OPTIONS,
  LINE_HEIGHT_OPTIONS,
  MAX_WIDTH_OPTIONS,
  FONT_FAMILY_LABELS,
  BG_THEME_LABELS,
  AUTO_ADVANCE_ROUND_OPTIONS,
} from '@/lib/settings'
import { t } from '@/lib/i18n'
import { useAppSettings } from '@/hooks/useAppSettings'
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
  return (
    <div className="flex items-center justify-between gap-4">
      <Label className="text-sm text-game-muted shrink-0">{label}</Label>
      <Select value={String(value)} onValueChange={(v) => onChange(isNaN(Number(v)) ? v : Number(v))}>
        <SelectTrigger className="w-[140px] h-8 text-xs">
          <SelectValue />
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
  const { language } = useAppSettings()
  const lang = language as 'zh' | 'en' | 'ja'
  const [saved, setSaved] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [apiKeyMasked, setApiKeyMasked] = useState('')
  const [model, setModel] = useState('deepseek-chat')
  const [stream, setStream] = useState(false)
  const [maxContextMsgs, setMaxContextMsgs] = useState(20)
  const [autoCompress, setAutoCompress] = useState(true)

  const defaultValues = loadSettings()
  const form = useForm<SettingsForm>({
    resolver: zodResolver(settingsSchema),
    defaultValues,
  })

  const { watch, setValue, formState: { isDirty } } = form
  const values = watch()

  // Persist on change
  const persist = useCallback((key: keyof AppSettings, value: unknown) => {
    saveSettings({ [key]: value } as Partial<AppSettings>)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }, [])

  // Sync all changes
  useEffect(() => {
    const sub = form.watch((data) => {
      if (data && isDirty) {
        saveSettings(data as Partial<AppSettings>)
        setSaved(true)
        const t = setTimeout(() => setSaved(false), 1500)
        return () => clearTimeout(t)
      }
    })
    return () => sub.unsubscribe()
  }, [form, isDirty])

  // API settings — refetch when entering settings or tab refocus (sync max_tokens after game page edits)
  const location = useLocation()
  const loadEngineSettings = useCallback(() => {
    getEngineSettings()
      .then((data) => {
        if (data.api_key_masked) setApiKeyMasked(data.api_key_masked)
        setModel(data.model)
        setStream(data.stream)
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

  const [apiSaving, setApiSaving] = useState(false)
  const [apiSaved, setApiSaved] = useState(false)

  const saveApiKey = useCallback(async () => {
    setApiSaving(true)
    setApiSaved(false)
    try {
      const data = await saveEngineSettings({
        apiKey: apiKey || undefined,
        model,
        stream,
        maxContextMsgs,
        autoCompress,
      })
      if (data.api_key_masked) setApiKeyMasked(data.api_key_masked)
      setApiKey('')
      setApiSaved(true)
      setSaved(true)
      setTimeout(() => { setSaved(false); setApiSaved(false) }, 2500)
    } catch (e) {
      logger.error('Settings', 'Save API failed', { error: String(e) })
    }
    setApiSaving(false)
  }, [apiKey, model, stream, maxContextMsgs, autoCompress])

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-game-accent font-bold text-xl">⚙️ {t('settings.title', lang)}</h1>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: saved ? 1 : 0 }}
          className="flex items-center gap-2"
        >
          <Badge variant="success" size="sm">✅ 已保存</Badge>
        </motion.div>
      </div>

      <Accordion type="multiple" defaultValue={['reading', 'data', 'ui']} className="space-y-3">
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
                <SelectRow label="字体大小" value={values.fontSize} options={FONT_SIZE_OPTIONS} onChange={(v) => setValue('fontSize', v as number)} />
                <SelectRow label="行高" value={values.lineHeight} options={LINE_HEIGHT_OPTIONS} onChange={(v) => setValue('lineHeight', v as number)} />
                <SelectRow label="正文字体" value={values.fontFamily} options={['system', 'serif', 'sans', 'kai']} onChange={(v) => setValue('fontFamily', v as string)} labels={FONT_FAMILY_LABELS} />
                <SelectRow label="最大宽度" value={values.maxWidth} options={MAX_WIDTH_OPTIONS} onChange={(v) => setValue('maxWidth', v as number)} />
                <SelectRow label="背景色调" value={values.bgTheme} options={['dark', 'sepia', 'gray']} onChange={(v) => setValue('bgTheme', v as string)} labels={BG_THEME_LABELS} />
                <SelectRow label="段落间距" value={values.paragraphSpacing} options={['compact', 'standard', 'relaxed']} onChange={(v) => setValue('paragraphSpacing', v as string)} labels={{ compact: '紧凑', standard: '标准', relaxed: '宽松' }} />

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
                  开启后游戏页可自动选 A；可在对局内暂停/继续，每轮成功生成后扣减剩余轮数。
                </p>
                <div className="flex items-center justify-between">
                  <Label className="text-sm text-game-muted">动画效果</Label>
                  <Switch
                    checked={values.animations}
                    onCheckedChange={(v) => setValue('animations', v)}
                  />
                </div>
                <SelectRow
                  label="侧栏默认"
                  value={values.sidebarDefault}
                  options={['expanded', 'collapsed']}
                  onChange={(v) => setValue('sidebarDefault', v as string)}
                  labels={{ expanded: '展开', collapsed: '折叠' }}
                />
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
                <div className="flex items-center justify-between">
                  <Label>📡 流式输出</Label>
                  <Switch checked={stream} onCheckedChange={setStream} />
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
                <Button variant={apiSaved ? 'success' : 'success'} className="w-full" onClick={saveApiKey} disabled={apiSaving}>
                  {apiSaving ? '⏳ 保存中…' : apiSaved ? '✅ 已保存' : '💾 保存 API 设置'}
                </Button>
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
