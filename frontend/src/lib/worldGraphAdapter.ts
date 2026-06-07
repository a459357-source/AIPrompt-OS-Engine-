import type { Node, Edge } from '@xyflow/react'

export type WorldNodeType = 'worldCore' | 'faction' | 'character' | 'artifact'

export interface WorldCoreData {
  title: string
  world: string
  genre: string[]
  scene: string
  main_goal: string
}

export interface FactionNodeData {
  index: number
  name: string
  type: string
  leader: string
  influence: number
}

export interface CharacterNodeData {
  index: number
  name: string
  isMain: boolean
  faction?: string
}

export interface ArtifactNodeData {
  index: number
  name: string
  type: string
  ownerId: string
}

export type WorldNodeData =
  | ({ nodeType: 'worldCore' } & WorldCoreData)
  | ({ nodeType: 'faction' } & FactionNodeData)
  | ({ nodeType: 'character' } & CharacterNodeData)
  | ({ nodeType: 'artifact' } & ArtifactNodeData)

export interface WorldGraphInput {
  title: string
  world: string
  genre: string[]
  scene: string
  main_goal: string
  characters: Array<{ name: string; isMain: boolean; faction?: string }>
  factions: Array<{ name: string; type: string; leader: string; influence: number }>
  artifacts: Array<{ name: string; type: string; ownerId: string }>
  characterRelations: Record<string, unknown>
  /** 来自 world_state_v2 的显式边，用于仪表盘只读图谱 */
  networkEdges?: Array<{ from: string; to: string; kind: string; label: string }>
  nodePositions?: Record<string, { x: number; y: number }>
}

const CORE_ID = 'world-core'

function pos(id: string, positions: Record<string, { x: number; y: number }> | undefined, x: number, y: number) {
  return positions?.[id] ?? { x, y }
}

export function buildWorldGraph(input: WorldGraphInput): { nodes: Node[]; edges: Edge[] } {
  const positions = input.nodePositions
  const nodes: Node[] = []
  const edges: Edge[] = []

  nodes.push({
    id: CORE_ID,
    type: 'worldCore',
    position: pos(CORE_ID, positions, 400, 200),
    data: {
      nodeType: 'worldCore',
      title: input.title || '未命名世界',
      world: input.world,
      genre: input.genre,
      scene: input.scene,
      main_goal: input.main_goal,
    },
  })

  input.factions.forEach((f, i) => {
    const id = `faction-${i}`
    const angle = (i / Math.max(input.factions.length, 1)) * Math.PI * 2
    nodes.push({
      id,
      type: 'faction',
      position: pos(id, positions, 400 + Math.cos(angle) * 220, 80 + Math.sin(angle) * 120),
      data: {
        nodeType: 'faction',
        index: i,
        name: f.name || '未命名势力',
        type: f.type,
        leader: f.leader,
        influence: f.influence,
      },
    })
  })

  input.characters.forEach((c, i) => {
    const id = `character-${i}`
    const row = Math.floor(i / 3)
    const col = i % 3
    nodes.push({
      id,
      type: 'character',
      position: pos(id, positions, 180 + col * 180, 320 + row * 140),
      data: {
        nodeType: 'character',
        index: i,
        name: c.name || (c.isMain ? '主角' : 'NPC'),
        isMain: c.isMain,
        faction: c.faction,
      },
    })

    if (c.faction) {
      const fi = input.factions.findIndex((f) => f.name === c.faction)
      if (fi >= 0) {
        edges.push({
          id: `belongs-${id}`,
          source: id,
          target: `faction-${fi}`,
          type: 'relation',
          data: { edgeType: 'belongsTo' },
          animated: true,
        })
      }
    }
  })

  input.factions.forEach((f, i) => {
    if (!f.leader) return
    const ci = input.characters.findIndex((c) => c.name === f.leader)
    if (ci >= 0) {
      edges.push({
        id: `leads-faction-${i}`,
        source: `faction-${i}`,
        target: `character-${ci}`,
        type: 'relation',
        data: { edgeType: 'leads' },
      })
    }
  })

  const mainChar = input.characters.find((c) => c.isMain) || input.characters[0]
  const mainIdx = input.characters.findIndex((c) => c === mainChar)
  if (mainIdx >= 0) {
    Object.keys(input.characterRelations).forEach((npcName) => {
      const ni = input.characters.findIndex((c) => c.name === npcName && !c.isMain)
      if (ni >= 0) {
        edges.push({
          id: `rel-${mainIdx}-${ni}`,
          source: `character-${mainIdx}`,
          target: `character-${ni}`,
          type: 'relation',
          data: { edgeType: 'relates' },
          animated: true,
          style: { stroke: '#ff2d95' },
        })
      }
    })
  }

  if (input.networkEdges?.length) {
    const charIdByName = new Map(input.characters.map((c, i) => [c.name, `character-${i}`]))
    const factionIdByName = new Map(input.factions.map((f, i) => [f.name, `faction-${i}`]))
    for (const e of input.networkEdges) {
      const src = charIdByName.get(e.from) ?? factionIdByName.get(e.from)
      const tgt = charIdByName.get(e.to) ?? factionIdByName.get(e.to)
      if (!src || !tgt || src === tgt) continue
      const edgeId = `net-${src}-${tgt}-${e.kind}`
      if (edges.some((edge) => edge.id === edgeId)) continue
      edges.push({
        id: edgeId,
        source: src,
        target: tgt,
        type: 'relation',
        data: { edgeType: e.kind, label: e.label },
        label: e.label,
        animated: e.kind === 'relation',
        style: e.kind === 'relation' ? { stroke: '#ff2d95' } : undefined,
      })
    }
  }

  input.artifacts.forEach((a, i) => {
    const id = `artifact-${i}`
    nodes.push({
      id,
      type: 'artifact',
      position: pos(id, positions, 620 + (i % 2) * 100, 400 + Math.floor(i / 2) * 90),
      data: {
        nodeType: 'artifact',
        index: i,
        name: a.name || '未命名物品',
        type: a.type,
        ownerId: a.ownerId,
      },
    })

    if (a.ownerId) {
      const ci = input.characters.findIndex((c) => c.name === a.ownerId)
      const fi = input.factions.findIndex((f) => f.name === a.ownerId)
      if (ci >= 0) {
        edges.push({
          id: `owns-${id}-char`,
          source: id,
          target: `character-${ci}`,
          type: 'relation',
          data: { edgeType: 'owns' },
        })
      } else if (fi >= 0) {
        edges.push({
          id: `owns-${id}-fac`,
          source: id,
          target: `faction-${fi}`,
          type: 'relation',
          data: { edgeType: 'owns' },
        })
      }
    }
  })

  return { nodes, edges }
}

