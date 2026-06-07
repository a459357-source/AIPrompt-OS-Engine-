import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, PointElement,
  LineElement, ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { Bar, Line, Doughnut } from 'react-chartjs-2'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { StatusToast } from '@/components/StatusToast'
import { getDashboard, type DashboardData } from '@/lib/api'
import { logger } from '@/lib/logger'

ChartJS.register(
  CategoryScale, LinearScale, BarElement,
  PointElement, LineElement, ArcElement,
  Tooltip, Legend, Filler,
)

const CHART_COLORS = [
  '#58a6ff', '#3fb950', '#d29922', '#da3633',
  '#bc8cff', '#79c0ff', '#f0883e', '#56d364',
]

const CHART_OPTIONS_DARK = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: { labels: { color: '#8b949e', font: { size: 11 } } },
  },
  scales: {
    x: {
      ticks: { color: '#8b949e', font: { size: 10 } },
      grid: { color: '#21262d' },
    },
    y: {
      ticks: { color: '#8b949e', font: { size: 10 } },
      grid: { color: '#21262d' },
    },
  },
}

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

  const a = data.analytics
  const costEst = a?.api_usage?.totals?.cost_usd ?? (data.total_tokens / 1_000_000 * 0.2)

  const statsData = [
    { label: '总轮次', value: String(data.turn), icon: '🔄' },
    { label: '角色数', value: String(data.character_count), icon: '👥' },
    { label: '总字数', value: data.word_count > 1000 ? `${(data.word_count / 1000).toFixed(1)}k` : String(data.word_count), icon: '📝' },
    { label: '分支节点', value: String(data.node_count), icon: '🔀' },
    { label: 'API 调用', value: String(data.api_calls), icon: '🤖' },
    { label: '费用', value: `$${costEst.toFixed(3)}`, icon: '💰' },
  ]

  // ── Chart: Trust over time ───────────────────────────────────────
  const trustCurve = a?.metrics_curves?.['trust']
  const trustChart = trustCurve && trustCurve.datasets.length > 0 ? {
    labels: trustCurve.labels.map(String),
    datasets: trustCurve.datasets.map((ds, i) => ({
      label: ds.name,
      data: ds.data,
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '22',
      tension: 0.3,
      fill: false,
      pointRadius: 3,
    })),
  } : null

  // ── Chart: API usage ─────────────────────────────────────────────
  const apiUsage = a?.api_usage
  const apiChart = apiUsage?.per_turn && apiUsage.per_turn.length > 0 ? {
    labels: apiUsage.per_turn.map(p => `T${p.turn}`),
    datasets: [
      {
        label: 'Prompt',
        data: apiUsage.per_turn.map(p => p.prompt_tokens),
        backgroundColor: '#58a6ff88',
        borderColor: '#58a6ff',
        borderWidth: 1,
      },
      {
        label: 'Completion',
        data: apiUsage.per_turn.map(p => p.completion_tokens),
        backgroundColor: '#3fb95088',
        borderColor: '#3fb950',
        borderWidth: 1,
      },
    ],
  } : null

  // ── Chart: Choice distribution ───────────────────────────────────
  const choiceStats = a?.choice_stats
  const choiceChart = choiceStats && choiceStats.counts.some(c => c > 0) ? {
    labels: choiceStats.labels,
    datasets: [{
      data: choiceStats.counts,
      backgroundColor: ['#58a6ff88', '#3fb95088', '#d2992288', '#da363388'],
      borderColor: ['#58a6ff', '#3fb950', '#d29922', '#da3633'],
      borderWidth: 1,
    }],
  } : null

  // ── Chart: Word counts ───────────────────────────────────────────
  const wordData = a?.word_counts
  const wordChart = wordData && wordData.length > 0 ? {
    labels: wordData.map(w => `T${w.turn}`),
    datasets: [{
      label: '字数',
      data: wordData.map(w => w.chars),
      backgroundColor: '#bc8cff66',
      borderColor: '#bc8cff',
      borderWidth: 1,
      borderRadius: 4,
    }],
  } : null

  // ── Chart: Character frequency ───────────────────────────────────
  const freqData = a?.character_frequency
  const freqChart = freqData && freqData.labels.length > 0 ? {
    labels: freqData.labels,
    datasets: [{
      label: '出场次数',
      data: freqData.counts,
      backgroundColor: CHART_COLORS.map(c => c + '88'),
      borderColor: CHART_COLORS,
      borderWidth: 1,
      borderRadius: 4,
    }],
  } : null

  // ── Chart: Faction reputation ──────────────────────────────────────
  const factionCurves = a?.faction_curves
  const factionChart = (() => {
    if (!factionCurves || Object.keys(factionCurves).length === 0) return null
    const entries = Object.values(factionCurves)
    const allTurns = new Set<number>()
    entries.forEach((curve) => curve.labels.forEach((t) => allTurns.add(t)))
    const labels = Array.from(allTurns).sort((x, y) => x - y).map(String)
    const datasets = entries.map((curve, i) => {
      const turnMap = new Map(curve.labels.map((t, idx) => [t, curve.datasets[0]?.data[idx] ?? 0]))
      return {
        label: curve.label || curve.datasets[0]?.name || `势力 ${i + 1}`,
        data: labels.map((l) => turnMap.get(Number(l)) ?? null),
        borderColor: CHART_COLORS[i % CHART_COLORS.length],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length] + '22',
        tension: 0.3,
        fill: false,
        pointRadius: 3,
        spanGaps: true,
      }
    })
    return { labels, datasets }
  })()

  const statusTimeline = a?.status_timeline?.filter((item) => item.turn > 0) ?? []

  // ── Branch stats ─────────────────────────────────────────────────
  const bs = a?.branch_stats

  const hasCharts = trustChart || apiChart || choiceChart || wordChart || freqChart || factionChart
  const showAnalytics = hasCharts || statusTimeline.length > 0

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
          <motion.div key={stat.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
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

      {/* Char Trust + Story Info */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
            {bs && (
              <>
                <Separator />
                <div className="flex justify-between text-sm">
                  <span className="text-game-muted">分支深度</span>
                  <span className="text-game-text">{bs.max_depth}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-game-muted">平均分支</span>
                  <span className="text-game-text">{bs.avg_branches}</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Section */}
      {showAnalytics && (
        <>
          <Separator className="my-2" />

          {/* Trust over time */}
          {trustChart && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">📈 好感度变化曲线</CardTitle>
                <CardDescription>角色信任度随剧情推进的变化</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <Line data={trustChart} options={{
                    ...CHART_OPTIONS_DARK,
                    scales: {
                      ...CHART_OPTIONS_DARK.scales,
                      y: { ...CHART_OPTIONS_DARK.scales?.y, min: 0, max: 100 },
                    },
                  }} />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Word counts + API on same row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {wordChart && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">📝 每轮字数</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-56">
                    <Bar data={wordChart} options={CHART_OPTIONS_DARK} />
                  </div>
                </CardContent>
              </Card>
            )}

            {apiChart && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">🤖 Token 用量</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-56">
                    <Bar data={apiChart} options={{
                      ...CHART_OPTIONS_DARK,
                      scales: {
                        ...CHART_OPTIONS_DARK.scales,
                        x: { ...CHART_OPTIONS_DARK.scales?.x, stacked: true },
                        y: { ...CHART_OPTIONS_DARK.scales?.y, stacked: true },
                      },
                    }} />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Choice + Character Freq */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {choiceChart && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">🎯 选择偏好</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-56 max-w-xs mx-auto">
                    <Doughnut data={choiceChart} options={{
                      responsive: true,
                      maintainAspectRatio: true,
                      plugins: {
                        legend: { labels: { color: '#8b949e', font: { size: 11 } } },
                      },
                    }} />
                  </div>
                </CardContent>
              </Card>
            )}

            {freqChart && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">👥 角色出场频率</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-56">
                    <Bar data={freqChart} options={{
                      ...CHART_OPTIONS_DARK,
                      indexAxis: 'y' as const,
                    }} />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Faction + Status timeline */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {factionChart && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">🏛️ 势力声望曲线</CardTitle>
                  <CardDescription>各势力声望随回合变化（来自 memory.json）</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-56">
                    <Line data={factionChart} options={{
                      ...CHART_OPTIONS_DARK,
                      scales: {
                        ...CHART_OPTIONS_DARK.scales,
                        y: { ...CHART_OPTIONS_DARK.scales?.y, min: 0, max: 100 },
                      },
                    }} />
                  </div>
                </CardContent>
              </Card>
            )}

            {statusTimeline.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">🕐 状态时间线</CardTitle>
                  <CardDescription>每轮叙事状态与场景（来自剧情图）</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="max-h-56 overflow-y-auto space-y-2 pr-1">
                    {statusTimeline.map((item) => (
                      <div
                        key={`tl-${item.turn}-${item.scene}`}
                        className="flex items-start gap-2 text-xs border-b border-game-border/50 pb-2 last:border-0"
                      >
                        <Badge variant="outline" size="sm" className="shrink-0 tabular-nums">
                          T{item.turn}
                        </Badge>
                        <Badge
                          variant={
                            item.status === 'TENSION' ? 'warning' :
                            item.status === 'CLIMAX' ? 'danger' :
                            item.status === 'COOLDOWN' ? 'success' : 'primary'
                          }
                          size="sm"
                          className="shrink-0"
                        >
                          {item.status}
                        </Badge>
                        <span className="text-game-muted leading-relaxed">{item.scene || '—'}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </>
      )}

      {!showAnalytics && (
        <Card>
          <CardContent className="py-8 text-center text-game-dim text-sm">
            📈 进行更多轮次后，这里会展示数据可视化图表
          </CardContent>
        </Card>
      )}
    </div>
  )
}
