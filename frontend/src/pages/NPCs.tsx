import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { StatusToast } from '@/components/StatusToast'
import { CharacterCard } from '@/components/CharacterCard'
import { TagInput } from '@/components/TagInput'
import { InspectorPanel } from '@/components/layout/InspectorPanel'
import { usePageShell } from '@/components/layout/usePageShell'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { GlassPanel } from '@/components/neural/GlassPanel'
import { Users } from 'lucide-react'
import {
  getNpcs,
  generateNpc,
  patchNpcPersonality,
  EMPTY_PERSONALITY_BRAIN,
  type NpcData,
  type PersonalityBrain,
} from '@/lib/api'
import { logger } from '@/lib/logger'
import { useAppSettings } from '@/hooks/useAppSettings'
import { t } from '@/lib/i18n'

type FilterType = 'all' | 'main' | 'npc'

function mergePersonality(npc: NpcData | null): PersonalityBrain {
  if (!npc?.personality) return { ...EMPTY_PERSONALITY_BRAIN }
  return {
    desire: npc.personality.desire || npc.goal || '',
    fear: npc.personality.fear || '',
    taboo: npc.personality.taboo || '',
    secret: npc.personality.secret || npc.secret || '',
    values: npc.personality.values?.length
      ? npc.personality.values
      : [...(npc.personality_tags || [])],
  }
}