export function extractNodePositions(nodes: Node[]): Record<string, { x: number; y: number }> {
  const out: Record<string, { x: number; y: number }> = {}
  for (const n of nodes) {
    out[n.id] = { x: n.position.x, y: n.position.y }
  }
  return out
}

export function parseNodeSelection(nodeId: string | null): {
  type: WorldNodeType | null
  index: number | null
} {
  if (!nodeId) return { type: null, index: null }
  if (nodeId === CORE_ID) return { type: 'worldCore', index: null }
  const m = nodeId.match(/^(faction|character|artifact)-(\d+)$/)
  if (!m) return { type: null, index: null }
  return { type: m[1] as WorldNodeType, index: parseInt(m[2], 10) }
}

export function handleNewConnection(
  connection: { source: string; target: string },
  input: WorldGraphInput,
): Partial<{
  factions: WorldGraphInput['factions']
  characters: WorldGraphInput['characters']
  characterRelations: WorldGraphInput['characterRelations']
}> | null {
  const src = parseNodeSelection(connection.source)
  const tgt = parseNodeSelection(connection.target)

  if (src.type === 'character' && tgt.type === 'faction' && src.index != null && tgt.index != null) {
    const characters = [...input.characters]
    characters[src.index] = {
      ...characters[src.index],
      faction: input.factions[tgt.index]?.name || '',
    }
    return { characters }
  }

  if (src.type === 'faction' && tgt.type === 'character' && src.index != null && tgt.index != null) {
    const factions = [...input.factions]
    factions[src.index] = {
      ...factions[src.index],
      leader: input.characters[tgt.index]?.name || '',
    }
    return { factions }
  }

  if (src.type === 'character' && tgt.type === 'character' && src.index != null && tgt.index != null) {
    const a = input.characters[src.index]
    const b = input.characters[tgt.index]
    if (!a?.name || !b?.name || a.isMain === b.isMain) return null
    const npcName = a.isMain ? b.name : a.name
    return {
      characterRelations: {
        ...input.characterRelations,
        [npcName]: input.characterRelations[npcName] || {
          relationshipType: 'friend',
          affection: 50,
          trust: 50,
          respect: 50,
          dependence: 50,
          hostility: 30,
          attraction: 50,
          tags: [],
        },
      },
    }
  }

  return null
}
