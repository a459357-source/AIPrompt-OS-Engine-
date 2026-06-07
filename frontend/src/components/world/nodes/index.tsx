import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import type { WorldNodeData } from '@/lib/worldGraphAdapter'

function WorldCoreNode({ data, selected }: NodeProps) {
  const d = data as unknown as WorldNodeData & { nodeType: 'worldCore' }
  return (
    <div
      className={cn(
        'glass-panel-glow rounded-full w-36 h-36 flex flex-col items-center justify-center text-center p-3',
        selected && 'ring-2 ring-neural-cyan shadow-[0_0_32px_rgba(0,240,255,0.3)]',
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-neural-cyan !w-2 !h-2" />
      <span className="text-[10px] font-neural-mono text-neural-cyan/70 uppercase">Core</span>
      <span className="text-sm font-neural-display text-neural-cyan neural-text-glow truncate w-full">
        {d.title || '世界核心'}
      </span>
      {d.genre?.length > 0 && (
        <span className="text-[9px] text-game-muted mt-1 truncate w-full">{d.genre.slice(0, 2).join(' · ')}</span>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-neural-violet !w-2 !h-2" />
    </div>
  )
}

function FactionNode({ data, selected }: NodeProps) {
  const d = data as unknown as WorldNodeData & { nodeType: 'faction' }
  return (
    <div
      className={cn(
        'glass-panel px-3 py-2 min-w-[120px] border-neural-violet/30',
        selected && 'ring-2 ring-neural-violet',
      )}
      style={{ clipPath: 'polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)' }}
    >
      <Handle type="target" position={Position.Top} id="core-in" className="!bg-neural-cyan !w-2 !h-2" />
      <Handle type="target" position={Position.Left} className="!bg-neural-violet !w-2 !h-2" />
      <div className="text-[9px] font-neural-mono text-neural-violet uppercase">Faction</div>
      <div className="text-xs font-bold text-game-text truncate">{d.name}</div>
      {d.leader && <div className="text-[10px] text-game-muted">首领: {d.leader}</div>}
      <Handle type="source" position={Position.Right} className="!bg-neural-violet !w-2 !h-2" />
    </div>
  )
}

function CharacterNode({ data, selected }: NodeProps) {
  const d = data as unknown as WorldNodeData & { nodeType: 'character' }
  return (
    <div
      className={cn(
        'glass-panel px-3 py-2 min-w-[100px]',
        d.isMain ? 'border-neural-magenta/40 bg-neural-magenta/5' : 'border-neural-cyan/20',
        selected && 'ring-2 ring-neural-cyan',
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-neural-cyan !w-2 !h-2" />
      <div className="text-[9px] font-neural-mono text-neural-cyan uppercase">
        {d.isMain ? 'Protagonist' : 'Character'}
      </div>
      <div className="text-xs font-bold truncate">{d.name}</div>
      {d.faction && <div className="text-[10px] text-game-muted">{d.faction}</div>}
      <Handle type="source" position={Position.Bottom} className="!bg-neural-magenta !w-2 !h-2" />
    </div>
  )
}

function ArtifactNode({ data, selected }: NodeProps) {
  const d = data as unknown as WorldNodeData & { nodeType: 'artifact' }
  return (
    <div
      className={cn(
        'glass-panel px-2 py-2 w-24 rotate-45 flex items-center justify-center',
        selected && 'ring-2 ring-neural-magenta',
      )}
    >
      <div className="-rotate-45 text-center">
        <div className="text-[8px] font-neural-mono text-neural-magenta">ITEM</div>
        <div className="text-[10px] font-bold truncate max-w-[70px]">{d.name}</div>
      </div>
      <Handle type="target" position={Position.Left} className="!bg-neural-magenta !w-2 !h-2" />
      <Handle type="source" position={Position.Right} className="!bg-neural-magenta !w-2 !h-2" />
    </div>
  )
}

function RelationEdge() {
  return null
}

export const worldNodeTypes = {
  worldCore: memo(WorldCoreNode),
  faction: memo(FactionNode),
  character: memo(CharacterNode),
  artifact: memo(ArtifactNode),
}

export const worldEdgeTypes = {
  relation: memo(RelationEdge),
}
