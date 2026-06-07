import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Globe, Network, Users, GitBranch, Gem } from 'lucide-react'
import { generateWorld, generateField, generateRules, createStory } from '@/lib/api'
import { logger } from '@/lib/logger'
import { useAutoSave } from '@/hooks/useAutoSave'
import { notifyDraftTitle, notifyWorldTitleChanged } from '@/hooks/useDocumentTitle'
import { useAppSettings } from '@/hooks/useAppSettings'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { TagInput } from '@/components/TagInput'
import { AIButton } from '@/components/AIButton'
import { StatusToast } from '@/components/StatusToast'
import { WorldGraphCanvas } from '@/components/world/WorldGraphCanvas'
import { InspectorPanel } from '@/components/layout/InspectorPanel'
import { usePageShell } from '@/components/layout/usePageShell'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { GlowDivider } from '@/components/neural/GlowDivider'
import { parseNodeSelection, createDemoGraphSeed, graphStructureKey } from '@/lib/worldGraphAdapter'
import {
  normalizeFactionMemberships,
  syncCharacterFactions,
  type FactionMembership,
  type FactionVisibility,
} from '@/lib/factionMembership'
import { t, tTheme } from '@/lib/i18n'
import { useAdultThemeOptional } from '@/contexts/AdultThemeContext'
import type { Character, WorldGenResponse, PersonalityBrain } from '@/lib/types'
import { EMPTY_PERSONALITY_BRAIN } from '@/lib/types'
import { STORY_PRESETS, type StoryPreset } from '@/lib/storyPresets'

const WORLD_BUILDER_FORM_ID = 'world-builder-form'
type BuilderSection = 'core' | 'factions' | 'characters' | 'relations' | 'artifacts'

const WORLD_GEN_CONFIRM_MSG =
  '一键生成会用 AI 结果覆盖当前表单中的全部设定（标题、世界观、角色、势力、物品、关系维度等），此操作不可撤销。\n\n确定继续？'

const START_STORY_CONFIRM_MSG =
  '开始新故事将初始化全新对局，当前游戏进度、剧情记录与相关存档将被覆盖，此操作不可撤销。\n\n确定继续？'

const factionMembershipSchema = z.object({
  faction: z.string(),
  visibility: z.enum(['public', 'hidden']),
})

const PERSONALITY_BRAIN_VALUE_PRESETS = [
  '荣誉', '自由', '血统', '忠诚', '利益', '正义', '家族', '权力', '爱情', '生存',
]

const personalityBrainSchema = z.object({
  desire: z.string(),
  fear: z.string(),
  taboo: z.string(),
  secret: z.string(),
  values: z.array(z.string()),
})

// ── Schema ──
const characterSchema = z.object({
  name: z.string().min(1, '必填'),
  isMain: z.boolean(),
  faction: z.string().optional(),
  factionMemberships: z.array(factionMembershipSchema).optional(),
  role_tags: z.array(z.string()),
  personality_tags: z.array(z.string()),
  appearance: z.string(),
  relationship: z.array(z.string()),
  goal: z.string(),
  secret: z.string(),
  personality: personalityBrainSchema,
  background: z.string(),
  special_ability: z.string(),
})

function emptyCharacter(isMain: boolean): FormValues['characters'][number] {
  return {
    name: '',
    isMain,
    role_tags: [],
    personality_tags: [],
    appearance: '',
    relationship: [],
    goal: '',
    secret: '',
    personality: { ...EMPTY_PERSONALITY_BRAIN },
    background: '',
    special_ability: '',
  }
}

function normalizeFormPersonality(
  c: Partial<Character & { personality?: PersonalityBrain }>,
): PersonalityBrain {
  const p = c.personality
  if (p && (p.desire || p.fear || p.taboo || p.secret || (p.values?.length ?? 0) > 0)) {
    return {
      desire: p.desire || c.goal || '',
      fear: p.fear || '',
      taboo: p.taboo || '',
      secret: p.secret || c.secret || '',
      values: p.values?.length ? p.values : [...(c.personality_tags || [])],
    }
  }
  return {
    desire: c.goal || '',
    fear: '',
    taboo: '',
    secret: c.secret || '',
    values: [...(c.personality_tags || [])],
  }
}

function syncCharacterGoalSecret(char: FormValues['characters'][number]): void {
  const desire = (char.personality?.desire || '').trim()
  const pSecret = (char.personality?.secret || '').trim()
  const goal = (char.goal || '').trim()
  const secret = (char.secret || '').trim()
  if (desire && !goal) char.goal = desire
  else if (goal && !desire) char.personality.desire = goal
  if (pSecret && !secret) char.secret = pSecret
  else if (secret && !pSecret) char.personality.secret = secret
}

function mapGeneratedCharacter(
  c: Partial<Character & { personality?: PersonalityBrain; factionMemberships?: FactionMembership[] }>,
  facs: FactionRow[],
  index: number,
): FormValues['characters'][number] {
  const personality = normalizeFormPersonality(c)
  const goal = c.goal || personality.desire || ''
  const secret = c.secret || personality.secret || ''
  const mapped = mapFormCharacter({
    name: c.name || '',
    isMain: c.isMain ?? index === 0,
    faction: c.faction,
    factionMemberships: c.factionMemberships,
    role_tags: Array.isArray(c.role_tags) ? c.role_tags : (c.role_tags ? [c.role_tags as string] : []),
    personality_tags: Array.isArray(c.personality_tags) ? c.personality_tags : [],
    appearance: c.appearance || '',
    relationship: Array.isArray(c.relationship) ? c.relationship : [],
    goal,
    secret,
    personality: {
      ...personality,
      desire: personality.desire || goal,
      secret: personality.secret || secret,
    },
    background: c.background || '',
    special_ability: c.special_ability || '',
  }, facs)
  syncCharacterGoalSecret(mapped)
  return mapped
}

function applyGeneratedPersonality(
  target: FormValues['characters'][number],
  data: Partial<Character & { personality?: PersonalityBrain }>,
): void {
  const p = data.personality
  if (p && typeof p === 'object') {
    target.personality = {
      desire: p.desire || data.goal || target.personality.desire || '',
      fear: p.fear || '',
      taboo: p.taboo || '',
      secret: p.secret || data.secret || target.personality.secret || '',
      values: p.values?.length ? p.values : target.personality.values,
    }
  } else if (data.goal || data.secret) {
    target.personality = normalizeFormPersonality({
      ...target,
      goal: data.goal || target.goal,
      secret: data.secret || target.secret,
    })
  }
  syncCharacterGoalSecret(target)
}

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

const DEFAULT_REL = { relationshipType:'friend', affection:50, trust:50, respect:50, dependence:50, hostility:30, attraction:50, tags:[] as string[] }

type CharRel = typeof DEFAULT_REL

const REL_TYPE_SET = new Set(['friend', 'lover', 'family', 'teacher', 'rival', 'ally', 'enemy'])

function clampRelMetric(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : parseInt(String(value), 10)
  return Number.isFinite(n) ? Math.max(0, Math.min(100, n)) : fallback
}

function pickRelationRaw(
  raw: Record<string, unknown> | undefined,
  npcName: string,
  usedKeys: Set<string>,
): Record<string, unknown> {
  if (!raw) return {}
  if (raw[npcName] && typeof raw[npcName] === 'object') {
    usedKeys.add(npcName)
    return raw[npcName] as Record<string, unknown>
  }
  for (const [key, val] of Object.entries(raw)) {
    if (usedKeys.has(key) || typeof val !== 'object' || val === null) continue
    if (key === npcName || key.includes(npcName) || npcName.includes(key)) {
      usedKeys.add(key)
      return val as Record<string, unknown>
    }
  }
  return {}
}

