/** Parse relationship / stat / faction / event hints from AI option text. */

export type HintKind = 'character' | 'faction' | 'stat' | 'event'

export interface RelationHint {
  kind: HintKind
  name: string
  metric: string
  metricLabel: string
  icon: string
  delta: number
  tone: 'up' | 'down' | 'neutral' | 'new' | 'event' | 'warning'
  /** Full phrase for event / faction warnings */
  text?: string
}

const METRIC_ICONS: Record<string, string> = {
  trust: '🤝',
  affection: '❤️',
  respect: '🙏',
  dependence: '🔗',
  hostility: '⚔️',
  attraction: '💫',
  stat: '📊',
  faction: '🏛️',
  event: '⚡',
  default: '💞',
}

const METRIC_LABELS: Record<string, string> = {
  trust: '信任',
  affection: '好感',
  respect: '尊重',
  dependence: '依赖',
  hostility: '敌意',
  attraction: '吸引',
  stat: '数值',
  new: '新人',
}

const METRIC_ALIASES: Record<string, string> = {
  trust: 'trust', 信任: 'trust', 信任度: 'trust',
  affection: 'affection', 好感: 'affection', 好感度: 'affection',
  respect: 'respect', 尊重: 'respect', 尊重度: 'respect',
  dependence: 'dependence', 依赖: 'dependence', 依赖度: 'dependence',
  hostility: 'hostility', 敌意: 'hostility', 敌意度: 'hostility',
  attraction: 'attraction', 吸引: 'attraction', 吸引度: 'attraction',
}

const METRIC_WORDS = new Set(Object.keys(METRIC_ALIASES).filter((k) => /^[a-z]/i.test(k)))

const METRIC_TOKEN =
  'affection|trust|respect|dependence|hostility|attraction|好感度?|信任度?|尊重度?|依赖度?|敌意度?|吸引度?'

const DELTA = '[+\\-➕➖−－]'

function makeHint(
  kind: HintKind,
  name: string,
  metric: string,
  delta: number,
  extra?: Partial<RelationHint>,
): RelationHint {
  const tone =
    extra?.tone
    ?? (kind === 'event' ? 'event' : delta > 0 ? 'up' : delta < 0 ? 'down' : 'neutral')
  return {
    kind,
    name,
    metric,
    metricLabel: extra?.metricLabel ?? (extra?.text ? '' : (METRIC_LABELS[metric] || metric)),
    icon:
      extra?.icon
      ?? (kind === 'event' ? METRIC_ICONS.event : kind === 'faction' ? METRIC_ICONS.faction : kind === 'stat' ? METRIC_ICONS.stat : METRIC_ICONS[metric] || METRIC_ICONS.default),
    delta,
    tone,
    ...extra,
  }
}

function parseDelta(sign: string, value: number): number {
  if (!sign || sign === '+' || sign === '➕') return value
  return -value
}

function resolveMetric(raw: string): string {
  return METRIC_ALIASES[raw.toLowerCase()] || METRIC_ALIASES[raw] || 'trust'
}

/** 「若成功则苏晴」→「苏晴」 */
function cleanCharacterName(name: string): string {
  const cleaned = name.replace(/^若(?:成功|失败)?(?:则|时|后)?/, '').trim()
  return cleaned || name
}

