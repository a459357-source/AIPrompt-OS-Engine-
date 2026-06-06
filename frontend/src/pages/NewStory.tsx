import { useState, useCallback, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { generateWorld, generateField, generateRules, createStory } from '@/lib/api'
import { logger } from '@/lib/logger'
import { useAutoSave } from '@/hooks/useAutoSave'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { TagInput } from '@/components/TagInput'
import { AIButton } from '@/components/AIButton'
import { StatusToast } from '@/components/StatusToast'
import type { Character } from '@/lib/types'

// ── Schema ──
const characterSchema = z.object({
  name: z.string().min(1, '必填'),
  isMain: z.boolean(),
  role_tags: z.array(z.string()),
  personality_tags: z.array(z.string()),
  appearance: z.string(),
  relationship: z.array(z.string()),
  goal: z.string(),
  secret: z.string(),
  background: z.string(),
  special_ability: z.string(),
})

const formSchema = z.object({
  title: z.string().min(1, '请输入标题').max(20, '最多20字'),
  world: z.string().max(300, '最多300字'),
  genre: z.array(z.string()),
  scene: z.string().min(1, '请输入开局地点'),
  main_goal: z.string(),
  characters: z.array(characterSchema).min(1, '至少需要一个角色'),
  rel_stages: z.array(z.string()).min(2, '至少2个阶段'),
  rel_affection: z.number().min(0).max(100),
})

type FormValues = z.infer<typeof formSchema>

// ── Constants ──
const GENRE_PRESETS = [
  '校园', '恋爱', '后宫', '日常', '轻小说', '科幻', '奇幻',
  '修仙', '末日', '悬疑', '推理', '克苏鲁', '冒险', '战争',
  '搞笑', '黑暗', '治愈', '百合', '女性向', '赛博朋克', '热血', '权谋',
]

const PERSONALITY_PRESETS = [
  '冷静', '热情', '理性', '冲动', '内敛', '外向', '乐观', '悲观',
  '勇敢', '谨慎', '狡猾', '正直', '温柔', '冷酷', '幽默', '严肃',
  '忠诚', '叛逆', '善良', '自私', '敏感', '迟钝', '固执', '灵活',
  '孤僻', '开朗', '腹黑', '天然呆', '傲娇', '病娇', '毒舌', '冒失', '高冷', '护短',
]

const RELATION_PRESETS = [
  '同伴', '朋友', '恋人', '暗恋对象', '青梅竹马', '上级', '下属',
  '导师', '学生', '对手', '仇人', '陌生人', '盟友', '房东', '师尊',
  '同班同学', '工作伙伴', '上司', '救命恩人',
]

const ROLE_PRESETS = [
  '战士', '法师', '剑士', '船长', '科学家', '学生', '教师', '侦探',
  '记者', '商人', '贵族', '平民', '黑客', '特工', '流浪者', '隐士',
  '炼丹师', '掌门', '外门弟子', '转学生', '学生会长',
]

const DEFAULT_STAGES = ['陌生', '熟悉', '朋友', '信赖', '暧昧', '恋人']

// ── Main Page ──
export default function NewStory() {
  const [aiStatus, setAiStatus] = useState('')
  const [aiStatusType, setAiStatusType] = useState<'info' | 'success' | 'error' | 'loading'>('info')
  const [generating, setGenerating] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({})
  const kwRef = useRef<HTMLTextAreaElement>(null)

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: '',
      world: '',
      genre: [],
      scene: '',
      main_goal: '',
      characters: [
        {
          name: '', isMain: true, role_tags: [], personality_tags: [],
          appearance: '', relationship: [], goal: '', secret: '',
          background: '', special_ability: '',
        },
        {
          name: '', isMain: false, role_tags: [], personality_tags: [],
          appearance: '', relationship: [], goal: '', secret: '',
          background: '', special_ability: '',
        },
      ],
      rel_stages: DEFAULT_STAGES,
      rel_affection: 0,
    },
  })

  const { register, control, watch, setValue, getValues, formState: { errors } } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'characters' })
  const watchAll = watch()

  // Auto-save
  const { restoredData } = useAutoSave('new-story-form', watchAll)
  useEffect(() => {
    if (restoredData) {
      Object.entries(restoredData).forEach(([key, val]) => {
        setValue(key as keyof FormValues, val as never)
      })
    }
  }, [restoredData, setValue])

  const showStatus = (msg: string, type: 'info' | 'success' | 'error' | 'loading') => {
    setAiStatus(msg)
    setAiStatusType(type)
  }

  // ── AI Generation handlers ──
  const handleWorldGen = useCallback(async () => {
    setGenerating('world')
    showStatus('正在生成世界观、角色和规则…', 'loading')
    logger.info('NewStory', 'handleWorldGen: starting')
    try {
      const kw = kwRef.current?.value?.trim() || '奇幻冒险'
      const data = await generateWorld(kw)
      if (data.title) setValue('title', data.title)
      if (data.world) setValue('world', data.world)
      if (data.genre) setValue('genre', Array.isArray(data.genre) ? data.genre : [])
      if (data.scene) setValue('scene', data.scene)
      if (data.main_goal) setValue('main_goal', data.main_goal)
      if (data.characters) {
        const chars = data.characters.map((c, i) => ({
          name: c.name || '',
          isMain: c.isMain ?? i === 0,
          role_tags: Array.isArray(c.role_tags) ? c.role_tags : (c.role_tags ? [c.role_tags] : []),
          personality_tags: Array.isArray(c.personality_tags) ? c.personality_tags : [],
          appearance: c.appearance || '',
          relationship: Array.isArray(c.relationship) ? c.relationship : [],
          goal: c.goal || '',
          secret: c.secret || '',
          background: c.background || '',
          special_ability: c.special_ability || '',
        }))
        setValue('characters', chars)
      }
      if (data.rel_stages) setValue('rel_stages', data.rel_stages)
      if (data.rel_affection != null) setValue('rel_affection', data.rel_affection)
      showStatus('✅ 生成完成，可继续修改', 'success')
      setFieldErrors((prev) => ({ ...prev, world: null }))
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('NewStory', 'handleWorldGen: failed', { error: msg })
      showStatus(`❌ ${msg}`, 'error')
      setFieldErrors((prev) => ({ ...prev, world: msg }))
    }
    setGenerating(null)
  }, [setValue])

  const handleFieldGen = useCallback(async (field: string) => {
    setGenerating(field)
    logger.info('NewStory', `handleFieldGen: ${field}`)
    const fieldLabels: Record<string, string> = { title: '标题', main_goal: '主线目标', scene: '场景', world: '世界观' }
    showStatus(`正在生成${fieldLabels[field] || field}…`, 'loading')
    setFieldErrors((prev) => ({ ...prev, [field]: null }))
    try {
      const data = await generateField({
        field,
        title: getValues('title'),
        world: getValues('world'),
        genre: getValues('genre').join('/'),
      })
      const story = data.story || data.title || ''
      if (field === 'title') setValue('title', story.replace(/["']/g, '').trim().slice(0, 20))
      if (field === 'world') setValue('world', story.trim())
      if (field === 'main_goal') setValue('main_goal', (data.main_goal || story).trim())
      if (field === 'scene') setValue('scene', story.trim())
      showStatus('✅ 生成完成', 'success')
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('NewStory', `handleFieldGen: ${field} failed`, { error: msg })
      showStatus(`❌ ${msg}`, 'error')
      setFieldErrors((prev) => ({ ...prev, [field]: msg }))
    }
    setGenerating(null)
  }, [getValues, setValue])

  const handleCharGen = useCallback(async (idx: number) => {
    setGenerating(`char-${idx}`)
    logger.info('NewStory', `handleCharGen: char-${idx}`)
    showStatus('正在生成角色…', 'loading')
    setFieldErrors((prev) => ({ ...prev, [`char-${idx}`]: null }))
    try {
      const data = await generateField({
        field: 'character',
        title: getValues('title'),
        world: getValues('world'),
        char_role: '',
      })
      const chars = getValues('characters')
      if (data.name) chars[idx].name = data.name
      if (data.role_tags) chars[idx].role_tags = Array.isArray(data.role_tags) ? data.role_tags : [data.role_tags]
      if (data.personality_tags) chars[idx].personality_tags = Array.isArray(data.personality_tags) ? data.personality_tags : [data.personality_tags]
      if (data.appearance) chars[idx].appearance = data.appearance
      if (data.relationship) chars[idx].relationship = Array.isArray(data.relationship) ? data.relationship : [data.relationship]
      if (data.goal) chars[idx].goal = data.goal
      if (data.secret) chars[idx].secret = data.secret
      setValue('characters', chars)
      showStatus('✅ 角色生成完成', 'success')
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('NewStory', `handleCharGen: char-${idx} failed`, { error: msg })
      showStatus(`❌ ${msg}`, 'error')
      setFieldErrors((prev) => ({ ...prev, [`char-${idx}`]: msg }))
    }
    setGenerating(null)
  }, [getValues, setValue])

  const handleRulesGen = useCallback(async () => {
    setGenerating('rules')
    logger.info('NewStory', 'handleRulesGen: starting')
    showStatus('正在生成专属规则…', 'loading')
    setFieldErrors((prev) => ({ ...prev, rules: null }))
    try {
      const chars = getValues('characters')
      const data = await generateRules({
        title: getValues('title'),
        world: getValues('world'),
        genre: getValues('genre').join('/'),
        char1_name: chars[0]?.name || '主角',
        char1_role: chars[0]?.role_tags?.[0] || '',
        char2_name: chars[1]?.name || '',
        char2_role: chars[1]?.role_tags?.[0] || '',
      })
      if (data.stages?.length) setValue('rel_stages', data.stages)
      showStatus('✅ 专属规则生成完成', 'success')
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('NewStory', 'handleRulesGen: failed', { error: msg })
      showStatus(`❌ ${msg}`, 'error')
      setFieldErrors((prev) => ({ ...prev, rules: msg }))
    }
    setGenerating(null)
  }, [getValues, setValue])

  const onSubmit = useCallback(async (data: FormValues) => {
    const fd = new FormData()
    fd.append('title', data.title)
    fd.append('world', data.world)
    fd.append('genre', data.genre.join(' / '))
    fd.append('scene', data.scene)
    fd.append('main_goal', data.main_goal)
    fd.append('chars_json', JSON.stringify(data.characters))
    fd.append('rel_system', JSON.stringify({ stages: data.rel_stages, affection: data.rel_affection }))
    showStatus('正在创建故事…', 'loading')
    try {
      await createStory(fd)
      window.location.href = '/'
    } catch (e) {
      showStatus(`❌ ${(e as Error).message}`, 'error')
    }
  }, [])

  const genre = watch('genre')
  const relStages = watch('rel_stages')
  const titleLen = (watch('title') || '').length
  const worldLen = (watch('world') || '').length

  return (
    <div className="max-w-6xl mx-auto">
      {/* AI Status Toast */}
      <StatusToast message={aiStatus} type={aiStatusType} />

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* ═══════════ Sidebar ═══════════ */}
          <div className="lg:col-span-1 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">🤖 一键生成</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  ref={kwRef}
                  id="kw-input"
                  placeholder="粘贴小说简介 / 世界观描述 / 关键词均可&#10;&#10;示例①：修仙 宗门 重生&#10;示例②：被退婚的废柴少年捡到神秘戒指…"
                  className="h-28 resize-y text-xs"
                />
                <Button
                  type="button"
                  variant="success"
                  className="w-full"
                  disabled={generating === 'world'}
                  onClick={handleWorldGen}
                >
                  {generating === 'world' ? (
                    <>
                      <span className="inline-block w-3 h-3 border-2 border-game-success/30 border-t-game-success rounded-full animate-spin" />
                      生成中…
                    </>
                  ) : fieldErrors.world ? (
                    '🔄 重试一键生成'
                  ) : (
                    '✨ 一键生成完整设定'
                  )}
                </Button>
                {fieldErrors.world && (
                  <p className="text-[11px] text-game-danger">{fieldErrors.world}</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">📦 预设模板</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                {['🚀 星痕纪元', '🌸 樱之诗', '⚔️ 剑与星辉', '🔍 第七日'].map((p) => (
                  <Button
                    key={p}
                    type="button"
                    variant="ghost"
                    className="w-full justify-start text-xs h-8"
                  >
                    {p}
                  </Button>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* ═══════════ Main Form ═══════════ */}
          <div className="lg:col-span-3 space-y-4">
            {/* Part 1: Story Basics */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">1</span>
                  故事基础信息
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Title */}
                <div className="space-y-1.5">
                  <Label className="flex justify-between">
                    <span>📖 故事标题</span>
                    <span className="text-game-dim font-normal">{titleLen}/20</span>
                  </Label>
                  <div className="flex gap-2">
                    <Input {...register('title')} placeholder="给你的故事起个名字…" className="flex-1" />
                    <AIButton
                      loading={generating === 'title'}
                      error={fieldErrors.title}
                      onClick={() => handleFieldGen('title')}
                    >生成</AIButton>
                  </div>
                  {errors.title && <p className="text-[11px] text-game-danger">{errors.title.message}</p>}
                </div>

                {/* Genre */}
                <div className="space-y-1.5">
                  <Label>🎭 类型 / 风格</Label>
                  <TagInput
                    value={genre}
                    onChange={(tags) => setValue('genre', tags)}
                    presets={GENRE_PRESETS}
                    placeholder="输入自定义风格，回车添加…"
                    color="primary"
                  />
                </div>

                {/* Scene */}
                <div className="space-y-1.5">
                  <Label>📍 开局地点</Label>
                  <div className="flex gap-2">
                    <Input {...register('scene')} placeholder="如：高二三班教室、回声号舰桥" className="flex-1" />
                    <AIButton
                      loading={generating === 'scene'}
                      error={fieldErrors.scene}
                      onClick={() => handleFieldGen('scene')}
                    >生成</AIButton>
                  </div>
                  {errors.scene && <p className="text-[11px] text-game-danger">{errors.scene.message}</p>}
                </div>

                {/* Main Goal */}
                <div className="space-y-1.5">
                  <Label>🎯 故事主线目标</Label>
                  <div className="flex gap-2">
                    <Input {...register('main_goal')} placeholder="如：调查失踪舰队、找到失踪的妹妹…" className="flex-1" />
                    <AIButton
                      loading={generating === 'main_goal'}
                      error={fieldErrors.main_goal}
                      onClick={() => handleFieldGen('main_goal')}
                    >生成</AIButton>
                  </div>
                </div>

                {/* World (optional) */}
                <div className="border border-dashed border-game-border rounded-lg p-4 opacity-80 hover:opacity-100 transition-opacity space-y-1.5">
                  <Label className="flex justify-between">
                    <span>🌍 世界观背景 <span className="text-game-dim">· 可选</span></span>
                    <span className="text-game-dim font-normal">{worldLen}/300</span>
                  </Label>
                  <div className="flex gap-2">
                    <Textarea
                      {...register('world')}
                      rows={3}
                      placeholder="校园恋爱/都市日常可跳过不填…"
                      className="flex-1 resize-y"
                    />
                    <AIButton
                      loading={generating === 'world'}
                      error={fieldErrors.world}
                      onClick={() => handleFieldGen('world')}
                    >生成</AIButton>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Part 2: Relationship System */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">2</span>
                  ❤️ 关系系统
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Who's involved */}
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-bold text-game-accent">
                    {watch('characters.0.name') || '主角'}
                  </span>
                  <span className="text-game-accent text-lg">💞</span>
                  <span className="font-bold text-game-primary">
                    {watch('characters.1.name') || 'NPC'}
                  </span>
                </div>
                <p className="text-xs text-game-muted">
                  设置主角与核心 NPC 之间的关系阶段递进路径。AI 会根据此路径推进角色关系发展。
                </p>

                {/* Stage chain with descriptions */}
                <div className="space-y-2">
                  <Label className="text-xs text-game-muted">关系阶段递进</Label>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {relStages.map((s, i) => (
                      <span key={i} className="flex items-center gap-1">
                        <Badge variant="primary" size="sm">{s}</Badge>
                        {i < relStages.length - 1 && (
                          <span className="text-game-dim text-[10px]">→</span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Affection slider with visual bar */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-game-muted">初始好感度</Label>
                    <Badge variant="accent" size="sm">
                      {watch('rel_affection')}/100
                    </Badge>
                  </div>
                  {/* Visual bar */}
                  <div className="h-3 bg-game-border rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-game-primary via-game-accent to-game-success rounded-full transition-all duration-300"
                      style={{ width: `${watch('rel_affection')}%` }}
                    />
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    {...register('rel_affection', { valueAsNumber: true })}
                    className="w-full accent-game-accent h-1.5"
                  />
                  <div className="flex justify-between text-[10px] text-game-dim">
                    <span>陌生人</span>
                    <span>初识</span>
                    <span>朋友</span>
                    <span>亲密</span>
                    <span>灵魂伴侣</span>
                  </div>
                </div>

                {/* Stage-affinity mapping hint */}
                <div className="bg-game-surface border border-game-border rounded-md p-3 text-xs text-game-muted space-y-1">
                  <p className="text-game-accent font-medium mb-1">📋 阶段与好感度对应</p>
                  {relStages.map((s, i) => {
                    const pct = Math.round((i / Math.max(1, relStages.length - 1)) * 100)
                    return (
                      <div key={s} className="flex items-center gap-2">
                        <Badge variant="outline" size="sm" className="w-16 justify-center">{s}</Badge>
                        <div className="flex-1 h-1.5 bg-game-border rounded-full overflow-hidden">
                          <div
                            className="h-full bg-game-primary/40 rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-game-dim w-8 text-right tabular-nums">{pct}%</span>
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Part 3: Characters */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">3</span>
                  角色系统
                </CardTitle>
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => append({
                    name: '', isMain: false, role_tags: [], personality_tags: [],
                    appearance: '', relationship: [], goal: '', secret: '',
                    background: '', special_ability: '',
                  })}
                >
                  ➕ 新增 NPC
                </Button>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  <AnimatePresence>
                    {fields.map((field, idx) => {
                      const c = watch(`characters.${idx}`)
                      const isMain = c?.isMain

                      return (
                        <motion.div
                          key={field.id}
                          initial={{ opacity: 0, scale: 0.95 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.95 }}
                        >
                          <Card className={`${isMain ? 'border-game-accent/50 bg-game-accent/[0.03]' : ''}`}>
                            <CardHeader className="pb-2">
                              <div className="flex items-center justify-between">
                                <Badge variant={isMain ? 'accent' : 'success'} size="sm">
                                  {isMain ? '⭐ 主角' : '👤 NPC'}
                                </Badge>
                                {!isMain && fields.length > 1 && (
                                  <button
                                    type="button"
                                    onClick={() => remove(idx)}
                                    className="text-game-dim hover:text-game-danger transition-colors text-sm"
                                  >
                                    ✕
                                  </button>
                                )}
                              </div>
                              <Input
                                {...register(`characters.${idx}.name`)}
                                placeholder="角色姓名"
                                className="mt-2 font-bold"
                              />
                            </CardHeader>
                            <CardContent className="space-y-3">
                              {/* Role tags */}
                              <div>
                                <Label className="text-[11px]">身份 / 职业</Label>
                                <TagInput
                                  value={c?.role_tags || []}
                                  onChange={(tags) => setValue(`characters.${idx}.role_tags`, tags)}
                                  presets={ROLE_PRESETS}
                                  placeholder="输入后回车添加…"
                                  color="primary"
                                />
                              </div>

                              {/* Priority 1: Relationship (NPC only) */}
                              {!isMain && (
                                <div>
                                  <Label className="text-[11px]">💞 与主角关系</Label>
                                  <TagInput
                                    value={c?.relationship || []}
                                    onChange={(tags) => setValue(`characters.${idx}.relationship`, tags)}
                                    presets={RELATION_PRESETS}
                                    placeholder="如：同伴、青梅竹马…"
                                    color="accent"
                                  />
                                </div>
                              )}

                              {/* Priority 2: Goal */}
                              <div>
                                <Label className="text-[11px]">🎯 当前目标</Label>
                                <Input
                                  {...register(`characters.${idx}.goal`)}
                                  placeholder="角色想要达成的事…"
                                  className="text-xs h-8"
                                />
                              </div>

                              {/* Priority 3: Secret */}
                              <div>
                                <Label className="text-[11px] text-game-accent">🔒 隐藏秘密</Label>
                                <Input
                                  {...register(`characters.${idx}.secret`)}
                                  placeholder="用于制造剧情爆点…"
                                  className="text-xs h-8 border-game-secret/40 bg-game-secret/10 text-game-accent placeholder:text-game-dim"
                                />
                              </div>

                              {/* Priority 4: Personality */}
                              <div>
                                <Label className="text-[11px]">🎭 性格标签（3~5个）</Label>
                                <TagInput
                                  value={c?.personality_tags || []}
                                  onChange={(tags) => setValue(`characters.${idx}.personality_tags`, tags)}
                                  presets={PERSONALITY_PRESETS}
                                  placeholder="选择或输入性格标签…"
                                  color="accent"
                                />
                              </div>

                              {/* Priority 5: Appearance */}
                              <div>
                                <Label className="text-[11px]">👤 外貌特征</Label>
                                <Input
                                  {...register(`characters.${idx}.appearance`)}
                                  placeholder="银白长发，紫色眼瞳…"
                                  className="text-xs h-8"
                                />
                              </div>

                              <Separator />

                              <AIButton
                                loading={generating === `char-${idx}`}
                                error={fieldErrors[`char-${idx}`]}
                                onClick={() => handleCharGen(idx)}
                              >
                                {isMain ? '生成主角' : '生成此角色'}
                              </AIButton>
                            </CardContent>
                          </Card>
                        </motion.div>
                      )
                    })}
                  </AnimatePresence>
                </div>
              </CardContent>
            </Card>

            {/* Part 4: Custom Rules */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">4</span>
                  专属规则
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-game-dim">
                  📊 默认追踪：好感度（陌生→恋人，7阶段）· 无需生成即可使用
                </p>
                <AIButton
                  loading={generating === 'rules'}
                  error={fieldErrors.rules}
                  onClick={handleRulesGen}
                >
                  AI 生成专属规则
                </AIButton>
              </CardContent>
            </Card>

            {/* Submit */}
            <Button
              type="submit"
              variant="success"
              size="lg"
              className="w-full text-base"
            >
              🎬 开始新故事
            </Button>
          </div>
        </div>
      </form>
    </div>
  )
}
