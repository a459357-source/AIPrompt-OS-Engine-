import type { WorldGraphInput } from './worldGraphAdapter'

const CORE_ID = 'world-core'

const SIZE = {
  worldCore: { w: 144, h: 144 },
  faction: { w: 132, h: 68 },
  character: { w: 112, h: 62 },
  artifact: { w: 96, h: 96 },
} as const

type NodeKind = keyof typeof SIZE

interface LayoutNode {
  id: string
  kind: NodeKind
  cx: number
  cy: number
}

function centerOf(kind: NodeKind, x: number, y: number) {
  const s = SIZE[kind]
  return { cx: x + s.w / 2, cy: y + s.h / 2 }
}

function topLeft(kind: NodeKind, cx: number, cy: number) {
  const s = SIZE[kind]
  return { x: cx - s.w / 2, y: cy - s.h / 2 }
}

function spreadOnArc(
  count: number,
  cx: number,
  cy: number,
  radius: number,
  startAngle: number,
  endAngle: number,
): Array<{ cx: number; cy: number }> {
  if (count <= 0) return []
  if (count === 1) {
    const a = (startAngle + endAngle) / 2
    return [{ cx: cx + Math.cos(a) * radius, cy: cy + Math.sin(a) * radius }]
  }
  return Array.from({ length: count }, (_, i) => {
    const t = i / (count - 1)
    const a = startAngle + (endAngle - startAngle) * t
    return { cx: cx + Math.cos(a) * radius, cy: cy + Math.sin(a) * radius }
  })
}

function resolveOverlaps(nodes: LayoutNode[], iterations = 48) {
  for (let pass = 0; pass < iterations; pass++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i]
        const b = nodes[j]
        const dx = b.cx - a.cx
        const dy = b.cy - a.cy
        const dist = Math.hypot(dx, dy) || 0.01
        const minDist =
          (Math.max(SIZE[a.kind].w, SIZE[a.kind].h) + Math.max(SIZE[b.kind].w, SIZE[b.kind].h)) / 2 + 28
        if (dist < minDist) {
          const push = (minDist - dist) / 2
          const nx = dx / dist
          const ny = dy / dist
          if (a.id === CORE_ID) {
            b.cx += nx * (minDist - dist)
            b.cy += ny * (minDist - dist)
          } else if (b.id === CORE_ID) {
            a.cx -= nx * (minDist - dist)
            a.cy -= ny * (minDist - dist)
          } else {
            a.cx -= nx * push
            a.cy -= ny * push
            b.cx += nx * push
            b.cy += ny * push
          }
        }
      }
    }
  }
}

/** 关系结构指纹：变化时触发重新布局 */
export function graphStructureKey(input: WorldGraphInput): string {
  return JSON.stringify({
    factions: input.factions.map((f) => `${f.name}|${f.leader}`),
    characters: input.characters.map((c) => `${c.name}|${c.isMain}|${c.faction || ''}`),
    artifacts: input.artifacts.map((a) => `${a.name}|${a.ownerId}`),
    relations: Object.keys(input.characterRelations).sort(),
    network: (input.networkEdges || []).map((e) => `${e.from}->${e.to}:${e.kind}`),
  })
}

/**
 * 语义分层布局：核心居中 → 势力弧顶 → 主角下方 → NPC 聚类于势力/关系 → 物品挂靠持有者
 */
