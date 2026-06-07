// ── Settings types, defaults, and localStorage persistence ──

import { applyDocumentLanguage } from './i18n'

export interface AppSettings {
  // Reading
  fontSize: number
  lineHeight: number
  fontFamily: string
  maxWidth: number
  bgTheme: string
  paragraphSpacing: string

  // Gameplay (frontend only)
  autoAdvance: boolean
  autoAdvanceRounds: number

  // Data (synced to backend via /api/app-settings)
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

  autoAdvance: false,
  autoAdvanceRounds: 3,

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

const ENGINE_SYNC_KEYS = new Set<keyof AppSettings>([
  'autoSaveInterval',
  'maxSaveSlots',
  'exportFormat',
  'autoExport',
])

let _syncTimer: ReturnType<typeof setTimeout> | null = null

async function syncEngineSettingsToBackend(patch: Partial<AppSettings>) {
  const keys = Object.keys(patch) as (keyof AppSettings)[]
  if (!keys.some((k) => ENGINE_SYNC_KEYS.has(k))) return
  const { updateAppSettings } = await import('./api')
  await updateAppSettings({
    autoSaveInterval: patch.autoSaveInterval,
    maxSaveSlots: patch.maxSaveSlots,
    exportFormat: patch.exportFormat,
    autoExport: patch.autoExport,
  })
}

export function saveSettings(s: Partial<AppSettings>, opts?: { skipEngineSync?: boolean }) {
  _settings = { ...getSettings(), ...s }
  localStorage.setItem(KEY, JSON.stringify(_settings))
  applySettings(_settings)
  applyDocumentLanguage(_settings.language as 'zh' | 'en' | 'ja')
  window.dispatchEvent(new CustomEvent('app-settings-changed', { detail: _settings }))
  if (opts?.skipEngineSync) return
  if (_syncTimer) clearTimeout(_syncTimer)
  _syncTimer = setTimeout(() => {
    syncEngineSettingsToBackend(s).catch(() => {})
  }, 400)
}

export function initSettings(): AppSettings {
  _settings = loadSettings()
  applySettings(_settings)
  applyDocumentLanguage(_settings.language as 'zh' | 'en' | 'ja')
  return _settings
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
    dark: { bg: '#0d1117', surface: '#1a1f2b', card: '#1e2433', text: '#e2e5ea' },
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

export const AUTO_ADVANCE_ROUND_OPTIONS = [1, 3, 5, 10, 20] as const

export function clampAutoAdvanceRounds(n: number): number {
  return Math.max(1, Math.min(50, Math.floor(n)))
}

export const LINE_HEIGHT_OPTIONS = [1.6, 1.8, 2.0, 2.4]
export const FONT_SIZE_OPTIONS = [14, 17, 20, 24, 28]
export const MAX_WIDTH_OPTIONS = [
  { value: 600, label: '窄栏' },
  { value: 800, label: '标准' },
  { value: 100, label: '全宽' }, // 100 = 100%
]