function PersonalityBrainEditor({
  npc,
  onSaved,
}: {
  npc: NpcData
  onSaved: (personality: PersonalityBrain) => void
}) {
  const [draft, setDraft] = useState<PersonalityBrain>(() => mergePersonality(npc))
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')

  useEffect(() => {
    setDraft(mergePersonality(npc))
    setSaveMsg('')
  }, [npc.name])

  const handleSave = async () => {
    setSaving(true)
    setSaveMsg('')
    try {
      const result = await patchNpcPersonality(npc.name, draft)
      if (result.error) {
        setSaveMsg(result.error)
        return
      }
      const saved = result.personality || draft
      setDraft(saved)
      onSaved(saved)
      setSaveMsg('已保存')
    } catch (e) {
      setSaveMsg((e as Error).message || String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3 pt-3 border-t border-game-border/60">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-medium text-game-text">人格核心</h4>
        <Button variant="primary" size="sm" onClick={handleSave} disabled={saving}>
          {saving ? '保存中…' : '保存'}
        </Button>
      </div>
      {saveMsg && (
        <p className={`text-xs ${saveMsg === '已保存' ? 'text-game-success' : 'text-game-danger'}`}>{saveMsg}</p>
      )}
      <div className="space-y-2">
        <label className="text-[10px] text-game-muted">欲望</label>
        <Input
          value={draft.desire}
          onChange={(e) => setDraft((p) => ({ ...p, desire: e.target.value }))}
          placeholder="角色最想要什么"
        />
      </div>
      <div className="space-y-2">
        <label className="text-[10px] text-game-muted">恐惧</label>
        <Input
          value={draft.fear}
          onChange={(e) => setDraft((p) => ({ ...p, fear: e.target.value }))}
          placeholder="角色最害怕什么"
        />
      </div>
      <div className="space-y-2">
        <label className="text-[10px] text-game-accent">禁忌</label>
        <Input
          value={draft.taboo}
          onChange={(e) => setDraft((p) => ({ ...p, taboo: e.target.value }))}
          placeholder="触犯时即使高好感也会拒绝"
        />
      </div>
      <div className="space-y-2">
        <label className="text-[10px] text-game-accent">秘密</label>
        <Textarea
          value={draft.secret}
          onChange={(e) => setDraft((p) => ({ ...p, secret: e.target.value }))}
          placeholder="隐藏秘密"
          rows={2}
          className="text-xs"
        />
      </div>
      <div className="space-y-2">
        <label className="text-[10px] text-game-muted">价值观</label>
        <TagInput
          value={draft.values}
          onChange={(values) => setDraft((p) => ({ ...p, values }))}
          presets={['荣誉', '自由', '血统', '忠诚', '利益', '正义']}
          placeholder="输入后回车添加"
          color="primary"
          compact
        />
      </div>
    </div>
  )
}

export default function NPCs() {
  const { language } = useAppSettings()
  const lang = language as 'zh' | 'en' | 'ja'
  const [characters, setCharacters] = useState<NpcData[]>([])
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [stats, setStats] = useState({ total: 0, main: 0, npc: 0, avg_trust: 0 })
  const [filter, setFilter] = useState<FilterType>('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)

  const loadNpcs = useCallback(async () => {
    setLoading(true)
    logger.info('NPCs', 'Loading characters...')
    try {
      const data = await getNpcs()
      if (data.error) { setError(data.error); setLoading(false); return }
      setError('')
      setCharacters(data.characters)
      setStats(data.stats)
    } catch (e) {
      setError((e as Error).message || String(e))
      logger.error('NPCs', 'Load failed', { error: String(e) })
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadNpcs() }, [loadNpcs])

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    logger.info('NPCs', 'Generating new NPC...')
    try {
      const npc = await generateNpc()
      if (npc.error) { setError(npc.error); setGenerating(false); return }
      setError('')
      setCharacters((prev) => [...prev, npc])
      setStats((prev) => ({
        total: prev.total + 1,
        main: prev.main,
        npc: prev.npc + 1,
        avg_trust: Math.round((prev.avg_trust * prev.total + npc.trust_pct) / (prev.total + 1)),
      }))
    } catch (e) {
      setError((e as Error).message || String(e))
      logger.error('NPCs', 'Generate failed', { error: String(e) })
    }
    setGenerating(false)
  }, [])

  const handlePersonalitySaved = useCallback((name: string, personality: PersonalityBrain) => {
    setCharacters((prev) =>
      prev.map((c) => (c.name === name ? { ...c, personality } : c)),
    )
  }, [])

  const filtered = characters.filter((c) => {
    if (filter === 'main' && !c.isMain) return false
    if (filter === 'npc' && c.isMain) return false
    if (search && !c.name.includes(search) && !c.role_tags.some((t) => t.includes(search))) return false
    return true
  })

  const selected = selectedIndex != null ? filtered[selectedIndex] : null

  const navItems = [
    { id: 'all', label: '全部' },
    { id: 'main', label: '主角' },
    { id: 'npc', label: 'NPC' },
  ]

  usePageShell({
    navItems,
    activeNavId: filter,
    inspector: selected ? (
      <InspectorPanel title={selected.name}>
        <CharacterCard
          character={{
            name: selected.name,
            isMain: selected.isMain,
            role_tags: selected.role_tags,
            personality_tags: selected.personality_tags,
            appearance: selected.appearance,
            relationship: selected.relationship,
            goal: selected.goal,
            secret: selected.secret,
            background: selected.background,
            special_ability: selected.special_ability,
          }}
          index={0}
          isMain={selected.isMain}
          trustPct={selected.trust_pct}
          className="border-none shadow-none bg-transparent"
        />
        <PersonalityBrainEditor
          npc={selected}
          onSaved={(personality) => handlePersonalitySaved(selected.name, personality)}
        />
      </InspectorPanel>
    ) : (
      <InspectorPanel title={t('world.characters', lang)}>
        <p className="text-sm text-game-muted">选择人物卡片查看详情</p>
      </InspectorPanel>
    ),
  })

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6 space-y-4">
      <StatusToast
        message={loading ? '加载角色数据…' : error ? `❌ ${error}` : ''}
        type={loading ? 'loading' : error ? 'error' : 'info'}
      />

      <SectionHeader
        icon={Users}
        title={t('world.characters', lang)}
        subtitle={`共 ${stats.total} 位 · 平均好感 ${stats.avg_trust}%`}
        status={loading ? 'active' : 'idle'}
      />
      <GlassPanel className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <p className="text-xs text-game-dim">角色由对局与记忆系统自动维护；人格核心影响 AI 行为决策</p>
        <Button variant="neural" size="sm" onClick={handleGenerate} disabled={generating}>
          {generating ? '生成中…' : '✨ AI 生成角色'}
        </Button>
      </GlassPanel>

      <div className="flex flex-col sm:flex-row gap-3">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索角色名或身份…"
          className="max-w-xs"
        />
        <div className="flex gap-1">
          {([
            { key: 'all' as const, label: '全部' },
            { key: 'main' as const, label: '⭐ 主角' },
            { key: 'npc' as const, label: '👤 NPC' },
          ]).map((f) => (
            <Button
              key={f.key}
              variant={filter === f.key ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </Button>
          ))}
        </div>
      </div>

      {characters.length === 0 && !loading ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16 space-y-4"
        >
          <p className="text-game-muted text-lg">还没有角色</p>
          <p className="text-game-dim text-sm">点击上方「✨ AI生成角色」创建第一个角色，或前往「新故事」创建完整故事</p>
          <Button variant="neural" onClick={() => { window.location.href = '/new' }}>
            前往世界构建
          </Button>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <AnimatePresence>
            {filtered.map((c, i) => (
              <div
                key={c.name + i}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedIndex(i)}
                onKeyDown={(e) => { if (e.key === 'Enter') setSelectedIndex(i) }}
                className={`cursor-pointer transition-transform ${selectedIndex === i ? 'ring-2 ring-neural-cyan rounded-lg scale-[1.02]' : 'hover:scale-[1.01]'}`}
              >
              <CharacterCard
                key={c.name + i}
                character={{
                  name: c.name,
                  isMain: c.isMain,
                  role_tags: c.role_tags,
                  personality_tags: c.personality_tags,
                  appearance: c.appearance,
                  relationship: c.relationship,
                  goal: c.goal,
                  secret: c.secret,
                  background: c.background,
                  special_ability: c.special_ability,
                }}
                index={i}
                isMain={c.isMain}
                trustPct={c.trust_pct}
              />
              </div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {filtered.length === 0 && characters.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-16">
          <p className="text-game-muted text-lg">未找到匹配的角色</p>
          <p className="text-game-dim text-sm mt-1">试试调整搜索条件</p>
        </motion.div>
      )}
    </div>
  )
}
