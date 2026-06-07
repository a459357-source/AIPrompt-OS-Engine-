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

const DEFAULT_STAGES = ['崩坏', '敌视', '对立', '冷漠', '疏远', '陌生', '认识', '信赖', '盟友', '羁绊']

// ── Main Page ──
export default function NewStory() {
  const [aiStatus, setAiStatus] = useState('')
  const [aiStatusType, setAiStatusType] = useState<'info' | 'success' | 'error' | 'loading'>('info')
  const [generating, setGenerating] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({})
  const [characterRelations, setCharacterRelations] = useState<Record<string, {
    relationshipType: string; affection: number; trust: number; respect: number;
    dependence: number; hostility: number; attraction: number; tags: string[];
  }>>({})
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
      artifacts: [] as { name: string; type: 'personal'|'faction'|'world'; description: string; ownerType: 'character'|'faction'|'location'|'none'; ownerId: string; importance: number; abilities: string[]; tags: string[] }[],
      factions: [] as { name: string; type: string; description: string; goals: string[]; resources: string[]; controlledTerritories: string[]; subordinateOrganizations: string[]; keyAssets: string[]; power: { military: number; economic: number; political: number; technology: number }; influence: number; relation_to_player: string; leader: string }[],
      customStats: [] as { key: string; label: string; max: number }[],
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
      if (data.stats) setValue('customStats', data.stats)
      if (data.factions) {
        const facs = (data.factions as Array<Record<string,unknown>>).map((f: Record<string,unknown>) => ({
          name: (f.name as string) || '',
          type: (f.type as string) || 'organization',
          description: (f.description as string) || '',
          goals: (f.goals as string[]) || [],
          resources: (f.resources as string[]) || [],
          controlledTerritories: (f.controlledTerritories as string[]) || [],
          subordinateOrganizations: (f.subordinateOrganizations as string[]) || [],
          keyAssets: (f.keyAssets as string[]) || [],
          power: (f.power as { military: number; economic: number; political: number; technology: number }) || { military: 0, economic: 0, political: 0, technology: 0 },
          influence: (f.influence as number) || 50,
          relation_to_player: (f.relation_to_player as string) || 'neutral',
          leader: (f.leader as string) || '',
        }))
        setValue('factions', facs)
      }
      if (data.artifacts) {
        const arts = (data.artifacts as Array<Record<string,unknown>>).map((a: Record<string,unknown>) => ({
          name: (a.name as string) || '',
          type: ((a.type as string) || 'personal') as 'personal'|'faction'|'world',
          description: (a.description as string) || '',
          ownerType: ((a.ownerType as string) || 'none') as 'character'|'faction'|'location'|'none',
          ownerId: (a.ownerId as string) || '',
          importance: (a.importance as number) || 50,
          abilities: (a.abilities as string[]) || [],
          tags: (a.tags as string[]) || [],
        }))
        setValue('artifacts', arts)
      }
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

  const onSubmit = useCallback(async (data: FormValues) => {
    const fd = new FormData()
    fd.append('title', data.title)
    fd.append('world', data.world)
    fd.append('genre', data.genre.join(' / '))
    fd.append('scene', data.scene)
    fd.append('main_goal', data.main_goal)
    fd.append('chars_json', JSON.stringify(data.characters))
    fd.append('rel_system', JSON.stringify({ stages: data.rel_stages, affection: data.rel_affection }))
    fd.append('custom_rules', JSON.stringify({ stats: data.customStats || [], stages: data.rel_stages, characterRelations: characterRelations }))
    fd.append('artifacts_json', JSON.stringify(data.artifacts || []))
    fd.append('factions_json', JSON.stringify(data.factions || []))
    showStatus('正在创建故事…', 'loading')
    try {
      await createStory(fd)
      window.location.href = '/game'
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

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6" onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName === 'INPUT' && (e.target as HTMLInputElement).type === 'number') e.preventDefault() }}>
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

            {/* Part 3: Characters — 编号顺延，Part2已合并到Part4专属规则 */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">2</span>
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

                              {/* Faction */}
                              <div>
                                <Label className="text-[11px]">🏛️ 所属势力</Label>
                                <select
                                  value={c?.faction || ''}
                                  onChange={(e) => setValue(`characters.${idx}.faction`, e.target.value)}
                                  className="w-full bg-game-bg border border-game-border rounded-md px-2 py-1.5 text-xs text-game-text mt-0.5"
                                >
                                  <option value="">无</option>
                                  {(getValues('factions') || []).map((f: { name: string }) => (
                                    <option key={f.name} value={f.name}>{f.name}</option>
                                  ))}
                                </select>
                              </div>

                              {/* Goal (原关系字段已合并到Part3多维关系) */}
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

            {/* Part 3: Custom Rules — 关系系统已合并到此 */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">3</span>
                  专属规则 & 多维关系
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Who's involved — 每个NPC与主角的独立多维关系 */}
                {(() => {
                  const allChars = watch('characters') || []
                  const mainChar = allChars.find((c: { isMain?: boolean }) => c.isMain) || allChars[0]
                  const npcs = allChars.filter((c: { isMain?: boolean }) => !c.isMain && c.name)
                  const DIMS = [
                    ['❤️好感', 'affection'], ['🤝信任', 'trust'], ['🙏尊重', 'respect'],
                    ['🔗依赖', 'dependence'], ['⚔️敌意', 'hostility'], ['💫吸引', 'attraction'],
                  ]
                  const REL_TYPES = ['friend','lover','family','teacher','rival','ally','enemy']
                  const REL_LABELS: Record<string,string> = {friend:'朋友',lover:'恋人',family:'家人',teacher:'师徒',rival:'对手',ally:'盟友',enemy:'敌人'}

                  if (npcs.length === 0) return <p className="text-xs text-game-dim">添加 NPC 后自动显示关系对</p>

                  return (
                    <div className="space-y-3">
                      {npcs.map((c: { name: string }) => {
                        const r = characterRelations[c.name] || { relationshipType:'friend', affection:50, trust:50, respect:50, dependence:50, hostility:30, attraction:50, tags:[] as string[] }
                        const updateRel = (k: string, v: unknown) => {
                          setCharacterRelations(prev => ({
                            ...prev,
                            [c.name]: { ...(prev[c.name] || r), [k]: v }
                          }))
                        }
                        return (
                          <div key={c.name} className="bg-game-surface border border-game-border rounded-md p-3 space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2 text-sm">
                                <span className="font-bold text-game-accent">{mainChar?.name || '主角'}</span>
                                <span className="text-game-accent">↔</span>
                                <span className="font-bold text-game-primary">{c.name}</span>
                              </div>
                              <select
                                value={r.relationshipType}
                                onChange={(e) => updateRel('relationshipType', e.target.value)}
                                className="bg-game-bg border border-game-border rounded-md px-2 py-0.5 text-[10px] text-game-text"
                              >
                                {REL_TYPES.map(t => <option key={t} value={t}>{REL_LABELS[t]}</option>)}
                              </select>
                            </div>
                            <div className="grid grid-cols-3 gap-x-3 gap-y-1">
                              {DIMS.map(([label, key]) => {
                                const val = (r as Record<string,number>)[key] ?? 50
                                const barColor = key === 'hostility' ? '#da3633' : '#58a6ff'
                                return (
                                  <div key={key} className="flex items-center gap-1">
                                    <span className="text-[10px] text-game-dim w-12 shrink-0">{label}</span>
                                    <input
                                      type="number"
                                      min={0} max={100} value={val}
                                      onChange={(e) => { const v = parseInt(e.target.value); if (!isNaN(v)) updateRel(key, Math.max(0, Math.min(100, v))) }}
                                      onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
                                      className="w-12 text-center text-[11px] h-6 bg-game-bg border border-game-border rounded text-game-text"
                                      style={{minWidth: '36px'}}
                                    />
                                    <div className="flex-1 h-2 bg-game-border rounded-full overflow-hidden">
                                      <div className="h-full rounded-full transition-all" style={{width: `${val}%`, background: barColor}} />
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="text-[10px] text-game-dim shrink-0">标签</span>
                              <input
                                type="text"
                                defaultValue={(r.tags || []).join('、')}
                                onBlur={(e) => updateRel('tags', e.target.value.split(/[、,，]/).map(s => s.trim()).filter(Boolean))}
                                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); (e.target as HTMLInputElement).blur() } }}
                                placeholder="青梅竹马、救命恩人…"
                                className="flex-1 text-[11px] h-6 bg-game-bg border border-game-border rounded px-2 text-game-text"
                              />
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )
                })()}

                {/* Current custom stats */}
                {(() => {
                  const stats = getValues('customStats') || []
                  return stats.length > 0 ? (
                    <div>
                      <span className="text-[10px] text-game-muted">📊 追踪维度</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {stats.map((s: { key: string; label: string; max: number }) => (
                          <Badge key={s.key} variant="accent" size="sm">{s.label} (0-{s.max})</Badge>
                        ))}
                      </div>
                    </div>
                  ) : null
                })()}

                <AIButton
                  loading={generating === 'rules'}
                  error={fieldErrors.rules}
                  onClick={async () => {
                    setGenerating('rules')
                    showStatus('正在根据当前内容推理专属规则…', 'loading')
                    try {
                      const allChars = getValues('characters') || []
                      const data = await generateRules({
                        title: getValues('title'),
                        world: getValues('world') + '\n势力：' + JSON.stringify(getValues('factions') || []) + '\n物品：' + JSON.stringify(getValues('artifacts') || []),
                        genre: getValues('genre').join('/'),
                        char1_name: allChars[0]?.name || '主角',
                        char1_role: allChars[0]?.role_tags?.[0] || '',
                        char2_name: allChars[1]?.name || '',
                        char2_role: allChars[1]?.role_tags?.[0] || '',
                      })
                      if (data.stages?.length) setValue('rel_stages', data.stages)
                      if (data.stats?.length) setValue('customStats', data.stats)
                      showStatus('✅ 专属规则生成完成', 'success')
                    } catch (e) {
                      const msg = (e as Error).message || String(e)
                      showStatus(`❌ ${msg}`, 'error')
                    }
                    setGenerating(null)
                  }}
                >
                  ✨ 根据当前内容推理专属规则
                </AIButton>
              </CardContent>
            </Card>

            {/* Part 5: Artifacts */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-accent/20 text-game-accent text-xs flex items-center justify-center">4</span>
                  🗝️ 关键物品
                </CardTitle>
                <div className="flex gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    disabled={generating === 'artifacts-all'}
                    onClick={async () => {
                      setGenerating('artifacts-all')
                      showStatus('正在批量生成关键物品…', 'loading')
                      const current = getValues('artifacts') || []
                      const newArts: typeof current = []
                      for (let i = 0; i < 3; i++) {
                        try {
                          const data = await generateField({
                            field: 'artifact',
                            title: getValues('title'),
                            world: getValues('world'),
                            genre: getValues('genre').join('/'),
                          })
                          if ((data as { name?: string }).name) {
                            newArts.push({
                              name: (data as { name: string }).name,
                              type: ((data as { type?: string }).type || 'personal') as 'personal' | 'faction' | 'world',
                              description: (data as { description?: string }).description || '',
                              ownerType: ((data as { ownerType?: string }).ownerType || 'none') as 'character' | 'faction' | 'location' | 'none',
                              ownerId: (data as { ownerId?: string }).ownerId || '',
                              importance: (data as { importance?: number }).importance || 50,
                              abilities: (data as { abilities?: string[] }).abilities || [],
                              tags: (data as { tags?: string[] }).tags || [],
                            })
                          }
                        } catch { /* continue */ }
                      }
                      setValue('artifacts', [...current, ...newArts])
                      showStatus(`✅ 已生成 ${newArts.length} 个关键物品`, 'success')
                      setGenerating(null)
                    }}
                  >
                    {generating === 'artifacts-all' ? '⏳' : '✨'} 模块生成(×3)
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    onClick={() => {
                      const current = getValues('artifacts') || []
                      setValue('artifacts', [...current, {
                        name: '', type: 'personal' as const, description: '',
                        ownerType: 'none' as const, ownerId: '',
                        importance: 50, abilities: [], tags: [],
                      }])
                    }}
                  >
                    ➕ 添加物品
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                  {(getValues('artifacts') || []).map((art, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                    >
                      <Card className="border-game-accent/30">
                        <CardHeader className="pb-1">
                          <div className="flex items-center justify-between">
                            <Badge variant="accent" size="sm">
                              {art.type === 'world' ? '🌍 世界级' : art.type === 'faction' ? '🏛️ 势力资产' : '👤 个人物品'}
                            </Badge>
                            <div className="flex gap-1">
                              <AIButton
                                loading={generating === `artifact-${idx}`}
                                onClick={async () => {
                                  setGenerating(`artifact-${idx}`)
                                  try {
                                    const data = await generateField({
                                      field: 'artifact',
                                      title: getValues('title'),
                                      world: getValues('world'),
                                      genre: getValues('genre').join('/'),
                                    })
                                    if ((data as { name?: string }).name) {
                                      const current = getValues('artifacts') || []
                                      current[idx] = {
                                        name: (data as { name: string }).name,
                                        type: ((data as { type?: string }).type || 'personal') as 'personal' | 'faction' | 'world',
                                        description: (data as { description?: string }).description || '',
                                        ownerType: ((data as { ownerType?: string }).ownerType || 'none') as 'character' | 'faction' | 'location' | 'none',
                                        ownerId: (data as { ownerId?: string }).ownerId || '',
                                        importance: (data as { importance?: number }).importance || 50,
                                        abilities: (data as { abilities?: string[] }).abilities || [],
                                        tags: (data as { tags?: string[] }).tags || [],
                                      }
                                      setValue('artifacts', [...current])
                                    }
                                    showStatus('✅ 物品生成完成', 'success')
                                  } catch (e) { showStatus(`❌ ${(e as Error).message}`, 'error') }
                                  setGenerating(null)
                                }}
                              >生成</AIButton>
                              <button
                                type="button"
                                onClick={() => {
                                  const current = getValues('artifacts') || []
                                  current.splice(idx, 1)
                                  setValue('artifacts', [...current])
                                }}
                                className="text-game-dim hover:text-game-danger transition-colors text-sm"
                              >✕</button>
                            </div>
                          </div>
                          <Input
                            value={art.name}
                            onChange={(e) => {
                              const current = getValues('artifacts') || []
                              current[idx] = { ...current[idx], name: e.target.value }
                              setValue('artifacts', [...current])
                            }}
                            placeholder="物品名称"
                            className="mt-1 font-bold text-sm h-8"
                          />
                        </CardHeader>
                        <CardContent className="space-y-2 pt-0">
                          <div className="flex gap-2">
                            <select
                              value={art.type}
                              onChange={(e) => {
                                const current = getValues('artifacts') || []
                                current[idx] = { ...current[idx], type: e.target.value as 'personal' | 'faction' | 'world' }
                                setValue('artifacts', [...current])
                              }}
                              className="bg-game-bg border border-game-border rounded-md px-2 py-1 text-xs text-game-text"
                            >
                              <option value="personal">个人物品</option>
                              <option value="faction">势力资产</option>
                              <option value="world">世界级</option>
                            </select>
                            <Input
                              value={art.ownerId}
                              onChange={(e) => {
                                const current = getValues('artifacts') || []
                                current[idx] = { ...current[idx], ownerId: e.target.value }
                                setValue('artifacts', [...current])
                              }}
                              placeholder="持有者（角色名/势力名）"
                              className="flex-1 text-xs h-7"
                            />
                            <Input
                              type="number"
                              value={art.importance}
                              onChange={(e) => {
                                const current = getValues('artifacts') || []
                                current[idx] = { ...current[idx], importance: Math.max(1, Math.min(100, parseInt(e.target.value) || 50)) }
                                setValue('artifacts', [...current])
                              }}
                              className="w-16 text-xs h-7"
                              placeholder="重要度"
                            />
                          </div>
                          <Input
                            value={art.description}
                            onChange={(e) => {
                              const current = getValues('artifacts') || []
                              current[idx] = { ...current[idx], description: e.target.value }
                              setValue('artifacts', [...current])
                            }}
                            placeholder="物品描述（用途、背景…）"
                            className="text-xs h-7"
                          />
                          <div className="flex gap-1 flex-wrap">
                            <TagInput
                              value={art.tags || []}
                              onChange={(tags) => {
                                const current = getValues('artifacts') || []
                                current[idx] = { ...current[idx], tags }
                                setValue('artifacts', [...current])
                              }}
                              presets={['国宝','机密','武器','货币','信物','钥匙','证据','传家宝']}
                              placeholder="标签…"
                              color="accent"
                            />
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                  {(getValues('artifacts') || []).length === 0 && (
                    <p className="text-game-dim text-xs text-center py-4 col-span-2">
                      暂无关键物品 · 点击「✨ 模块生成」AI 批量生成，或「➕ 添加物品」手动填写
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Part 6: Factions */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-warning/20 text-game-warning text-xs flex items-center justify-center">5</span>
                  🏛️ 势力
                </CardTitle>
                <div className="flex gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    disabled={generating === 'factions-all'}
                    onClick={async () => {
                      setGenerating('factions-all')
                      showStatus('正在批量生成势力…', 'loading')
                      const current = getValues('factions') || []
                      const newFacs: typeof current = []
                      for (let i = 0; i < 3; i++) {
                        try {
                          const data = await generateField({
                            field: 'faction',
                            title: getValues('title'),
                            world: getValues('world'),
                            genre: getValues('genre').join('/'),
                          })
                          if ((data as { name?: string }).name) {
                            newFacs.push({
                              name: (data as { name: string }).name,
                              type: ((data as { type?: string }).type || 'organization') as string,
                              description: (data as { description?: string }).description || '',
                              goals: (data as { goals?: string[] }).goals || [],
                              resources: (data as { resources?: string[] }).resources || [],
                              controlledTerritories: (data as { controlledTerritories?: string[] }).controlledTerritories || [],
                              subordinateOrganizations: (data as { subordinateOrganizations?: string[] }).subordinateOrganizations || [],
                              keyAssets: (data as { keyAssets?: string[] }).keyAssets || [],
                              power: (data as { power?: { military: number; economic: number; political: number; technology: number } }).power || { military: 0, economic: 0, political: 0, technology: 0 },
                              influence: (data as { influence?: number }).influence || 50,
                              relation_to_player: ((data as { relation_to_player?: string }).relation_to_player || 'neutral') as string,
                              leader: (data as { leader?: string }).leader || '',
                            })
                          }
                        } catch { /* continue */ }
                      }
                      setValue('factions', [...current, ...newFacs])
                      showStatus(`✅ 已生成 ${newFacs.length} 个势力`, 'success')
                      setGenerating(null)
                    }}
                  >
                    {generating === 'factions-all' ? '⏳' : '✨'} 模块生成(×3)
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    onClick={() => {
                      const current = getValues('factions') || []
                      setValue('factions', [...current, {
                        name: '', type: 'organization', description: '',
                        goals: [], resources: [], controlledTerritories: [],
                        subordinateOrganizations: [], keyAssets: [],
                        power: { military: 0, economic: 0, political: 0, technology: 0 },
                        influence: 50, relation_to_player: 'neutral', leader: '',
                      }])
                    }}
                  >
                    ➕ 添加势力
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                  {(getValues('factions') || []).map((fac, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                    >
                      <Card className="border-game-warning/30">
                        <CardHeader className="pb-1">
                          <div className="flex items-center justify-between">
                            <Badge variant="warning" size="sm">
                              {fac.type === 'government' ? '🏛️ 政府' : fac.type === 'corporation' ? '💼 企业' : fac.type === 'family' ? '👪 家族' : fac.type === 'religion' ? '⛪ 宗教' : '🏢 组织'}
                            </Badge>
                            <div className="flex gap-1">
                              <AIButton
                                loading={generating === `faction-${idx}`}
                                onClick={async () => {
                                  setGenerating(`faction-${idx}`)
                                  try {
                                    const data = await generateField({
                                      field: 'faction',
                                      title: getValues('title'),
                                      world: getValues('world'),
                                      genre: getValues('genre').join('/'),
                                    })
                                    if ((data as { name?: string }).name) {
                                      const current = getValues('factions') || []
                                      current[idx] = {
                                        name: (data as { name: string }).name,
                                        type: ((data as { type?: string }).type || 'organization') as string,
                                        description: (data as { description?: string }).description || '',
                                        goals: (data as { goals?: string[] }).goals || [],
                                        resources: (data as { resources?: string[] }).resources || [],
                                        controlledTerritories: (data as { controlledTerritories?: string[] }).controlledTerritories || [],
                                        subordinateOrganizations: (data as { subordinateOrganizations?: string[] }).subordinateOrganizations || [],
                                        keyAssets: (data as { keyAssets?: string[] }).keyAssets || [],
                                        power: (data as { power?: { military: number; economic: number; political: number; technology: number } }).power || { military: 0, economic: 0, political: 0, technology: 0 },
                                        influence: (data as { influence?: number }).influence || 50,
                                        relation_to_player: ((data as { relation_to_player?: string }).relation_to_player || 'neutral') as string,
                                        leader: (data as { leader?: string }).leader || '',
                                      }
                                      setValue('factions', [...current])
                                    }
                                    showStatus('✅ 势力生成完成', 'success')
                                  } catch (e) { showStatus(`❌ ${(e as Error).message}`, 'error') }
                                  setGenerating(null)
                                }}
                              >生成</AIButton>
                              <button
                                type="button"
                                onClick={() => {
                                  const current = getValues('factions') || []
                                  current.splice(idx, 1)
                                  setValue('factions', [...current])
                                }}
                                className="text-game-dim hover:text-game-danger transition-colors text-sm"
                              >✕</button>
                            </div>
                          </div>
                          <Input
                            value={fac.name}
                            onChange={(e) => {
                              const current = getValues('factions') || []
                              current[idx] = { ...current[idx], name: e.target.value }
                              setValue('factions', [...current])
                            }}
                            placeholder="势力名称"
                            className="mt-1 font-bold text-sm h-8"
                          />
                        </CardHeader>
                        <CardContent className="space-y-2 pt-0">
                          <div className="flex gap-2">
                            <select
                              value={fac.type}
                              onChange={(e) => {
                                const current = getValues('factions') || []
                                current[idx] = { ...current[idx], type: e.target.value }
                                setValue('factions', [...current])
                              }}
                              className="bg-game-bg border border-game-border rounded-md px-2 py-1 text-xs text-game-text"
                            >
                              <option value="government">政府</option>
                              <option value="corporation">企业</option>
                              <option value="family">家族</option>
                              <option value="organization">组织</option>
                              <option value="guild">行会</option>
                              <option value="school">学院</option>
                              <option value="religion">宗教</option>
                              <option value="kingdom">王国</option>
                              <option value="other">其他</option>
                            </select>
                            <select
                              value={fac.relation_to_player}
                              onChange={(e) => {
                                const current = getValues('factions') || []
                                current[idx] = { ...current[idx], relation_to_player: e.target.value }
                                setValue('factions', [...current])
                              }}
                              className="bg-game-bg border border-game-border rounded-md px-2 py-1 text-xs text-game-text"
                            >
                              <option value="ally">盟友</option>
                              <option value="friendly">友好</option>
                              <option value="neutral">中立</option>
                              <option value="hostile">敌对</option>
                              <option value="enemy">死敌</option>
                            </select>
                            <Input
                              value={fac.leader}
                              onChange={(e) => {
                                const current = getValues('factions') || []
                                current[idx] = { ...current[idx], leader: e.target.value }
                                setValue('factions', [...current])
                              }}
                              placeholder="首领"
                              className="flex-1 text-xs h-7"
                            />
                            <Input
                              type="number"
                              value={fac.influence}
                              onChange={(e) => {
                                const current = getValues('factions') || []
                                current[idx] = { ...current[idx], influence: Math.max(1, Math.min(100, parseInt(e.target.value) || 50)) }
                                setValue('factions', [...current])
                              }}
                              className="w-16 text-xs h-7"
                              placeholder="影响力"
                            />
                          </div>
                          <Input
                            value={fac.description}
                            onChange={(e) => {
                              const current = getValues('factions') || []
                              current[idx] = { ...current[idx], description: e.target.value }
                              setValue('factions', [...current])
                            }}
                            placeholder="势力描述…"
                            className="text-xs h-7"
                          />
                          <div className="grid grid-cols-4 gap-1 text-[10px]">
                            {(['military','economic','political','technology'] as const).map((k) => (
                              <div key={k} className="flex items-center gap-1">
                                <span className="text-game-dim w-8">{{military:'军事',economic:'经济',political:'政治',technology:'科技'}[k]}</span>
                                <Input
                                  type="number"
                                  value={fac.power?.[k] ?? 0}
                                  onChange={(e) => {
                                    const current = getValues('factions') || []
                                    current[idx] = { ...current[idx], power: { ...(current[idx].power || { military:0,economic:0,political:0,technology:0 }), [k]: Math.max(0, Math.min(100, parseInt(e.target.value) || 0)) } }
                                    setValue('factions', [...current])
                                  }}
                                  className="flex-1 text-[10px] h-6 text-center"
                                />
                              </div>
                            ))}
                          </div>
                          <TagInput
                            value={fac.goals || []}
                            onChange={(goals) => {
                              const current = getValues('factions') || []
                              current[idx] = { ...current[idx], goals }
                              setValue('factions', [...current])
                            }}
                            presets={[]}
                            placeholder="目标…"
                            color="warning"
                          />
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                  {(getValues('factions') || []).length === 0 && (
                    <p className="text-game-dim text-xs text-center py-4 col-span-2">
                      暂无势力 · 点击「✨ 模块生成」AI 批量生成，或「➕ 添加势力」手动填写
                    </p>
                  )}
                </div>
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
