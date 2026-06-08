import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Image } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { getEventTimeline, type VisualEventView } from '@/lib/api'
import { logger } from '@/lib/logger'
import { cn } from '@/lib/utils'

function EventRow({ event }: { event: VisualEventView }) {
  const [open, setOpen] = useState(false)
  const thumb = event.scene_images[0] || event.linked_assets[0]?.image_url

  return (
    <Card className="border-neural-cyan/10 bg-neural-glass/20">
      <button
        type="button"
        className="w-full flex items-start gap-3 p-3 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="w-16 h-16 shrink-0 rounded overflow-hidden bg-neural-void/80">
          {thumb ? (
            <img src={thumb} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Image className="w-6 h-6 text-game-dim" />
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {open ? <ChevronDown className="w-4 h-4 shrink-0" /> : <ChevronRight className="w-4 h-4 shrink-0" />}
            <span className="font-medium text-sm truncate">{event.display_name}</span>
            <Badge variant="outline" className="text-[10px] shrink-0">回合 {event.created_turn}</Badge>
          </div>
          <div className="text-[10px] text-game-dim font-neural-mono mt-1 truncate">{event.event_id}</div>
        </div>
      </button>

      {open && (
        <CardContent className="pt-0 pb-3 px-3 space-y-3 border-t border-neural-cyan/10">
          {event.scene_images.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {event.scene_images.map((url) => (
                <img key={url} src={url} alt="" className="rounded border border-neural-cyan/10 aspect-video object-cover" />
              ))}
            </div>
          )}
          {event.characters.length > 0 && (
            <div>
              <div className="text-[10px] text-game-dim mb-1">参与角色</div>
              <div className="flex flex-wrap gap-1">
                {event.characters.map((name) => (
                  <Badge key={name} variant="outline" className="text-xs">{name}</Badge>
                ))}
              </div>
            </div>
          )}
          <div className="text-[10px] font-neural-mono text-game-dim space-y-0.5">
            <div>identity_id: {event.identity_id || '—'}</div>
            <div>prompt_hash: {event.prompt_hash?.slice(0, 16) || '—'}</div>
            <div>timestamp: {event.timestamp || '—'}</div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

export default function EventTimeline() {
  const [events, setEvents] = useState<VisualEventView[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setEvents(await getEventTimeline())
      setError('')
    } catch (e) {
      setError((e as Error).message)
      logger.error('EventTimeline', 'load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  if (loading) return <p className="text-sm text-game-dim p-2">加载事件时间线…</p>
  if (error) return <p className="text-sm text-red-400 p-2">{error}</p>
  if (!events.length) {
    return <p className="text-sm text-game-dim p-2">尚无事件场景图。</p>
  }

  return (
    <div className={cn('h-full overflow-auto space-y-2 pr-1')}>
      {events.map((ev) => <EventRow key={ev.event_id} event={ev} />)}
    </div>
  )
}
