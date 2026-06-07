import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import mermaid from 'mermaid'
import { motion } from 'framer-motion'
import { Activity, BarChart3, GitBranch, Network, Clock } from 'lucide-react'
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
import { WorldGraphCanvas } from '@/components/world/WorldGraphCanvas'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { usePageShell } from '@/components/layout/usePageShell'
import { InspectorPanel } from '@/components/layout/InspectorPanel'
import { getDashboard, type DashboardData } from '@/lib/api'
import { logger } from '@/lib/logger'
import { useAppSettings } from '@/hooks/useAppSettings'
import { t } from '@/lib/i18n'

type DashSection = 'overview' | 'timeline' | 'network' | 'branch' | 'factions'

const CHART_COLORS = [
  '#00f0ff', '#7b5cff', '#ff2d95', '#ffb870',
  '#8aef93', '#79c0ff', '#f0883e', '#56d364',
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
      grid: { color: 'rgba(0,240,255,0.06)' },
    },
    y: {
      ticks: { color: '#8b949e', font: { size: 10 } },
      grid: { color: 'rgba(0,240,255,0.06)' },
    },
  },
}

ChartJS.register(
  CategoryScale, LinearScale, BarElement,
  PointElement, LineElement, ArcElement,
  Tooltip, Legend, Filler,
)

mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'strict' })

