import type {
  WorldGenResponse,
  FieldGenRequest,
  FieldGenResponse,
  GameTurnResponse,
  CustomRules,
} from './types'

const BASE = '/api'

async function post<T>(url: string, body: Record<string, string>): Promise<T> {
  const params = new URLSearchParams(body)
  const res = await fetch(`${BASE}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  })
  const data = await res.json()
  if (data.error) throw new Error(data.error)
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
  const res = await fetch('/')
  const html = await res.text()
  // Parse the embedded JSON from the HTML (legacy endpoint)
  const match = html.match(/__STATE__\s*=\s*({[^<]+})/)
  if (match) {
    return JSON.parse(match[1])
  }
  return { story: '', options: [], state: {}, error: 'Failed to parse state' }
}

export async function nextTurn(choice: string): Promise<GameTurnResponse> {
  const res = await fetch(`/next?choice=${encodeURIComponent(choice)}`)
  const html = await res.text()
  const match = html.match(/__STATE__\s*=\s*({[^<]+})/)
  if (match) {
    return JSON.parse(match[1])
  }
  return { story: '', state: {} as GameTurnResponse['state'], options: [], error: 'Failed to parse state' }
}
