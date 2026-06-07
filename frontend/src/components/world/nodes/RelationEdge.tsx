import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react'

export function RelationEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  animated,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  })
  return (
    <BaseEdge
      id={id}
      path={edgePath}
      style={{
        strokeWidth: 2,
        stroke: '#58a6ff',
        ...style,
      }}
      markerEnd={markerEnd}
      interactionWidth={20}
      className={animated ? 'animated' : undefined}
    />
  )
}
