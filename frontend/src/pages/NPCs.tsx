import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { StatusToast } from '@/components/StatusToast'
import { CharacterCard } from '@/components/CharacterCard'
import { InspectorPanel } from '@/components/layout/InspectorPanel'
import { usePageShell } from '@/components/layout/usePageShell'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { GlassPanel } from '@/components/neural/GlassPanel'
import { Users } from 'lucide-react'
import { getNpcs, generateNpc, type NpcData } from '@/lib/api'
import { logger } from '@/lib/logger'
import { useAppSettings } from '@/hooks/useAppSettings'
import { t } from '@/lib/i18n'

type FilterType = 'all' | 'main' | 'npc'

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
        <p className="text-xs text-game-dim">角色由对局与记忆系统自动维护</p>
        <Button variant="neural" size="sm" onClick={handleGenerate} disabled={generating}>
          {generating ? '生成中…' : '✨ AI 生成角色'}
        </Button>
      </GlassPanel>

      {/* Filters */}
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

      {/* Character Grid */}
      {characters.length === 0 && !loading ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16 space-y-4"
        >
          <p className="text-game-muted text-lg">还没有角色</p>
          <p className="text-game-dim text-sm">点击上方「✨ AI生成角色」创建第一个角色，或前往「新故事」创建完整故事</p>
          <Button variant="neural" onClick={() => window.location.href = '/new'}>
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
