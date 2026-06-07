import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import mermaid from 'mermaid'
import { motion } from 'framer-motion'
import { Activity, BarChart3, GitBranch, Network, Clock, Clapperboard, Target } from 'lucide-react'
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
import { graphStructureKey } from '@/lib/worldGraphAdapter'
import { SectionHeader } from '@/components/neural/SectionHeader'
import { usePageShell } from '@/components/layout/usePageShell'
import { InspectorPanel } from '@/components/layout/InspectorPanel'
import { getDashboard, type DashboardData } from '@/lib/api'
import { logger } from '@/lib/logger'
import { useAppSettings } from '@/hooks/useAppSettings'
import { useAdultThemeOptional } from '@/contexts/AdultThemeContext'
import { t, tTheme } from '@/lib/i18n'

type DashSection = 'overview' | 'timeline' | 'network' | 'branch' | 'factions' | 'director' | 'objectives'

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
  const adultMode = useAdultThemeOptional()?.adultMode ?? false
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
    if (activeSection !== 'branch') return
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
  }, [data?.story_graph?.mermaid, data?.story_graph?.nodes, activeSection])

  const sectionIcon =
    activeSection === 'timeline' ? Clock :
    activeSection === 'network' ? Network :
    activeSection === 'branch' ? GitBranch :
    activeSection === 'factions' ? BarChart3 :
    activeSection === 'director' ? Clapperboard :
    activeSection === 'objectives' ? Target :
    Activity

  const navItems = useMemo(() => [
    { id: 'overview', label: t('dashboard.overview', lang), icon: <Activity className="w-4 h-4" /> },
    { id: 'timeline', label: t('dashboard.timeline', lang), icon: <Clock className="w-4 h-4" /> },
    { id: 'network', label: t('dashboard.network', lang), icon: <Network className="w-4 h-4" /> },
    { id: 'branch', label: t('dashboard.branch', lang), icon: <GitBranch className="w-4 h-4" /> },
    { id: 'factions', label: t('dashboard.factions', lang), icon: <BarChart3 className="w-4 h-4" /> },
    { id: 'director', label: t('dashboard.director', lang), icon: <Clapperboard className="w-4 h-4" /> },
    { id: 'objectives', label: t('dashboard.objectives', lang), icon: <Target className="w-4 h-4" /> },
  ], [lang])

  const graphInput = useMemo(() => {
    const ws = data?.analytics?.world_state_v2
    const net = ws?.relationship_network
    const netNodes = net?.nodes ?? []
    const netEdges = net?.edges ?? []

    const characterRelations: Record<string, unknown> = {}
    for (const e of netEdges) {
      if (e.kind === 'relation') {
        characterRelations[e.to] = { relationshipType: e.label || 'friend' }
      }
    }
    for (const n of netNodes) {
      if (!n.is_main && n.relationship_type && !characterRelations[n.name]) {
        characterRelations[n.name] = { relationshipType: n.relationship_type }
      }
    }

    return {
      title: data?.scene || 'World State',
      world: ws?.location || data?.scene || '',
      genre: [] as string[],
      scene: data?.scene || '',
      main_goal: '',
      characters: netNodes.length > 0
        ? netNodes.map((n) => ({
            name: n.name,
            isMain: n.is_main,
            faction: n.faction || '',
          }))
        : (data?.characters || []).map((c, i) => ({
            name: c.name,
            isMain: i === 0,
            faction: '',
          })),
      factions: (ws?.factions || []).map((f) => ({
        name: f.name,
        type: f.type || 'organization',
        leader: f.leader || '',
        influence: Math.abs(f.reputation_pct) + 50,
      })),
      artifacts: [] as { name: string; type: string; ownerId: string }[],
      characterRelations,
      networkEdges: netEdges,
    }
  }, [data])

  const dashboardLayoutKey = useMemo(
    () => graphStructureKey(graphInput),
    [graphInput],
  )

  usePageShell({
    navItems,
    activeNavId: activeSection,
    onNavSelect: (id) => setActiveSection(id as DashSection),
    hideShellPanels: !data,
    inspector: data ? (
      <InspectorPanel title={navItems.find((n) => n.id === activeSection)?.label || ''}>
        <p className="text-sm text-game-muted">第 {data.turn} 轮 · {data.status}</p>
        <p className="text-xs text-game-dim mt-2">📍 {data.scene}</p>
        {activeSection === 'timeline' && (
          <p className="text-xs text-game-muted mt-3">
            共 {(data.analytics?.status_timeline?.filter((item) => item.turn > 0) ?? []).length} 条状态记录
          </p>
        )}
        {activeSection === 'branch' && (
          <p className="text-xs text-game-muted mt-3">{data.node_count} 节点 · {data.branch_count} 分支</p>
        )}
        {activeSection === 'factions' && data.analytics?.world_state_v2 && (
          <p className="text-xs text-game-muted mt-3">{data.analytics.world_state_v2.factions.length} 个势力</p>
        )}
        {activeSection === 'network' && data.analytics?.world_state_v2 && (
          <p className="text-xs text-game-muted mt-3">
            {data.analytics.world_state_v2.relationship_network.nodes.length} 角色 ·{' '}
            {data.analytics.world_state_v2.relationship_network.edges.length} 关系边
          </p>
        )}
        {activeSection === 'director' && data.plot_director && (
          <p className="text-xs text-game-muted mt-3">
            {data.plot_director.main_plot.progress}% · {data.plot_director.unresolved_hooks.length} 伏笔
          </p>
        )}
        {activeSection === 'objectives' && data.objectives && (
          <p className="text-xs text-game-muted mt-3">
            {data.objectives.main.length + data.objectives.side.length} 活跃 ·{' '}
            {data.objectives.completed.length} 已完成
          </p>
        )}
      </InspectorPanel>
    ) : null,
  })

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

  const sectionHeader = (
    <>
      <SectionHeader
        icon={sectionIcon}
        title={navItems.find((n) => n.id === activeSection)?.label || t('dashboard.title', lang)}
        subtitle={`第 ${data.turn} 轮 · ${data.status} · ${data.scene}`}
        status="active"
      />
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={loadDashboard}>🔄 刷新</Button>
      </div>
    </>
  )

  const statsCards = (
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
  )

  if (activeSection === 'network') {
    return (
      <div className="h-full w-full relative">
        <WorldGraphCanvas input={graphInput} layoutKey={dashboardLayoutKey} selectedNodeId={null} onSelectNode={() => {}} readOnly />
        <div className="absolute top-3 left-12 md:left-4 z-10 max-w-md space-y-2">
          <SectionHeader
            icon={Network}
            title={navItems.find((n) => n.id === 'network')?.label || t('dashboard.network', lang)}
            subtitle={`第 ${data.turn} 轮 · ${data.status}`}
            status="active"
            className="pointer-events-none mb-0"
          />
          <div className="flex justify-end pointer-events-auto">
            <Button variant="outline" size="sm" onClick={loadDashboard}>🔄 刷新</Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6 space-y-6">
      {sectionHeader}

      {activeSection === 'overview' && (
        <>
          {statsCards}
          {ws && (
            <Card className="border-game-primary/30">
              <CardHeader>
                <CardTitle className="text-sm">🌍 世界状态概览</CardTitle>
                <CardDescription>当前地点 · 势力 · 关系网摘要</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                  <div className="rounded-lg border border-game-border/60 p-3 space-y-1">
                    <p className="text-[10px] text-game-muted uppercase tracking-wide">世界时间</p>
                    <p className="font-medium text-game-accent">{ws.world_time.label}</p>
                    <p className="text-xs text-game-dim">{ws.world_time.era}</p>
                  </div>
                  <div className="rounded-lg border border-game-border/60 p-3 space-y-1 md:col-span-2">
                    <p className="text-[10px] text-game-muted uppercase tracking-wide">当前地点</p>
                    <p className="text-sm text-game-text leading-relaxed">{ws.location || '—'}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {ws.factions.slice(0, 6).map((f) => (
                    <Badge key={f.name} variant="outline" size="sm">{f.name} {f.reputation_pct > 0 ? '+' : ''}{f.reputation_pct}%</Badge>
                  ))}
                  {ws.relationship_network.nodes.slice(0, 8).map((n) => (
                    <Badge key={n.name} variant={n.is_main ? 'accent' : 'primary'} size="sm">
                      {n.name} ({n.trust_pct}%)
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">💞 {tTheme('dashboard.affection', lang, adultMode)}</CardTitle>
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
                        <div className="h-full bg-gradient-to-r from-game-primary to-game-accent rounded-full" style={{ width: `${c.trust_pct}%` }} />
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">📋 故事信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between text-sm"><span className="text-game-muted">章节</span><Badge variant="primary" size="sm">第 {data.chapter} 章</Badge></div>
                <div className="flex justify-between text-sm"><span className="text-game-muted">状态</span><Badge variant="primary" size="sm">{data.status}</Badge></div>
                <div className="flex justify-between text-sm"><span className="text-game-muted">场景</span><span className="text-game-text text-xs">{data.scene || '—'}</span></div>
                <Separator />
                <div className="flex justify-between text-sm"><span className="text-game-muted">分支数</span><span>{data.branch_count}</span></div>
                <div className="flex justify-between text-sm"><span className="text-game-muted">节点数</span><span>{data.node_count}</span></div>
              </CardContent>
            </Card>
          </div>
          {(wordChart || apiChart || trustChart || freqChart) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {trustChart && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">📈 {tTheme('dashboard.affectionChart', lang, adultMode)}</CardTitle></CardHeader>
                  <CardContent><div className="h-56"><Line data={trustChart} options={{ ...CHART_OPTIONS_DARK, scales: { ...CHART_OPTIONS_DARK.scales, y: { ...CHART_OPTIONS_DARK.scales?.y, min: 0, max: 100 } } }} /></div></CardContent>
                </Card>
              )}
              {wordChart && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">📝 每轮字数</CardTitle></CardHeader>
                  <CardContent><div className="h-56"><Bar data={wordChart} options={CHART_OPTIONS_DARK} /></div></CardContent>
                </Card>
              )}
              {apiChart && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">🤖 Token 用量</CardTitle></CardHeader>
                  <CardContent><div className="h-56"><Bar data={apiChart} options={{ ...CHART_OPTIONS_DARK, scales: { ...CHART_OPTIONS_DARK.scales, x: { ...CHART_OPTIONS_DARK.scales?.x, stacked: true }, y: { ...CHART_OPTIONS_DARK.scales?.y, stacked: true } } }} /></div></CardContent>
                </Card>
              )}
              {freqChart && (
                <Card>
                  <CardHeader><CardTitle className="text-sm">👥 角色出场频率</CardTitle></CardHeader>
                  <CardContent><div className="h-56"><Bar data={freqChart} options={{ ...CHART_OPTIONS_DARK, indexAxis: 'y' as const }} /></div></CardContent>
                </Card>
              )}
            </div>
          )}
          {!ws && !trustChart && !wordChart && (
            <Card><CardContent className="py-8 text-center text-game-dim text-sm">进行更多轮次后，概览数据会逐步丰富</CardContent></Card>
          )}
        </>
      )}

      {activeSection === 'timeline' && (
        <>
          {ws && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">🕐 叙事状态时间线</CardTitle>
                <CardDescription>每轮状态机阶段与场景变迁</CardDescription>
              </CardHeader>
              <CardContent>
                {statusTimeline.length === 0 ? (
                  <p className="text-game-dim text-sm text-center py-8">暂无时间线记录，推进对局后自动生成</p>
                ) : (
                  <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                    {statusTimeline.map((item) => (
                      <div key={`tl-${item.turn}-${item.scene}`} className="flex items-start gap-2 text-xs border border-game-border/40 rounded-md p-3">
                        <Badge variant="outline" size="sm" className="shrink-0 tabular-nums">T{item.turn}</Badge>
                        <Badge variant={item.status === 'TENSION' ? 'warning' : item.status === 'CLIMAX' ? 'danger' : item.status === 'COOLDOWN' ? 'success' : 'primary'} size="sm" className="shrink-0">{item.status}</Badge>
                        <span className="text-game-muted leading-relaxed">{item.scene || '—'}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
          {ws && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">📅 世界事件</CardTitle>
                <CardDescription>引擎调度的事件与重要度</CardDescription>
              </CardHeader>
              <CardContent>
                {ws.events.length === 0 ? (
                  <p className="text-game-dim text-sm text-center py-8">暂无世界事件</p>
                ) : (
                  <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
                    {ws.events.map((e) => (
                      <div key={e.id || e.title} className="text-xs border border-game-border/40 rounded-md p-3">
                        <div className="flex justify-between gap-2">
                          <span className="font-medium">{e.title}</span>
                          <Badge variant={e.status === 'active' ? 'warning' : e.status === 'resolved' ? 'success' : 'outline'} size="sm">{e.status}</Badge>
                        </div>
                        <p className="text-game-dim mt-1">T{e.trigger_turn} · 重要度 {e.importance}</p>
                        {e.related_characters.length > 0 && (
                          <p className="text-game-muted mt-1">相关角色：{e.related_characters.join('、')}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
          {!ws && (
            <Card><CardContent className="py-8 text-center text-game-dim text-sm">暂无时间线数据</CardContent></Card>
          )}
        </>
      )}

      {activeSection === 'branch' && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">🔀 剧情分支图</CardTitle>
              <CardDescription>
                故事节点与选择路径（当前：{data.story_graph?.current_node ?? '—'}）
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.node_count === 0 ? (
                <p className="text-game-dim text-sm text-center py-12">暂无分支节点，进行游戏后将自动生成</p>
              ) : (
                <div className="overflow-x-auto rounded-md border border-game-border/60 bg-game-bg/40 p-4 min-h-[320px]">
                  {mermaidError ? (
                    <p className="text-game-dim text-sm text-center py-6">分支图暂时无法渲染（{mermaidError}）</p>
                  ) : null}
                  <div ref={graphRef} className="min-w-[320px] flex justify-center" />
                </div>
              )}
            </CardContent>
          </Card>
          {(bs || data.node_count > 0) && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: '分支节点', value: String(data.node_count) },
                { label: '分支数', value: String(data.branch_count) },
                ...(bs ? [
                  { label: '最大深度', value: String(bs.max_depth) },
                  { label: '平均分支', value: String(bs.avg_branches) },
                ] : []),
              ].map((item) => (
                <Card key={item.label}>
                  <CardContent className="pt-4 pb-3 text-center">
                    <p className="text-xl font-bold text-game-accent">{item.value}</p>
                    <p className="text-[11px] text-game-muted mt-1">{item.label}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
          {choiceChart && (
            <Card>
              <CardHeader><CardTitle className="text-sm">🎯 选择偏好分布</CardTitle></CardHeader>
              <CardContent>
                <div className="h-56 max-w-sm mx-auto"><Doughnut data={choiceChart} options={{ responsive: true, maintainAspectRatio: true, plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } } }} /></div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {activeSection === 'director' && (
        <>
          {data.plot_director ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">🎬 {t('dashboard.director.progress', lang)}</CardTitle>
                  <CardDescription>{data.plot_director.main_goal || data.plot_director.main_plot.name}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs text-game-muted mb-1">
                      <span>{data.plot_director.main_plot.name}</span>
                      <span>{data.plot_director.main_plot.progress}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-game-border/40 overflow-hidden">
                      <div
                        className="h-full bg-cyan-500/80 transition-all"
                        style={{ width: `${Math.min(100, Math.max(0, data.plot_director.main_plot.progress))}%` }}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div className="border border-game-border/40 rounded-lg p-3">
                      <p className="text-xs text-game-dim">{t('dashboard.director.stage', lang)}</p>
                      <p className="font-bold mt-1">{data.plot_director.main_plot.stage}</p>
                    </div>
                    <div className="border border-game-border/40 rounded-lg p-3">
                      <p className="text-xs text-game-dim">{t('dashboard.director.lastProgress', lang)}</p>
                      <p className="font-bold mt-1">T{data.plot_director.last_progress_turn}</p>
                    </div>
                    <div className="border border-game-border/40 rounded-lg p-3">
                      <p className="text-xs text-game-dim">{t('dashboard.director.stall', lang)}</p>
                      <p className="font-bold mt-1">{data.plot_director.stall_turns}</p>
                    </div>
                    <div className="border border-game-border/40 rounded-lg p-3">
                      <p className="text-xs text-game-dim">{t('dashboard.director.hooks', lang)}</p>
                      <p className="font-bold mt-1">{data.plot_director.unresolved_hooks.length}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">📌 {t('dashboard.director.hooks', lang)}</CardTitle>
                </CardHeader>
                <CardContent>
                  {data.plot_director.unresolved_hooks.length > 0 ? (
                    <div className="space-y-2">
                      {data.plot_director.unresolved_hooks.map((h) => (
                        <div key={h.id || h.title} className="flex justify-between gap-2 text-sm border border-game-border/40 rounded-lg p-3">
                          <span className="font-medium">{h.title}</span>
                          <Badge variant="outline" size="sm">
                            T{h.created_turn ?? '?'} · {h.kind || 'foreshadow'}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-game-dim text-center py-4">暂无开放伏笔</p>
                  )}
                </CardContent>
              </Card>
              {data.plot_director.resolved_hooks.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">✅ {t('dashboard.director.resolved', lang)}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-1">
                      {data.plot_director.resolved_hooks.map((h) => (
                        <p key={h.id || h.title} className="text-xs text-game-muted">
                          {h.title}
                          {h.resolved_turn != null ? ` · T${h.resolved_turn}` : ''}
                        </p>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <Card><CardContent className="py-8 text-center text-game-dim text-sm">暂无剧情导演数据，开局后会自动初始化</CardContent></Card>
          )}
        </>
      )}

      {activeSection === 'objectives' && (
        <>
          {data.objectives ? (
            <>
              {([
                { key: 'main', title: t('dashboard.objectives.main', lang), items: data.objectives.main },
                { key: 'side', title: t('dashboard.objectives.side', lang), items: data.objectives.side },
                { key: 'completed', title: t('dashboard.objectives.completed', lang), items: data.objectives.completed },
                { key: 'failed', title: t('dashboard.objectives.failed', lang), items: data.objectives.failed },
                { key: 'hidden', title: t('dashboard.objectives.hidden', lang), items: data.objectives.hidden },
              ] as const).map(({ key, title, items }) => (
                <Card key={key}>
                  <CardHeader>
                    <CardTitle className="text-sm">{title}</CardTitle>
                    <CardDescription>{items.length} 项</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {items.length > 0 ? (
                      <div className="space-y-2">
                        {items.map((obj) => (
                          <div
                            key={obj.id || obj.title}
                            className="border border-game-border/40 rounded-lg p-3 space-y-2"
                          >
                            <div className="flex justify-between gap-2 text-sm">
                              <span className="font-medium">{obj.title}</span>
                              <Badge variant="outline" size="sm">{obj.status}</Badge>
                            </div>
                            <div className="flex justify-between text-xs text-game-muted">
                              <span className="font-mono text-game-dim">{obj.id}</span>
                              <span>{obj.progress}%</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-game-border/40 overflow-hidden">
                              <div
                                className="h-full bg-neural-cyan/70 transition-all"
                                style={{ width: `${Math.min(100, Math.max(0, obj.progress))}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-game-dim text-center py-4">{t('dashboard.objectives.empty', lang)}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </>
          ) : (
            <Card>
              <CardContent className="py-8 text-center text-game-dim text-sm">
                暂无任务数据，开局后会自动初始化
              </CardContent>
            </Card>
          )}
        </>
      )}

      {activeSection === 'factions' && (
        <>
          {factionChart ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">🏛️ 势力声望曲线</CardTitle>
                <CardDescription>各势力声望随回合变化</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-72">
                  <Line data={factionChart} options={{
                    ...CHART_OPTIONS_DARK,
                    scales: { ...CHART_OPTIONS_DARK.scales, y: { ...CHART_OPTIONS_DARK.scales?.y, min: 0, max: 100 } },
                  }} />
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card><CardContent className="py-8 text-center text-game-dim text-sm">暂无势力曲线数据，对局推进后会记录各势力声望变化</CardContent></Card>
          )}
          {ws && ws.factions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">🏛️ 势力详情 ({ws.factions.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {ws.factions.map((f) => (
                    <div key={f.name} className="text-sm border border-game-border/40 rounded-lg p-4 space-y-2">
                      <div className="flex justify-between gap-2">
                        <span className="font-bold">{f.name}</span>
                        <Badge variant="outline" size="sm">{f.reputation_pct > 0 ? '+' : ''}{f.reputation_pct}%</Badge>
                      </div>
                      <p className="text-xs text-game-dim">{f.relation_to_player} · 影响力 {f.influence} · 首领 {f.leader || '—'}</p>
                      {f.goals.length > 0 && <p className="text-xs text-game-muted">目标：{f.goals.join('；')}</p>}
                      {f.attitudes.length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1">
                          {f.attitudes.slice(0, 4).map((a) => (
                            <Badge key={a.target} variant="primary" size="sm" className="text-[10px]">{a.target} {a.label}</Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {ws.faction_links.length > 0 && (
                  <>
                    <Separator className="my-4" />
                    <p className="text-xs font-medium text-game-muted mb-2">势力间关系</p>
                    <div className="space-y-1">
                      {ws.faction_links.map((l, i) => (
                        <p key={`${l.from}-${l.to}-${i}`} className="text-xs text-game-muted">
                          {l.from} → {l.to} · {l.label} ({l.attitude > 0 ? '+' : ''}{l.attitude})
                        </p>
                      ))}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
