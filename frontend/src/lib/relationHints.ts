/** Parse relationship hint strings from AI options into display chips. */

export interface RelationHint {
  name: string
  metric: string
  metricLabel: string
  icon: string
  delta: number
  tone: 'up' | 'down' | 'neutral' | 'new'
}

const METRIC_ICONS: Record<string, string> = {
  trust: '🤝',
  affection: '❤️',
  respect: '🙏',
  dependence: '🔗',
  hostility: '⚔️',
  attraction: '💫',
  default: '💞',
}

const METRIC_LABELS: Record<string, string> = {
  trust: '信任',
  affection: '好感',
  respect: '尊重',
  dependence: '依赖',
  hostility: '敌意',
  attraction: '吸引',
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

function makeHint(name: string, metric: string, delta: number): RelationHint {
  return {
    name,
    metric,
    metricLabel: METRIC_LABELS[metric] || metric,
    icon: METRIC_ICONS[metric] || METRIC_ICONS.default,
    delta,
    tone: delta > 0 ? 'up' : delta < 0 ? 'down' : 'neutral',
  }
}

function parseDelta(sign: string, value: number): number {
  return sign === '↓' || sign === '➖' || sign === '-' ? -value : value
}

export function parseRelationHints(text: string): RelationHint[] {
  if (!text?.trim()) return []
  const hints: RelationHint[] = []
  const seen = new Set<string>()

  const add = (name: string, metric: string, delta: number) => {
    const key = `${name}:${metric}:${delta}`
    if (seen.has(key)) return
    seen.add(key)
    hints.push(makeHint(name, metric, delta))
  }

  // Split by comma /顿号 — each segment may carry its own character name
  const segments = text.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
  const parts = segments.length > 1 ? segments : [text.trim()]

  for (const part of parts) {
    // 「景璃 affection+2 trust+1」— name once, multiple English metrics
    const multiMatch = part.match(
      new RegExp(`^([\\u4e00-\\u9fff·]{1,12})\\s+((?:${METRIC_TOKEN})\\s*[+\\-➕➖]?\\s*\\d+\\s*)+$`, 'i'),
    )
    if (multiMatch) {
      const charName = multiMatch[1]
      const metricRe = new RegExp(`(${METRIC_TOKEN})\\s*([+\\-➕➖]?)\\s*(\\d+)`, 'gi')
      let m: RegExpExecArray | null
      while ((m = metricRe.exec(part)) !== null) {
        const metric = METRIC_ALIASES[m[1].toLowerCase()] || METRIC_ALIASES[m[1]] || 'trust'
        add(charName, metric, parseDelta(m[2] || '+', parseInt(m[3], 10)))
      }
      continue
    }

    // 「艾琳↑5」 / 「艾琳 信任度+10」
    const arrowRe = /([\u4e00-\u9fff·]{1,12})\s*([↑➕\+↓➖\-])\s*(\d+)/g
    let m: RegExpExecArray | null
    while ((m = arrowRe.exec(part)) !== null) {
      add(m[1], 'trust', parseDelta(m[2], parseInt(m[3], 10)))
    }

    const namedMetricRe = new RegExp(
      `([\\u4e00-\\u9fff·]{1,12})\\s*(${METRIC_TOKEN})\\s*([+\\-➕➖]?)\\s*(\\d+)`,
      'gi',
    )
    while ((m = namedMetricRe.exec(part)) !== null) {
      const metric = METRIC_ALIASES[m[2].toLowerCase()] || METRIC_ALIASES[m[2]] || 'trust'
      add(m[1], metric, parseDelta(m[3] || '+', parseInt(m[4], 10)))
    }
  }

  // Fallback: scan whole text for stray English metrics (avoid matching metric as character)
  if (hints.length === 0) {
    const bareRe = new RegExp(`\\b(${METRIC_TOKEN})\\s*([+\\-➕➖]?)\\s*(\\d+)`, 'gi')
    let m: RegExpExecArray | null
    while ((m = bareRe.exec(text)) !== null) {
      if (METRIC_WORDS.has(m[1].toLowerCase())) {
        const metric = METRIC_ALIASES[m[1].toLowerCase()] || 'trust'
        add('角色', metric, parseDelta(m[2] || '+', parseInt(m[3], 10)))
      }
    }
  }

  if (/新人|new/i.test(text)) {
    hints.push({
      name: '新人',
      metric: 'new',
      metricLabel: METRIC_LABELS.new,
      icon: '✨',
      delta: 0,
      tone: 'new',
    })
  }

  return hints
}
