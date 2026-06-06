import { useState } from 'react'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'

// ── Mock character data ──
const MOCK_CHARS = [
  { name: '艾琳', role: '考古语言学家', relation: '工作伙伴', affection: 68 },
  { name: '林夜', role: '退役军官', relation: '护卫', affection: 45 },
  { name: '雪乃', role: '神秘少女', relation: '被保护者', affection: 82 },
]

// ── Affection Bar Component ──
function AffectionBar({ value, name }: { value: number; name: string }) {
  const filled = Math.floor(value / 10)
  const empty = 10 - filled
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-game-muted w-12 truncate">{name}</span>
      <div className="flex-1 flex items-center gap-0.5">
        <span className="text-xs text-game-accent tracking-[2px]">{'█'.repeat(filled)}{'░'.repeat(empty)}</span>
      </div>
      <span className="text-xs text-game-dim w-8 text-right tabular-nums">{value}%</span>
    </div>
  )
}

// ── Main Page ──
export default function Game() {
  const [story, setStory] = useState<string[]>([])
  const [choices, setChoices] = useState<string[]>([])
  const [turn, setTurn] = useState(0)
  const [status, setStatus] = useState('SETUP')

  // This would be populated by the API
  const hasGame = story.length > 0

  return (
    <div className="max-w-5xl mx-auto">
      {!hasGame ? (
        /* ── Empty State ── */
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center justify-center min-h-[60vh] gap-6 text-center"
        >
          <div className="text-6xl animate-pulse-glow rounded-full w-24 h-24 flex items-center justify-center bg-game-primary/10 border border-game-primary/20">
            🎮
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-bold text-game-accent">尚未开始游戏</h2>
            <p className="text-game-muted text-sm max-w-md">
              前往「新故事」页面创建你的世界，或者加载一个存档，开始属于你的冒险旅程。
            </p>
          </div>
          <div className="flex gap-3">
            <Button variant="glow" onClick={() => window.location.href = '/new'}>
              ✨ 创建新故事
            </Button>
            <Button variant="outline" disabled>
              📂 加载存档
            </Button>
          </div>
        </motion.div>
      ) : (
        /* ── Game Layout ── */
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* Character Sidebar (desktop) */}
          <Card className="hidden lg:block lg:col-span-1 h-fit">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">👥 角色状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {MOCK_CHARS.map((c) => (
                <div key={c.name} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-game-text">{c.name}</span>
                    <Badge variant="outline" size="sm">{c.role}</Badge>
                  </div>
                  <p className="text-xs text-game-muted">{c.relation}</p>
                  <AffectionBar value={c.affection} name="" />
                  <Separator className="mt-2" />
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Mobile character drawer */}
          <Sheet>
            <SheetTrigger className="lg:hidden fixed right-4 bottom-20 z-40">
              <Button variant="accent" size="icon" className="rounded-full shadow-lg w-12 h-12">
                👥
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-72">
              <SheetHeader>
                <SheetTitle>👥 角色状态</SheetTitle>
              </SheetHeader>
              <div className="mt-4 space-y-4">
                {MOCK_CHARS.map((c) => (
                  <div key={c.name} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{c.name}</span>
                      <Badge variant="outline" size="sm">{c.role}</Badge>
                    </div>
                    <AffectionBar value={c.affection} name="" />
                    <Separator />
                  </div>
                ))}
              </div>
            </SheetContent>
          </Sheet>

          {/* Main Story Area */}
          <div className="lg:col-span-3 space-y-4">
            <Card className="min-h-[50vh]">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <span>📖 第 {turn} 轮</span>
                  <Badge variant={status === 'TENSION' ? 'warning' : status === 'CLIMAX' ? 'danger' : 'primary'}>
                    {status}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="prose prose-invert max-w-none">
                {story.map((paragraph, i) => (
                  <motion.p
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="text-game-text leading-relaxed text-[15px] mb-4"
                  >
                    {paragraph}
                  </motion.p>
                ))}
              </CardContent>
            </Card>

            {/* Choices */}
            {choices.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-game-muted font-medium">🎯 做出你的选择</p>
                {choices.map((choice, i) => (
                  <Button
                    key={i}
                    variant="outline"
                    className="w-full justify-start text-left h-auto py-3 px-4 hover:bg-game-primary/10 hover:border-game-primary/50 transition-all"
                  >
                    <span className="text-game-accent mr-2 font-bold">{String.fromCharCode(65 + i)}.</span>
                    <span className="text-sm">{choice}</span>
                  </Button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
