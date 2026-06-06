import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { StatusToast } from '@/components/StatusToast'
import { getDashboard, type DashboardData } from '@/lib/api'
import { logger } from '@/lib/logger'

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    logger.info('Dashboard', 'Loading...')
    try {
      const d = await getDashboard()
      if (d.error) { setError(d.error); setLoading(false); return }
      setData(d)
    } catch (e) {
      setError((e as Error).message || String(e))
      logger.error('Dashboard', 'Load failed', { error: String(e) })
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadDashboard() }, [loadDashboard])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <StatusToast message="加载数据…" type="loading" />
      </div>
    )
  }

  if (!data || error) {
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center justify-center min-h-[40vh] gap-6 text-center"
      >
        <div className="text-5xl">📊</div>
        <div className="space-y-2">
          <h2 className="text-lg font-bold text-game-accent">还没有数据</h2>
          <p className="text-game-muted text-sm max-w-md">
            {error || '开始一个新故事后，这里会展示你的故事进度、角色关系变化、字数统计等数据可视化。'}
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadDashboard}>🔄 重试</Button>
          <Button variant="glow" onClick={() => window.location.href = '/new'}>
            ✨ 创建第一个故事
          </Button>
        </div>
      </motion.div>
    )
  }

  const statsData = [
    { label: '总轮次', value: String(data.turn), icon: '🔄' },
    { label: '角色数', value: String(data.character_count), icon: '👥' },
    { label: '总字数', value: data.word_count > 1000 ? `${(data.word_count / 1000).toFixed(1)}k` : String(data.word_count), icon: '📝' },
    { label: '分支节点', value: String(data.node_count), icon: '🔀' },
    { label: 'API 调用', value: String(data.api_calls), icon: '🤖' },
    { label: 'Tokens', value: data.total_tokens > 1000 ? `${(data.total_tokens / 1000).toFixed(1)}k` : String(data.total_tokens), icon: '💎' },
  ]

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-game-accent font-bold text-xl">📊 仪表盘</h1>
          <p className="text-game-muted text-sm mt-1">
            第 {data.turn} 轮 · {data.status} · 📍 {data.scene}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadDashboard}>🔄 刷新</Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {statsData.map((stat) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card className="text-center hover:shadow-md transition-shadow">
              <CardContent className="pt-5 pb-4 space-y-1.5">
                <span className="text-xl">{stat.icon}</span>
                <p className="text-2xl font-bold text-game-accent">{stat.value}</p>
                <p className="text-[11px] text-game-muted">{stat.label}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Character Trust + Chapter Info */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Character Trust */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">💞 角色好感度</CardTitle>
            <CardDescription>当前各角色好感度一览</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.characters.length === 0 ? (
              <p className="text-game-dim text-sm text-center py-4">暂无角色</p>
            ) : (
              data.characters.map((c) => (
                <div key={c.name} className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-game-text font-medium">{c.name}</span>
                    <span className="text-game-dim">{c.trust_pct}%</span>
                  </div>
                  <div className="h-2.5 bg-game-border rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-game-primary to-game-accent rounded-full transition-all"
                      style={{ width: `${c.trust_pct}%` }}
                    />
                  </div>
                  {c.relation && (
                    <p className="text-[10px] text-game-dim">{c.relation}</p>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Status Info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">📋 故事信息</CardTitle>
            <CardDescription>当前进度概览</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-game-muted">章节</span>
              <Badge variant="primary" size="sm">第 {data.chapter} 章</Badge>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-game-muted">状态</span>
              <Badge
                variant={
                  data.status === 'TENSION' ? 'warning' :
                  data.status === 'CLIMAX' ? 'danger' :
                  data.status === 'COOLDOWN' ? 'success' : 'primary'
                }
                size="sm"
              >
                {data.status}
              </Badge>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-game-muted">场景</span>
              <span className="text-game-text text-xs">{data.scene || '—'}</span>
            </div>
            <Separator />
            <div className="flex justify-between text-sm">
              <span className="text-game-muted">分支数</span>
              <span className="text-game-text">{data.branch_count}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-game-muted">节点数</span>
              <span className="text-game-text">{data.node_count}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-game-muted">估算费用</span>
              <span className="text-game-dim text-xs">
                ¥{((data.total_tokens / 1_000_000) * 1.2).toFixed(4)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
