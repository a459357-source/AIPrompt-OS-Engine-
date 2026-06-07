import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { buildWorldGraph, extractNodePositions, handleNewConnection, type WorldGraphInput } from '@/lib/worldGraphAdapter'
import { worldNodeTypes, worldEdgeTypes } from './nodes'

interface WorldGraphCanvasProps {
  input: WorldGraphInput
  selectedNodeId: string | null
  onSelectNode: (nodeId: string | null) => void
  onPositionsChange?: (positions: Record<string, { x: number; y: number }>) => void
  onGraphUpdate?: (update: Partial<WorldGraphInput>) => void
  readOnly?: boolean
  focusSection?: string | null
  className?: string
}

export function WorldGraphCanvas({
  input,
  selectedNodeId,
  onSelectNode,
  onPositionsChange,
  onGraphUpdate,
  readOnly = false,
  className,
}: WorldGraphCanvasProps) {
  const graph = useMemo(() => buildWorldGraph(input), [input])
  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges)

  useEffect(() => {
    setNodes(graph.nodes.map((n) => ({
      ...n,
      selected: n.id === selectedNodeId,
    })))
    setEdges(graph.edges)
  }, [graph, selectedNodeId, setNodes, setEdges])

  const onConnect = useCallback(
    (connection: Connection) => {
      if (readOnly || !connection.source || !connection.target || !onGraphUpdate) return
      const update = handleNewConnection(
        { source: connection.source, target: connection.target },
        input,
      )
      if (update) onGraphUpdate(update)
    },
    [readOnly, input, onGraphUpdate],
  )

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onSelectNode(node.id === selectedNodeId ? null : node.id)
    },
    [onSelectNode, selectedNodeId],
  )

  const onNodeDragStop = useCallback(
    () => {
      onPositionsChange?.(extractNodePositions(nodes))
    },
    [onPositionsChange, nodes],
  )

  return (
    <div className={`h-full w-full neural-grid-bg ${className || ''}`}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={readOnly ? undefined : onNodesChange}
        onEdgesChange={readOnly ? undefined : onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onNodeDragStop={onNodeDragStop}
        nodeTypes={worldNodeTypes}
        edgeTypes={worldEdgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={!readOnly}
        nodesConnectable={!readOnly}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <Background variant={BackgroundVariant.Lines} gap={32} color="rgba(0,240,255,0.04)" />
        <Controls className="!glass-panel !border-neural-cyan/20 [&>button]:!bg-neural-glass [&>button]:!border-neural-cyan/20 [&>button]:!text-neural-cyan" />
        <MiniMap
          className="!glass-panel !border-neural-cyan/20"
          nodeColor={(n) => {
            if (n.type === 'worldCore') return '#00f0ff'
            if (n.type === 'faction') return '#7b5cff'
            if (n.type === 'character') return '#ff2d95'
            return '#ffb870'
          }}
        />
        {readOnly && (
          <Panel position="top-right" className="glass-panel px-2 py-1 text-[10px] font-neural-mono text-neural-cyan/60">
            READ ONLY
          </Panel>
        )}
      </ReactFlow>
    </div>
  )
}
