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

export async function getGameState(): Promise<{ story: string; options: string[]; state: Record<string, unknown>; error?: string }> {
  const res = await fetch('/api/game-state')
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { story: '', options: [], state: {}, error: (data as { error?: string }).error || 'Failed to load game' }
  }
  return res.json()
}

export async function nextTurn(choice: string): Promise<GameTurnResponse> {
  const res = await fetch(`/api/next?choice=${encodeURIComponent(choice)}`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    return { story: '', state: {} as GameTurnResponse['state'], options: [], error: (data as { error?: string }).error || 'Failed to advance' }
  }
  return res.json()
}
