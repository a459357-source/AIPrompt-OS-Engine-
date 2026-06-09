import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Image, Link2, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { enterNarrativeFromFaction, enterNarrativeFromLocation } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getWorldExplorer, type VisualAssetItem, type VisualIdentityView, type VisualWorldView } from '@/lib/api'
import { logger } from '@/lib/logger'

function PreviewCard({ item, onEnter, enterLabel }: { item: VisualAssetItem; onEnter?: () => void; enterLabel?: string }) {
  return (
    <div className="rounded-lg border border-neural-cyan/15 bg-neural-glass/30 overflow-hidden">
      <div className="aspect-video bg-neural-void/80">
        {item.image_url ? (
          <img src={item.image_url} alt={item.display_name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Image className="w-8 h-8 text-game-dim" />
          </div>
        )}
      </div>
      <div className="p-2 space-y-2">
        <div className="text-sm font-medium truncate">{item.display_name || item.entity_id}</div>
        <div className="text-[10px] text-game-dim font-neural-mono truncate">{item.identity_id || '—'}</div>
        {onEnter && (
          <Button size="sm" variant="outline" className="w-full h-7 text-xs gap-1" onClick={onEnter}>
            <Play className="w-3 h-3" />
            {enterLabel || '进入区域剧情'}
          </Button>
        )}
      </div>
    </div>
  )
}

function CharacterChip({ item }: { item: VisualIdentityView }) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-md border border-neural-cyan/10 bg-neural-glass/20">
      <div className="w-10 h-10 rounded overflow-hidden bg-neural-void shrink-0">
        {item.latest_image ? (
          <img src={item.latest_image} alt="" className="w-full h-full object-cover object-top" />
        ) : null}
      </div>
      <div className="min-w-0">
        <div className="text-sm truncate">{item.entity_name}</div>
        <div className="text-[10px] text-game-dim font-neural-mono truncate">{item.identity_id}</div>
      </div>
    </div>
  )
}

export default function WorldExplorer() {
  const navigate = useNavigate()
  const [world, setWorld] = useState<VisualWorldView | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setWorld(await getWorldExplorer())
      setError('')
    } catch (e) {
      setError((e as Error).message)
      logger.error('WorldExplorer', 'load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  if (loading) return <p className="text-sm text-game-dim p-2">加载世界视图…</p>
  if (error) return <p className="text-sm text-red-400 p-2">{error}</p>
  if (!world) return null

  const empty = !world.locations.length && !world.factions.length && !world.characters.length

  return (
    <div className="h-full overflow-auto space-y-6 pr-1">
      {/* ── World Summary Header ── */}
      {world.world_summary && (
        <div className="rounded-lg border border-neural-cyan/15 bg-neural-glass/30 p-4 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h2 className="text-lg font-bold text-game-accent">{world.world_summary.title}</h2>
              <p className="text-xs text-game-muted">{world.world_summary.genre} · {world.world_summary.era}</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-game-dim">
              <span>第 {world.world_summary.turn} 回合</span>
              <span>·</span>
              <span>{world.world_summary.status}</span>
            </div>
          </div>
          {world.generation_progress && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(['characters', 'factions', 'locations', 'events'] as const).map((scope) => {
                const p = world.generation_progress![scope]
                const pct = p?.total ? Math.round((p.ready / p.total) * 100) : 0
                const labelMap: Record<string, string> = {
                  characters: '角色', factions: '势力', locations: '地点', events: '事件',
                }
                return (
                  <div key={scope} className="space-y-1">
                    <div className="flex justify-between text-[10px] text-game-dim">
                      <span>{labelMap[scope]}</span>
                      <span>{p?.ready ?? 0}/{p?.total ?? 0}</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-neural-void/80 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-game-accent transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {empty && (
        <p className="text-sm text-game-dim">尚无世界视觉资产。</p>
      )}

      <section>
        <h3 className="text-xs text-game-dim mb-2 uppercase tracking-wide">地点</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          {world.locations.map((l) => (
            <PreviewCard
              key={l.asset_id}
              item={l}
              onEnter={async () => {
                const res = await enterNarrativeFromLocation(l.display_name || l.entity_id)
                navigate(`/visual/narrative/node/${encodeURIComponent(res.narrative_event_id)}`)
              }}
            />
          ))}
          {!world.locations.length && <p className="text-sm text-game-dim col-span-full">暂无地点图</p>}
        </div>
      </section>

      <section>
        <h3 className="text-xs text-game-dim mb-2 uppercase tracking-wide">势力</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          {world.factions.map((f) => (
            <div key={f.asset_id} className="rounded-lg border border-neural-cyan/15 bg-neural-glass/30 overflow-hidden">
              <div className="p-3 flex items-center gap-3">
                <div className="w-8 h-8 rounded-md overflow-hidden border border-game-border/50 shrink-0 bg-neural-void/60">
                  {f.image_url ? (
                    <img src={f.image_url} alt={f.display_name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-game-dim">
                      <span className="text-[10px]">🏛</span>
                    </div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{f.display_name || f.entity_id}</div>
                  <div className="text-[10px] text-game-dim font-neural-mono truncate">{f.identity_id || '—'}</div>
                </div>
              </div>
              <div className="px-3 pb-3">
                <Button size="sm" variant="outline" className="w-full h-7 text-xs gap-1" onClick={async () => {
                  const res = await enterNarrativeFromFaction(f.display_name || f.entity_id)
                  navigate(`/visual/narrative/node/${encodeURIComponent(res.narrative_event_id)}`)
                }}>
                  <Play className="w-3 h-3" />
                  进入势力剧情
                </Button>
              </div>
            </div>
          ))}
          {!world.factions.length && <p className="text-sm text-game-dim col-span-full">暂无势力图</p>}
        </div>
      </section>

      <section>
        <h3 className="text-xs text-game-dim mb-2 uppercase tracking-wide">角色（Identity 绑定）</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {world.characters.map((c) => <CharacterChip key={c.identity_id} item={c} />)}
        </div>
      </section>

      {world.character_links.length > 0 && (
        <section>
          <Card className="border-neural-cyan/10 bg-neural-glass/20">
            <CardHeader className="py-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Link2 className="w-4 h-4 text-neural-cyan" />
                角色关系（只读）
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {world.character_links.map((link, i) => (
                <Badge key={`${link.from}-${link.to}-${i}`} variant="outline" className="text-xs">
                  {link.from} → {link.to}{link.label ? ` (${link.label})` : ''}
                </Badge>
              ))}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  )
}