export function parseOptionEffects(text: string): { hints: RelationHint[]; narrative: string[] } {
  if (!text?.trim()) return { hints: [], narrative: [] }

  const hints: RelationHint[] = []
  const seen = new Set<string>()
  const consumed = new Set<string>()

  const add = (hint: RelationHint) => {
    const key = `${hint.kind}:${hint.name}:${hint.metric}:${hint.delta}:${hint.text ?? ''}`
    if (seen.has(key)) return
    seen.add(key)
    hints.push(hint)
  }

  const mark = (snippet: string) => {
    if (snippet.trim()) consumed.add(snippet.trim())
  }

  // ── 1. Character / stat metrics (segment order, carry character name) ──
  const segments = text.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
  let lastCharacter = ''

  for (const part of segments) {
    const multiMatch = part.match(
      new RegExp(`^([\\u4e00-\\u9fff·]{1,12})\\s+((?:${METRIC_TOKEN})\\s*${DELTA}?\\s*\\d+\\s*)+$`, 'i'),
    )
    if (multiMatch) {
      lastCharacter = multiMatch[1]
      lastCharacter = cleanCharacterName(lastCharacter)
      const metricRe = new RegExp(`(${METRIC_TOKEN})\\s*(${DELTA}?)\\s*(\\d+)`, 'gi')
      let m: RegExpExecArray | null
      while ((m = metricRe.exec(part)) !== null) {
        add(makeHint('character', lastCharacter, resolveMetric(m[1]), parseDelta(m[2] || '+', parseInt(m[3], 10))))
      }
      mark(part)
      continue
    }

    const charMetricRe = new RegExp(
      `([\\u4e00-\\u9fff·]{2,8})(${METRIC_TOKEN})\\s*(${DELTA}?)\\s*(\\d+)`,
      'gi',
    )
    let matchedChar = false
    let m: RegExpExecArray | null
    while ((m = charMetricRe.exec(part)) !== null) {
      matchedChar = true
      lastCharacter = cleanCharacterName(m[1])
      add(makeHint('character', lastCharacter, resolveMetric(m[2]), parseDelta(m[3] || '+', parseInt(m[4], 10))))
    }
    if (matchedChar) {
      mark(part)
      continue
    }

    const bareMetricRe = new RegExp(`^(${METRIC_TOKEN})\\s*(${DELTA}?)\\s*(\\d+)$`, 'i')
    const bare = part.match(bareMetricRe)
    if (bare && lastCharacter) {
      add(makeHint('character', lastCharacter, resolveMetric(bare[1]), parseDelta(bare[2] || '+', parseInt(bare[3], 10))))
      mark(part)
      continue
    }

    const customStatRe = new RegExp(`^([\\u4e00-\\u9fff·]{2,10}(?:值|度))\\s*(${DELTA}?)\\s*(\\d+)$`)
    const statMatch = part.match(customStatRe)
    if (statMatch) {
      const label = statMatch[1]
      add(makeHint('stat', label.replace(/[值度]$/, '') || label, 'stat', parseDelta(statMatch[2] || '+', parseInt(statMatch[3], 10)), {
        metricLabel: label,
      }))
      mark(part)
      continue
    }

    const arrowRe = /([\u4e00-\u9fff·]{1,12})\s*([↑➕\+↓➖\-])\s*(\d+)/g
    while ((m = arrowRe.exec(part)) !== null) {
      lastCharacter = cleanCharacterName(m[1])
      add(makeHint('character', lastCharacter, 'trust', parseDelta(m[2], parseInt(m[3], 10))))
      mark(part)
    }
  }

  // ── 2. Events ──
  const eventPatterns = [
    /但?可能触发[^，,、|]+(?:出手|反击|干预|现身|降临)?/g,
    /可能(?:导致|引发|引来)[^，,、|]+/g,
    /(?:重要|重大)事件[^，,、|]*/g,
  ]
  for (const re of eventPatterns) {
    let m: RegExpExecArray | null
    const clone = new RegExp(re.source, re.flags)
    while ((m = clone.exec(text)) !== null) {
      const phrase = m[0].replace(/^但/, '').trim()
      add(makeHint('event', '', 'event', 0, { tone: 'event', text: phrase, icon: '⚡' }))
      mark(m[0])
    }
  }

  // ── 3. Faction conflict / reputation (不含「好感」，避免与角色混淆) ──
  const factionConflictRe = /(?:直接)?与([\u4e00-\u9fff·]{2,10})(?:势力|门派|宗|帮|盟|教|族|国|军)?冲突/g
  let fm: RegExpExecArray | null
  while ((fm = factionConflictRe.exec(text)) !== null) {
    add(makeHint('faction', fm[1], 'faction', 0, {
      tone: 'warning',
      text: `与${fm[1]}冲突`,
      icon: '🏛️',
    }))
    mark(fm[0])
  }

  const factionDeltaRe = new RegExp(
    `([\\u4e00-\\u9fff·]{2,10})(?:势力|门派)?(?:声望|关系|态度)\\s*(${DELTA}?)\\s*(\\d+)`,
    'g',
  )
  while ((fm = factionDeltaRe.exec(text)) !== null) {
    add(makeHint('faction', fm[1], 'faction', parseDelta(fm[2] || '+', parseInt(fm[3], 10))))
    mark(fm[0])
  }

  // ── 4. Fallback English metrics ──
  if (!hints.some((h) => h.kind === 'character')) {
    const bareRe = new RegExp(`\\b(${METRIC_TOKEN})\\s*(${DELTA}?)\\s*(\\d+)`, 'gi')
    let m: RegExpExecArray | null
    while ((m = bareRe.exec(text)) !== null) {
      if (METRIC_WORDS.has(m[1].toLowerCase())) {
        add(makeHint('character', '角色', resolveMetric(m[1]), parseDelta(m[2] || '+', parseInt(m[3], 10))))
      }
    }
  }

  if (/新人|new/i.test(text)) {
    add(makeHint('character', '新人', 'new', 0, { tone: 'new', metricLabel: METRIC_LABELS.new, icon: '✨' }))
  }

  const narrative = segments.filter((s) => !consumed.has(s) && s.length > 1)

  return { hints, narrative }
}

