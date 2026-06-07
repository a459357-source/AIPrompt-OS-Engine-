/** UI theme — Normal (World Builder) vs Desire+ (adult_mode) */

export type UiTheme = 'normal' | 'adult'

export type AdultThemeId = 'deep_purple' | 'dark_crimson' | 'midnight_bar' | 'luxury_suite'

export const UI_THEME_ATTR = 'data-ui-theme'
export const ADULT_THEME_ATTR = 'data-adult-theme'

export const ADULT_THEME_NAME = 'Desire+'

export const ADULT_THEME_OPTIONS: AdultThemeId[] = [
  'deep_purple',
  'dark_crimson',
  'midnight_bar',
  'luxury_suite',
]

export const ADULT_THEME_LABELS: Record<AdultThemeId, string> = {
  deep_purple: '深紫迷离',
  dark_crimson: '暗红暧昧',
  midnight_bar: '深夜酒馆',
  luxury_suite: '豪华套房',
}

export interface RelationLevel {
  key: string
  label: string
  color: string
  min: number
  max: number
}

/** Desire+ relation tiers */
export const ADULT_RELATION_LEVELS: RelationLevel[] = [
  { key: 'glance', label: '初遇', color: '#9CA3AF', min: 0, max: 20 },
  { key: 'heartbeat', label: '心动', color: '#FF4D6D', min: 21, max: 40 },
  { key: 'tension', label: '情感张力', color: '#FF004D', min: 41, max: 55 },
  { key: 'danger', label: '危险关系', color: '#A855F7', min: 56, max: 70 },
  { key: 'encounter', label: '命运邂逅', color: '#FF4D6D', min: 71, max: 85 },
  { key: 'resonance', label: '欲望共鸣', color: '#FFD1DC', min: 86, max: 100 },
]

export const ADULT_STAT_LABELS: Record<string, string> = {
  affection: '吸引力',
  trust: '情感张力',
  intimacy: '情感张力',
  bond: '欲望共鸣',
  好感度: '吸引力',
  好感: '吸引力',
  亲密度: '情感张力',
  亲密: '情感张力',
  羁绊: '欲望共鸣',
}

export function getAdultStatLabel(label: string): string {
  return ADULT_STAT_LABELS[label] ?? ADULT_STAT_LABELS[label.trim()] ?? label
}

export function getAdultRelationLevel(affection: number): RelationLevel {
  const safe = Number.isFinite(affection) ? Math.max(0, Math.min(100, Math.round(affection))) : 50
  return (
    ADULT_RELATION_LEVELS.find((l) => safe >= l.min && safe <= l.max) ??
    ADULT_RELATION_LEVELS[2]
  )
}

export function applyAdultThemePack(themeId: AdultThemeId | null) {
  const root = document.documentElement
  if (themeId) {
    root.setAttribute(ADULT_THEME_ATTR, themeId)
  } else {
    root.removeAttribute(ADULT_THEME_ATTR)
  }
}

export function applyUiTheme(theme: UiTheme, adultThemePack?: AdultThemeId | null) {
  document.documentElement.setAttribute(UI_THEME_ATTR, theme)
  if (theme === 'adult') {
    applyAdultThemePack(adultThemePack ?? 'deep_purple')
    document.documentElement.style.setProperty('--story-max-width', '800px')
  } else {
    applyAdultThemePack(null)
    const saved = localStorage.getItem('app-settings')
    let maxWidth = 960
    try {
      if (saved) maxWidth = JSON.parse(saved).maxWidth ?? 960
    } catch { /* ignore */ }
    document.documentElement.style.setProperty(
      '--story-max-width',
      maxWidth === 100 ? '100%' : `${maxWidth}px`,
    )
  }
}

export const ADULT_MODE_EVENT = 'adult-mode-changed'

export function dispatchAdultModeChange(adultMode: boolean) {
  window.dispatchEvent(new CustomEvent(ADULT_MODE_EVENT, { detail: { adultMode } }))
}
