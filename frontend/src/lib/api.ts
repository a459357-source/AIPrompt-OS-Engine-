import type {
  WorldGenResponse,
  FieldGenRequest,
  FieldGenResponse,
  GameTurnResponse,
  CustomRules,
} from './types'
import { logger } from './logger'

const BASE = ''

async function post<T>(url: string, body: Record<string, string>): Promise<T> {
  const params = new URLSearchParams(body)
  const startTime = Date.now()
  logger.info('API', `→ POST ${url}`, { ...body })

  let res: Response
  try {
    res = await fetch(`${BASE}${url}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    })
  } catch (err) {
    logger.error('API', `✗ POST ${url} — network error`, err)
    throw err
  }

  if (!res.ok) {
    logger.error('API', `✗ POST ${url} — HTTP ${res.status}`, { status: res.status })
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }

  let data: T & { error?: string }
  try {
    data = await res.json()
  } catch (err) {
    logger.error('API', `✗ POST ${url} — JSON parse failed`, err)
    throw new Error('服务器返回了无效数据')
  }

  const elapsed = Date.now() - startTime
  if (data.error) {
    logger.warn('API', `✗ POST ${url} — ${elapsed}ms — ${data.error}`)
    throw new Error(data.error)
  }

  logger.info('API', `✓ POST ${url} — ${elapsed}ms`)
  return data as T
}

export async function generateWorld(keywords: string): Promise<WorldGenResponse> {
  return post<WorldGenResponse>('/generate-world', { keywords })
}

export async function generateField(req: FieldGenRequest): Promise<FieldGenResponse> {
  return post<FieldGenResponse>('/generate-field', {
    field: req.field,
    title: req.title || '',
    world: req.world || '',
    genre: (req.genre || '').toString(),
    context: req.context || '',
    char_role: req.char_role || '',
  })
}

export async function generateRules(data: {
  title: string
  world: string
  genre: string
  char1_name: string
  char1_role: string
  char2_name: string
  char2_role: string
}): Promise<CustomRules> {
  return post<CustomRules>('/generate-rules', {
    title: data.title,
    world: data.world,
    genre: data.genre,
    char1_name: data.char1_name,
    char1_role: data.char1_role,
    char2_name: data.char2_name,
    char2_role: data.char2_role,
  })
}

export async function createStory(formData: FormData): Promise<Response> {
  return fetch('/new', { method: 'POST', body: formData })
}

export async function getGameState(): Promise<{ story: string; options: string[]; state: Record<string, unknown>; not_started?: boolean; error?: string }> {
  const res = await fetch('/api/game-state')
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { story: '', options: [], state: {}, error: (data as { error?: string }).error || 'Failed to load game' }
  }
  return res.json()
}

// ── NPCs ──
export interface NpcData {
  name: string
  isMain: boolean
  role_tags: string[]
  personality_tags: string[]
  appearance: string
  relationship: string[]
  goal: string
  secret: string
  background: string
  special_ability: string
  faction: string
  trust: number
  trust_pct: number
  flags: string[]
}

export async function getNpcs(): Promise<{ characters: NpcData[]; stats: { total: number; main: number; npc: number; avg_trust: number }; error?: string }> {
  const res = await fetch('/api/npcs')
  if (!res.ok) return { characters: [], stats: { total: 0, main: 0, npc: 0, avg_trust: 0 }, error: `HTTP ${res.status}` }
  return res.json()
}

export async function generateNpc(roleHint?: string): Promise<NpcData & { error?: string }> {
  const fd = new FormData()
  fd.append('role_hint', roleHint || '')
  const res = await fetch('/api/npcs/generate', { method: 'POST', body: fd })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { ...data, name: '', isMain: false, role_tags: [], personality_tags: [], appearance: '', relationship: [], goal: '', secret: '', background: '', special_ability: '', trust: 0, trust_pct: 0, flags: [] }
  }
  return res.json()
}

// ── Dashboard ──
export interface DashboardData {
  turn: number
  status: string
  scene: string
  chapter: number
  word_count: number
  character_count: number
  branch_count: number
  node_count: number
  api_calls: number
  total_tokens: number
  characters: { name: string; trust_pct: number; relation: string; flags: string[] }[]
  history: unknown[]
  analytics?: {
    metrics_curves?: Record<string, { labels: number[]; datasets: { name: string; data: number[] }[]; label: string }>
    status_timeline?: { turn: number; status: string; scene: string }[]
    word_counts?: { turn: number; words: number; chars: number }[]
    choice_stats?: { labels: string[]; counts: number[] }
    api_usage?: { per_turn: { turn: number; prompt_tokens: number; completion_tokens: number; total_tokens: number }[]; totals: { calls: number; total_tokens: number; cost_usd: number } }
    character_frequency?: { labels: string[]; counts: number[] }
    branch_stats?: { total_nodes: number; leaf_count: number; max_depth: number; avg_branches: number }
    faction_curves?: Record<string, { labels: number[]; datasets: { name: string; data: number[] }[]; label: string }>
    summary?: { turns: number; status: string; characters: number; total_words: number; nodes: number; edges: number }
  }
  error?: string
}

// ── History ──
export interface HistoryTurn {
  turn: number
  story: string
  options: string[]
  choice: string
  status: string
  scene: string
}

export async function getHistory(): Promise<{ turns: HistoryTurn[]; total: number; error?: string }> {
  const res = await fetch('/api/history')
  if (!res.ok) return { turns: [], total: 0, error: `HTTP ${res.status}` }
  return res.json()
}

export async function getDashboard(): Promise<DashboardData> {
  const res = await fetch('/api/dashboard')
  if (!res.ok) return { turn: 0, status: '', scene: '', chapter: 0, word_count: 0, character_count: 0, branch_count: 0, node_count: 0, api_calls: 0, total_tokens: 0, characters: [], history: [], error: `HTTP ${res.status}` }
  return res.json()
}

export async function nextTurn(choice: string): Promise<GameTurnResponse> {
  const formData = new FormData()
  formData.append('choice', choice)
  const res = await fetch('/api/next', { method: 'POST', body: formData })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { story: '', state: {} as GameTurnResponse['state'], options: [], error: (data as { error?: string }).error || 'Failed to advance' }
  }
  return res.json()
}

export async function startGame(): Promise<{ story: string; options: string[]; state: Record<string, unknown>; error?: string }> {
  const res = await fetch('/api/start', { method: 'POST' })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { story: '', options: [], state: {}, error: (data as { error?: string }).error || 'Failed to start game' }
  }
  return res.json()
}
