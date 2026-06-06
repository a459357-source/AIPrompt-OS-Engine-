import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { StatusToast } from '@/components/StatusToast'
import { getGameState, nextTurn } from '@/lib/api'
import { logger } from '@/lib/logger'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'

interface CharInfo {
  name: string
  role: string
  relation: string
  level: string
  affection?: number
}

// ── Affection Bar ──
function AffectionBar({ value, name }: { value: number; name: string }) {
  const filled = Math.floor(value / 10)
  const empty = 10 - filled
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-game-muted w-12 truncate">{name}</span>
      <div className="flex-1 flex items-center gap-0.5">
        <span className="text-xs text-game-accent tracking-[2px] select-none">
          {'█'.repeat(filled)}{'░'.repeat(empty)}
        </span>
      </div>
      <span className="text-xs text-game-dim w-8 text-right tabular-nums">{value}%</span>
    </div>
  )
}

// ── Main Page ──
export default function Game() {
  const [story, setStory] = useState('')
  const [options, setOptions] = useState<string[]>([])
  const [turn, setTurn] = useState(0)
  const [status, setStatus] = useState('SETUP')
  const [scene, setScene] = useState('')
  const [characters, setCharacters] = useState<CharInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [choosing, setChoosing] = useState(false)

  // Load initial game state
  const loadGame = useCallback(async () => {
    setLoading(true)
    setError('')
    logger.info('Game', 'Loading game state...')
    try {
      const data = await getGameState()
      if (data.error) {
        setError(data.error)
        setLoading(false)
        return
      }
      setStory(data.story)
      setOptions(data.options || [])
      const state = data.state as Record<string, unknown>
      setTurn((state.turn as number) || 1)
      setStatus((state.status as string) || 'SETUP')
      setScene((state.scene as string) || '')

      // Parse characters
      const chars = state.characters as Record<string, { name: string; role: string; relation: string; level: string }> | undefined
      if (chars) {
        const list: CharInfo[] = Object.values(chars).map((c) => ({
          name: c.name || '',
          role: c.role || '',
          relation: c.relation || '',
          level: c.level || 'L0',
          affection: 50, // default
        }))
        setCharacters(list)
      }
      logger.info('Game', `Loaded: turn=${state.turn}, status=${state.status}`)
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('Game', 'Failed to load game', { error: msg })
      setError(msg)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadGame() }, [loadGame])

  // Make a choice
  const handleChoice = useCallback(async (choice: string) => {
    setChoosing(true)
    logger.info('Game', `Choice: ${choice}`)
    try {
      const data = await nextTurn(choice)
      if (data.error) {
        setError(data.error)
        setChoosing(false)
        return
      }
      setStory(data.story)
      setOptions(data.options || [])
      const s = data.state
      setTurn(s.turn)
      setStatus(s.status)
      setScene(s.scene)

      // Update characters
      const chars = s.characters as Record<string, { name: string; role: string; relation: string; level: string }> | undefined
      if (chars) {
        const list: CharInfo[] = Object.values(chars).map((c) => ({
          name: c.name || '',
          role: c.role || '',
          relation: c.relation || '',
          level: c.level || 'L0',
          affection: 50,
        }))
        setCharacters(list)
      }
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('Game', 'Choice failed', { error: msg })
      setError(msg)
    }
    setChoosing(false)
  }, [])

  const hasGame = !loading && !error && story.length > 0

  return (
    <div className="max-w-5xl mx-auto">
      <StatusToast
        message={loading ? '正在生成开篇剧情…' : error ? `❌ ${error}` : ''}
        type={loading ? 'loading' : error ? 'error' : 'info'}
      />

      {loading && (
        <div className="flex items-center justify-center min-h-[50vh]">
          <motion.div
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className="text-game-muted text-lg flex items-center gap-3"
          >
            <span className="inline-block w-4 h-4 border-2 border-game-accent/30 border-t-game-accent rounded-full animate-spin" />
            AI 正在生成开篇剧情…
          </motion.div>
        </div>
      )}

      {!loading && error && !story && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center justify-center min-h-[50vh] gap-6 text-center"
        >
          <div className="text-5xl">❌</div>
          <div className="space-y-2">
            <h2 className="text-lg font-bold text-game-danger">加载失败</h2>
            <p className="text-game-muted text-sm">{error}</p>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={loadGame}>🔄 重试</Button>
            <Button variant="glow" onClick={() => window.location.href = '/new'}>
              ✨ 创建新故事
            </Button>
          </div>
        </motion.div>
      )}

      {hasGame && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* Character Sidebar (desktop) */}
          <Card className="hidden lg:block lg:col-span-1 h-fit sticky top-16">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">👥 角色状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {characters.length === 0 && (
                <p className="text-xs text-game-dim">暂无角色数据</p>
              )}
              {characters.map((c) => (
                <div key={c.name} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-game-text">{c.name}</span>
                    <Badge variant="outline" size="sm">{c.role}</Badge>
                  </div>
                  <p className="text-xs text-game-muted">{c.relation}</p>
                  <AffectionBar value={c.affection ?? 50} name="" />
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
                {characters.map((c) => (
                  <div key={c.name} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{c.name}</span>
                      <Badge variant="outline" size="sm">{c.role}</Badge>
                    </div>
                    <AffectionBar value={c.affection ?? 50} name="" />
                    <Separator />
                  </div>
                ))}
              </div>
            </SheetContent>
          </Sheet>

          {/* Main Story Area */}
          <div className="lg:col-span-3 space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <span>📖 第 {turn} 轮</span>
                  <Badge
                    variant={
                      status === 'TENSION' ? 'warning' :
                      status === 'CLIMAX' ? 'danger' :
                      status === 'COOLDOWN' ? 'success' : 'primary'
                    }
                    size="sm"
                  >
                    {status}
                  </Badge>
                  {scene && <span className="text-game-dim text-xs">📍 {scene}</span>}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <motion.div
                  key={turn}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                >
                  {story.split('\n').filter(Boolean).map((paragraph, i) => (
                    <motion.p
                      key={i}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.08 }}
                      className="text-game-text leading-relaxed text-[15px] mb-4"
                    >
                      {paragraph}
                    </motion.p>
                  ))}
                </motion.div>
              </CardContent>
            </Card>

            {/* Choices */}
            <AnimatePresence>
              {options.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-2"
                >
                  <p className="text-xs text-game-muted font-medium">🎯 做出你的选择</p>
                  {options.map((choice, i) => (
                    <Button
                      key={`${turn}-${i}`}
                      variant="outline"
                      disabled={choosing}
                      onClick={() => handleChoice(String.fromCharCode(65 + i))}
                      className="w-full justify-start text-left h-auto py-3 px-4 hover:bg-game-primary/10 hover:border-game-primary/50 transition-all"
                    >
                      <span className="text-game-accent mr-2 font-bold shrink-0">
                        {String.fromCharCode(65 + i)}.
                      </span>
                      <span className="text-sm">{choice}</span>
                    </Button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {choosing && (
              <div className="text-center text-game-muted text-sm py-4">
                <span className="inline-block w-3 h-3 border-2 border-game-accent/30 border-t-game-accent rounded-full animate-spin mr-2" />
                AI 正在生成下一段剧情…
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
