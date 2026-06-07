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
    edges.push({
      id: `core-faction-${i}`,
      source: CORE_ID,
      target: id,
      type: 'relation',
      data: { edgeType: 'inWorld' },
      style: { stroke: 'rgba(0,240,255,0.45)', strokeDasharray: '6 4' },
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
    edges.push({
      id: `core-main-${mainIdx}`,
      source: CORE_ID,
      target: `character-${mainIdx}`,
      type: 'relation',
      data: { edgeType: 'protagonist' },
      animated: true,
      style: { stroke: '#ff2d95' },
    })
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

export type WorldGraphUpdate = Partial<{
  factions: WorldGraphInput['factions']
  characters: WorldGraphInput['characters']
  artifacts: WorldGraphInput['artifacts']
  characterRelations: WorldGraphInput['characterRelations']
}>

function setProtagonist(input: WorldGraphInput, charIndex: number): WorldGraphUpdate | null {
  if (charIndex < 0 || charIndex >= input.characters.length) return null
  const characters = input.characters.map((c, i) => ({
    ...c,
    isMain: i === charIndex,
  }))
  return { characters }
}

function setCharacterFaction(
  input: WorldGraphInput,
  charIndex: number,
  factionIndex: number,
): WorldGraphUpdate | null {
  if (charIndex < 0 || factionIndex < 0) return null
  const factionName = input.factions[factionIndex]?.name || ''
  const characters = [...input.characters]
  characters[charIndex] = { ...characters[charIndex], faction: factionName }
  return { characters }
}

function setFactionLeader(
  input: WorldGraphInput,
  factionIndex: number,
  charIndex: number,
): WorldGraphUpdate | null {
  if (factionIndex < 0 || charIndex < 0) return null
  const leaderName = input.characters[charIndex]?.name || ''
  const factions = [...input.factions]
  factions[factionIndex] = { ...factions[factionIndex], leader: leaderName }
  return { factions }
}

function setArtifactOwner(
  input: WorldGraphInput,
  artifactIndex: number,
  ownerName: string,
): WorldGraphUpdate | null {
  if (artifactIndex < 0) return null
  const artifacts = [...input.artifacts]
  artifacts[artifactIndex] = { ...artifacts[artifactIndex], ownerId: ownerName }
  return { artifacts }
}

function addCharacterRelation(
  input: WorldGraphInput,
  indexA: number,
  indexB: number,
): WorldGraphUpdate | null {
  const a = input.characters[indexA]
  const b = input.characters[indexB]
  if (!a || !b || a.isMain === b.isMain) return null
  const npcName = a.isMain ? b.name : a.name
  if (!npcName.trim()) return null
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

export function handleNewConnection(
  connection: { source: string; target: string },
  input: WorldGraphInput,
): WorldGraphUpdate | null {
  const src = parseNodeSelection(connection.source)
  const tgt = parseNodeSelection(connection.target)

  // 世界核心 ↔ 角色：指定主角
  if (src.type === 'worldCore' && tgt.type === 'character' && tgt.index != null) {
    return setProtagonist(input, tgt.index)
  }
  if (src.type === 'character' && tgt.type === 'worldCore' && src.index != null) {
    return setProtagonist(input, src.index)
  }

  // 角色 ↔ 势力：所属
  if (src.type === 'character' && tgt.type === 'faction' && src.index != null && tgt.index != null) {
    return setCharacterFaction(input, src.index, tgt.index)
  }
  if (src.type === 'faction' && tgt.type === 'character' && src.index != null && tgt.index != null) {
    const char = input.characters[tgt.index]
    const fac = input.factions[src.index]
    // 已有首领且连到不同角色 → 视为所属；否则设为首领
    if (fac?.leader && char?.name && fac.leader !== char.name) {
      return setCharacterFaction(input, tgt.index, src.index)
    }
    return setFactionLeader(input, src.index, tgt.index)
  }

  // 角色 ↔ 角色：关系
  if (src.type === 'character' && tgt.type === 'character' && src.index != null && tgt.index != null) {
    return addCharacterRelation(input, src.index, tgt.index)
  }

  // 角色 / 势力 → 物品：持有者
  if (src.type === 'character' && tgt.type === 'artifact' && src.index != null && tgt.index != null) {
    const ownerName = input.characters[src.index]?.name || ''
    if (!ownerName.trim()) return null
    return setArtifactOwner(input, tgt.index, ownerName)
  }
  if (src.type === 'faction' && tgt.type === 'artifact' && src.index != null && tgt.index != null) {
    const ownerName = input.factions[src.index]?.name || ''
    if (!ownerName.trim()) return null
    return setArtifactOwner(input, tgt.index, ownerName)
  }
  if (src.type === 'artifact' && tgt.type === 'character' && src.index != null && tgt.index != null) {
    const ownerName = input.characters[tgt.index]?.name || ''
    if (!ownerName.trim()) return null
    return setArtifactOwner(input, src.index, ownerName)
  }
  if (src.type === 'artifact' && tgt.type === 'faction' && src.index != null && tgt.index != null) {
    const ownerName = input.factions[tgt.index]?.name || ''
    if (!ownerName.trim()) return null
    return setArtifactOwner(input, src.index, ownerName)
  }

  return null
}

/** 示例数据：预填势力/角色/关系，便于验证图谱连线可见 */
export function createDemoGraphSeed(): WorldGraphUpdate & {
  title: string
  scene: string
  main_goal: string
} {
  const factions: WorldGraphInput['factions'] = [
    { name: '星穹学院', type: 'school', leader: '苏浅', influence: 72 },
    { name: '暗域议会', type: 'organization', leader: '', influence: 58 },
  ]
  const characters: WorldGraphInput['characters'] = [
    { name: '林远', isMain: true, faction: '' },
    { name: '苏浅', isMain: false, faction: '星穹学院' },
    { name: '陈默', isMain: false, faction: '暗域议会' },
  ]
  return {
    title: '星痕纪元',
    scene: '星穹学院·新生报到处',
    main_goal: '查明暗域议会渗透学院的真相',
    factions,
    characters,
    characterRelations: {
      苏浅: {
        relationshipType: 'friend',
        affection: 62,
        trust: 55,
        respect: 60,
        dependence: 40,
        hostility: 10,
        attraction: 45,
        tags: ['青梅竹马', '同窗'],
      },
      陈默: {
        relationshipType: 'rival',
        affection: 35,
        trust: 28,
        respect: 50,
        dependence: 20,
        hostility: 55,
        attraction: 15,
        tags: ['对手', '互相试探'],
      },
    },
    artifacts: [
      { name: '学院徽章', type: 'personal', ownerId: '林远' },
    ],
  }
}