export function parseRelationHints(text: string): RelationHint[] {
  return parseOptionEffects(text).hints
}

export function deltaArrow(delta: number): string {
  if (delta > 0) return '↑'
  if (delta < 0) return '↓'
  return '·'
}

/** 解析选项字符串：支持「行动→发展|态度|影响」与「行动|态度|影响」（无箭头） */
export interface ParsedGameOption {
  action: string
  consequence: string
  attitude: string
  relation: string
  effectText: string
}

const EFFECTS_LIKE = /(?:affection|trust|respect|dependence|hostility|attraction|[\u4e00-\u9fff·]{1,12}\s*(?:affection|trust|respect|dependence|hostility|attraction|[\u4e00-\u9fff]+(?:值|度)?\s*[+−\-↑↓➕➖]))/i

export function parseGameOption(choice: string): ParsedGameOption {
  const trimmed = choice.trim()
  if (!trimmed) {
    return { action: '', consequence: '', attitude: '', relation: '', effectText: '' }
  }

  const empty = { consequence: '', attitude: '', relation: '', effectText: '' }

  if (/\s*[→]\s*/.test(trimmed)) {
    const parts = trimmed.split(/\s*[→]\s*/)
    const action = (parts[0] || trimmed).trim()
    const meta = parts.slice(1).join(' → ').trim()
    const segments = meta.split(/\s*\|\s*/).map((s) => s.trim())
    const consequence = segments[0] || ''
    const attitude = segments[1] || ''
    const relation = segments.slice(2).join(' | ') || ''
    const effectText = [consequence, relation].filter(Boolean).join('，')
    return { action, consequence, attitude, relation, effectText }
  }

  const pipeParts = trimmed.split(/\s*\|\s*/).map((s) => s.trim()).filter(Boolean)
  if (pipeParts.length >= 3) {
    const action = pipeParts[0]
    const attitude = pipeParts[pipeParts.length - 2]
    const relation = pipeParts[pipeParts.length - 1]
    const consequence = pipeParts.length > 3 ? pipeParts.slice(1, -2).join(' | ') : ''
    const effectText = [consequence, relation].filter(Boolean).join('，')
    return { action, consequence, attitude, relation, effectText }
  }

  if (pipeParts.length === 2) {
    const [first, second] = pipeParts
    if (EFFECTS_LIKE.test(second)) {
      return { action: first, ...empty, relation: second, effectText: second }
    }
    return { action: first, ...empty, attitude: second }
  }

  return { action: trimmed, ...empty }
}

/** 单行状态摘要：艾莉丝 好感+2 信任+1 */
export function formatOptionStatusMetrics(hints: RelationHint[]): string {
  const charGroups = new Map<string, string[]>()
  const extras: string[] = []

  for (const h of hints) {
    if (h.kind === 'event' && h.text) {
      extras.push(h.text)
      continue
    }
    if (h.kind === 'faction') {
      const seg = h.text || (h.delta !== 0 ? `${h.name}${h.delta > 0 ? '+' : ''}${h.delta}` : h.name)
      if (seg) extras.push(seg)
      continue
    }
    if (h.kind === 'stat' && h.metricLabel) {
      extras.push(
        h.delta !== 0
          ? `${h.metricLabel}${h.delta > 0 ? '+' : ''}${h.delta}`
          : h.metricLabel,
      )
      continue
    }
    if (h.kind === 'character' && h.name && h.metric !== 'new') {
      const seg =
        h.delta !== 0
          ? `${h.metricLabel}${h.delta > 0 ? '+' : ''}${h.delta}`
          : h.metricLabel
      if (seg) {
        const list = charGroups.get(h.name) ?? []
        list.push(seg)
        charGroups.set(h.name, list)
      }
    }
  }

  const charParts = [...charGroups.entries()].map(([name, segs]) => `${name} ${segs.join(' ')}`)
  return [...charParts, ...extras].join(' · ')
}