function normalizeCharacterRelations(
  raw: Record<string, unknown> | undefined,
  npcNames: string[],
): Record<string, CharRel> {
  const out: Record<string, CharRel> = {}
  const usedKeys = new Set<string>()
  for (const name of npcNames) {
    const rel = pickRelationRaw(raw, name, usedKeys)
    const relType = typeof rel.relationshipType === 'string' && REL_TYPE_SET.has(rel.relationshipType)
      ? rel.relationshipType
      : DEFAULT_REL.relationshipType
    const tags = Array.isArray(rel.tags)
      ? rel.tags.filter((t): t is string => typeof t === 'string' && !!t.trim())
      : []
    out[name] = {
      relationshipType: relType,
      affection: clampRelMetric(rel.affection, DEFAULT_REL.affection),
      trust: clampRelMetric(rel.trust, DEFAULT_REL.trust),
      respect: clampRelMetric(rel.respect, DEFAULT_REL.respect),
      dependence: clampRelMetric(rel.dependence, DEFAULT_REL.dependence),
      hostility: clampRelMetric(rel.hostility, DEFAULT_REL.hostility),
      attraction: clampRelMetric(rel.attraction, DEFAULT_REL.attraction),
      tags,
    }
  }
  return out
}

type FactionRow = {
  name: string
  type: string
  description: string
  goals: string[]
  resources: string[]
  controlledTerritories: string[]
  subordinateOrganizations: string[]
  keyAssets: string[]
  power: { military: number; economic: number; political: number; technology: number }
  influence: number
  relation_to_player: string
  leader: string
}

function factionTypeLabel(type: string): string {
  const map: Record<string, string> = {
    government: '🏛️ 政府',
    corporation: '💼 企业',
    family: '👪 家族',
    organization: '🏢 组织',
    guild: '⚔️ 行会',
    school: '📚 学院',
    religion: '⛪ 宗教',
    kingdom: '👑 王国',
    other: '📋 其他',
  }
  return map[type] || map.organization
}

const FACTION_RELATION_LABELS: Record<string, string> = {
  ally: '盟友',
  friendly: '友好',
  neutral: '中立',
  hostile: '敌对',
  enemy: '死敌',
}

const FACTION_POWER_LABELS = {
  military: '军事',
  economic: '经济',
  political: '政治',
  technology: '科技',
} as const

const selectFieldClass =
  'w-full h-9 bg-game-bg border border-game-border rounded-md px-2.5 text-sm text-game-text'

function mapGeneratedFactions(raw: Array<Record<string, unknown>>): FactionRow[] {
  return raw.map((f) => ({
    name: (f.name as string) || '',
    type: (f.type as string) || 'organization',
    description: (f.description as string) || '',
    goals: (f.goals as string[]) || [],
    resources: (f.resources as string[]) || [],
    controlledTerritories: (f.controlledTerritories as string[]) || [],
    subordinateOrganizations: (f.subordinateOrganizations as string[]) || [],
    keyAssets: (f.keyAssets as string[]) || [],
    power: (f.power as FactionRow['power']) || { military: 0, economic: 0, political: 0, technology: 0 },
    influence: (f.influence as number) || 50,
    relation_to_player: (f.relation_to_player as string) || 'neutral',
    leader: (f.leader as string) || '',
  }))
}

function resolveCharacterMemberships(
  char: {
    faction?: string
    factionMemberships?: Array<{ faction: string; visibility?: string }>
  },
  charName: string,
  factions: FactionRow[],
): FactionMembership[] {
  const rawList = char.factionMemberships
  if (Array.isArray(rawList) && rawList.length) {
    const resolved = rawList
      .map((m) => ({
        faction: resolveCharacterFaction(m.faction, charName, factions),
        visibility: (m.visibility === 'hidden' ? 'hidden' : 'public') as FactionVisibility,
      }))
      .filter((m) => m.faction)
    if (resolved.length) return normalizeFactionMemberships({ factionMemberships: resolved }, factions)
  }
  const legacy = resolveCharacterFaction(char.faction, charName, factions)
  if (legacy) return [{ faction: legacy, visibility: 'public' }]
  return []
}

function mapFormCharacter(
  c: FormValues['characters'][number],
  factions: FactionRow[],
): FormValues['characters'][number] {
  return syncCharacterFactions({
    ...c,
    factionMemberships: resolveCharacterMemberships(c, c.name || '', factions),
  })
}

function resolveCharacterFaction(
  faction: unknown,
  charName: string,
  factions: FactionRow[],
): string {
  const names = factions.map((f) => f.name).filter(Boolean)
  const raw = typeof faction === 'string' ? faction.trim() : ''
  if (raw && names.includes(raw)) return raw
  const byLeader = factions.find((f) => f.leader === charName)
  if (byLeader?.name) return byLeader.name
  if (raw) {
    const fuzzy = names.find((n) => raw.includes(n) || n.includes(raw))
    if (fuzzy) return fuzzy
  }
  return ''
}

type ArtifactRow = {
  name: string
  type: string
  description: string
  ownerType: string
  ownerId: string
  importance: number
  abilities: string[]
  tags: string[]
}

function resolveArtifactOwner(
  ownerId: unknown,
  ownerType: string,
  charNames: string[],
  facNames: string[],
): string {
  const raw = typeof ownerId === 'string' ? ownerId.trim() : ''
  if (!raw) return ''
  const pool = ownerType === 'character'
    ? charNames
    : ownerType === 'faction'
      ? facNames
      : [...charNames, ...facNames]
  if (pool.includes(raw)) return raw
  const fuzzy = pool.find((n) => raw.includes(n) || n.includes(raw))
  return fuzzy || raw
}

function mapGeneratedArtifacts(
  raw: Array<Record<string, unknown>>,
  charNames: string[],
  factions: FactionRow[],
): ArtifactRow[] {
  const facNames = factions.map((f) => f.name).filter(Boolean)
  return raw.map((a) => ({
    name: (a.name as string) || '',
    type: ((a.type as string) || 'personal') as 'personal' | 'faction' | 'world',
    description: (a.description as string) || '',
    ownerType: ((a.ownerType as string) || 'none') as 'character' | 'faction' | 'location' | 'none',
    ownerId: resolveArtifactOwner(a.ownerId, (a.ownerType as string) || 'none', charNames, facNames),
    importance: (a.importance as number) || 50,
    abilities: (a.abilities as string[]) || [],
    tags: (a.tags as string[]) || [],
  }))
}

function artifactFromGenData(
  data: Record<string, unknown>,
  charNames: string[],
  facNames: string[],
): ArtifactRow | null {
  if (!data.name) return null
  const ownerType = (data.ownerType as string) || 'none'
  return {
    name: String(data.name),
    type: ((data.type as string) || 'personal') as 'personal' | 'faction' | 'world',
    description: (data.description as string) || '',
    ownerType: (ownerType || 'none') as 'character' | 'faction' | 'location' | 'none',
    ownerId: resolveArtifactOwner(data.ownerId, ownerType, charNames, facNames),
    importance: (data.importance as number) || 50,
    abilities: (data.abilities as string[]) || [],
    tags: (data.tags as string[]) || [],
  }
}

function getOwnerNames(characters: FormValues['characters'], factionList: FactionRow[]) {
  return {
    charNames: characters.map((c) => c.name).filter(Boolean),
    facNames: factionList.map((f) => f.name).filter(Boolean),
  }
}

function assessWorldGenCompleteness(data: WorldGenResponse): string[] {
  const warnings: string[] = []
  if (!data.characters?.length) warnings.push('缺少角色')
  else if (!data.characters.some((c) => !c.isMain)) warnings.push('缺少 NPC')
  if (!data.factions?.length) warnings.push('缺少势力')
  if (!data.artifacts?.length) warnings.push('缺少关键物品')
  if (!data.stats?.length) warnings.push('缺少追踪维度')
  const npcNames = (data.characters || []).filter((c) => !c.isMain && c.name).map((c) => c.name as string)
  if (npcNames.length) {
    const rels = (data.characterRelations || {}) as Record<string, { tags?: string[] }>
    if (npcNames.some((n) => !rels[n]?.tags?.length)) warnings.push('部分关系标签未生成')
    const missingTaboo = npcNames.filter((n) => {
      const ch = (data.characters || []).find((c) => c.name === n)
      if (!ch) return true
      return !normalizeFormPersonality(ch).taboo.trim()
    })
    if (missingTaboo.length) {
      warnings.push(`${missingTaboo.length} 名 NPC 缺少行为禁忌(taboo)，可在角色页补全`)
    }
  }
  return warnings
}

interface NewStorySavedState {
  form?: FormValues
  factions?: FactionRow[]
  artifacts?: ArtifactRow[]
  characterRelations?: Record<string, CharRel>
  customStats?: { key: string; label: string; max: number }[]
  keywords?: string
  activePreset?: string | null
  nodePositions?: Record<string, { x: number; y: number }>
  activeSection?: BuilderSection
}

