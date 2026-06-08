import { useCallback, useEffect, useState } from 'react'
import { Bug } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getVisualDebug, type VisualDebugAsset } from '@/lib/api'
import { logger } from '@/lib/logger'
import { cn } from '@/lib/utils'

function DebugDetail({ item }: { item: VisualDebugAsset }) {
  const rows: [string, string][] = [
    ['registry_id', item.registry_id],
    ['identity_id', item.identity_id],
    ['asset_id', item.asset_id],
    ['prompt_hash', item.prompt_hash],
    ['seed', String(item.seed ?? '')],
    ['provider', item.provider],
    ['cache_hit', String(item.cache_hit)],
    ['cache_status', item.cache_status],
    ['scope', item.scope || ''],
    ['image_path', item.image_path],
  ]
  return (
    <Card className="border-neural-cyan/10 bg-neural-glass/20">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Bug className="w-4 h-4 text-neural-cyan" />
          {item.display_name || item.asset_id}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-xs font-neural-mono">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[110px_1fr] gap-2">
            <span className="text-game-dim">{k}</span>
            <span className="break-all">{v || '—'}</span>
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

export default function VisualDebug() {
  const [assets, setAssets] = useState<VisualDebugAsset[]>([])
  const [selected, setSelected] = useState<VisualDebugAsset | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getVisualDebug()
      setAssets(data.assets)
      if (data.assets.length) setSelected(data.assets[0])
      setError('')
    } catch (e) {
      setError((e as Error).message)
      logger.error('VisualDebug', 'load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  if (loading) return <p className="text-sm text-game-dim p-2">加载调试数据…</p>
  if (error) return <p className="text-sm text-red-400 p-2">{error}</p>

  return (
    <div className="h-full grid grid-cols-1 lg:grid-cols-2 gap-3 min-h-0 overflow-hidden">
      <Card className="border-neural-cyan/10 bg-neural-glass/20 flex flex-col min-h-0">
        <CardHeader className="py-3 shrink-0">
          <CardTitle className="text-sm">资产列表 ({assets.length})</CardTitle>
        </CardHeader>
        <CardContent className="p-2 flex-1 overflow-auto space-y-1">
          {assets.map((a) => (
            <button
              key={`${a.scope}-${a.registry_id}`}
              type="button"
              onClick={() => setSelected(a)}
              className={cn(
                'w-full text-left p-2 rounded text-xs font-neural-mono transition-colors',
                selected?.registry_id === a.registry_id && selected?.scope === a.scope
                  ? 'bg-neural-cyan/10 border border-neural-cyan/25'
                  : 'hover:bg-neural-glass/40 border border-transparent',
              )}
            >
              <span className="text-neural-cyan">{a.scope}</span> · {a.display_name}
              <div className="flex gap-1 mt-1">
                <Badge variant="outline" className="text-[9px]">{a.cache_hit ? 'hit' : 'miss'}</Badge>
                <Badge variant="outline" className="text-[9px]">{a.prompt_hash?.slice(0, 8)}</Badge>
              </div>
            </button>
          ))}
        </CardContent>
      </Card>
      <div className="overflow-auto min-h-0">
        {selected ? <DebugDetail item={selected} /> : (
          <p className="text-sm text-game-dim p-2">选择资产查看 identity / cache / prompt 状态</p>
        )}
      </div>
    </div>
  )
}
