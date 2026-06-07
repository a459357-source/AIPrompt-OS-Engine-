import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'

const LEGEND_ITEMS = [
  {
    key: 'inWorld',
    label: '世界包含',
    hint: '核心 → 势力',
    stroke: 'rgba(0,240,255,0.65)',
    dash: '5 3',
    width: 2,
  },
  {
    key: 'protagonist',
    label: '主角锚定',
    hint: '核心 → 主角',
    stroke: '#ff2d95',
    dash: undefined,
    width: 2,
    animated: true,
  },
  {
    key: 'belongsPublic',
    label: '明面隶属',
    hint: '角色 → 势力',
    stroke: '#58a6ff',
    dash: undefined,
    width: 2,
    animated: true,
  },
  {
    key: 'belongsHidden',
    label: '暗中隶属',
    hint: '角色 → 势力',
    stroke: 'rgba(136,146,176,0.65)',
    dash: '5 3',
    width: 2,
    opacity: 0.75,
  },
  {
    key: 'leads',
    label: '势力首领',
    hint: '势力 → 角色',
    stroke: '#58a6ff',
    dash: undefined,
    width: 2,
  },
  {
    key: 'relates',
    label: '人物关系',
    hint: '主角 ↔ NPC',
    stroke: '#ff2d95',
    dash: undefined,
    width: 2,
    animated: true,
  },
  {
    key: 'owns',
    label: '物品持有',
    hint: '物品 → 角色/势力',
    stroke: '#58a6ff',
    dash: undefined,
    width: 1.5,
  },
] as const

function LegendSwatch({
  stroke,
  dash,
  width = 2,
  opacity = 1,
  animated,
}: {
  stroke: string
  dash?: string
  width?: number
  opacity?: number
  animated?: boolean
}) {
  return (
    <svg width="36" height="10" className="shrink-0" aria-hidden>
      <line
        x1="2"
        y1="5"
        x2="34"
        y2="5"
        stroke={stroke}
        strokeWidth={width}
        strokeDasharray={dash}
        opacity={opacity}
        className={animated ? 'world-legend-edge-animated' : undefined}
      />
    </svg>
  )
}

/** 迷你拓扑示例：展示典型节点与连线关系 */
function MiniExampleDiagram() {
  return (
    <svg viewBox="0 0 200 120" className="w-full h-auto mt-2" aria-label="图谱结构示例">
      {/* 核心 */}
      <circle cx="100" cy="28" r="14" fill="rgba(0,240,255,0.12)" stroke="rgba(0,240,255,0.5)" strokeWidth="1.5" />
      <text x="100" y="32" textAnchor="middle" fill="rgba(0,240,255,0.8)" fontSize="8">核心</text>

      {/* 势力 */}
      <rect x="28" y="58" width="44" height="18" rx="2" fill="rgba(123,92,255,0.12)" stroke="rgba(123,92,255,0.45)" strokeWidth="1" />
      <text x="50" y="70" textAnchor="middle" fill="rgba(123,92,255,0.85)" fontSize="7">势力A</text>
      <rect x="128" y="58" width="44" height="18" rx="2" fill="rgba(123,92,255,0.12)" stroke="rgba(123,92,255,0.45)" strokeWidth="1" />
      <text x="150" y="70" textAnchor="middle" fill="rgba(123,92,255,0.85)" fontSize="7">势力B</text>

      {/* 角色 */}
      <rect x="78" y="92" width="36" height="16" rx="2" fill="rgba(255,45,149,0.1)" stroke="rgba(255,45,149,0.45)" strokeWidth="1" />
      <text x="96" y="103" textAnchor="middle" fill="rgba(255,45,149,0.85)" fontSize="7">主角</text>
      <rect x="148" y="88" width="32" height="14" rx="2" fill="rgba(0,240,255,0.08)" stroke="rgba(0,240,255,0.35)" strokeWidth="1" />
      <text x="164" y="98" textAnchor="middle" fill="rgba(0,240,255,0.75)" fontSize="6.5">NPC</text>

      {/* 物品 */}
      <rect x="18" y="88" width="22" height="22" rx="1" transform="rotate(45 29 99)" fill="rgba(255,184,112,0.12)" stroke="rgba(255,184,112,0.5)" strokeWidth="1" />
      <text x="29" y="102" textAnchor="middle" fill="rgba(255,184,112,0.85)" fontSize="6">物</text>

      {/* inWorld */}
      <path d="M 92 38 Q 60 48 50 58" fill="none" stroke="rgba(0,240,255,0.5)" strokeWidth="1.2" strokeDasharray="4 2" />
      <path d="M 108 38 Q 140 48 150 58" fill="none" stroke="rgba(0,240,255,0.5)" strokeWidth="1.2" strokeDasharray="4 2" />
      {/* protagonist */}
      <path d="M 100 42 L 96 92" fill="none" stroke="#ff2d95" strokeWidth="1.3" className="world-legend-edge-animated" />
      {/* belongs public */}
      <path d="M 78 100 Q 55 82 50 76" fill="none" stroke="#58a6ff" strokeWidth="1.2" className="world-legend-edge-animated" />
      {/* belongs hidden */}
      <path d="M 110 98 Q 130 82 150 76" fill="none" stroke="rgba(136,146,176,0.55)" strokeWidth="1.2" strokeDasharray="4 2" opacity="0.8" />
      {/* relates */}
      <path d="M 114 98 L 148 95" fill="none" stroke="#ff2d95" strokeWidth="1.2" className="world-legend-edge-animated" />
      {/* owns */}
      <path d="M 40 95 L 78 98" fill="none" stroke="#58a6ff" strokeWidth="1" />
    </svg>
  )
}

interface WorldGraphLegendProps {
  className?: string
  defaultCollapsed?: boolean
}

export function WorldGraphLegend({ className, defaultCollapsed = false }: WorldGraphLegendProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  return (
    <div className={cn('glass-panel border border-neural-cyan/20 rounded-md text-left max-w-[220px]', className)}>
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 text-[11px] font-neural-mono text-neural-cyan/80 hover:bg-neural-cyan/5 transition-colors rounded-t-md"
      >
        <span>📐 连线图例 & 示例</span>
        {collapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
      </button>
      {!collapsed && (
        <div className="px-2.5 pb-2.5 pt-0.5 border-t border-neural-cyan/10">
          <MiniExampleDiagram />
          <ul className="mt-2 space-y-1">
            {LEGEND_ITEMS.map((item) => (
              <li key={item.key} className="flex items-center gap-1.5">
                <LegendSwatch
                  stroke={item.stroke}
                  dash={item.dash}
                  width={item.width}
                  opacity={'opacity' in item ? item.opacity : 1}
                  animated={'animated' in item ? item.animated : false}
                />
                <span className="text-[10px] text-game-text leading-tight">
                  {item.label}
                  <span className="text-game-muted ml-1">{item.hint}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-[9px] text-game-muted mt-2 leading-snug">
            拖线：核心↔角色设主角；角色→势力追加/切换明暗隶属；势力→角色设首领；主角↔NPC 建关系；↔物品设持有者。
          </p>
        </div>
      )}
    </div>
  )
}
