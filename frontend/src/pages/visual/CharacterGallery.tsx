import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Image, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { enterNarrativeFromCharacter } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getCharacterGallery, type VisualIdentityView } from '@/lib/api'
import { logger } from '@/lib/logger'
import { cn } from '@/lib/utils'

export default function CharacterGallery() {
  const navigate = useNavigate()
  const [items, setItems] = useState<VisualIdentityView[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [assetIndex, setAssetIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getCharacterGallery()
      setItems(data)
      setError('')
      if (data.length && !selectedId) setSelectedId(data[0].identity_id)
    } catch (e) {
      setError((e as Error).message)
      logger.error('CharacterGallery', 'load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const selected = items.find((x) => x.identity_id === selectedId) ?? null
  const assets = selected?.all_assets ?? []
  const currentAsset = assets[assetIndex] ?? assets[assets.length - 1]

  useEffect(() => { setAssetIndex(0) }, [selectedId])

  if (loading) return <p className="text-sm text-game-dim p-2">加载角色画廊…</p>
  if (error) return <p className="text-sm text-red-400 p-2">{error}</p>
  if (!items.length) {
    return (
      <p className="text-sm text-game-dim p-2">
        尚无角色视觉资产。生成后将按 identity_id 聚合展示。
      </p>
    )
  }

  return (
    <div className="h-full grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-3 min-h-0">
      <Card className="border-neural-cyan/10 bg-neural-glass/20 overflow-hidden flex flex-col min-h-0">
        <CardHeader className="py-3 px-3 shrink-0">
          <CardTitle className="text-sm">角色列表</CardTitle>
        </CardHeader>
        <CardContent className="p-2 flex-1 overflow-auto space-y-1">
          {items.map((item) => (
            <button
              key={item.identity_id}
              type="button"
              onClick={() => setSelectedId(item.identity_id)}
              className={cn(
                'w-full text-left p-2 rounded-md text-sm transition-colors',
                selectedId === item.identity_id
                  ? 'bg-neural-cyan/10 border border-neural-cyan/25'
                  : 'hover:bg-neural-glass/50 border border-transparent',
              )}
            >
              <div className="font-medium truncate">{item.entity_name || item.identity_id}</div>
              <div className="text-[10px] text-game-dim font-neural-mono truncate">{item.identity_id}</div>
              <div className="text-[10px] text-game-dim">{item.all_assets.length} 张资产</div>
            </button>
          ))}
        </CardContent>
      </Card>

      {selected && (
        <div className="flex flex-col gap-3 min-h-0 overflow-auto">
          <Card className="border-neural-cyan/10 bg-neural-glass/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{selected.entity_name}</CardTitle>
              <p className="text-[10px] font-neural-mono text-game-dim break-all">{selected.identity_id}</p>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="aspect-[3/4] max-h-[360px] mx-auto rounded-lg overflow-hidden bg-neural-void/80 border border-neural-cyan/10">
                {(currentAsset?.image_url || selected.latest_image) ? (
                  <img
                    src={currentAsset?.image_url || selected.latest_image}
                    alt={selected.entity_name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Image className="w-12 h-12 text-game-dim" />
                  </div>
                )}
              </div>

              {assets.length > 1 && (
                <div className="flex items-center justify-center gap-2">
                  <button
                    type="button"
                    className="p-1 rounded hover:bg-neural-cyan/10"
                    onClick={() => setAssetIndex((i) => Math.max(0, i - 1))}
                    disabled={assetIndex <= 0}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-xs text-game-dim font-neural-mono">
                    {assetIndex + 1} / {assets.length}
                  </span>
                  <button
                    type="button"
                    className="p-1 rounded hover:bg-neural-cyan/10"
                    onClick={() => setAssetIndex((i) => Math.min(assets.length - 1, i + 1))}
                    disabled={assetIndex >= assets.length - 1}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}

              <div className="flex flex-wrap gap-1">
                {Object.entries(selected.traits).map(([k, v]) => (
                  <Badge key={k} variant="outline" className="text-[10px]">{k}: {String(v)}</Badge>
                ))}
              </div>
              <Button
                size="sm"
                className="gap-1"
                onClick={async () => {
                  const res = await enterNarrativeFromCharacter(selected.entity_name)
                  navigate(`/visual/narrative/node/${encodeURIComponent(res.narrative_event_id)}`)
                }}
              >
                <Play className="w-3.5 h-3.5" />
                进入该角色剧情
              </Button>
            </CardContent>
          </Card>

          {assets.length > 0 && (
            <Card className="border-neural-cyan/10 bg-neural-glass/20 shrink-0">
              <CardHeader className="py-2 px-3">
                <CardTitle className="text-xs text-game-dim">历史视觉资产</CardTitle>
              </CardHeader>
              <CardContent className="p-2 flex gap-2 overflow-x-auto">
                {assets.map((a, idx) => (
                  <button
                    key={a.asset_id}
                    type="button"
                    onClick={() => setAssetIndex(idx)}
                    className={cn(
                      'shrink-0 w-16 h-16 rounded overflow-hidden border',
                      idx === assetIndex ? 'border-neural-cyan' : 'border-neural-cyan/15',
                    )}
                  >
                    {a.image_url ? (
                      <img src={a.image_url} alt="" className="w-full h-full object-cover" />
                    ) : null}
                  </button>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