// ── Main Page ──
export default function NewStory() {
  const { language } = useAppSettings()
  const adultMode = useAdultThemeOptional()?.adultMode ?? false
  const lang = language as 'zh' | 'en' | 'ja'
  const [aiStatus, setAiStatus] = useState('')
  const [aiStatusType, setAiStatusType] = useState<'info' | 'success' | 'error' | 'loading'>('info')
  const [generating, setGenerating] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string | null>>({})
  const [activeSection, setActiveSection] = useState<BuilderSection>('core')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({})
  const [characterRelations, setCharacterRelations] = useState<Record<string, {
    relationshipType: string; affection: number; trust: number; respect: number;
    dependence: number; hostility: number; attraction: number; tags: string[];
  }>>({})
  const [artifacts, setArtifacts] = useState<{ name: string; type: string; description: string; ownerType: string; ownerId: string; importance: number; abilities: string[]; tags: string[] }[]>([])
  const [factions, setFactions] = useState<FactionRow[]>([])
  const patchFaction = useCallback((idx: number, patch: Partial<FactionRow>) => {
    setFactions((prev) => prev.map((f, i) => (i === idx ? { ...f, ...patch } : f)))
  }, [])
  const patchFactionPower = useCallback(
    (idx: number, key: keyof FactionRow['power'], val: number) => {
      setFactions((prev) =>
        prev.map((f, i) =>
          i !== idx
            ? f
            : { ...f, power: { ...f.power, [key]: Math.max(0, Math.min(100, val)) } },
        ),
      )
    },
    [],
  )
  const removeFaction = useCallback((idx: number) => {
    setFactions((prev) => prev.filter((_, i) => i !== idx))
  }, [])
  const [customStats, setCustomStats] = useState<{ key: string; label: string; max: number }[]>([])
  const [keywords, setKeywords] = useState('')
  const [activePreset, setActivePreset] = useState<string | null>(null)

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: '',
      world: '',
      genre: [],
      scene: '',
      main_goal: '',
      characters: [emptyCharacter(true), emptyCharacter(false)],
      rel_stages: DEFAULT_STAGES,
      rel_affection: 0,
    },
  })

  const { register, control, watch, setValue, getValues, formState: { errors } } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'characters' })
  const watchAll = watch()

  const saveBundle = useMemo<NewStorySavedState>(() => ({
    form: watchAll,
    factions,
    artifacts,
    characterRelations,
    customStats,
    keywords,
    activePreset,
    nodePositions,
    activeSection,
  }), [watchAll, factions, artifacts, characterRelations, customStats, keywords, activePreset, nodePositions, activeSection])

  const { restoredData, clearSaved } = useAutoSave('new-story-draft-v2', saveBundle)
  useEffect(() => {
    if (!restoredData) return
    const saved = restoredData as NewStorySavedState & Partial<FormValues>
    if (saved.form && typeof saved.form === 'object') {
      const form = saved.form as FormValues
      if (form.characters?.length) {
        form.characters = form.characters.map((c) => ({
          ...c,
          personality: c.personality
            ? { ...EMPTY_PERSONALITY_BRAIN, ...c.personality }
            : normalizeFormPersonality(c),
        }))
      }
      Object.entries(form).forEach(([key, val]) => {
        setValue(key as keyof FormValues, val as never)
      })
      setFactions(saved.factions || [])
      setArtifacts(saved.artifacts || [])
      setCharacterRelations(saved.characterRelations || {})
      setCustomStats(saved.customStats || [])
      if (saved.keywords != null) setKeywords(saved.keywords)
      if (saved.activePreset != null) setActivePreset(saved.activePreset)
      if (saved.nodePositions) setNodePositions(saved.nodePositions)
      if (saved.activeSection) setActiveSection(saved.activeSection)
      return
    }
    if ('title' in saved || 'characters' in saved) {
      Object.entries(saved).forEach(([key, val]) => {
        if (['factions', 'artifacts', 'characterRelations', 'customStats', 'keywords', 'activePreset', 'form'].includes(key)) return
        setValue(key as keyof FormValues, val as never)
      })
    }
  }, [restoredData, setValue])

  const showStatus = (msg: string, type: 'info' | 'success' | 'error' | 'loading') => {
    setAiStatus(msg)
    setAiStatusType(type)
  }

  const applyDemoGraph = useCallback(() => {
    const seed = createDemoGraphSeed()
    setValue('title', seed.title.slice(0, 20))
    setValue('scene', seed.scene)
    setValue('main_goal', seed.main_goal)
    const facRows = mapGeneratedFactions(seed.factions as unknown as Array<Record<string, unknown>>)
    setFactions(facRows)
    const base = getValues('characters')
    const merged = (seed.characters || []).map((c, i) =>
      mapGeneratedCharacter(
        { ...(base[i] || emptyCharacter(false)), ...c },
        facRows,
        i,
      ),
    )
    setValue('characters', merged)
    if (seed.characterRelations) {
      setCharacterRelations(seed.characterRelations as typeof characterRelations)
    }
    if (seed.artifacts?.length) {
      setArtifacts(mapGeneratedArtifacts(
        seed.artifacts as unknown as Array<Record<string, unknown>>,
        merged.map((c) => c.name).filter(Boolean),
        facRows,
      ))
    }
    setNodePositions({})
    showStatus('✅ 已加载示例图（含多势力明/暗隶属与全部连线类型）', 'success')
  }, [getValues, setValue])

  const relayoutGraph = useCallback(() => {
    setNodePositions({})
    showStatus('✨ 已按关系重新优化布局', 'success')
  }, [])

  const demoGraphLoadedRef = useRef(false)
  useEffect(() => {
    if (demoGraphLoadedRef.current) return
    const timer = setTimeout(() => {
      if (demoGraphLoadedRef.current) return
      if (factions.length > 0) return
      const chars = getValues('characters')
      if (chars.some((c) => c.name.trim())) return
      demoGraphLoadedRef.current = true
      applyDemoGraph()
    }, 600)
    return () => clearTimeout(timer)
  }, [factions.length, getValues, applyDemoGraph])

  const applyWorldGenResult = useCallback((data: WorldGenResponse): string[] => {
    if (!data.characters?.length) {
      if (data.title) setValue('title', String(data.title).slice(0, 20))
      if (data.world) setValue('world', String(data.world).trim().slice(0, 300))
      if (data.genre?.length) setValue('genre', data.genre)
      if (data.scene) setValue('scene', data.scene)
      if (data.main_goal) setValue('main_goal', data.main_goal)
      return ['生成结果被截断，未更新角色/势力/物品/关系（已保留现有内容）。请提高 Token 后重试']
    }

    setFactions([])
    setArtifacts([])
    setCharacterRelations({})
    setCustomStats([])
    setActivePreset(null)

    if (data.title) setValue('title', String(data.title).slice(0, 20))
    if (data.world) setValue('world', String(data.world).trim().slice(0, 300))
    if (data.genre) setValue('genre', Array.isArray(data.genre) ? data.genre : [])
    if (data.scene) setValue('scene', data.scene)
    if (data.main_goal) setValue('main_goal', data.main_goal)

    const facs = data.factions
      ? mapGeneratedFactions(data.factions as unknown as Array<Record<string, unknown>>)
      : []
    setFactions(facs)

    let charNames: string[] = []
    const chars = data.characters.map((c, i) => mapGeneratedCharacter(c, facs, i))
    setValue('characters', chars)
    charNames = chars.map((c) => c.name).filter(Boolean)
    const npcNames = chars.filter((c) => !c.isMain && c.name).map((c) => c.name)
    setCharacterRelations(normalizeCharacterRelations(
      data.characterRelations as Record<string, unknown> | undefined,
      npcNames,
    ))

    if (data.rel_stages) setValue('rel_stages', data.rel_stages)
    if (data.rel_affection != null) setValue('rel_affection', data.rel_affection)
    if (data.stats?.length) {
      setCustomStats(data.stats.map((s) => ({
        key: String(s.key || 'stat'),
        label: String(s.label || s.key || '维度'),
        max: typeof s.max === 'number' ? s.max : 100,
      })))
    }

    const arts = data.artifacts
      ? mapGeneratedArtifacts(
        data.artifacts as unknown as Array<Record<string, unknown>>,
        charNames,
        facs,
      )
      : []
    setArtifacts(arts)

    return assessWorldGenCompleteness(data)
  }, [setValue])

  const runWorldGen = useCallback(async (kwOverride?: string) => {
    setGenerating('world')
    showStatus('正在生成世界观、角色和规则…', 'loading')
    logger.info('NewStory', 'runWorldGen: starting')
    try {
      const kw = (kwOverride ?? keywords).trim() || '奇幻冒险'
      const data = await generateWorld(kw, adultMode)
      const warnings = applyWorldGenResult(data)

      if (data.characters?.length && !data.stats?.length) {
        try {
          const allChars = getValues('characters') || []
          const rules = await generateRules({ adultMode,
            title: getValues('title'),
            world: getValues('world'),
            genre: getValues('genre').join('/'),
            char1_name: allChars[0]?.name || '主角',
            char1_role: allChars[0]?.role_tags?.[0] || '',
            char2_name: allChars[1]?.name || '',
            char2_role: allChars[1]?.role_tags?.[0] || '',
          })
          if (rules.stats?.length) setCustomStats(rules.stats)
          if (rules.stages?.length && !data.rel_stages?.length) {
            setValue('rel_stages', rules.stages)
          }
        } catch {
          // 规则补全失败不影响主流程
        }
      }

      if (warnings.length) {
        showStatus(`⚠️ ${warnings.join('；')}。可在设置中提高 Token 后重试`, 'error')
      } else {
        showStatus(
          adultMode ? '✅ 成人向设定生成完成，可继续修改' : '✅ 生成完成，可继续修改',
          'success',
        )
      }
      setFieldErrors((prev) => ({ ...prev, world: warnings.some((w) => w.includes('截断')) ? warnings[0] : null }))
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('NewStory', 'runWorldGen: failed', { error: msg })
      showStatus(`❌ ${msg}`, 'error')
      setFieldErrors((prev) => ({ ...prev, world: msg }))
    }
    setGenerating(null)
  }, [keywords, applyWorldGenResult, getValues, setValue, adultMode])

  const handleWorldGen = useCallback(() => {
    if (!window.confirm(WORLD_GEN_CONFIRM_MSG)) return
    runWorldGen()
  }, [runWorldGen])

  const handlePresetSelect = useCallback(async (preset: StoryPreset) => {
    if (!window.confirm(WORLD_GEN_CONFIRM_MSG)) return
    setActivePreset(preset.id)
    const kw = [preset.keywords, preset.form.title, preset.form.world].filter(Boolean).join('\n')
    setKeywords(kw)
    setFieldErrors({})
    showStatus(`正在基于「${preset.label.replace(/^[^\s]+\s*/, '')}」一键生成…`, 'loading')
    await runWorldGen(kw)
  }, [runWorldGen])

  const handleFieldGen = useCallback(async (field: string) => {
    setGenerating(field)
    logger.info('NewStory', `handleFieldGen: ${field}`)
    const fieldLabels: Record<string, string> = { title: '标题', main_goal: '主线目标', scene: '场景', world: '世界观' }
    showStatus(`正在生成${fieldLabels[field] || field}…`, 'loading')
    setFieldErrors((prev) => ({ ...prev, [field]: null }))
    try {
      const data = await generateField({ adultMode,
        field,
        title: getValues('title'),
        world: getValues('world'),
        genre: getValues('genre').join('/'),
      })
      const story = data.story || data.title || ''
      if (field === 'title') setValue('title', story.replace(/["']/g, '').trim().slice(0, 20))
      if (field === 'world') setValue('world', story.trim().slice(0, 300))
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
      const data = await generateField({ adultMode,
        field: 'character',
        title: getValues('title'),
        world: getValues('world'),
        char_role: '',
        context: JSON.stringify((factions || []).map((f) => ({ name: f.name, leader: f.leader }))),
      })
      const chars = getValues('characters')
      if (data.name) chars[idx].name = data.name
      const genMemberships = (data as { factionMemberships?: FactionMembership[] }).factionMemberships
      if (Array.isArray(genMemberships) && genMemberships.length) {
        Object.assign(chars[idx], mapFormCharacter({
          ...chars[idx],
          factionMemberships: genMemberships,
        }, factions || []))
      } else if (data.faction !== undefined) {
        Object.assign(chars[idx], mapFormCharacter({
          ...chars[idx],
          faction: resolveCharacterFaction(data.faction, data.name || chars[idx].name || '', factions || []),
        }, factions || []))
      }
      if (data.role_tags) chars[idx].role_tags = Array.isArray(data.role_tags) ? data.role_tags : [data.role_tags]
      if (data.personality_tags) chars[idx].personality_tags = Array.isArray(data.personality_tags) ? data.personality_tags : [data.personality_tags]
      if (data.appearance) chars[idx].appearance = data.appearance
      if (data.relationship) chars[idx].relationship = Array.isArray(data.relationship) ? data.relationship : [data.relationship]
      if (data.goal) chars[idx].goal = data.goal
      if (data.secret) chars[idx].secret = data.secret
      applyGeneratedPersonality(chars[idx], data as Character & { personality?: PersonalityBrain })
      setValue('characters', chars)
      showStatus('✅ 角色生成完成', 'success')
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('NewStory', `handleCharGen: char-${idx} failed`, { error: msg })
      showStatus(`❌ ${msg}`, 'error')
      setFieldErrors((prev) => ({ ...prev, [`char-${idx}`]: msg }))
    }
    setGenerating(null)
  }, [getValues, setValue, factions])

  const handleRelGen = useCallback(async (npcName: string) => {
    const genKey = `rel-${npcName}`
    setGenerating(genKey)
    showStatus(`正在生成与 ${npcName} 的关系设定…`, 'loading')
    setFieldErrors((prev) => ({ ...prev, [genKey]: null }))
    try {
      const allChars = getValues('characters')
      const mainChar = allChars.find((c) => c.isMain) || allChars[0]
      const npc = allChars.find((c) => c.name === npcName)
      const context = [
        mainChar?.name ? `主角：${mainChar.name}` : '',
        mainChar?.personality_tags?.length ? `主角性格：${mainChar.personality_tags.join('、')}` : '',
        npc?.name ? `NPC：${npc.name}` : '',
        npc?.personality_tags?.length ? `NPC性格：${npc.personality_tags.join('、')}` : '',
        npc?.relationship?.length ? `关系描述：${npc.relationship.join('、')}` : '',
        npc?.goal ? `NPC目标：${npc.goal}` : '',
        npc?.secret ? `NPC秘密：${npc.secret}` : '',
        npc?.personality?.taboo ? `NPC禁忌：${npc.personality.taboo}` : '',
        npc?.personality?.desire ? `NPC欲望：${npc.personality.desire}` : '',
      ].filter(Boolean).join('\n')
      const data = await generateField({ adultMode,
        field: 'character_relation',
        title: getValues('title'),
        world: getValues('world'),
        char_name: npcName,
        context,
      })
      const normalized = normalizeCharacterRelations({ [npcName]: data as Record<string, unknown> }, [npcName])
      setCharacterRelations((prev) => ({
        ...prev,
        [npcName]: { ...(prev[npcName] || DEFAULT_REL), ...normalized[npcName] },
      }))
      showStatus('✅ 关系设定生成完成', 'success')
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('NewStory', `handleRelGen: ${npcName} failed`, { error: msg })
      showStatus(`❌ ${msg}`, 'error')
      setFieldErrors((prev) => ({ ...prev, [genKey]: msg }))
    }
    setGenerating(null)
  }, [getValues])

  const onSubmit = useCallback(async (data: FormValues) => {
    if (!window.confirm(START_STORY_CONFIRM_MSG)) return
    const fd = new FormData()
    fd.append('title', data.title)
    fd.append('world', data.world)
    fd.append('genre', data.genre.join(' / '))
    fd.append('scene', data.scene)
    fd.append('main_goal', data.main_goal)
    fd.append('chars_json', JSON.stringify(data.characters.map((c) => mapFormCharacter(c, factions))))
    fd.append('rel_system', JSON.stringify({ stages: data.rel_stages, affection: data.rel_affection }))
    fd.append('custom_rules', JSON.stringify({ stats: customStats, stages: data.rel_stages, characterRelations: characterRelations }))
    fd.append('artifacts_json', JSON.stringify(artifacts))
    fd.append('factions_json', JSON.stringify(factions))
    showStatus('正在创建故事…', 'loading')
    try {
      await createStory(fd)
      notifyWorldTitleChanged()
      clearSaved()
      window.location.href = '/game'
    } catch (e) {
      showStatus(`❌ ${(e as Error).message}`, 'error')
    }
  }, [customStats, characterRelations, artifacts, factions, clearSaved])

  const genre = watch('genre')
  const relStages = watch('rel_stages')
  const watchedTitle = watch('title')
  const titleLen = (watchedTitle || '').length
  const worldLen = (watch('world') || '').length

  useEffect(() => {
    notifyDraftTitle(watchedTitle || '')
  }, [watchedTitle])

  const graphInput = useMemo(() => ({
    title: watchAll.title || '',
    world: watchAll.world || '',
    genre: watchAll.genre || [],
    scene: watchAll.scene || '',
    main_goal: watchAll.main_goal || '',
    characters: (watchAll.characters || []).map((c) => {
      const synced = mapFormCharacter(c, factions)
      return {
        name: synced.name,
        isMain: synced.isMain,
        faction: synced.faction,
        factionMemberships: synced.factionMemberships,
      }
    }),
    factions: factions.map((f) => ({
      name: f.name,
      type: f.type,
      leader: f.leader,
      influence: f.influence,
    })),
    artifacts: artifacts.map((a) => ({
      name: a.name,
      type: a.type,
      ownerId: a.ownerId,
    })),
    characterRelations,
    nodePositions: Object.keys(nodePositions).length > 0 ? nodePositions : undefined,
  }), [watchAll, factions, artifacts, characterRelations, nodePositions])

  const graphLayoutKey = useMemo(
    () => graphStructureKey({
      title: watchAll.title || '',
      world: watchAll.world || '',
      genre: watchAll.genre || [],
      scene: watchAll.scene || '',
      main_goal: watchAll.main_goal || '',
      characters: (watchAll.characters || []).map((c) => {
        const synced = mapFormCharacter(c, factions)
        return {
          name: synced.name,
          isMain: synced.isMain,
          faction: synced.faction,
          factionMemberships: synced.factionMemberships,
        }
      }),
      factions: factions.map((f) => ({
        name: f.name,
        type: f.type,
        leader: f.leader,
        influence: f.influence,
      })),
      artifacts: artifacts.map((a) => ({
        name: a.name,
        type: a.type,
        ownerId: a.ownerId,
      })),
      characterRelations,
    }),
    [watchAll.characters, factions, artifacts, characterRelations, watchAll.title, watchAll.world, watchAll.genre, watchAll.scene, watchAll.main_goal],
  )

  const prevGraphLayoutKey = useRef<string | null>(null)
  useEffect(() => {
    if (prevGraphLayoutKey.current !== null && prevGraphLayoutKey.current !== graphLayoutKey) {
      setNodePositions({})
    }
    prevGraphLayoutKey.current = graphLayoutKey
  }, [graphLayoutKey])

  const navItems = useMemo(() => {
    if (adultMode) {
      return [
        { id: 'core', label: tTheme('world.core', lang, true), icon: <Globe className="w-4 h-4" /> },
        { id: 'factions', label: tTheme('world.factions', lang, true), icon: <Network className="w-4 h-4" /> },
        { id: 'characters', label: t('world.nav.characters', lang), icon: <Users className="w-4 h-4" /> },
        { id: 'relations', label: tTheme('world.relations', lang, true), icon: <GitBranch className="w-4 h-4" /> },
        { id: 'artifacts', label: t('world.artifacts', lang), icon: <Gem className="w-4 h-4" /> },
      ]
    }
    return [
      { id: 'core', label: t('world.nav.core', lang), icon: <Globe className="w-4 h-4" /> },
      { id: 'factions', label: t('world.nav.factions', lang), icon: <Network className="w-4 h-4" /> },
      { id: 'characters', label: t('world.nav.characters', lang), icon: <Users className="w-4 h-4" /> },
      { id: 'relations', label: t('world.relations', lang), icon: <GitBranch className="w-4 h-4" /> },
      { id: 'artifacts', label: t('world.artifacts', lang), icon: <Gem className="w-4 h-4" /> },
    ]
  }, [lang, adultMode])

  useEffect(() => {
    if (!selectedNodeId) return
    const parsed = parseNodeSelection(selectedNodeId)
    if (parsed.type === 'worldCore') setActiveSection('core')
    else if (parsed.type === 'faction') setActiveSection('factions')
    else if (parsed.type === 'character') setActiveSection('characters')
    else if (parsed.type === 'artifact') setActiveSection('artifacts')
  }, [selectedNodeId])

  const inspector = (
    <InspectorPanel
      title={navItems.find((n) => n.id === activeSection)?.label}
      footer={
        <Button type="submit" form={WORLD_BUILDER_FORM_ID} variant="neural" size="lg" className="w-full">
          {t('world.launch', lang)}
        </Button>
      }
    >
      <form
        id={WORLD_BUILDER_FORM_ID}
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-4"
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.target as HTMLElement).tagName === 'INPUT' && (e.target as HTMLInputElement).type === 'number') {
            e.preventDefault()
          }
        }}
      >
        <div className={activeSection === 'core' ? '' : 'hidden'}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t('world.core', lang)}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Card className="border-neural-cyan/10 bg-neural-cyan/[0.03]">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-neural-cyan">{t('world.aiGen', lang)}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {adultMode && (
                      <p className="text-[11px] text-pink-300/90 rounded-md border border-pink-500/25 bg-pink-500/10 px-2.5 py-1.5">
                        ❤️ 成人模式已开启：一键生成与各字段「生成」将按成人向设定输出
                      </p>
                    )}
                    <Textarea
                      id="kw-input"
                      value={keywords}
                      onChange={(e) => setKeywords(e.target.value)}
                      placeholder="粘贴小说简介 / 世界观描述 / 关键词…"
                      className="min-h-[5rem] resize-y text-xs"
                    />
                    <Button type="button" variant="neural" className="w-full" disabled={generating === 'world'} onClick={handleWorldGen}>
                      {generating === 'world' ? '生成中…' : '✨ 一键生成完整设定'}
                    </Button>
                    <GlowDivider label={t('world.presets', lang)} />
                    <div className="flex flex-wrap gap-1">
                      {STORY_PRESETS.map((preset) => (
                        <Button
                          key={preset.id}
                          type="button"
                          variant={activePreset === preset.id ? 'default' : 'outline'}
                          size="xs"
                          onClick={() => handlePresetSelect(preset)}
                          disabled={generating === 'world'}
                        >
                          {preset.label}
                        </Button>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Title */}
                <div className="space-y-1.5">
                  <Label className="flex justify-between">
                    <span>📖 故事标题</span>
                    <span className="text-game-dim font-normal">{titleLen}/20</span>
                  </Label>
                  <div className="space-y-2">
                    <Input {...register('title')} placeholder="给你的故事起个名字…" />
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
                  <div className="space-y-2">
                    <Input {...register('scene')} placeholder="如：高二三班教室、回声号舰桥" />
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
                  <div className="space-y-2">
                    <Input {...register('main_goal')} placeholder="如：调查失踪舰队、找到失踪的妹妹…" />
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
                  <div className="space-y-2">
                    <Textarea
                      {...register('world')}
                      rows={4}
                      placeholder="校园恋爱/都市日常可跳过不填…"
                      className="resize-y"
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
        </div>

        <div className={activeSection === 'factions' ? '' : 'hidden'}>
            <Card>
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle className="flex items-center gap-2 text-sm shrink-0">
                  {t('world.factions', lang)}
                </CardTitle>
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    disabled={generating === 'factions-all'}
                    onClick={async () => {
                      setGenerating('factions-all')
                      showStatus('正在批量生成势力…', 'loading')
                      const current = factions || []
                      const newFacs: typeof current = []
                      for (let i = 0; i < 3; i++) {
                        try {
                          const data = await generateField({ adultMode,
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
                      setFactions( [...current, ...newFacs])
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
                      const current = factions || []
                      setFactions( [...current, {
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
                <div className="space-y-4">
                  {(factions || []).map((fac, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <Card className="border-game-warning/30 bg-game-bg/40">
                        <CardHeader className="pb-3 space-y-3">
                          <div className="flex items-start justify-between gap-2">
                            <Badge variant="warning" size="sm" className="shrink-0 mt-1">
                              {factionTypeLabel(fac.type)}
                            </Badge>
                            <div className="flex gap-1 shrink-0">
                              <AIButton
                                loading={generating === `faction-${idx}`}
                                onClick={async () => {
                                  setGenerating(`faction-${idx}`)
                                  try {
                                    const data = await generateField({ adultMode,
                                      field: 'faction',
                                      title: getValues('title'),
                                      world: getValues('world'),
                                      genre: getValues('genre').join('/'),
                                    })
                                    if ((data as { name?: string }).name) {
                                      patchFaction(idx, {
                                        name: (data as { name: string }).name,
                                        type: ((data as { type?: string }).type || 'organization') as string,
                                        description: (data as { description?: string }).description || '',
                                        goals: (data as { goals?: string[] }).goals || [],
                                        resources: (data as { resources?: string[] }).resources || [],
                                        controlledTerritories: (data as { controlledTerritories?: string[] }).controlledTerritories || [],
                                        subordinateOrganizations: (data as { subordinateOrganizations?: string[] }).subordinateOrganizations || [],
                                        keyAssets: (data as { keyAssets?: string[] }).keyAssets || [],
                                        power: (data as { power?: FactionRow['power'] }).power || { military: 0, economic: 0, political: 0, technology: 0 },
                                        influence: (data as { influence?: number }).influence || 50,
                                        relation_to_player: ((data as { relation_to_player?: string }).relation_to_player || 'neutral') as string,
                                        leader: (data as { leader?: string }).leader || '',
                                      })
                                    }
                                    showStatus('✅ 势力生成完成', 'success')
                                  } catch (e) { showStatus(`❌ ${(e as Error).message}`, 'error') }
                                  setGenerating(null)
                                }}
                              >AI 生成</AIButton>
                              <button
                                type="button"
                                onClick={() => removeFaction(idx)}
                                className="h-8 w-8 rounded-md text-game-dim hover:text-game-danger hover:bg-game-danger/10 transition-colors text-sm"
                                aria-label="删除势力"
                              >✕</button>
                            </div>
                          </div>
                          <div className="space-y-1.5">
                            <Label className="text-xs text-game-muted">势力名称</Label>
                            <Input
                              value={fac.name}
                              onChange={(e) => patchFaction(idx, { name: e.target.value })}
                              placeholder="例如：光之圣域"
                              className="font-medium h-9"
                            />
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-4 pt-0">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">类型</Label>
                              <select
                                value={fac.type}
                                onChange={(e) => patchFaction(idx, { type: e.target.value })}
                                className={selectFieldClass}
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
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">与主角关系</Label>
                              <select
                                value={fac.relation_to_player}
                                onChange={(e) => patchFaction(idx, { relation_to_player: e.target.value })}
                                className={selectFieldClass}
                              >
                                {Object.entries(FACTION_RELATION_LABELS).map(([val, label]) => (
                                  <option key={val} value={val}>{label}</option>
                                ))}
                              </select>
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">首领 / 领袖</Label>
                              <Input
                                value={fac.leader}
                                onChange={(e) => patchFaction(idx, { leader: e.target.value })}
                                placeholder="角色名"
                                className="h-9"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">影响力 (1–100)</Label>
                              <Input
                                type="number"
                                min={1}
                                max={100}
                                value={fac.influence}
                                onChange={(e) => patchFaction(idx, {
                                  influence: Math.max(1, Math.min(100, parseInt(e.target.value, 10) || 50)),
                                })}
                                className="h-9"
                              />
                            </div>
                          </div>

                          <div className="space-y-1.5">
                            <Label className="text-xs text-game-muted">势力描述</Label>
                            <Textarea
                              value={fac.description}
                              onChange={(e) => patchFaction(idx, { description: e.target.value })}
                              placeholder="背景、立场、与主线关系…"
                              className="min-h-[72px] resize-y text-sm"
                            />
                          </div>

                          <div className="space-y-2">
                            <Label className="text-xs text-game-muted">实力评分 (0–100)</Label>
                            <div className="grid grid-cols-2 gap-3">
                              {(Object.keys(FACTION_POWER_LABELS) as Array<keyof typeof FACTION_POWER_LABELS>).map((k) => (
                                <div key={k} className="space-y-1">
                                  <span className="text-[11px] text-game-dim">{FACTION_POWER_LABELS[k]}</span>
                                  <Input
                                    type="number"
                                    min={0}
                                    max={100}
                                    value={fac.power?.[k] ?? 0}
                                    onChange={(e) => patchFactionPower(idx, k, parseInt(e.target.value, 10) || 0)}
                                    className="h-9 text-sm"
                                  />
                                </div>
                              ))}
                            </div>
                          </div>

                          <Separator className="bg-game-border/50" />

                          <div className="space-y-3">
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">🎯 目标</Label>
                              <TagInput
                                value={fac.goals || []}
                                onChange={(goals) => patchFaction(idx, { goals })}
                                presets={[]}
                                placeholder="回车添加目标…"
                                color="warning"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">📦 资源</Label>
                              <TagInput
                                value={fac.resources || []}
                                onChange={(resources) => patchFaction(idx, { resources })}
                                presets={[]}
                                placeholder="回车添加资源…"
                                color="warning"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">🗺️ 控制区域</Label>
                              <TagInput
                                value={fac.controlledTerritories || []}
                                onChange={(controlledTerritories) => patchFaction(idx, { controlledTerritories })}
                                presets={[]}
                                placeholder="回车添加区域…"
                                color="warning"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">🏢 下属机构</Label>
                              <TagInput
                                value={fac.subordinateOrganizations || []}
                                onChange={(subordinateOrganizations) => patchFaction(idx, { subordinateOrganizations })}
                                presets={[]}
                                placeholder="回车添加机构…"
                                color="warning"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs text-game-muted">💎 关键资产</Label>
                              <TagInput
                                value={fac.keyAssets || []}
                                onChange={(keyAssets) => patchFaction(idx, { keyAssets })}
                                presets={[]}
                                placeholder="回车添加资产…"
                                color="warning"
                              />
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                  {(factions || []).length === 0 && (
                    <p className="text-game-dim text-xs text-center py-6">
                      暂无势力 · 点击「✨ 模块生成」AI 批量生成，或「➕ 添加势力」手动填写
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
        </div>

        <div className={activeSection === 'characters' ? '' : 'hidden'}>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2 text-sm min-w-0">
                  {t('world.characters', lang)}
                </CardTitle>
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => append(emptyCharacter(false))}
                >
                  ➕ 新增 NPC
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
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
                                  compact
                                />
                              </div>

                              {/* Faction memberships */}
                              <div>
                                <Label className="text-[11px]">🏛️ 势力隶属</Label>
                                <p className="text-[10px] text-game-muted mt-0.5 mb-1">
                                  可多个；明面实线、暗中虚线。图谱拖线可追加或切换明/暗。
                                </p>
                                {(normalizeFactionMemberships(c || {}, factions)).map((m, mi) => (
                                  <div key={`${idx}-fac-${mi}-${m.faction}`} className="flex gap-1.5 mt-1 items-center">
                                    <select
                                      value={m.faction}
                                      onChange={(e) => {
                                        const list = [...normalizeFactionMemberships(c || {}, factions)]
                                        list[mi] = { ...list[mi], faction: e.target.value }
                                        const chars = getValues('characters')
                                        chars[idx] = mapFormCharacter({ ...chars[idx], factionMemberships: list }, factions)
                                        setValue('characters', chars)
                                      }}
                                      className="flex-1 bg-game-bg border border-game-border rounded-md px-2 py-1.5 text-xs text-game-text"
                                    >
                                      <option value="">选择势力</option>
                                      {(factions || []).map((f: { name: string }) => (
                                        <option key={f.name} value={f.name}>{f.name}</option>
                                      ))}
                                    </select>
                                    <button
                                      type="button"
                                      className={`shrink-0 px-2 py-1 text-[10px] rounded border ${
                                        m.visibility === 'hidden'
                                          ? 'border-game-muted/50 text-game-muted bg-game-bg'
                                          : 'border-neural-cyan/40 text-neural-cyan bg-neural-cyan/5'
                                      }`}
                                      onClick={() => {
                                        const list = [...normalizeFactionMemberships(c || {}, factions)]
                                        list[mi] = {
                                          ...list[mi],
                                          visibility: list[mi].visibility === 'public' ? 'hidden' : 'public',
                                        }
                                        const chars = getValues('characters')
                                        chars[idx] = mapFormCharacter({ ...chars[idx], factionMemberships: list }, factions)
                                        setValue('characters', chars)
                                      }}
                                    >
                                      {m.visibility === 'hidden' ? '暗' : '明'}
                                    </button>
                                    <button
                                      type="button"
                                      className="shrink-0 text-game-muted hover:text-game-accent text-xs px-1"
                                      onClick={() => {
                                        const list = normalizeFactionMemberships(c || {}, factions)
                                          .filter((_, j) => j !== mi)
                                        const chars = getValues('characters')
                                        chars[idx] = mapFormCharacter({ ...chars[idx], factionMemberships: list }, factions)
                                        setValue('characters', chars)
                                      }}
                                    >
                                      ✕
                                    </button>
                                  </div>
                                ))}
                                <button
                                  type="button"
                                  className="mt-1.5 text-[11px] text-neural-cyan hover:underline"
                                  onClick={() => {
                                    const list = [...normalizeFactionMemberships(c || {}, factions)]
                                    const used = new Set(list.map((x) => x.faction))
                                    const nextFac = (factions || []).find((f) => f.name && !used.has(f.name))?.name || ''
                                    list.push({ faction: nextFac, visibility: 'public' })
                                    const chars = getValues('characters')
                                    chars[idx] = mapFormCharacter({ ...chars[idx], factionMemberships: list }, factions)
                                    setValue('characters', chars)
                                  }}
                                >
                                  + 添加隶属
                                </button>
                              </div>

                              {/* Goal (原关系字段已合并到Part3多维关系) */}
                              <div>
                                <Label className="text-[11px]">🎯 当前目标</Label>
                                <Input
                                  {...register(`characters.${idx}.goal`)}
                                  placeholder="角色想要达成的事…"
                                  onChange={(e) => {
                                    const v = e.target.value
                                    setValue(`characters.${idx}.goal`, v)
                                    if (!c?.personality?.desire || c.personality.desire === c?.goal) {
                                      setValue(`characters.${idx}.personality.desire`, v)
                                    }
                                  }}
                                />
                              </div>

                              <div className="space-y-2 rounded-md border border-game-border/50 bg-game-bg/20 p-3">
                                <Label className="text-[11px] text-game-text">🧠 人格核心</Label>
                                <div>
                                  <Label className="text-[10px] text-game-muted">欲望</Label>
                                  <Input
                                    {...register(`characters.${idx}.personality.desire`)}
                                    placeholder="角色最想要什么…"
                                    className="text-xs h-8 mt-0.5"
                                    onChange={(e) => {
                                      const v = e.target.value
                                      setValue(`characters.${idx}.personality.desire`, v)
                                      if (!c?.goal || c.goal === c?.personality?.desire) {
                                        setValue(`characters.${idx}.goal`, v)
                                      }
                                    }}
                                  />
                                </div>
                                <div>
                                  <Label className="text-[10px] text-game-muted">恐惧</Label>
                                  <Input
                                    {...register(`characters.${idx}.personality.fear`)}
                                    placeholder="角色最害怕什么…"
                                    className="text-xs h-8 mt-0.5"
                                  />
                                </div>
                                <div>
                                  <Label className="text-[10px] text-game-accent">禁忌</Label>
                                  <Input
                                    {...register(`characters.${idx}.personality.taboo`)}
                                    placeholder="触犯时即使高好感也会拒绝…"
                                    className="text-xs h-8 mt-0.5 border-game-secret/40"
                                  />
                                </div>
                                <div>
                                  <Label className="text-[10px] text-game-accent">🔒 秘密</Label>
                                  <Textarea
                                    value={c?.personality?.secret ?? c?.secret ?? ''}
                                    onChange={(e) => {
                                      const v = e.target.value
                                      setValue(`characters.${idx}.secret`, v)
                                      setValue(`characters.${idx}.personality.secret`, v)
                                    }}
                                    placeholder="隐藏秘密，用于制造剧情爆点…"
                                    rows={2}
                                    className="text-xs border-game-secret/40 bg-game-secret/10 text-game-accent placeholder:text-game-dim"
                                  />
                                </div>
                                <div>
                                  <Label className="text-[10px] text-game-muted">价值观</Label>
                                  <TagInput
                                    value={c?.personality?.values || []}
                                    onChange={(values) => setValue(`characters.${idx}.personality.values`, values)}
                                    presets={PERSONALITY_BRAIN_VALUE_PRESETS}
                                    placeholder="荣誉、自由…"
                                    color="primary"
                                    compact
                                  />
                                </div>
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
                                  compact
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

                              <div>
                                <Label className="text-[11px]">📜 背景故事</Label>
                                <Textarea
                                  {...register(`characters.${idx}.background`)}
                                  placeholder="成长经历、过往事件…"
                                  className="text-xs min-h-[56px] resize-y"
                                />
                              </div>

                              <div>
                                <Label className="text-[11px]">✨ 特殊能力</Label>
                                <Input
                                  {...register(`characters.${idx}.special_ability`)}
                                  placeholder="如：读心术、剑术天赋…"
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
        </div>

        <div className={activeSection === 'relations' ? '' : 'hidden'}>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t('world.relations', lang)}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2 rounded-md border border-game-border/60 bg-game-bg/30 p-3">
                  <Label className="text-xs text-game-muted">关系阶段（全局）</Label>
                  <TagInput
                    value={relStages || []}
                    onChange={(tags) => setValue('rel_stages', tags, { shouldValidate: true })}
                    presets={DEFAULT_STAGES}
                    placeholder="如：初识、试探、信任…"
                    color="primary"
                  />
                  {errors.rel_stages && (
                    <p className="text-[11px] text-game-danger">{errors.rel_stages.message}</p>
                  )}
                  <div className="flex items-center gap-3 pt-1">
                    <Label className="text-xs text-game-muted shrink-0">
                      {adultMode ? `初始${tTheme('stat.affection', lang, true)}` : '初始好感度'}
                    </Label>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={watch('rel_affection') ?? 0}
                      onChange={(e) => setValue('rel_affection', parseInt(e.target.value, 10))}
                      className="flex-1 accent-game-primary"
                    />
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      value={watch('rel_affection') ?? 0}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10)
                        if (!isNaN(v)) setValue('rel_affection', Math.max(0, Math.min(100, v)))
                      }}
                      className="w-16 h-7 text-xs text-center tabular-nums"
                    />
                  </div>
                </div>

                {/* Who's involved — 每个NPC与主角的独立多维关系 */}
                {(() => {
                  const allChars = watch('characters') || []
                  const mainChar = allChars.find((c: { isMain?: boolean }) => c.isMain) || allChars[0]
                  const npcs = allChars.filter((c: { isMain?: boolean; name?: string }) => !c.isMain && c.name)
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
                        const r = characterRelations[c.name] || DEFAULT_REL
                        const updateRel = (k: string, v: unknown) => {
                          setCharacterRelations(prev => ({
                            ...prev,
                            [c.name]: { ...(prev[c.name] || DEFAULT_REL), [k]: v }
                          }))
                        }
                        return (
                          <div key={c.name} className="bg-game-surface border border-game-border rounded-md p-3 space-y-2">
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                              <div className="flex flex-wrap items-center gap-2 text-sm min-w-0">
                                <span className="font-bold text-game-accent truncate max-w-[40%]">{mainChar?.name || '主角'}</span>
                                <span className="text-game-accent shrink-0">↔</span>
                                <span className="font-bold text-game-primary truncate max-w-[40%]">{c.name}</span>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                <AIButton
                                  loading={generating === `rel-${c.name}`}
                                  error={fieldErrors[`rel-${c.name}`]}
                                  onClick={() => handleRelGen(c.name)}
                                >
                                  生成关系
                                </AIButton>
                                <select
                                  value={r.relationshipType}
                                  onChange={(e) => { updateRel('relationshipType', e.target.value) }}
                                  className="bg-game-bg border border-game-border rounded-md px-2 py-0.5 text-[10px] text-game-text"
                                >
                                  {REL_TYPES.map(t => <option key={t} value={t}>{REL_LABELS[t]}</option>)}
                                </select>
                              </div>
                            </div>
                            <div className="space-y-2">
                              {DIMS.map(([label, key]) => {
                                const val = (r as unknown as Record<string,number>)[key] ?? 50
                                const barColor = key === 'hostility' ? '#da3633' : '#58a6ff'
                                return (
                                  <div key={key} className="flex items-center gap-2">
                                    <span className="text-xs text-game-dim w-14 shrink-0">{label}</span>
                                    <input
                                      type="number"
                                      min={0} max={100} value={val}
                                      onChange={(e) => { const v = parseInt(e.target.value); if (!isNaN(v)) updateRel(key, Math.max(0, Math.min(100, v))) }}
                                      onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault() }}
                                      className="w-14 text-center text-xs h-8 bg-game-bg border border-game-border rounded text-game-text shrink-0"
                                    />
                                    <div className="flex-1 h-2.5 bg-game-border rounded-full overflow-hidden min-w-[4rem]">
                                      <div className="h-full rounded-full transition-all" style={{width: `${val}%`, background: barColor}} />
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                            <TagInput
                              value={r.tags || []}
                              onChange={(tags) => updateRel('tags', tags)}
                              presets={['青梅竹马','救命恩人','秘密共享','竞争意识','单向暗恋','互相试探','过去纠葛','命运绑定','生死之交','不共戴天']}
                              placeholder="关系标签…"
                              color="accent"
                            />
                          </div>
                        )
                      })}
                    </div>
                  )
                })()}

                {/* Current custom stats */}
                {(() => {
                  const stats = customStats || []
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
                      const data = await generateRules({ adultMode,
                        title: getValues('title'),
                        world: getValues('world') + '\n势力：' + JSON.stringify(factions || []) + '\n物品：' + JSON.stringify(artifacts || []),
                        genre: getValues('genre').join('/'),
                        char1_name: allChars[0]?.name || '主角',
                        char1_role: allChars[0]?.role_tags?.[0] || '',
                        char2_name: allChars[1]?.name || '',
                        char2_role: allChars[1]?.role_tags?.[0] || '',
                      })
                      if (data.stages?.length) setValue('rel_stages', data.stages)
                      if (data.stats?.length) setCustomStats( data.stats)
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
        </div>

        <div className={activeSection === 'artifacts' ? '' : 'hidden'}>
            <Card>
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle className="flex items-center gap-2 text-sm shrink-0">
                  {t('world.artifacts', lang)}
                </CardTitle>
                <div className="flex flex-wrap gap-1.5">
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    disabled={generating === 'artifacts-all'}
                    onClick={async () => {
                      setGenerating('artifacts-all')
                      showStatus('正在批量生成关键物品…', 'loading')
                      const current = artifacts || []
                      const { charNames, facNames } = getOwnerNames(getValues('characters'), factions || [])
                      const newArts: typeof current = []
                      for (let i = 0; i < 3; i++) {
                        try {
                          const data = await generateField({ adultMode,
                            field: 'artifact',
                            title: getValues('title'),
                            world: getValues('world'),
                            genre: getValues('genre').join('/'),
                            context: JSON.stringify({ characters: charNames, factions: facNames }),
                          })
                          const art = artifactFromGenData(data as Record<string, unknown>, charNames, facNames)
                          if (art) newArts.push(art)
                        } catch { /* continue */ }
                      }
                      setArtifacts( [...current, ...newArts])
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
                      const current = artifacts || []
                      setArtifacts( [...current, {
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
                <div className="space-y-3">
                  {(artifacts || []).map((art, idx) => (
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
                                    const data = await generateField({ adultMode,
                                      field: 'artifact',
                                      title: getValues('title'),
                                      world: getValues('world'),
                                      genre: getValues('genre').join('/'),
                                      context: JSON.stringify(getOwnerNames(getValues('characters'), factions || [])),
                                    })
                                    const { charNames, facNames } = getOwnerNames(getValues('characters'), factions || [])
                                    const art = artifactFromGenData(data as Record<string, unknown>, charNames, facNames)
                                    if (art) {
                                      const current = artifacts || []
                                      current[idx] = art
                                      setArtifacts( [...current])
                                    }
                                    showStatus('✅ 物品生成完成', 'success')
                                  } catch (e) { showStatus(`❌ ${(e as Error).message}`, 'error') }
                                  setGenerating(null)
                                }}
                              >生成</AIButton>
                              <button
                                type="button"
                                onClick={() => {
                                  const current = artifacts || []
                                  current.splice(idx, 1)
                                  setArtifacts( [...current])
                                }}
                                className="text-game-dim hover:text-game-danger transition-colors text-sm"
                              >✕</button>
                            </div>
                          </div>
                          <Input
                            value={art.name}
                            onChange={(e) => {
                              const current = artifacts || []
                              current[idx] = { ...current[idx], name: e.target.value }
                              setArtifacts( [...current])
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
                                const current = artifacts || []
                                current[idx] = { ...current[idx], type: e.target.value as 'personal' | 'faction' | 'world' }
                                setArtifacts( [...current])
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
                                const current = artifacts || []
                                current[idx] = { ...current[idx], ownerId: e.target.value }
                                setArtifacts( [...current])
                              }}
                              placeholder="持有者（角色名/势力名）"
                              className="flex-1 text-xs h-7"
                            />
                            <Input
                              type="number"
                              value={art.importance}
                              onChange={(e) => {
                                const current = artifacts || []
                                current[idx] = { ...current[idx], importance: Math.max(1, Math.min(100, parseInt(e.target.value) || 50)) }
                                setArtifacts( [...current])
                              }}
                              className="w-16 text-xs h-7"
                              placeholder="重要度"
                            />
                          </div>
                          <Input
                            value={art.description}
                            onChange={(e) => {
                              const current = artifacts || []
                              current[idx] = { ...current[idx], description: e.target.value }
                              setArtifacts( [...current])
                            }}
                            placeholder="物品描述（用途、背景…）"
                            className="text-xs h-7"
                          />
                          <div className="flex gap-1 flex-wrap">
                            <TagInput
                              value={art.tags || []}
                              onChange={(tags) => {
                                const current = artifacts || []
                                current[idx] = { ...current[idx], tags }
                                setArtifacts( [...current])
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
                  {(artifacts || []).length === 0 && (
                    <p className="text-game-dim text-xs text-center py-4">
                      暂无关键物品 · 点击「✨ 模块生成」AI 批量生成，或「➕ 添加物品」手动填写
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
        </div>
      </form>
    </InspectorPanel>
  )

  usePageShell({
    navItems,
    activeNavId: activeSection,
    onNavSelect: (id) => {
      setActiveSection(id as BuilderSection)
      setSelectedNodeId(null)
    },
    inspector,
  })

  return (
    <>
      <StatusToast message={aiStatus} type={aiStatusType} />
      <div className="h-full w-full relative">
        <WorldGraphCanvas
          input={graphInput}
          layoutKey={graphLayoutKey + (Object.keys(nodePositions).length ? '-manual' : '-auto')}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
          onPositionsChange={setNodePositions}
          onApplyDemo={applyDemoGraph}
          onRelayout={relayoutGraph}
          onGraphUpdate={(update) => {
            if (update.factions) {
              setFactions((prev) =>
                update.factions!.map((f, i) => ({ ...(prev[i] || {}), ...f })),
              )
            }
            if (update.characters) {
              const current = getValues('characters')
              setValue(
                'characters',
                update.characters.map((c, i) =>
                  mapFormCharacter({
                    ...(current[i] || {}),
                    ...c,
                  } as FormValues['characters'][number], factions),
                ) as FormValues['characters'],
              )
            }
            if (update.artifacts) {
              setArtifacts((prev) =>
                update.artifacts!.map((a, i) => ({ ...(prev[i] || {}), ...a })),
              )
            }
            if (update.characterRelations) setCharacterRelations(update.characterRelations as typeof characterRelations)
          }}
        />
        <SectionHeader
          icon={Globe}
          title={watchAll.title || t('world.core', lang)}
          subtitle={t('brand.subtitle', lang)}
          status={generating ? 'active' : 'idle'}
          className="absolute top-3 left-12 md:left-4 z-10 pointer-events-none max-w-md"
        />
      </div>
    </>
  )
}
