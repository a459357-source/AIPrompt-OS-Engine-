import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { CharacterCard } from '@/components/CharacterCard'

// ── Mock characters ──
const MOCK_CHARACTERS = [
  {
    id: '1', name: '艾琳·维斯特', isMain: false,
    role_tags: ['考古语言学家', '学者'],
    personality_tags: ['热情', '好奇', '冒失'],
    appearance: '金棕色短发，翡翠绿眼瞳，常戴一副半框眼镜',
    relationship: ['工作伙伴', '朋友'],
    goal: '解读上古碑文，揭开失落文明的真相',
    secret: '她其实是某个古代预言中提到的"钥匙"',
    background: '帝国中央大学的年轻教授',
    special_ability: '古文字解读',
  },
  {
    id: '2', name: '林夜', isMain: false,
    role_tags: ['退役军官', '护卫'],
    personality_tags: ['冷静', '忠诚', '寡言'],
    appearance: '黑色短发，锐利的灰色眼瞳，左脸有一道旧伤疤',
    relationship: ['护卫', '下属'],
    goal: '保护主角安全，完成最后一次任务',
    secret: '曾奉命暗中监视主角的一举一动',
    background: '前帝国第七舰队陆战队长',
    special_ability: '近身格斗',
  },
  {
    id: '3', name: '雪乃', isMain: false,
    role_tags: ['神秘少女', '异能者'],
    personality_tags: ['温柔', '敏感', '内向'],
    appearance: '银白长发及腰，紫色眼瞳，肤色苍白近乎透明',
    relationship: ['被保护者', '暗恋对象'],
    goal: '寻找自己失散多年的亲人',
    secret: '她的异能来自一次非法基因实验',
    background: '从研究所逃出的实验体',
    special_ability: '精神感应',
  },
  {
    id: '0', name: '主角（你）', isMain: true,
    role_tags: ['冒险者', '自由佣兵'],
    personality_tags: ['勇敢', '善良', '灵活'],
    appearance: '',
    relationship: [],
    goal: '在这个崩坏的世界中寻找生存的意义',
    secret: '',
    background: '',
    special_ability: '',
  },
]

type FilterType = 'all' | 'main' | 'npc'

export default function NPCs() {
  const [filter, setFilter] = useState<FilterType>('all')
  const [search, setSearch] = useState('')

  const filtered = MOCK_CHARACTERS.filter((c) => {
    if (filter === 'main' && !c.isMain) return false
    if (filter === 'npc' && c.isMain) return false
    if (search && !c.name.includes(search) && !c.role_tags.some((t) => t.includes(search))) return false
    return true
  })

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-game-accent font-bold text-xl">👥 角色管理</h1>
          <p className="text-game-muted text-sm mt-1">
            共 {MOCK_CHARACTERS.length} 位角色 · 管理关系、目标和秘密
          </p>
        </div>
        <Button variant="glow" size="sm">
          ✨ AI生成角色
        </Button>
      </div>

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
            { key: 'all', label: '全部' },
            { key: 'main', label: '⭐ 主角' },
            { key: 'npc', label: '👤 NPC' },
          ] as const).map((f) => (
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
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <AnimatePresence>
          {filtered.map((c) => (
            <CharacterCard
              key={c.id}
              character={c}
              index={parseInt(c.id)}
              isMain={c.isMain}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16"
        >
          <p className="text-game-muted text-lg">未找到匹配的角色</p>
          <p className="text-game-dim text-sm mt-1">试试调整搜索条件</p>
        </motion.div>
      )}

      {/* Stats Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">📊 角色统计</CardTitle>
          <CardDescription>角色关系与指标概览</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            {[
              { label: '总角色数', value: MOCK_CHARACTERS.length, icon: '👥' },
              { label: '主角', value: MOCK_CHARACTERS.filter((c) => c.isMain).length, icon: '⭐' },
              { label: 'NPC', value: MOCK_CHARACTERS.filter((c) => !c.isMain).length, icon: '👤' },
              { label: '关系总数', value: '8', icon: '💞' },
            ].map((stat) => (
              <div key={stat.label} className="space-y-1">
                <span className="text-2xl">{stat.icon}</span>
                <p className="text-2xl font-bold text-game-accent">{stat.value}</p>
                <p className="text-xs text-game-muted">{stat.label}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
