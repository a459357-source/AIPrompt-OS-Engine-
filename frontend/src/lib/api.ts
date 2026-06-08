import type {
  WorldGenResponse,
  FieldGenRequest,
  FieldGenResponse,
  GameTurnResponse,
  CustomRules,
} from './types'
import { logger } from './logger'
import { storyTargetBounds } from './storyLength'

const BASE = ''

const BACKEND_HINT =
  '请先运行 prompt-os-engine 目录下的「启动.bat」（开发）或「启动-单机.bat」（单机），并保持后端窗口不要关闭。'

/** Turn browser "Failed to fetch" into actionable Chinese. */
export function formatFetchError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err)
  const lower = msg.toLowerCase()
  if (
    msg === 'Failed to fetch'
    || lower.includes('failed to fetch')
    || lower.includes('networkerror')
    || lower.includes('load failed')
    || lower.includes('network request failed')
  ) {
    return `无法连接后端 API。${BACKEND_HINT}`
  }
  return msg
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch (err) {
    throw new Error(formatFetchError(err))
  }
}

async function post<T>(url: string, body: Record<string, string>): Promise<T> {
  const params = new URLSearchParams(body)
  const startTime = Date.now()
  logger.info('API', `→ POST ${url}`, { ...body })

  let res: Response
  try {
    res = await apiFetch(`${BASE}${url}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    })
  } catch (err) {
    logger.error('API', `✗ POST ${url} — network error`, err)
    throw new Error(formatFetchError(err))
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

export async function generateWorld(keywords: string, adultMode?: boolean): Promise<WorldGenResponse> {
  const body: Record<string, string> = { keywords }
  if (adultMode != null) body.adult_mode = adultMode ? 'true' : 'false'
  return post<WorldGenResponse>('/generate-world', body)
}

export async function generateField(req: FieldGenRequest): Promise<FieldGenResponse> {
  const body: Record<string, string> = {
    field: req.field,
    title: req.title || '',
    world: req.world || '',
    genre: (req.genre || '').toString(),
    context: req.context || '',
    char_role: req.char_role || '',
    char_name: req.char_name || '',
  }
  if (req.adultMode != null) body.adult_mode = req.adultMode ? 'true' : 'false'
  return post<FieldGenResponse>('/generate-field', body)
}

export async function generateRules(data: {
  title: string
  world: string
  genre: string
  char1_name: string
  char1_role: string
  char2_name: string
  char2_role: string
  adultMode?: boolean
}): Promise<CustomRules> {
  const body: Record<string, string> = {
    title: data.title,
    world: data.world,
    genre: data.genre,
    char1_name: data.char1_name,
    char1_role: data.char1_role,
    char2_name: data.char2_name,
    char2_role: data.char2_role,
  }
  if (data.adultMode != null) body.adult_mode = data.adultMode ? 'true' : 'false'
  return post<CustomRules>('/generate-rules', body)
}

export async function createStory(formData: FormData): Promise<void> {
  const res = await apiFetch('/new', { method: 'POST', body: formData, redirect: 'manual' })
  if (res.type === 'opaqueredirect' || res.status === 303 || res.status === 302) {
    return
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `创建故事失败 (HTTP ${res.status})`)
  }
}

/** Reset session to world_init snapshot (or factory defaults). */
export async function resetGame(): Promise<void> {
  const res = await apiFetch('/reset', { method: 'GET', redirect: 'manual' })
  if (res.type === 'opaqueredirect' || res.status === 303 || res.status === 302) {
    return
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `重置游戏失败 (HTTP ${res.status})`)
  }
}

// ── Save / Load / Export / Server ──

export interface SaveSlotInfo {
  slot: string
  turn: number
  status: string
  scene: string
  saved_at: string
}

export async function listSaves(): Promise<SaveSlotInfo[]> {
  const res = await apiFetch('/saves')
  if (!res.ok) {
    const data = await res.json().catch(() => ({})) as { error?: string }
    throw new Error(data.error || `读取存档列表失败 (HTTP ${res.status})`)
  }
  return res.json() as Promise<SaveSlotInfo[]>
}

export async function saveGameSlot(slot: string): Promise<SaveSlotInfo> {
  const res = await apiFetch(`/save?slot=${encodeURIComponent(slot)}`)
  const data = await res.json().catch(() => ({})) as SaveSlotInfo & { error?: string }
  if (!res.ok) throw new Error(data.error || `存档失败 (HTTP ${res.status})`)
  return data
}

/** Load a save slot; backend redirects to /game on success. */
export async function loadGameSlot(slot: string): Promise<void> {
  const res = await apiFetch(`/load?slot=${encodeURIComponent(slot)}`, { redirect: 'manual' })
  if (res.type === 'opaqueredirect' || res.status === 303 || res.status === 302) {
    return
  }
  const data = await res.json().catch(() => ({})) as { error?: string }
  if (!res.ok) throw new Error(data.error || `读档失败 (HTTP ${res.status})`)
}

export async function downloadStoryExport(): Promise<void> {
  const res = await apiFetch('/export')
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `导出失败 (HTTP ${res.status})`)
  }
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i)
  const filename = match ? decodeURIComponent(match[1].replace(/"/g, '')) : '星痕纪元_完整叙事.md'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function checkHealth(): Promise<{ status: string; engine?: string }> {
  const res = await apiFetch('/health')
  if (!res.ok) throw new Error(`后端无响应 (HTTP ${res.status})`)
  return res.json() as Promise<{ status: string; engine?: string }>
}

export async function shutdownServer(): Promise<void> {
  const res = await apiFetch('/shutdown', { method: 'POST' })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `关服失败 (HTTP ${res.status})`)
  }
}

export async function getGameState(): Promise<{ story: string; options: string[]; state: Record<string, unknown>; world_title?: string; not_started?: boolean; generating?: boolean; suggest_adult_mode?: boolean; error?: string }> {
  const res = await apiFetch('/api/game-state')
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { story: '', options: [], state: {}, error: (data as { error?: string }).error || 'Failed to load game' }
  }
  return res.json()
}

export async function getWorldMeta(): Promise<{ world_title: string; app_name?: string }> {
  const res = await apiFetch('/api/world-meta')
  if (!res.ok) return { world_title: '' }
  return res.json()
}

/** Poll until opening turn is persisted (history written). */
export async function waitForGameReady(timeoutMs = 120_000): Promise<{ story: string; options: string[]; state: Record<string, unknown> }> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const data = await getGameState()
    if (data.error) throw new Error(data.error)
    if (!data.not_started && data.story) {
      return { story: data.story, options: data.options, state: data.state }
    }
    await new Promise((r) => setTimeout(r, 1500))
  }
  throw new Error('等待游戏加载超时，请稍后重试')
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
  personality?: import('@/lib/types').PersonalityBrain
}

export type PersonalityBrain = import('@/lib/types').PersonalityBrain

export const EMPTY_PERSONALITY_BRAIN: PersonalityBrain = {
  desire: '',
  fear: '',
  taboo: '',
  secret: '',
  values: [],
}

export async function patchNpcPersonality(
  name: string,
  personality: PersonalityBrain,
): Promise<{ ok?: boolean; personality?: PersonalityBrain; error?: string }> {
  const res = await apiFetch(`/api/npcs/${encodeURIComponent(name)}/personality`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(personality),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    return { error: data.error || `HTTP ${res.status}` }
  }
  return data
}

export async function getNpcs(): Promise<{ characters: NpcData[]; stats: { total: number; main: number; npc: number; avg_trust: number }; error?: string }> {
  const res = await apiFetch('/api/npcs')
  if (!res.ok) return { characters: [], stats: { total: 0, main: 0, npc: 0, avg_trust: 0 }, error: `HTTP ${res.status}` }
  return res.json()
}

export async function generateNpc(roleHint?: string): Promise<NpcData & { error?: string }> {
  const fd = new FormData()
  fd.append('role_hint', roleHint || '')
  const res = await apiFetch('/api/npcs/generate', { method: 'POST', body: fd })
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { ...data, name: '', isMain: false, role_tags: [], personality_tags: [], appearance: '', relationship: [], goal: '', secret: '', background: '', special_ability: '', trust: 0, trust_pct: 0, flags: [], personality: EMPTY_PERSONALITY_BRAIN }
  }
  return res.json()
}

// ── Dashboard ──
export interface WorldStateV2 {
  location: string
  locations: { name: string; desc: string }[]
  world_time: {
    turn: number
    chapter: number
    era: string
    label: string
    scene_changes: number
  }
  factions: {
    name: string
    role: string
    type: string
    reputation_pct: number
    relation_to_player: string
    influence: number
    leader: string
    goals: string[]
    flags: string[]
    attitudes: { target: string; attitude: number; label: string }[]
  }[]
  faction_links: { from: string; to: string; attitude: number; label: string }[]
  events: {
    id: string
    title: string
    status: string
    importance: number
    trigger_turn: number
    related_factions: string[]
    related_characters: string[]
  }[]
  relationship_network: {
    nodes: {
      name: string
      is_main: boolean
      faction: string
      relationship_type: string
      trust_pct: number
      tags: string[]
      tier: string
    }[]
    edges: { from: string; to: string; kind: string; label: string }[]
  }
}

export interface PlotDirectorHook {
  id?: string
  title: string
  kind?: string
  created_turn?: number
  status?: string
  resolved_turn?: number
}

export interface PlotDirectorData {
  main_goal: string
  main_plot: { name: string; progress: number; stage: number }
  unresolved_hooks: PlotDirectorHook[]
  resolved_hooks: PlotDirectorHook[]
  last_progress_turn: number
  last_analysis_turn: number
  stall_turns: number
}

export interface ObjectiveItem {
  id: string
  title: string
  progress: number
  status: string
  scope?: string
}

export interface ObjectivesGameData {
  main: ObjectiveItem[]
  side: ObjectiveItem[]
  side_extra?: number
}

export interface ObjectivesDashboardData {
  main: ObjectiveItem[]
  side: ObjectiveItem[]
  completed: ObjectiveItem[]
  failed: ObjectiveItem[]
  hidden: ObjectiveItem[]
}

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
    world_state_v2?: WorldStateV2
  }
  story_graph?: {
    nodes: Record<string, unknown>
    edges: { from: string; to: string; choice?: string }[]
    mermaid: string
    current_node?: string
  }
  plot_director?: PlotDirectorData
  objectives?: ObjectivesDashboardData
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
  const res = await apiFetch('/api/history')
  if (!res.ok) return { turns: [], total: 0, error: `HTTP ${res.status}` }
  return res.json()
}

export async function getDashboard(): Promise<DashboardData> {
  const res = await apiFetch('/api/dashboard')
  if (!res.ok) return { turn: 0, status: '', scene: '', chapter: 0, word_count: 0, character_count: 0, branch_count: 0, node_count: 0, api_calls: 0, total_tokens: 0, characters: [], history: [], error: `HTTP ${res.status}` }
  return res.json()
}

export type TurnStreamHandlers = {
  onStoryDelta?: (delta: string) => void
  onStoryReset?: () => void
  onProgress?: (phase: string, data: Record<string, unknown>) => void
}

let activeTurnAbort: AbortController | null = null

export function cancelGeneration(): Promise<void> {
  activeTurnAbort?.abort()
  return apiFetch(`${BASE}/api/cancel-generation`, { method: 'POST' })
    .then(() => undefined)
    .catch(() => undefined)
}

export async function getGenerationStatus(): Promise<{ active: boolean; story: string; cancelled?: boolean }> {
  const res = await apiFetch(`${BASE}/api/generation-status`)
  if (!res.ok) return { active: false, story: '' }
  return res.json()
}

function parseSseBlock(
  block: string,
  handlers: TurnStreamHandlers | undefined,
  onDone: (payload: GameTurnResponse) => void,
  onError: (message: string) => void,
): void {
  let event = 'message'
  let dataLine = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLine = line.slice(5).trim()
  }
  if (!dataLine) return
  const data = JSON.parse(dataLine) as Record<string, unknown>
  if (event === 'story') {
    handlers?.onStoryDelta?.(String(data.delta ?? ''))
  } else if (event === 'story_reset') {
    handlers?.onStoryReset?.()
  } else if (event === 'progress') {
    const { phase, ...rest } = data
    handlers?.onProgress?.(String(phase ?? ''), rest)
  } else if (event === 'error') {
    onError(String(data.error ?? 'AI 生成失败，请重试'))
  } else if (event === 'done') {
    onDone(data as unknown as GameTurnResponse)
  }
}

async function consumeTurnStream(
  res: Response,
  handlers?: TurnStreamHandlers,
): Promise<GameTurnResponse> {
  const reader = res.body?.getReader()
  if (!reader) throw new Error('浏览器不支持流式响应')

  const decoder = new TextDecoder()
  let buffer = ''
  let final: GameTurnResponse | null = null
  let streamError = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let sep = buffer.indexOf('\n\n')
    while (sep >= 0) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      parseSseBlock(
        block,
        handlers,
        (payload) => { final = payload },
        (msg) => { streamError = msg },
      )
      sep = buffer.indexOf('\n\n')
    }
  }

  if (streamError) {
    return { story: '', state: {} as GameTurnResponse['state'], options: [], error: streamError }
  }
  if (final) return final
  throw new Error('流式响应未完成')
}

async function postGameTurn(
  path: string,
  body: FormData | undefined,
  handlers?: TurnStreamHandlers,
): Promise<GameTurnResponse> {
  activeTurnAbort?.abort()
  activeTurnAbort = new AbortController()
  const signal = activeTurnAbort.signal

  const startTime = Date.now()
  logger.info('API', `→ POST ${path}`)
  const res = await apiFetch(`${BASE}${path}`, { method: 'POST', body, signal })
  const contentType = res.headers.get('content-type') || ''
  const empty: GameTurnResponse = {
    story: '',
    options: [],
    state: {} as GameTurnResponse['state'],
  }

  if (!res.ok) {
    if (contentType.includes('application/json')) {
      const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
      return { ...empty, error: (data as { error?: string }).error || `HTTP ${res.status}` }
    }
    return { ...empty, error: `HTTP ${res.status}` }
  }

  if (contentType.includes('text/event-stream')) {
    const data = await consumeTurnStream(res, handlers)
    logger.info('API', `✓ POST ${path} (stream) — ${Date.now() - startTime}ms`)
    return data
  }

  const data = await res.json() as GameTurnResponse
  logger.info('API', `✓ POST ${path} — ${Date.now() - startTime}ms`)
  return data
}

export async function nextTurn(
  choice: string,
  handlers?: TurnStreamHandlers,
): Promise<GameTurnResponse> {
  const formData = new FormData()
  formData.append('choice', choice)
  return postGameTurn('/api/next', formData, handlers)
}

export async function startGame(
  handlers?: TurnStreamHandlers,
): Promise<GameTurnResponse> {
  return postGameTurn('/api/start', undefined, handlers)
}

let openingGamePromise: Promise<GameTurnResponse> | null = null

/** Dedupe concurrent opening requests when Game page remounts during first generation. */
export function startGameOnce(
  handlers?: TurnStreamHandlers,
): Promise<GameTurnResponse> {
  if (!openingGamePromise) {
    openingGamePromise = startGame(handlers).finally(() => {
      openingGamePromise = null
    })
  }
  return openingGamePromise
}

export async function getSettingsStatus(): Promise<{ configured: boolean; error?: string }> {
  try {
    const res = await apiFetch('/api/settings-status')
    if (!res.ok) return { configured: false, error: `HTTP ${res.status}` }
    return res.json()
  } catch {
    return { configured: false, error: 'network' }
  }
}

export async function clearApiKey(): Promise<EngineSettings> {
  const res = await apiFetch('/api/settings/clear', { method: 'POST' })
  const data = await res.json().catch(() => ({})) as EngineSettings & { error?: string }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}

export async function saveApiKey(key: string): Promise<{ ok?: boolean; error?: string }> {
  const params = new URLSearchParams({ api_key: key.trim() })
  const res = await apiFetch('/api/settings-key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  })
  const data = await res.json().catch(() => ({})) as { ok?: boolean; error?: string }
  if (!res.ok) return { error: data.error || `HTTP ${res.status}` }
  return data
}

export interface EngineSettings {
  configured: boolean
  api_key_masked: string
  model: string
  models: Record<string, string>
  story_length: number
  max_tokens: number
  matched_max_tokens?: number
  api_limits?: {
    context_tokens: number
    max_output_tokens: number
    max_temperature: number
    max_top_p: number
  }
  temperature: number
  top_p: number
  stream: boolean
  max_context_messages: number
  auto_compress: boolean
  compress_threshold: number
}

export async function getEngineSettings(): Promise<EngineSettings> {
  const res = await apiFetch('/api/settings')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function saveEngineSettings(params: {
  apiKey?: string
  model: string
  storyLength?: number
  maxTokens?: number
  temperature?: number
  topP?: number
  stream?: boolean
  maxContextMsgs?: number
  autoCompress?: boolean
  compressThreshold?: number
}): Promise<EngineSettings> {
  const fd = new FormData()
  if (params.apiKey) fd.append('api_key', params.apiKey)
  fd.append('model', params.model)
  if (params.storyLength != null) fd.append('story_length', String(params.storyLength))
  if (params.maxTokens != null) fd.append('max_tokens', String(params.maxTokens))
  if (params.temperature != null) fd.append('temperature', String(params.temperature))
  if (params.topP != null) fd.append('top_p', String(params.topP))
  if (params.stream != null) fd.append('stream', params.stream ? '1' : '0')
  if (params.maxContextMsgs != null) fd.append('max_context_messages', String(params.maxContextMsgs))
  if (params.autoCompress != null) fd.append('auto_compress', params.autoCompress ? '1' : '0')
  if (params.compressThreshold != null) fd.append('compress_threshold', String(params.compressThreshold))
  const res = await apiFetch('/api/settings', { method: 'POST', body: fd })
  if (!res.ok) {
    const data = await res.json().catch(() => ({})) as { error?: string }
    throw new Error(data.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export interface ContentWeights {
  story: number
  romance: number
  adult: number
}

export interface GameGenSettings {
  story_length: number
  min: number
  max: number
  recommended: number
  target_min?: number
  target_max?: number
  max_tokens: number
  matched_max_tokens: number
  max_output_tokens: number
  context_tokens: number
  temperature: number
  top_p: number
  compress_threshold: number
  matched_compress_threshold?: number
  option_count: number
  narrative_pov: string
  style_preference: string
  repetition_check: string
  adult_mode: boolean
  adult_unlocked: boolean
  adult_unlock_key_masked: string
  adult_profile: string
  adult_profile_options: string[]
  adult_profile_labels: Record<string, string>
  adult_profile_descriptions: Record<string, string>
  adult_theme: string
  adult_theme_options: string[]
  adult_theme_labels: Record<string, string>
  visual_theme: string
  visual_theme_options: string[]
  visual_theme_labels: Record<string, string>
  expression_style: string
  expression_style_options: string[]
  expression_style_labels: Record<string, string>
  content_weights: ContentWeights
  preset_weights: Record<string, ContentWeights>
  api_limits?: {
    context_tokens: number
    max_output_tokens: number
    max_temperature: number
    max_top_p: number
  }
  /** 切换成人模式等场景下重生本轮选项 */
  options?: string[]
  options_regenerated?: boolean
  options_regen_error?: string
}

const _FALLBACK_BOUNDS = storyTargetBounds(1000, 300)

const DEFAULT_CONTENT_WEIGHTS: ContentWeights = { story: 40, romance: 30, adult: 30 }

export type AdultProfileId = 'story_first' | 'balanced' | 'adult_first'
export type VisualThemeId = 'adult' | 'desire'
export type AdultThemeId = 'deep_purple' | 'dark_crimson' | 'midnight_bar' | 'luxury_suite'

const GAME_GEN_FALLBACK: GameGenSettings = {
  story_length: 1000,
  min: 300,
  max: 281851,
  recommended: 1000,
  target_min: _FALLBACK_BOUNDS.min,
  target_max: _FALLBACK_BOUNDS.max,
  max_tokens: 4850,
  matched_max_tokens: 4850,
  max_output_tokens: 384000,
  context_tokens: 1000000,
  temperature: 0.8,
  top_p: 0.9,
  compress_threshold: 7000,
  matched_compress_threshold: 7000,
  option_count: 4,
  narrative_pov: 'auto',
  style_preference: 'balanced',
  repetition_check: 'standard',
  adult_mode: false,
  adult_unlocked: false,
  adult_unlock_key_masked: '',
  adult_profile: 'balanced',
  adult_profile_options: ['story_first', 'balanced', 'adult_first'],
  adult_profile_labels: { story_first: '剧情优先', balanced: '平衡模式', adult_first: '成人优先' },
  adult_profile_descriptions: {
    story_first: '以剧情推进为主，亲密内容作为关系发展的结果',
    balanced: '剧情与感情并重',
    adult_first: '剧情主要围绕人物关系与亲密互动展开',
  },
  adult_theme: 'deep_purple',
  adult_theme_options: ['deep_purple', 'dark_crimson', 'midnight_bar', 'luxury_suite'],
  adult_theme_labels: {
    deep_purple: '深紫迷离',
    dark_crimson: '暗红暧昧',
    midnight_bar: '深夜酒馆',
    luxury_suite: '豪华套房',
  },
  visual_theme: 'desire',
  visual_theme_options: ['adult', 'desire'],
  visual_theme_labels: {
    adult: 'Adult Theme',
    desire: 'Desire+ Theme',
  },
  expression_style: 'light_novel',
  expression_style_options: ['literary', 'romantic', 'light_novel', 'direct'],
  expression_style_labels: { literary: '文学风', romantic: '浪漫风', light_novel: '轻小说风', direct: '直白风' },
  content_weights: { ...DEFAULT_CONTENT_WEIGHTS },
  preset_weights: {},
}

function parseGameGenSettings(data: Partial<GameGenSettings>): GameGenSettings {
  const storyLength = data.story_length ?? GAME_GEN_FALLBACK.story_length
  const min = data.min ?? GAME_GEN_FALLBACK.min
  const bounds = storyTargetBounds(storyLength, min)
  const targetMin = data.target_min ?? bounds.min
  const targetMax = data.target_max ?? bounds.max
  return {
    story_length: storyLength,
    min,
    max: data.max ?? GAME_GEN_FALLBACK.max,
    recommended: data.recommended ?? GAME_GEN_FALLBACK.recommended,
    target_min: targetMin,
    target_max: targetMax,
    max_tokens: data.max_tokens ?? GAME_GEN_FALLBACK.max_tokens,
    matched_max_tokens: data.matched_max_tokens ?? GAME_GEN_FALLBACK.matched_max_tokens,
    max_output_tokens: data.max_output_tokens ?? GAME_GEN_FALLBACK.max_output_tokens,
    context_tokens: data.context_tokens ?? GAME_GEN_FALLBACK.context_tokens,
    temperature: data.temperature ?? GAME_GEN_FALLBACK.temperature,
    top_p: data.top_p ?? GAME_GEN_FALLBACK.top_p,
    compress_threshold: data.compress_threshold ?? GAME_GEN_FALLBACK.compress_threshold,
    matched_compress_threshold: data.matched_compress_threshold ?? GAME_GEN_FALLBACK.matched_compress_threshold,
    option_count: data.option_count ?? GAME_GEN_FALLBACK.option_count,
    narrative_pov: data.narrative_pov ?? GAME_GEN_FALLBACK.narrative_pov,
    style_preference: data.style_preference ?? GAME_GEN_FALLBACK.style_preference,
    repetition_check: data.repetition_check ?? GAME_GEN_FALLBACK.repetition_check,
    adult_mode: data.adult_mode ?? GAME_GEN_FALLBACK.adult_mode,
    adult_unlocked: data.adult_unlocked ?? GAME_GEN_FALLBACK.adult_unlocked,
    adult_unlock_key_masked: data.adult_unlock_key_masked ?? GAME_GEN_FALLBACK.adult_unlock_key_masked,
    adult_profile: data.adult_profile ?? GAME_GEN_FALLBACK.adult_profile,
    adult_profile_options: data.adult_profile_options ?? GAME_GEN_FALLBACK.adult_profile_options,
    adult_profile_labels: data.adult_profile_labels ?? GAME_GEN_FALLBACK.adult_profile_labels,
    adult_profile_descriptions: data.adult_profile_descriptions ?? GAME_GEN_FALLBACK.adult_profile_descriptions,
    adult_theme: data.adult_theme ?? GAME_GEN_FALLBACK.adult_theme,
    adult_theme_options: data.adult_theme_options ?? GAME_GEN_FALLBACK.adult_theme_options,
    adult_theme_labels: data.adult_theme_labels ?? GAME_GEN_FALLBACK.adult_theme_labels,
    visual_theme: data.visual_theme ?? GAME_GEN_FALLBACK.visual_theme,
    visual_theme_options: data.visual_theme_options ?? GAME_GEN_FALLBACK.visual_theme_options,
    visual_theme_labels: data.visual_theme_labels ?? GAME_GEN_FALLBACK.visual_theme_labels,
    expression_style: data.expression_style ?? GAME_GEN_FALLBACK.expression_style,
    expression_style_options: data.expression_style_options ?? GAME_GEN_FALLBACK.expression_style_options,
    expression_style_labels: data.expression_style_labels ?? GAME_GEN_FALLBACK.expression_style_labels,
    content_weights: data.content_weights ?? { ...DEFAULT_CONTENT_WEIGHTS },
    preset_weights: data.preset_weights ?? GAME_GEN_FALLBACK.preset_weights,
    api_limits: data.api_limits,
    options: Array.isArray(data.options) ? data.options : undefined,
    options_regenerated: data.options_regenerated,
    options_regen_error: data.options_regen_error,
  }
}

export async function getGameGenSettings(): Promise<GameGenSettings> {
  const res = await apiFetch('/api/game-settings')
  if (!res.ok) return GAME_GEN_FALLBACK
  return parseGameGenSettings(await res.json() as Partial<GameGenSettings>)
}

export async function updateGameGenSettings(patch: {
  storyLength?: number
  temperature?: number
  topP?: number
  compressThreshold?: number
  optionCount?: number
  narrativePov?: string
  stylePreference?: string
  repetitionCheck?: string
  adultMode?: boolean
  adultUnlockKey?: string
  adultProfile?: string
  adultTheme?: string
  visualTheme?: string
  expressionStyle?: string
  contentWeights?: ContentWeights
}): Promise<GameGenSettings> {
  const fd = new FormData()
  if (patch.storyLength != null) fd.append('story_length', String(patch.storyLength))
  if (patch.temperature != null) fd.append('temperature', String(patch.temperature))
  if (patch.topP != null) fd.append('top_p', String(patch.topP))
  if (patch.compressThreshold != null) fd.append('compress_threshold', String(patch.compressThreshold))
  if (patch.optionCount != null) fd.append('option_count', String(patch.optionCount))
  if (patch.narrativePov != null) fd.append('narrative_pov', patch.narrativePov)
  if (patch.stylePreference != null) fd.append('style_preference', patch.stylePreference)
  if (patch.repetitionCheck != null) fd.append('repetition_check', patch.repetitionCheck)
  if (patch.adultMode != null) fd.append('adult_mode', patch.adultMode ? 'true' : 'false')
  if (patch.adultUnlockKey != null) fd.append('adult_unlock_key', patch.adultUnlockKey)
  if (patch.adultProfile != null) fd.append('adult_profile', patch.adultProfile)
  if (patch.adultTheme != null) fd.append('adult_theme', patch.adultTheme)
  if (patch.visualTheme != null) fd.append('visual_theme', patch.visualTheme)
  if (patch.expressionStyle != null) fd.append('expression_style', patch.expressionStyle)
  if (patch.contentWeights != null) fd.append('content_weights', JSON.stringify(patch.contentWeights))

  const endpoints = ['/api/game-settings', '/api/settings']
  let lastError = '保存失败'
  for (const endpoint of endpoints) {
    let res: Response
    try {
      res = await apiFetch(endpoint, { method: 'POST', body: fd })
    } catch (err) {
      throw new Error(formatFetchError(err))
    }
    const data = await res.json().catch(() => ({})) as Partial<GameGenSettings> & { error?: string }
    if (res.ok) return parseGameGenSettings(data)
    lastError = data.error || `HTTP ${res.status}`
    if (res.status !== 405 && res.status !== 404) break
  }
  throw new Error(lastError)
}

export interface BackendAppSettings {
  auto_save_interval: number
  max_save_slots: number
  export_format: string
  auto_export: string
  save_slots?: string[]
}

export async function getAppSettings(): Promise<BackendAppSettings | null> {
  const res = await apiFetch('/api/app-settings')
  if (!res.ok) return null
  return res.json() as Promise<BackendAppSettings>
}

export async function updateAppSettings(patch: {
  autoSaveInterval?: number
  maxSaveSlots?: number
  exportFormat?: string
  autoExport?: string
}): Promise<BackendAppSettings> {
  const fd = new FormData()
  if (patch.autoSaveInterval != null) fd.append('auto_save_interval', String(patch.autoSaveInterval))
  if (patch.maxSaveSlots != null) fd.append('max_save_slots', String(patch.maxSaveSlots))
  if (patch.exportFormat != null) fd.append('export_format', patch.exportFormat)
  if (patch.autoExport != null) fd.append('auto_export', patch.autoExport)

  const res = await apiFetch('/api/app-settings', { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({})) as BackendAppSettings & { error?: string }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}

export interface SupplementLoreResult {
  summary?: string
  changes?: string[]
  story_prompt_added?: boolean
  analysis?: { characters: number; factions: number; relations: number }
  story?: string
  options?: string[]
  state?: Record<string, unknown>
  suggest_adult_mode?: boolean
  error?: string
}

export interface VisualStatus {
  enabled: boolean
  provider: string
  cache_enabled: boolean
  read_only?: boolean
}

export interface VisualAssetItem {
  registry_id?: string
  asset_id: string
  entity_type: string
  entity_id: string
  identity_id: string
  display_name: string
  prompt_hash: string
  image_path: string
  image_url: string
  provider: string
  kind: string
  created_turn: number
  created_at: number
  seed: number
  cache_status: string
  cache_hit?: boolean
  identity?: Record<string, unknown>
  scope?: string
  canonical_traits?: Record<string, unknown>
  style_anchor?: Record<string, unknown>
  locked_descriptors?: string[]
}

export interface VisualIdentityView {
  identity_id: string
  entity_name: string
  latest_image: string
  latest_image_path: string
  all_assets: VisualAssetItem[]
  traits: Record<string, unknown>
  style_anchor: Record<string, unknown>
  seed: number
}

export interface VisualCharacterLink {
  from: string
  to: string
  label?: string
}

export interface VisualWorldView {
  locations: VisualAssetItem[]
  factions: VisualAssetItem[]
  characters: VisualIdentityView[]
  character_links: VisualCharacterLink[]
}

export interface VisualEventView {
  event_id: string
  display_name: string
  linked_assets: VisualAssetItem[]
  scene_images: string[]
  characters: string[]
  timestamp: number
  created_turn: number
  identity_id: string
  prompt_hash: string
}

export interface VisualDebugAsset extends VisualAssetItem {
  registry_id: string
  cache_hit: boolean
}

async function getJson<T>(url: string): Promise<T> {
  const res = await apiFetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json() as Promise<T>
}

export async function getVisualStatus(): Promise<VisualStatus> {
  return getJson<VisualStatus>('/api/visual/status')
}

export async function getCharacterGallery(): Promise<VisualIdentityView[]> {
  const data = await getJson<{ characters: VisualIdentityView[] }>('/api/visual/gallery/characters')
  return data.characters
}

export async function getWorldExplorer(): Promise<VisualWorldView> {
  return getJson<VisualWorldView>('/api/visual/world')
}

export async function getEventTimeline(): Promise<VisualEventView[]> {
  const data = await getJson<{ events: VisualEventView[] }>('/api/visual/events')
  return data.events
}

export async function getVisualDebug(): Promise<{
  status: VisualStatus
  identities: Record<string, unknown>[]
  assets: VisualDebugAsset[]
}> {
  return getJson('/api/visual/debug')
}

export interface NarrativeChoice {
  choice_id: string
  text: string
  target_event_id: string
  target_event_hint?: string
  tone: string
}

export interface NarrativeNode {
  event_id: string
  visual_event_id?: string
  label: string
  scene_image: string
  context: string
  characters: { name: string; identity_id: string; traits: Record<string, unknown> }[]
  current_state: { turn: number; scene: string; status: string; director_state: string }
  choices: NarrativeChoice[]
  next_events: string[]
  continuity: {
    identity_ids: string[]
    style_anchors: Record<string, Record<string, unknown>>
    prompt_hint: string
    visual_constraints: string[]
  }
}

export interface NarrativeState {
  mode: 'explore' | 'narrative'
  current_event_id: string
  entry_type: string
  choice_history: { event_id: string; choice_id: string; next_event_id: string; at: number }[]
}

async function postForm<T>(url: string, fields: Record<string, string>): Promise<T> {
  const body = new URLSearchParams(fields)
  const res = await apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  return res.json() as Promise<T>
}

export async function getNarrativeState(): Promise<NarrativeState> {
  return getJson<NarrativeState>('/api/narrative/state')
}

export async function setNarrativeMode(mode: 'explore' | 'narrative'): Promise<NarrativeState> {
  return postForm<NarrativeState>('/api/narrative/mode', { mode })
}

export async function getNarrativeNode(eventId: string): Promise<NarrativeNode> {
  return getJson<NarrativeNode>(`/api/narrative/node/${encodeURIComponent(eventId)}`)
}

export async function routeNarrativeChoice(
  eventId: string,
  choiceId: string,
): Promise<{ ok: boolean; next_event_id?: string; node?: NarrativeNode; error?: string }> {
  return postForm('/api/narrative/route', { event_id: eventId, choice_id: choiceId })
}

export async function enterNarrativeFromEvent(eventId: string): Promise<{ narrative_event_id: string; node: NarrativeNode }> {
  return postForm('/api/narrative/enter/event', { event_id: eventId })
}

export async function enterNarrativeFromCharacter(
  characterName: string,
): Promise<{ narrative_event_id: string; node: NarrativeNode }> {
  return postForm('/api/narrative/enter/character', { character_name: characterName })
}

export async function enterNarrativeFromLocation(
  locationName: string,
): Promise<{ narrative_event_id: string; node: NarrativeNode }> {
  return postForm('/api/narrative/enter/location', { location_name: locationName })
}

export async function supplementLore(text: string): Promise<SupplementLoreResult> {
  const fd = new FormData()
  fd.append('text', text.trim())
  const res = await apiFetch('/api/supplement-lore', { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({})) as SupplementLoreResult
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}
