import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

// ── Mock dashboard data ──
const STATS: { label: string; value: string; icon: string; trend: string | null }[] = [
  { label: '总轮次', value: '0', icon: '🔄', trend: null },
  { label: '角色数', value: '4', icon: '👥', trend: null },
  { label: '总字数', value: '0', icon: '📝', trend: null },
  { label: '分支节点', value: '0', icon: '🔀', trend: null },
]

const RECENT_EVENTS: { turn: number; event: string; type: string }[] = []

export default function Dashboard() {
  const hasData = false // Will be true when game is running

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-game-accent font-bold text-xl">📊 仪表盘</h1>
        <p className="text-game-muted text-sm mt-1">故事进度、角色关系、数据统计一览</p>
      </div>

      {!hasData ? (
        /* ── Empty State ── */
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center justify-center min-h-[40vh] gap-6 text-center"
        >
          <div className="text-5xl">📊</div>
          <div className="space-y-2">
            <h2 className="text-lg font-bold text-game-accent">还没有数据</h2>
            <p className="text-game-muted text-sm max-w-md">
              开始一个新故事后，这里会展示你的故事进度、角色关系变化、字数统计等数据可视化。
            </p>
          </div>
          <Button variant="glow" onClick={() => window.location.href = '/new'}>
            ✨ 创建第一个故事
          </Button>
        </motion.div>
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS.map((stat) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: STATS.indexOf(stat) * 0.05 }}
              >
                <Card className="text-center hover:shadow-md transition-shadow">
                  <CardContent className="pt-6 pb-4 space-y-2">
                    <span className="text-2xl">{stat.icon}</span>
                    <p className="text-3xl font-bold text-game-accent">{stat.value}</p>
                    <p className="text-xs text-game-muted">{stat.label}</p>
                    {stat.trend && (
                      <Badge variant={(stat.trend ?? '').startsWith('+') ? 'success' : 'warning'} size="sm">
                        {stat.trend}
                      </Badge>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          {/* Story Progress */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-sm">📈 故事进度</CardTitle>
                <CardDescription>状态流转与章节进度</CardDescription>
              </CardHeader>
              <CardContent className="min-h-[200px] flex items-center justify-center">
                <p className="text-game-dim text-sm">游戏开始后将显示进度图</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">💞 关系概览</CardTitle>
                <CardDescription>角色好感度一览</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {['艾琳', '林夜', '雪乃'].map((name, i) => {
                  const vals = [68, 45, 82]
                  return (
                    <div key={name} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-game-text">{name}</span>
                        <span className="text-game-dim">{vals[i]}%</span>
                      </div>
                      <div className="h-2 bg-game-border rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-game-primary to-game-accent rounded-full transition-all"
                          style={{ width: `${vals[i]}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </CardContent>
            </Card>
          </div>

          {/* Recent Events */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm">📋 最近事件</CardTitle>
                <CardDescription>关键剧情节点与选择记录</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {RECENT_EVENTS.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-game-dim text-sm">尚无事件记录</p>
                  <p className="text-game-dim text-xs mt-1">剧情推进后将自动记录关键事件</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {RECENT_EVENTS.map((e, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <Badge variant="outline" size="sm">第{e.turn}轮</Badge>
                      <span className="text-game-text flex-1">{e.event}</span>
                      <Badge variant="primary" size="sm">{e.type}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
