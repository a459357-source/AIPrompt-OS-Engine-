import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getNarrativeState, getNarrativeNode } from '@/lib/api'
import { logger } from '@/lib/logger'

export default function NarrativeHub() {
  const navigate = useNavigate()
  const [currentId, setCurrentId] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const state = await getNarrativeState()
      setCurrentId(state.current_event_id || '')
    } catch (e) {
      logger.error('NarrativeHub', 'load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const continueStory = async () => {
    const target = currentId || 'midnight_talk'
    try {
      await getNarrativeNode(target)
      navigate(`/visual/narrative/node/${encodeURIComponent(target)}`)
    } catch {
      navigate(`/visual/narrative/node/midnight_talk`)
    }
  }

  if (loading) return <p className="text-sm text-game-dim p-2">加载叙事入口…</p>

  return (
    <div className="max-w-lg space-y-4">
      <Card className="border-neural-cyan/20 bg-neural-glass/30">
        <CardHeader>
          <CardTitle className="text-base">叙事入口中心</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-game-muted">
            从事件、角色或世界地点进入剧情节点。本层只做路由与展示，不触发生成。
          </p>
          <Button className="w-full gap-2" onClick={() => void continueStory()}>
            <Play className="w-4 h-4" />
            {currentId ? '继续叙事' : '进入故事'}
          </Button>
          {currentId && (
            <p className="text-[10px] font-neural-mono text-game-dim">
              当前节点：{currentId}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
