import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { StatusToast } from '@/components/StatusToast'
import { getGameState, nextTurn } from '@/lib/api'
import { logger } from '@/lib/logger'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'

interface CharInfo {
  name: string
  role: string
  relation: string
  level: string
  affection?: number
}

function AffectionBar({ value }: { value: number; name?: string }) {
  const filled = Math.floor(value / 10)
  const empty = 10 - filled
  return (
    <span className="text-xs text-game-accent tracking-[2px] select-none">
      {'█'.repeat(filled)}{'░'.repeat(empty)}
    </span>
  )
}

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
  const [customInput, setCustomInput] = useState('')
  const [showCustomInput, setShowCustomInput] = useState(false)

  const loadGame = useCallback(async () => {
    setLoading(true)
    setError('')
    logger.info('Game', 'Loading game state...')
    try {
      const data = await getGameState()
      if (data.error) { setError(data.error); setLoading(false); return }
      setStory(data.story)
      setOptions(data.options || [])
      const st = data.state as Record<string, unknown>
      setTurn((st.turn as number) || 1)
      setStatus((st.status as string) || 'SETUP')
      setScene((st.scene as string) || '')
      const chars = st.characters as Record<string, CharInfo> | undefined
      if (chars) {
        setCharacters(Object.values(chars).map((c) => ({
          ...c, affection: 50,
        })))
      }
      logger.info('Game', `Loaded: turn=${st.turn}`)
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('Game', 'Load failed', { error: msg })
      setError(msg)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadGame() }, [loadGame])

  const handleChoice = useCallback(async (choice: string) => {
    setChoosing(true)
    logger.info('Game', `Choice: ${choice}`)
    try {
      const data = await nextTurn(choice)
      if (data.error) { setError(data.error); setChoosing(false); return }
      setStory(data.story)
      setOptions(data.options || [])
      setTurn(data.state.turn)
      setStatus(data.state.status)
      setScene(data.state.scene)
      const chars = data.state.characters as Record<string, CharInfo> | undefined
      if (chars) setCharacters(Object.values(chars).map((c) => ({ ...c, affection: 50 })))
    } catch (e) {
      const msg = (e as Error).message || String(e)
      logger.error('Game', 'Choice failed', { error: msg })
      setError(msg)
    }
    setChoosing(false)
  }, [])

  const hasGame = !loading && !error && story.length > 0

  // Shared character list component
  const CharacterList = () => (
    <div className="space-y-4">
      {characters.length === 0 && (
        <p className="text-xs text-game-dim text-center py-4">暂无角色数据</p>
      )}
      {characters.map((c) => (
        <div key={c.name} className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{c.name}</span>
            <Badge variant="outline" size="sm">{c.role}</Badge>
          </div>
          {c.relation && <p className="text-xs text-game-muted">{c.relation}</p>}
          <div className="flex items-center gap-2">
            <AffectionBar value={c.affection ?? 50} />
            <span className="text-xs text-game-dim tabular-nums">{c.affection ?? 50}%</span>
          </div>
          <Separator />
        </div>
      ))}
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto">
      <StatusToast
        message={loading ? '正在生成开篇剧情…' : error ? `❌ ${error}` : ''}
        type={loading ? 'loading' : error ? 'error' : 'info'}
      />

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center min-h-[50vh]">
          <motion.div animate={{ opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1.5 }}
            className="text-game-muted text-lg flex items-center gap-3"
          >
            <span className="inline-block w-4 h-4 border-2 border-game-accent/30 border-t-game-accent rounded-full animate-spin" />
            AI 正在生成开篇剧情…
          </motion.div>
        </div>
      )}

      {/* Error */}
      {!loading && error && !story && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center justify-center min-h-[50vh] gap-6 text-center"
        >
          <div className="text-5xl">❌</div>
          <h2 className="text-lg font-bold text-game-danger">加载失败</h2>
          <p className="text-game-muted text-sm">{error}</p>
          <div className="flex gap-3">
            <Button variant="outline" onClick={loadGame}>🔄 重试</Button>
            <Button variant="glow" onClick={() => window.location.href = '/new'}>✨ 创建新故事</Button>
          </div>
        </motion.div>
      )}

      {/* Game */}
      {hasGame && (
        <div className="space-y-4">
          {/* Top status bar */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-sm">
              <Badge variant="primary" size="sm">📖 第 {turn} 轮</Badge>
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
              {scene && <span className="text-game-dim text-xs truncate max-w-[200px]">📍 {scene}</span>}
            </div>

            {/* Character drawer trigger */}
            <Sheet>
              <SheetTrigger className="cursor-pointer">
                <Button variant="ghost" size="sm" className="gap-1.5 text-game-muted hover:text-game-text pointer-events-none">
                  👥 角色
                  {characters.length > 0 && (
                    <Badge variant="accent" size="sm" className="ml-0.5">{characters.length}</Badge>
                  )}
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-72">
                <SheetHeader>
                  <SheetTitle>👥 角色状态</SheetTitle>
                </SheetHeader>
                <div className="mt-6">
                  <CharacterList />
                </div>
              </SheetContent>
            </Sheet>
          </div>

          {/* Story */}
          <Card>
            <CardContent className="pt-6 md:px-8">
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
                    className="text-game-text leading-relaxed text-[16px] mb-5"
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
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-2">
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

                {/* Custom input toggle */}
                {!showCustomInput ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={choosing}
                    onClick={() => setShowCustomInput(true)}
                    className="w-full text-game-dim hover:text-game-text border border-dashed border-game-border"
                  >
                    ✏️ 自定义输入…
                  </Button>
                ) : (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="flex gap-2"
                  >
                    <input
                      value={customInput}
                      onChange={(e) => setCustomInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && customInput.trim()) {
                          handleChoice(customInput.trim())
                          setCustomInput('')
                          setShowCustomInput(false)
                        }
                        if (e.key === 'Escape') {
                          setShowCustomInput(false)
                          setCustomInput('')
                        }
                      }}
                      placeholder="输入你想做的事…"
                      disabled={choosing}
                      autoFocus
                      className="flex-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm text-game-text placeholder:text-game-dim focus:outline-none focus:border-game-primary"
                    />
                    <Button
                      variant="accent"
                      size="sm"
                      disabled={choosing || !customInput.trim()}
                      onClick={() => {
                        if (customInput.trim()) {
                          handleChoice(customInput.trim())
                          setCustomInput('')
                          setShowCustomInput(false)
                        }
                      }}
                    >
                      确定
                    </Button>
                  </motion.div>
                )}
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
      )}
    </div>
  )
}
