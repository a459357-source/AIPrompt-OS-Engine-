import { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { generateWorld, generateField, generateRules, createStory } from '@/lib/api'
import { useAutoSave } from '@/hooks/useAutoSave'
import type { Character, RelationshipSystem } from '@/lib/types'

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

// ── Tag Input Component ──
function TagInput({
  value,
  onChange,
  presets,
  placeholder,
  color = 'primary',
}: {
  value: string[]
  onChange: (tags: string[]) => void
  presets: string[]
  placeholder: string
  color?: 'primary' | 'accent' | 'secret'
}) {
  const [input, setInput] = useState('')

  const add = (tag: string) => {
    const t = tag.trim()
    if (t && !value.includes(t)) onChange([...value, t])
    setInput('')
  }

  const remove = (idx: number) => {
    onChange(value.filter((_, i) => i !== idx))
  }

  const colorMap = {
    primary: 'bg-game-primary/15 border-game-primary/30 text-game-primary',
    accent: 'bg-game-accent/15 border-game-accent/30 text-game-accent',
    secret: 'bg-game-secret/30 border-game-secret/50 text-game-accent',
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5 min-h-[24px]">
        <AnimatePresence>
          {value.map((tag, i) => (
            <motion.span
              key={`${tag}-${i}`}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border cursor-pointer ${colorMap[color]}`}
              onClick={() => remove(i)}
            >
              {tag} <span className="opacity-60">×</span>
            </motion.span>
          ))}
        </AnimatePresence>
      </div>
      <div className="flex gap-1.5">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(input) } }}
          placeholder={placeholder}
          className="flex-1 bg-game-bg border border-game-border rounded-md px-2.5 py-1.5 text-sm text-game-text placeholder:text-game-dim focus:outline-none focus:border-game-primary"
        />
      </div>
      <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
        {presets.filter((p) => !value.includes(p)).slice(0, 20).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => add(p)}
            className="px-1.5 py-0.5 text-[11px] bg-game-surface border border-game-border rounded text-game-muted hover:text-game-text hover:border-game-primary/50 transition-colors"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── AI Button Component ──
function AIButton({
  loading,
  error,
  onClick,
  children,
}: {
  loading: boolean
  error?: string | null
  onClick: () => void
  children: string
}) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <button
        type="button"
        disabled={loading}
        onClick={onClick}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border border-game-accent/50 rounded-md text-game-accent hover:bg-game-accent/10 disabled:opacity-40 transition-all"
      >
        {loading ? (
          <span className="inline-block w-3 h-3 border border-game-accent/30 border-t-game-accent rounded-full animate-spin" />
        ) : error ? (
          '🔄'
        ) : (
          '✨'
        )}
        {loading ? '生成中...' : error ? `重试${children}` : children}
      </button>
      {error && (
        <span className="text-[11px] text-game-danger animate-fade-in" title={error}>
          {error.length > 20 ? error.slice(0, 18) + '…' : error}
        </span>
      )}
    </div>
  )
}

// ── Main Page ──
export default function NewStory() {
  const [aiStatus, setAiStatus] = useState('')
  const [generating, setGenerating] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({})

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

  const { register, control, watch, setValue, getValues } = form
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

  // ── AI Generation handlers ──
  const handleWorldGen = useCallback(async () => {
    setGenerating('world')
    setAiStatus('正在生成世界观、角色和规则…')
    try {
      const kw = (document.getElementById('kw-input') as HTMLTextAreaElement)?.value || '奇幻冒险'
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
      setAiStatus('✅ 生成完成，可继续修改')
      setFieldErrors((prev) => ({ ...prev, world: null }))
    } catch (e) {
      const msg = (e as Error).message
      setAiStatus(`❌ ${msg}`)
      setFieldErrors((prev) => ({ ...prev, world: msg }))
    }
    setGenerating(null)
  }, [setValue])

  const handleFieldGen = useCallback(async (field: string) => {
    setGenerating(field)
    setAiStatus(`正在生成${field === 'title' ? '标题' : field === 'main_goal' ? '主线目标' : field === 'scene' ? '场景' : field === 'world' ? '世界观' : field}…`)
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
      setAiStatus('✅ 生成完成')
      setFieldErrors((prev) => ({ ...prev, [field]: null }))
    } catch (e) {
      const msg = (e as Error).message
      setAiStatus(`❌ ${msg}`)
      setFieldErrors((prev) => ({ ...prev, [field]: msg }))
    }
    setGenerating(null)
  }, [getValues, setValue])

  const handleCharGen = useCallback(async (idx: number) => {
    setGenerating(`char-${idx}`)
    setAiStatus(`正在生成角色…`)
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
      setAiStatus('✅ 角色生成完成')
      setFieldErrors((prev) => ({ ...prev, [`char-${idx}`]: null }))
    } catch (e) {
      const msg = (e as Error).message
      setAiStatus(`❌ ${msg}`)
      setFieldErrors((prev) => ({ ...prev, [`char-${idx}`]: msg }))
    }
    setGenerating(null)
  }, [getValues, setValue])

  const handleRulesGen = useCallback(async () => {
    setGenerating('rules')
    setAiStatus('正在生成专属规则…')
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
      setAiStatus('✅ 专属规则生成完成')
      setFieldErrors((prev) => ({ ...prev, rules: null }))
    } catch (e) {
      const msg = (e as Error).message
      setAiStatus(`❌ ${msg}`)
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
    setAiStatus('正在创建故事…')
    try {
      await createStory(fd)
      window.location.href = '/'
    } catch (e) {
      setAiStatus(`❌ ${(e as Error).message}`)
    }
  }, [])

  const genre = watch('genre')
  const relStages = watch('rel_stages')

  return (
    <div className="max-w-5xl mx-auto">
      {/* ── AI Status Toast ── */}
      <AnimatePresence>
        {aiStatus && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`mb-4 px-4 py-2.5 rounded-lg text-sm border ${
              aiStatus.includes('❌')
                ? 'bg-game-danger/10 border-game-danger/30 text-game-danger'
                : aiStatus.includes('✅')
                ? 'bg-game-success/10 border-game-success/30 text-game-success'
                : 'bg-game-primary/10 border-game-primary/30 text-game-primary'
            }`}
          >
            {aiStatus}
          </motion.div>
        )}
      </AnimatePresence>

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {/* ═══════════ Sidebar: One-click Gen ═══════════ */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="md:col-span-1 space-y-4">
            <div className="bg-game-card border border-game-border rounded-lg p-4 space-y-3">
              <h3 className="text-sm text-game-muted font-medium">🤖 一键生成</h3>
              <textarea
                id="kw-input"
                placeholder="粘贴小说简介 / 世界观描述 / 关键词均可&#10;&#10;示例①：修仙 宗门 重生&#10;示例②：被退婚的废柴少年捡到神秘戒指…"
                className="w-full h-28 bg-game-bg border border-game-border rounded-md p-2.5 text-sm text-game-text placeholder:text-game-dim resize-y focus:outline-none focus:border-game-primary"
              />
              <button
                type="button"
                disabled={generating === 'world'}
                onClick={handleWorldGen}
                className="w-full py-2 bg-game-success/20 text-game-success border border-game-success/30 rounded-md text-sm font-bold hover:bg-game-success/30 disabled:opacity-40 transition-colors"
              >
                {generating === 'world' ? '⏳ 生成中…' : fieldErrors.world ? '🔄 重试一键生成' : '✨ 一键生成完整设定'}
              </button>
              {fieldErrors.world && (
                <p className="text-[11px] text-game-danger mt-1 animate-fade-in">{fieldErrors.world}</p>
              )}
            </div>

            {/* Presets */}
            <div className="bg-game-card border border-game-border rounded-lg p-4 space-y-1.5">
              <h3 className="text-sm text-game-muted font-medium mb-2">📦 预设模板</h3>
              {['🚀 星痕纪元', '🌸 樱之诗', '⚔️ 剑与星辉', '🔍 第七日'].map((p) => (
                <button
                  key={p}
                  type="button"
                  className="w-full text-left px-3 py-1.5 rounded text-xs text-game-muted hover:text-game-text hover:bg-game-surface transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* ═══════════ Main Form ═══════════ */}
          <div className="md:col-span-3 space-y-4">
            {/* Part 1: Story Basics */}
            <div className="bg-game-card border border-game-border rounded-lg p-5 space-y-4">
              <h2 className="text-game-accent font-bold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">1</span>
                故事基础信息
              </h2>

              {/* Title */}
              <div>
                <label className="text-xs text-game-muted font-medium flex justify-between">
                  <span>📖 故事标题</span>
                  <span className="text-game-dim">{(watch('title') || '').length}/20</span>
                </label>
                <div className="flex gap-2 mt-1">
                  <input
                    {...register('title')}
                    placeholder="给你的故事起个名字…"
                    className="flex-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-game-primary"
                  />
                  <AIButton loading={generating === 'title'} error={fieldErrors.title} onClick={() => handleFieldGen('title')}>
                    AI生成
                  </AIButton>
                </div>
              </div>

              {/* Genre */}
              <div>
                <label className="text-xs text-game-muted font-medium">🎭 类型 / 风格</label>
                <TagInput
                  value={genre}
                  onChange={(tags) => setValue('genre', tags)}
                  presets={GENRE_PRESETS}
                  placeholder="输入自定义风格，回车添加…"
                  color="primary"
                />
              </div>

              {/* Scene */}
              <div>
                <label className="text-xs text-game-muted font-medium">📍 开局地点</label>
                <div className="flex gap-2 mt-1">
                  <input
                    {...register('scene')}
                    placeholder="如：高二三班教室、回声号舰桥"
                    className="flex-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-game-primary"
                  />
                  <AIButton loading={generating === 'scene'} error={fieldErrors.scene} onClick={() => handleFieldGen('scene')}>
                    AI生成
                  </AIButton>
                </div>
              </div>

              {/* Main Goal */}
              <div>
                <label className="text-xs text-game-muted font-medium">🎯 故事主线目标</label>
                <div className="flex gap-2 mt-1">
                  <input
                    {...register('main_goal')}
                    placeholder="如：调查失踪舰队、找到失踪的妹妹…"
                    className="flex-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-game-primary"
                  />
                  <AIButton loading={generating === 'main_goal'} error={fieldErrors.main_goal} onClick={() => handleFieldGen('main_goal')}>
                    AI生成
                  </AIButton>
                </div>
              </div>

              {/* World (optional) */}
              <div className="border border-dashed border-game-border rounded-md p-4 opacity-80 hover:opacity-100 transition-opacity">
                <label className="text-xs text-game-dim font-medium flex justify-between">
                  <span>🌍 世界观背景 <span className="text-game-dim">· 可选</span></span>
                  <span>{(watch('world') || '').length}/300</span>
                </label>
                <div className="flex gap-2 mt-1">
                  <textarea
                    {...register('world')}
                    rows={3}
                    placeholder="校园恋爱/都市日常可跳过不填…"
                    className="flex-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm resize-y focus:outline-none focus:border-game-primary"
                  />
                  <AIButton loading={generating === 'world'} error={fieldErrors.world} onClick={() => handleFieldGen('world')}>
                    AI生成
                  </AIButton>
                </div>
              </div>
            </div>

            {/* Part 2: Relationship System */}
            <div className="bg-game-card border border-game-border rounded-lg p-5 space-y-3">
              <h2 className="text-game-accent font-bold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">2</span>
                ❤️ 关系系统
              </h2>
              <div className="flex items-center gap-3 flex-wrap">
                {relStages.map((s, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <span className="px-2.5 py-1 bg-game-primary/15 border border-game-primary/30 rounded-full text-xs text-game-primary">
                      {s}
                    </span>
                    {i < relStages.length - 1 && <span className="text-game-dim text-xs">→</span>}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-4">
                <label className="text-xs text-game-muted whitespace-nowrap">初始好感（0~100）：</label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  {...register('rel_affection', { valueAsNumber: true })}
                  className="flex-1 accent-game-accent"
                />
                <span className="text-game-accent font-bold text-sm w-8 text-right">{watch('rel_affection')}</span>
              </div>
            </div>

            {/* Part 3: Characters */}
            <div className="bg-game-card border border-game-border rounded-lg p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-game-accent font-bold flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">3</span>
                  角色系统
                </h2>
                <button
                  type="button"
                  onClick={() => append({
                    name: '', isMain: false, role_tags: [], personality_tags: [],
                    appearance: '', relationship: [], goal: '', secret: '',
                    background: '', special_ability: '',
                  })}
                  className="px-3 py-1 text-xs border border-dashed border-game-border rounded-md text-game-muted hover:text-game-text hover:border-game-primary transition-colors"
                >
                  ➕ 新增 NPC
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                        className={`border rounded-lg p-4 space-y-2.5 ${
                          isMain ? 'border-game-accent/50 bg-game-accent/5' : 'border-game-border bg-game-bg'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                            isMain ? 'bg-game-accent/20 text-game-accent' : 'bg-game-success/20 text-game-success'
                          }`}>
                            {isMain ? '⭐ 主角' : '👤 NPC'}
                          </span>
                          {!isMain && fields.length > 1 && (
                            <button
                              type="button"
                              onClick={() => remove(idx)}
                              className="text-game-dim hover:text-game-danger text-sm"
                            >
                              ×
                            </button>
                          )}
                        </div>

                        <input
                          {...register(`characters.${idx}.name`)}
                          placeholder="角色姓名"
                          className="w-full bg-game-surface border border-game-border rounded px-2.5 py-1.5 text-sm font-bold focus:outline-none focus:border-game-primary"
                        />

                        {/* Role tags */}
                        <div>
                          <span className="text-[10px] text-game-muted">身份 / 职业</span>
                          <TagInput
                            value={c?.role_tags || []}
                            onChange={(tags) => setValue(`characters.${idx}.role_tags`, tags)}
                            presets={ROLE_PRESETS}
                            placeholder="输入后回车添加…"
                            color="primary"
                          />
                        </div>

                        {/* Appearance */}
                        <div>
                          <span className="text-[10px] text-game-muted">外貌特征</span>
                          <input
                            {...register(`characters.${idx}.appearance`)}
                            placeholder="银白长发，紫色眼瞳…"
                            className="w-full bg-game-surface border border-game-border rounded px-2.5 py-1.5 text-xs focus:outline-none focus:border-game-primary mt-0.5"
                          />
                        </div>

                        {/* Personality tags */}
                        <div>
                          <span className="text-[10px] text-game-muted">性格标签（3~5个）</span>
                          <TagInput
                            value={c?.personality_tags || []}
                            onChange={(tags) => setValue(`characters.${idx}.personality_tags`, tags)}
                            presets={PERSONALITY_PRESETS}
                            placeholder="输入后回车添加…"
                            color="accent"
                          />
                        </div>

                        {/* Relationship (NPC only) */}
                        {!isMain && (
                          <div>
                            <span className="text-[10px] text-game-muted">与主角关系</span>
                            <TagInput
                              value={c?.relationship || []}
                              onChange={(tags) => setValue(`characters.${idx}.relationship`, tags)}
                              presets={RELATION_PRESETS}
                              placeholder="输入后回车添加…"
                              color="accent"
                            />
                          </div>
                        )}

                        {/* Goal */}
                        <div>
                          <span className="text-[10px] text-game-muted">当前目标</span>
                          <input
                            {...register(`characters.${idx}.goal`)}
                            placeholder="角色想要达成的事…"
                            className="w-full bg-game-surface border border-game-border rounded px-2.5 py-1.5 text-xs focus:outline-none focus:border-game-primary mt-0.5"
                          />
                        </div>

                        {/* Secret */}
                        <div>
                          <span className="text-[10px] text-game-accent">🔒 隐藏秘密</span>
                          <input
                            {...register(`characters.${idx}.secret`)}
                            placeholder="用于制造剧情爆点…"
                            className="w-full bg-game-secret/10 border border-game-secret/40 rounded px-2.5 py-1.5 text-xs text-game-accent focus:outline-none focus:border-game-accent mt-0.5 placeholder:text-game-dim"
                          />
                        </div>

                        <AIButton
                          loading={generating === `char-${idx}`}
                          error={fieldErrors[`char-${idx}`]}
                          onClick={() => handleCharGen(idx)}
                        >
                          {isMain ? '生成主角' : '生成此角色'}
                        </AIButton>
                      </motion.div>
                    )
                  })}
                </AnimatePresence>
              </div>
            </div>

            {/* Part 4: Custom Rules */}
            <div className="bg-game-card border border-game-border rounded-lg p-5 space-y-3">
              <h2 className="text-game-accent font-bold flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-game-primary/20 text-game-primary text-xs flex items-center justify-center">4</span>
                专属规则
              </h2>
              <p className="text-xs text-game-dim">📊 默认追踪：好感度（陌生→恋人，7阶段）· 无需生成即可使用</p>
              <AIButton loading={generating === 'rules'} error={fieldErrors.rules} onClick={handleRulesGen}>
                AI 生成专属规则
              </AIButton>
            </div>

            {/* Submit */}
            <button
              type="submit"
              className="w-full py-3 bg-game-success/20 text-game-success border border-game-success/30 rounded-lg text-base font-bold hover:bg-game-success/30 transition-colors"
            >
              🎬 开始新故事
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
