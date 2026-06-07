export type FactionVisibility = 'public' | 'hidden'

export interface FactionMembership {
  faction: string
  visibility: FactionVisibility
}

type FactionLike = { faction?: string; factionMemberships?: FactionMembership[] }

function dedupeMemberships(memberships: FactionMembership[]): FactionMembership[] {
  const map = new Map<string, FactionVisibility>()
  for (const m of memberships) {
    const name = m.faction?.trim()
    if (!name) continue
    map.set(name, m.visibility === 'hidden' ? 'hidden' : 'public')
  }
  return Array.from(map, ([faction, visibility]) => ({ faction, visibility }))
}

export function normalizeFactionMemberships(
  char: FactionLike,
  factions?: Array<{ name: string }>,
): FactionMembership[] {
  const validNames = new Set((factions || []).map((f) => f.name).filter(Boolean))
  const fromArray = (char.factionMemberships || []).filter((m) => m?.faction?.trim())
  if (fromArray.length) {
    const normalized = fromArray.map((m) => ({
      faction: m.faction.trim(),
      visibility: (m.visibility === 'hidden' ? 'hidden' : 'public') as FactionVisibility,
    }))
    const deduped = dedupeMemberships(normalized)
    if (!validNames.size) return deduped
    return deduped.filter((m) => validNames.has(m.faction))
  }
  const legacy = (char.faction || '').trim()
  if (!legacy) return []
  if (validNames.size && !validNames.has(legacy)) return []
  return [{ faction: legacy, visibility: 'public' }]
}

export function primaryPublicFaction(memberships: FactionMembership[]): string {
  const pub = memberships.find((m) => m.visibility === 'public')
  if (pub) return pub.faction
  return memberships[0]?.faction || ''
}

export function syncCharacterFactions<T extends FactionLike>(char: T): T & {
  factionMemberships: FactionMembership[]
  faction: string
} {
  const factionMemberships = normalizeFactionMemberships(char)
  return {
    ...char,
    factionMemberships,
    faction: primaryPublicFaction(factionMemberships),
  }
}

/** 拖线：无则追加明面隶属，已有则切换明/暗 */
export function toggleOrAddMembership(
  memberships: FactionMembership[],
  factionName: string,
): FactionMembership[] {
  const name = factionName.trim()
  if (!name) return memberships
  const idx = memberships.findIndex((m) => m.faction === name)
  if (idx < 0) {
    return dedupeMemberships([...memberships, { faction: name, visibility: 'public' }])
  }
  const next = [...memberships]
  next[idx] = {
    ...next[idx],
    visibility: next[idx].visibility === 'public' ? 'hidden' : 'public',
  }
  return next
}

export function removeMembership(
  memberships: FactionMembership[],
  factionName: string,
): FactionMembership[] {
  return memberships.filter((m) => m.faction !== factionName)
}

export function belongsToEdgeStyle(visibility: FactionVisibility): Record<string, string | number> {
  if (visibility === 'hidden') {
    return {
      stroke: 'rgba(136, 146, 176, 0.55)',
      strokeDasharray: '6 4',
      opacity: 0.65,
    }
  }
  return { stroke: '#58a6ff' }
}

export function formatMembershipLabel(m: FactionMembership): string {
  return m.visibility === 'hidden' ? `${m.faction}(暗)` : m.faction
}

export function formatMembershipsSummary(memberships: FactionMembership[]): string {
  if (!memberships.length) return ''
  return memberships.map(formatMembershipLabel).join(' · ')
}