export default function Dashboard() {
  const { language } = useAppSettings()
  const lang = language as 'zh' | 'en' | 'ja'
  const [data, setData] = useState<DashboardData | null>(null)
  const [activeSection, setActiveSection] = useState<DashSection>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [mermaidError, setMermaidError] = useState('')
  const graphRef = useRef<HTMLDivElement>(null)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    logger.info('Dashboard', 'Loading...')
    try {
      const d = await getDashboard()
      if (d.error) { setError(d.error); setLoading(false); return }
      setError('')
      setData(d)
    } catch (e) {
      setError((e as Error).message || String(e))
      logger.error('Dashboard', 'Load failed', { error: String(e) })
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadDashboard() }, [loadDashboard])

  useEffect(() => {
    const src = data?.story_graph?.mermaid
    const el = graphRef.current
    if (!src || !el || Object.keys(data?.story_graph?.nodes ?? {}).length === 0) {
      setMermaidError('')
      return
    }
    el.innerHTML = ''
    setMermaidError('')
    const id = `mermaid-graph-${Date.now()}`
    mermaid.render(id, src).then(({ svg }) => {
      if (graphRef.current) graphRef.current.innerHTML = svg
    }).catch((e) => {
      const msg = e instanceof Error ? e.message : String(e)
      setMermaidError(msg || '分支图渲染失败')
      logger.warn('Dashboard', 'Mermaid render failed', { error: msg })
    })
  }, [data?.story_graph?.mermaid, data?.story_graph?.nodes])

  const navItems = useMemo(() => [
    { id: 'overview', label: t('dashboard.overview', lang), icon: <Activity className="w-4 h-4" /> },
    { id: 'timeline', label: t('dashboard.timeline', lang), icon: <Clock className="w-4 h-4" /> },
    { id: 'network', label: t('dashboard.network', lang), icon: <Network className="w-4 h-4" /> },
    { id: 'branch', label: t('dashboard.branch', lang), icon: <GitBranch className="w-4 h-4" /> },
    { id: 'factions', label: t('dashboard.factions', lang), icon: <BarChart3 className="w-4 h-4" /> },
  ], [lang])

  const graphInput = useMemo(() => ({
    title: data?.scene || 'World State',
    world: data?.analytics?.world_state_v2?.location || '',
    genre: [] as string[],
    scene: data?.scene || '',
    main_goal: '',
    characters: (data?.characters || []).map((c, i) => ({
      name: c.name,
      isMain: i === 0,
      faction: '',
    })),
    factions: (data?.analytics?.world_state_v2?.factions || []).map((f) => ({
      name: f.name,
      type: 'organization',
      leader: '',
      influence: Math.abs(f.reputation_pct) + 50,
    })),
    artifacts: [] as { name: string; type: string; ownerId: string }[],
    characterRelations: {} as Record<string, unknown>,
  }), [data])

  const shell = usePageShell({
    navItems,
    activeNavId: activeSection,
    hideShellPanels: !data,
    inspector: data ? (
      <InspectorPanel title={navItems.find((n) => n.id === activeSection)?.label || ''}>
        <p className="text-sm text-game-muted">第 {data.turn} 轮 · {data.status}</p>
        <p className="text-xs text-game-dim mt-2">📍 {data.scene}</p>
      </InspectorPanel>
    ) : null,
  })

  useEffect(() => {
    shell.setActiveNavId(activeSection)
  }, [activeSection, shell.setActiveNavId])

  useEffect(() => {
    if (shell.activeNavId && shell.activeNavId !== activeSection) {
      setActiveSection(shell.activeNavId as DashSection)
    }
  }, [shell.activeNavId, activeSection])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <StatusToast message="加载数据…" type="loading" />
      </div>
    )
  }

  if (error && !data) {
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center justify-center min-h-[40vh] gap-6 text-center"
      >
        <div className="text-5xl">📊</div>
        <div className="space-y-2">
          <h2 className="text-lg font-bold text-game-accent">{t('dashboard.empty', lang)}</h2>
          <p className="text-game-muted text-sm max-w-md">
            {error || '开始一个新故事后，这里会展示你的故事进度、角色关系变化、字数统计等数据可视化。'}
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadDashboard}>🔄 重试</Button>
          <Button variant="neural" onClick={() => window.location.href = '/new'}>
            启动世界构建
          </Button>
        </div>
      </motion.div>
    )
  }

  if (!data) {
    return (
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center justify-center min-h-[40vh] gap-6 text-center"
      >
        <div className="text-5xl">📊</div>
        <p className="text-game-muted text-sm">暂无仪表盘数据</p>
        <Button variant="outline" onClick={loadDashboard}>🔄 重试</Button>
      </motion.div>
    )
  }

  const a = data.analytics
  const ws = a?.world_state_v2
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

  if (activeSection === 'network' && data) {
    return (
      <div className="h-full w-full">
        <StatusToast message="" type="info" />
        <WorldGraphCanvas input={graphInput} selectedNodeId={null} onSelectNode={() => {}} readOnly />
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6 space-y-6">
      <SectionHeader
        icon={Activity}
        title={t('dashboard.title', lang)}
        subtitle={`第 ${data.turn} 轮 · ${data.status} · ${data.scene}`}
        status="active"
      />
      <div className="flex justify-end">
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

      {/* World State V2 */}
      {ws && (
        <Card className="border-game-primary/30">
          <CardHeader>
            <CardTitle className="text-sm">🌍 世界状态 V2</CardTitle>
            <CardDescription>
              势力 · 事件 · 关系网 · 世界时间 · 地点（压力测试/长局监控）
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <div className="rounded-lg border border-game-border/60 p-3 space-y-1">
                <p className="text-[10px] text-game-muted uppercase tracking-wide">世界时间</p>
                <p className="font-medium text-game-accent">{ws.world_time.label}</p>
                <p className="text-xs text-game-dim">{ws.world_time.era}</p>
                <p className="text-[11px] text-game-muted">场景变迁 {ws.world_time.scene_changes} 次</p>
              </div>
              <div className="rounded-lg border border-game-border/60 p-3 space-y-1 md:col-span-2">
                <p className="text-[10px] text-game-muted uppercase tracking-wide">当前地点</p>
                <p className="text-sm text-game-text leading-relaxed">{ws.location || '—'}</p>
                {ws.locations.length > 0 && (
                  <p className="text-[11px] text-game-dim mt-1">
                    世界观地点：{ws.locations.map((l) => l.name).join(' · ')}
                  </p>
                )}
              </div>
            </div>

            <Separator />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium text-game-muted mb-2">🏛️ 势力 ({ws.factions.length})</p>
                {ws.factions.length === 0 ? (
                  <p className="text-game-dim text-xs">暂无势力数据</p>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {ws.factions.map((f) => (
                      <div key={f.name} className="text-xs border border-game-border/40 rounded-md p-2">
                        <div className="flex justify-between gap-2">
                          <span className="font-medium">{f.name}</span>
                          <Badge variant="outline" size="sm">{f.reputation_pct > 0 ? '+' : ''}{f.reputation_pct}%</Badge>
                        </div>
                        <p className="text-game-dim mt-0.5">{f.relation_to_player} · 影响力 {f.influence}</p>
                        {f.goals[0] && <p className="text-game-muted mt-1 truncate">{f.goals[0]}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <p className="text-xs font-medium text-game-muted mb-2">📅 世界事件 ({ws.events.length})</p>
                {ws.events.length === 0 ? (
                  <p className="text-game-dim text-xs">暂无事件（对局推进后由引擎调度）</p>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {ws.events.slice(0, 12).map((e) => (
                      <div key={e.id || e.title} className="text-xs border border-game-border/40 rounded-md p-2">
                        <div className="flex justify-between gap-2">
                          <span className="font-medium truncate">{e.title}</span>
                          <Badge
                            variant={e.status === 'active' ? 'warning' : e.status === 'resolved' ? 'success' : 'outline'}
                            size="sm"
                          >
                            {e.status}
                          </Badge>
                        </div>
                        <p className="text-game-dim mt-0.5">T{e.trigger_turn} · 重要度 {e.importance}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <Separator />

            <div>
              <p className="text-xs font-medium text-game-muted mb-2">
                🔗 关系网 ({ws.relationship_network.nodes.length} 节点 · {ws.relationship_network.edges.length} 边)
              </p>
              {ws.relationship_network.nodes.length === 0 ? (
                <p className="text-game-dim text-xs">暂无关系数据</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {ws.relationship_network.nodes.map((n) => (
                    <Badge
                      key={n.name}
                      variant={n.is_main ? 'accent' : 'primary'}
                      size="sm"
                      className="text-[11px]"
                    >
                      {n.name}
                      {n.relationship_type ? ` · ${n.relationship_type}` : ''}
                      {' '}({n.trust_pct}%)
                    </Badge>
                  ))}
                </div>
              )}
              {ws.faction_links.length > 0 && (
                <p className="text-[11px] text-game-dim mt-2">
                  势力关系：{ws.faction_links.slice(0, 6).map((l) => `${l.from}→${l.to}(${l.label})`).join(' · ')}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Story branch graph */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">🔀 剧情分支图</CardTitle>
          <CardDescription>
            故事节点与角色关联（当前节点：{data.story_graph?.current_node ?? '—'}）
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.node_count === 0 ? (
            <p className="text-game-dim text-sm text-center py-6">暂无分支节点，进行游戏后将自动生成</p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-game-border/60 bg-game-bg/40 p-4">
              {mermaidError ? (
                <p className="text-game-dim text-sm text-center py-6">
                  分支图暂时无法渲染（{mermaidError}）。节点数据仍可在上方「关系网络」查看。
                </p>
              ) : null}
              <div ref={graphRef} className="min-w-[320px] flex justify-center" />
            </div>
          )}
        </CardContent>
      </Card>

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
