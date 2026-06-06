// ── Settings types, defaults, and localStorage persistence ──

export interface AppSettings {
  // Reading
  fontSize: number
  lineHeight: number
  fontFamily: string
  maxWidth: number
  bgTheme: string
  paragraphSpacing: string

  // AI
  temperature: number
  optionCount: number
  narrativePov: string
  stylePreference: string
  autoAdvance: boolean
  repetitionCheck: string

  // Data
  autoSaveInterval: number
  maxSaveSlots: number
  exportFormat: string
  autoExport: string

  // UI
  animations: boolean
  sidebarDefault: string
  charPanelPosition: string
  language: string
}

export const DEFAULTS: AppSettings = {
  fontSize: 17,
  lineHeight: 1.8,
  fontFamily: 'system',
  maxWidth: 800,
  bgTheme: 'dark',
  paragraphSpacing: 'standard',

  temperature: 0.8,
  optionCount: 4,
  narrativePov: 'auto',
  stylePreference: 'balanced',
  autoAdvance: false,
  repetitionCheck: 'standard',

  autoSaveInterval: 60,
  maxSaveSlots: 3,
  exportFormat: 'markdown',
  autoExport: 'off',

  animations: true,
  sidebarDefault: 'expanded',
  charPanelPosition: 'right',
  language: 'zh',
}

const KEY = 'app-settings'

export function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw)
    return { ...DEFAULTS, ...parsed }
  } catch {
    return { ...DEFAULTS }
  }
}

let _settings: AppSettings | null = null

export function getSettings(): AppSettings {
  if (!_settings) _settings = loadSettings()
  return _settings
}

export function saveSettings(s: Partial<AppSettings>) {
  _settings = { ...getSettings(), ...s }
  localStorage.setItem(KEY, JSON.stringify(_settings))
  applySettings(_settings)
}

export function applySettings(s: AppSettings) {
  const root = document.documentElement.style
  root.setProperty('--story-font-size', `${s.fontSize}px`)
  root.setProperty('--story-line-height', String(s.lineHeight))
  root.setProperty('--story-max-width', s.maxWidth === 100 ? '100%' : `${s.maxWidth}px`)
  root.setProperty('--story-font-family', FONT_FAMILIES[s.fontFamily] || 'system-ui')
  root.setProperty('--story-paragraph-spacing', PARAGRAPH_SPACING[s.paragraphSpacing] || '1.5em')

  // Background theme
  const bgMap: Record<string, { bg: string; surface: string; card: string; text: string }> = {
    dark: { bg: '#0d1117', surface: '#161b22', card: '#1c2333', text: '#c9d1d9' },
    sepia: { bg: '#2a2218', surface: '#332b1f', card: '#3d3326', text: '#d4c5a9' },
    gray: { bg: '#1a1a1a', surface: '#222222', card: '#2a2a2a', text: '#cccccc' },
  }
  const theme = bgMap[s.bgTheme]
  if (theme) {
    root.setProperty('--color-game-bg', theme.bg)
    root.setProperty('--color-game-surface', theme.surface)
    root.setProperty('--color-game-card', theme.card)
    root.setProperty('--color-game-text', theme.text)
  }
}

// ── Option maps ──

export const FONT_FAMILIES: Record<string, string> = {
  system: 'system-ui, "Segoe UI", "Noto Sans SC", sans-serif',
  serif: '"Noto Serif SC", "Source Han Serif SC", SimSun, serif',
  sans: '"Noto Sans SC", "Microsoft YaHei", sans-serif',
  kai: '"KaiTi", "STKaiti", "AR PL UKai CN", serif',
}

export const FONT_FAMILY_LABELS: Record<string, string> = {
  system: '系统默认',
  serif: '宋体/明体',
  sans: '黑体',
  kai: '楷体',
}

export const BG_THEME_LABELS: Record<string, string> = {
  dark: '深黑',
  sepia: '暖棕护眼',
  gray: '暗灰',
}

export const PARAGRAPH_SPACING: Record<string, string> = {
  compact: '0.8em',
  standard: '1.5em',
  relaxed: '2.5em',
}

export const LINE_HEIGHT_OPTIONS = [1.6, 1.8, 2.0, 2.4]
export const FONT_SIZE_OPTIONS = [14, 17, 20, 24, 28]
export const MAX_WIDTH_OPTIONS = [
  { value: 600, label: '窄栏' },
  { value: 800, label: '标准' },
  { value: 100, label: '全宽' }, // 100 = 100%
]
