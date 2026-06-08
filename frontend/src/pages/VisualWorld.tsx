import { useCallback, useEffect, useState } from 'react'
import { Image, Map, Clapperboard, Bug, Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { usePageShell } from '@/components/layout/usePageShell'
import { getVisualWorldData, type VisualAssetItem, type VisualWorldData } from '@/lib/api'
import { logger } from '@/lib/logger'

type VisualTab = 'gallery' | 'world' | 'events' | 'debug'

function AssetCard({ item, onSelect }: { item: VisualAssetItem; onSelect: (item: VisualAssetItem) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      className="text-left rounded-lg border border-neural-cyan/15 bg-neural-glass/30 hover:border-neural-cyan/40 transition-colors overflow-hidden"
    >
      <div className="aspect-square bg-neural-void/80 flex items-center justify-center">
        {item.image_url ? (
          <img src={item.image_url} alt={item.display_name} className="w-full h-full object-cover" />
        ) : (
          <Image className="w-10 h-10 text-game-dim" />
        )}
      </div>
      <div className="p-3 space-y-1">
        <div className="font-medium text-sm truncate">{item.display_name || item.entity_id}</div>
        <div className="text-[10px] text-game-dim font-neural-mono truncate">{item.identity_id || '—'}</div>
        <Badge variant="outline" className="text-[9px]">{item.provider}</Badge>
      </div>
    </button>
  )
}

function DebugPanel({ item }: { item: VisualAssetItem | null }) {
  if (!item) {
    return (
      <Card className="border-neural-cyan/10 bg-neural-glass/20">
        <CardContent className="p-4 text-sm text-game-dim">选择一项资产查看调试信息</CardContent>
      </Card>
    )
  }
  const rows: [string, string][] = [
    ['identity_id', item.identity_id],
    ['entity_id', item.entity_id],
    ['asset_id', item.asset_id],
    ['prompt_hash', item.prompt_hash],
    ['seed', String(item.seed ?? '')],
    ['provider', item.provider],
    ['cache', item.cache_status],
    ['image_path', item.image_path],
  ]
  return (
    <Card className="border-neural-cyan/10 bg-neural-glass/20">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Bug className="w-4 h-4 text-neural-cyan" />
          Visual Debug
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs font-neural-mono">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[120px_1fr] gap-2">
            <span className="text-game-dim">{k}</span>
            <span className="break-all text-game-text">{v || '—'}</span>
          </div>
        ))}
        {item.locked_descriptors && item.locked_descriptors.length > 0 && (
          <div className="pt-2 border-t border-neural-cyan/10">
            <div className="text-game-dim mb-1">locked_descriptors</div>
            <ul className="list-disc pl-4 space-y-0.5">
              {item.locked_descriptors.map((d) => <li key={d}>{d}</li>)}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function VisualWorld() {
  usePageShell({ hideShellPanels: true })
  const [data, setData] = useState<VisualWorldData | null>(null)
  const [tab, setTab] = useState<VisualTab>('gallery')
  const [selected, setSelected] = useState<VisualAssetItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const d = await getVisualWorldData()
      setData(d)
      setError('')
    } catch (e) {
      setError((e as Error).message)
      logger.error('VisualWorld', 'load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const empty = !loading && !error && data && data.characters.length === 0
    && data.locations.length === 0 && data.factions.length === 0 && data.events.length === 0

  return (
    <div className="h-full flex flex-col gap-4 p-4 overflow-hidden">
      <div className="flex items-start justify-between gap-3">
        <SectionHeader
          icon={Image}
          title="视觉世界"
          subtitle="只读浏览角色、地点、势力与事件场景（V6.5）"
        />
        {data && (
          <Badge variant="outline" className="font-neural-mono text-[10px] shrink-0 mt-2">
            {data.status.provider} · cache {data.status.cache_enabled ? 'on' : 'off'}
          </Badge>
        )}
      </div>

      {loading && <p className="text-sm text-game-dim">加载中…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {empty && (
        <p className="text-sm text-game-dim">
          尚无视觉资产。在游戏中通过视觉系统生成后，将在此展示。
        </p>
      )}

      {data && (
        <Tabs value={tab} onValueChange={(v) => setTab(v as VisualTab)} className="flex-1 flex flex-col min-h-0">
          <TabsList className="shrink-0">
            <TabsTrigger value="gallery" className="gap-1"><Users className="w-3.5 h-3.5" />角色</TabsTrigger>
            <TabsTrigger value="world" className="gap-1"><Map className="w-3.5 h-3.5" />世界</TabsTrigger>
            <TabsTrigger value="events" className="gap-1"><Clapperboard className="w-3.5 h-3.5" />事件</TabsTrigger>
            <TabsTrigger value="debug" className="gap-1"><Bug className="w-3.5 h-3.5" />调试</TabsTrigger>
          </TabsList>

          <TabsContent value="gallery" className="flex-1 overflow-auto mt-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {data.characters.map((c) => (
                <AssetCard key={c.asset_id} item={c} onSelect={setSelected} />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="world" className="flex-1 overflow-auto mt-3 space-y-6">
            <div>
              <h3 className="text-xs text-game-dim mb-2">地点</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {data.locations.map((l) => <AssetCard key={l.asset_id} item={l} onSelect={setSelected} />)}
              </div>
            </div>
            <div>
              <h3 className="text-xs text-game-dim mb-2">势力</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {data.factions.map((f) => <AssetCard key={f.asset_id} item={f} onSelect={setSelected} />)}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="events" className="flex-1 overflow-auto mt-3">
            <div className="space-y-3">
              {data.events.map((ev) => (
                <button
                  key={ev.asset_id}
                  type="button"
                  onClick={() => setSelected(ev)}
                  className="w-full flex gap-3 p-3 rounded-lg border border-neural-cyan/15 hover:border-neural-cyan/35 text-left"
                >
                  <div className="w-20 h-20 shrink-0 rounded bg-neural-void/80 overflow-hidden">
                    {ev.image_url ? (
                      <img src={ev.image_url} alt={ev.display_name} className="w-full h-full object-cover" />
                    ) : null}
                  </div>
                  <div className="min-w-0">
                    <div className="font-medium text-sm">{ev.display_name}</div>
                    <div className="text-[10px] text-game-dim font-neural-mono">回合 {ev.created_turn}</div>
                    <div className="text-[10px] text-game-dim truncate">{ev.identity_id}</div>
                  </div>
                </button>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="debug" className="flex-1 overflow-auto mt-3 grid lg:grid-cols-2 gap-4">
            <DebugPanel item={selected} />
            <Card className="border-neural-cyan/10 bg-neural-glass/20">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">全部资产 ({data.debug.assets.length})</CardTitle>
              </CardHeader>
              <CardContent className="max-h-[420px] overflow-auto space-y-2 text-xs font-neural-mono">
                {data.debug.assets.map((a) => (
                  <button
                    key={`${a.scope}-${a.asset_id}`}
                    type="button"
                    onClick={() => setSelected(a)}
                    className="block w-full text-left p-2 rounded hover:bg-neural-cyan/5"
                  >
                    <span className="text-neural-cyan">{a.scope}</span> · {a.display_name}
                    <span className="text-game-dim"> · {a.prompt_hash?.slice(0, 8)}</span>
                  </button>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
