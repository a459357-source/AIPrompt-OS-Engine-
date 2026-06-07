import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  addEdge,
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
  onApplyDemo?: () => void
  readOnly?: boolean
  focusSection?: string | null
  className?: string
}

function WorldGraphCanvasInner({
  input,
  selectedNodeId,
  onSelectNode,
  onPositionsChange,
  onGraphUpdate,
  onApplyDemo,
  readOnly = false,
  className,
}: WorldGraphCanvasProps) {
  const graph = useMemo(() => buildWorldGraph(input), [input])
  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges)

  useEffect(() => {
    setNodes((prev) => {
      const prevById = new Map(prev.map((n) => [n.id, n]))
      return graph.nodes.map((n) => ({
        ...n,
        position: prevById.get(n.id)?.position ?? n.position,
        selected: n.id === selectedNodeId,
      }))
    })
    setEdges(graph.edges)
  }, [graph, selectedNodeId, setNodes, setEdges])

  const onConnect = useCallback(
    (connection: Connection) => {
      if (readOnly || !connection.source || !connection.target || !onGraphUpdate) return
      const update = handleNewConnection(
        { source: connection.source, target: connection.target },
        input,
      )
      if (!update) return
      onGraphUpdate(update)
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            type: 'relation',
            id: `pending-${connection.source}-${connection.target}-${Date.now()}`,
          },
          eds,
        ),
      )
    },
    [readOnly, input, onGraphUpdate, setEdges],
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
        defaultEdgeOptions={{ type: 'relation' }}
        connectionLineStyle={{ stroke: '#58a6ff', strokeWidth: 2 }}
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
        {!readOnly && onApplyDemo && (
          <Panel position="top-left" className="m-12 md:m-4">
            <button
              type="button"
              onClick={onApplyDemo}
              className="glass-panel px-3 py-1.5 text-xs text-neural-cyan border border-neural-cyan/30 hover:bg-neural-cyan/10 transition-colors rounded-md"
            >
              🔗 加载示例连线
            </button>
          </Panel>
        )}
        {readOnly && (
          <Panel position="top-right" className="glass-panel px-2 py-1 text-[10px] font-neural-mono text-neural-cyan/60">
            READ ONLY
          </Panel>
        )}
      </ReactFlow>
    </div>
  )
}

export function WorldGraphCanvas(props: WorldGraphCanvasProps) {
  return (
    <ReactFlowProvider>
      <WorldGraphCanvasInner {...props} />
    </ReactFlowProvider>
  )
}