export function computeRelationLayout(input: WorldGraphInput): Record<string, { x: number; y: number }> {
  const cx = 520
  const cy = 360
  const layoutNodes: LayoutNode[] = []

  layoutNodes.push({
    id: CORE_ID,
    kind: 'worldCore',
    ...centerOf('worldCore', cx - SIZE.worldCore.w / 2, cy - SIZE.worldCore.h / 2),
  })

  const factionIds = input.factions.map((_, i) => `faction-${i}`)
  const factionSlots = spreadOnArc(
    factionIds.length,
    cx,
    cy - 20,
    Math.min(300, 220 + factionIds.length * 18),
    Math.PI * 1.08,
    Math.PI * 1.92,
  )
  factionIds.forEach((id, i) => {
    const slot = factionSlots[i] || { cx, cy: cy - 240 }
    layoutNodes.push({ id, kind: 'faction', ...slot })
  })

  const mainIdx = input.characters.findIndex((c) => c.isMain)
  const mainId = mainIdx >= 0 ? `character-${mainIdx}` : null
  if (mainId) {
    layoutNodes.push({
      id: mainId,
      kind: 'character',
      cx,
      cy: cy + 175,
    })
  }

  const factionCenters = new Map(
    factionIds.map((id, i) => {
      const n = layoutNodes.find((ln) => ln.id === id)!
      return [input.factions[i]?.name || '', n]
    }),
  )

  const npcIndices = input.characters
    .map((c, i) => ({ c, i }))
    .filter(({ c, i }) => !c.isMain && i !== mainIdx)

  const byFaction = new Map<string, number[]>()
  const unassigned: number[] = []
  const relatedToMain: number[] = []

  for (const { c, i } of npcIndices) {
    if (c.faction && factionCenters.has(c.faction)) {
      const list = byFaction.get(c.faction) || []
      list.push(i)
      byFaction.set(c.faction, list)
    } else if (c.name && input.characterRelations[c.name]) {
      relatedToMain.push(i)
    } else {
      unassigned.push(i)
    }
  }

  byFaction.forEach((indices, factionName) => {
    const fac = factionCenters.get(factionName)
    if (!fac) return
    const angleToCenter = Math.atan2(fac.cy - cy, fac.cx - cx)
    const slots = spreadOnArc(
      indices.length,
      fac.cx,
      fac.cy,
      95 + indices.length * 12,
      angleToCenter - 0.55,
      angleToCenter + 0.55,
    )
    indices.forEach((charIdx, si) => {
      const slot = slots[si] || slots[0]
      layoutNodes.push({
        id: `character-${charIdx}`,
        kind: 'character',
        ...slot,
      })
    })
  })

  const relatedSlots = spreadOnArc(
    relatedToMain.length,
    cx,
    cy + 175,
    200,
    Math.PI * 0.15,
    Math.PI * 0.85,
  )
  relatedToMain.forEach((charIdx, si) => {
    const slot = relatedSlots[si] || { cx: cx + 160, cy: cy + 120 }
    layoutNodes.push({
      id: `character-${charIdx}`,
      kind: 'character',
      ...slot,
    })
  })

  const unassignedSlots = spreadOnArc(
    unassigned.length,
    cx,
    cy + 300,
    180 + unassigned.length * 10,
    Math.PI * 0.05,
    Math.PI * 0.95,
  )
  unassigned.forEach((charIdx, si) => {
    const slot = unassignedSlots[si] || { cx, cy: cy + 320 }
    layoutNodes.push({
      id: `character-${charIdx}`,
      kind: 'character',
      ...slot,
    })
  })

  input.artifacts.forEach((art, i) => {
    const id = `artifact-${i}`
    let owner: LayoutNode | undefined
    if (art.ownerId) {
      const ci = input.characters.findIndex((c) => c.name === art.ownerId)
      const fi = input.factions.findIndex((f) => f.name === art.ownerId)
      if (ci >= 0) owner = layoutNodes.find((n) => n.id === `character-${ci}`)
      else if (fi >= 0) owner = layoutNodes.find((n) => n.id === `faction-${fi}`)
    }
    if (owner) {
      const angle = Math.atan2(owner.cy - cy, owner.cx - cx) + (i % 2 === 0 ? 0.35 : -0.35)
      const r = 72
      layoutNodes.push({
        id,
        kind: 'artifact',
        cx: owner.cx + Math.cos(angle) * r,
        cy: owner.cy + Math.sin(angle) * r,
      })
    } else {
      layoutNodes.push({
        id,
        kind: 'artifact',
        cx: cx + 320 + (i % 3) * 90,
        cy: cy + 280 + Math.floor(i / 3) * 80,
      })
    }
  })

  resolveOverlaps(layoutNodes)

  const out: Record<string, { x: number; y: number }> = {}
  for (const n of layoutNodes) {
    out[n.id] = topLeft(n.kind, n.cx, n.cy)
  }
  return out
}
