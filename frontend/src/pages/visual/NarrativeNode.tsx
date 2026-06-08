import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Play, Users, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  getNarrativeNode,
  routeNarrativeChoice,
  type NarrativeNode,
} from '@/lib/api'
import { logger } from '@/lib/logger'

export default function NarrativeNodePage() {
  const { eventId } = useParams<{ eventId: string }>()
  const navigate = useNavigate()
  const [node, setNode] = useState<NarrativeNode | null>(null)
  const [loading, setLoading] = useState(true)
  const [routing, setRouting] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (id: string) => {
    setLoading(true)
    try {
      setNode(await getNarrativeNode(id))
      setError('')
    } catch (e) {
      setError((e as Error).message)
      logger.error('NarrativeNode', 'load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (eventId) void load(eventId)
  }, [eventId, load])

  const onChoice = async (choiceId: string) => {
    if (!node) return
    setRouting(true)
    try {
      const res = await routeNarrativeChoice(node.event_id, choiceId)
      if (!res.ok || !res.next_event_id) {
        setError(res.error || '路由失败')
        return
      }
      navigate(`/visual/narrative/node/${encodeURIComponent(res.next_event_id)}`, { replace: false })
      if (res.node) setNode(res.node)
      else await load(res.next_event_id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRouting(false)
    }
  }

  if (loading) return <p className="text-sm text-game-dim p-2">加载叙事节点…</p>
  if (error && !node) return <p className="text-sm text-red-400 p-2">{error}</p>
  if (!node) return null

  return (
    <div className="h-full overflow-auto space-y-4 pr-1">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-neural-display text-neural-cyan">{node.label}</h2>
          <p className="text-[10px] font-neural-mono text-game-dim">{node.event_id}</p>
        </div>
        <Badge variant="outline" className="text-[10px]">叙事模式</Badge>
      </div>

      <Card className="border-neural-cyan/15 bg-neural-glass/20 overflow-hidden">
        <div className="aspect-video max-h-[320px] bg-neural-void/80">
          {node.scene_image ? (
            <img src={node.scene_image} alt={node.label} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-game-dim text-sm">暂无场景图</div>
          )}
        </div>
      </Card>

      <Card className="border-neural-cyan/10 bg-neural-glass/20">
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            情境
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-game-text pb-4">{node.context}</CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card className="border-neural-cyan/10 bg-neural-glass/20">
          <CardHeader className="py-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Users className="w-4 h-4" />
              参与角色
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pb-4">
            {node.characters.length ? node.characters.map((c) => (
              <div key={c.identity_id || c.name} className="text-xs">
                <span className="font-medium">{c.name}</span>
                <span className="text-game-dim font-neural-mono ml-2">{c.identity_id || '—'}</span>
              </div>
            )) : <p className="text-xs text-game-dim">暂无绑定角色</p>}
          </CardContent>
        </Card>

        <Card className="border-neural-cyan/10 bg-neural-glass/20">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">当前状态</CardTitle>
          </CardHeader>
          <CardContent className="text-xs font-neural-mono space-y-1 pb-4">
            <div>回合 {node.current_state.turn}</div>
            <div>场景 {node.current_state.scene || '—'}</div>
            <div>导演 {node.current_state.director_state || '—'}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-neural-cyan/20 bg-neural-glass/30">
        <CardHeader className="py-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Play className="w-4 h-4 text-neural-cyan" />
            选择（驱动下一节点）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pb-4">
          {node.choices.map((c, idx) => (
            <Button
              key={c.choice_id}
              variant="outline"
              className="w-full justify-start text-left h-auto py-3 whitespace-normal"
              disabled={routing}
              onClick={() => void onChoice(c.choice_id)}
            >
              <span className="text-neural-cyan font-neural-mono mr-2">[{idx + 1}]</span>
              {c.text}
            </Button>
          ))}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  )
}
