import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getGameGenSettings,
  updateGameGenSettings,
  type ContentWeights,
  type GameGenSettings,
} from '@/lib/api'
import {
  applyUiTheme,
  dispatchAdultModeChange,
  dispatchAdultThemeChange,
  dispatchContentPreferencesSaved,
  dispatchVisualThemeChange,
  VISUAL_THEME_LABELS,
  VISUAL_THEME_OPTIONS,
  type AdultThemeId,
  type VisualThemeId,
} from '@/lib/theme'

function weightsMatchPreset(a: ContentWeights, b: ContentWeights) {
  return a.story === b.story && a.romance === b.romance && a.adult === b.adult
}

function detectActiveProfile(weights: ContentWeights, presets: Record<string, ContentWeights>) {
  for (const [key, preset] of Object.entries(presets)) {
    if (weightsMatchPreset(weights, preset)) return key
  }
  return null
}

export type ContentPreferencesPatch = {
  adultMode?: boolean
  adultUnlockKey?: string
  adultProfile?: string
  adultTheme?: string
  visualTheme?: string
  expressionStyle?: string
  contentWeights?: ContentWeights
}

export function useContentPreferences() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [adultMode, setAdultMode] = useState(false)
  const [adultUnlocked, setAdultUnlocked] = useState(false)
  const [adultUnlockKeyMasked, setAdultUnlockKeyMasked] = useState('')
  const [adultProfile, setAdultProfile] = useState('balanced')
  const [adultProfileOptions, setAdultProfileOptions] = useState<string[]>(['story_first', 'balanced', 'adult_first'])
  const [adultProfileLabels, setAdultProfileLabels] = useState<Record<string, string>>({})
  const [adultProfileDescriptions, setAdultProfileDescriptions] = useState<Record<string, string>>({})
  const [adultTheme, setAdultTheme] = useState<AdultThemeId>('deep_purple')
  const [adultThemeOptions, setAdultThemeOptions] = useState<string[]>([])
  const [adultThemeLabels, setAdultThemeLabels] = useState<Record<string, string>>({})
  const [visualTheme, setVisualTheme] = useState<VisualThemeId>('desire')
  const [visualThemeOptions, setVisualThemeOptions] = useState<string[]>([...VISUAL_THEME_OPTIONS])
  const [visualThemeLabels, setVisualThemeLabels] = useState<Record<string, string>>({ ...VISUAL_THEME_LABELS })
  const [expressionStyle, setExpressionStyle] = useState('light_novel')
  const [expressionStyleOptions, setExpressionStyleOptions] = useState<string[]>(['literary', 'romantic', 'light_novel', 'direct'])
  const [expressionStyleLabels, setExpressionStyleLabels] = useState<Record<string, string>>({})
  const [contentWeights, setContentWeights] = useState<ContentWeights>({ story: 40, romance: 30, adult: 30 })
  const [presetWeights, setPresetWeights] = useState<Record<string, ContentWeights>>({})
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingRef = useRef<ContentPreferencesPatch>({})

  const applySettings = useCallback((data: GameGenSettings) => {
    const mode = !!data.adult_mode
    const themeId = (data.adult_theme || 'deep_purple') as AdultThemeId
    const visual = (data.visual_theme === 'adult' || data.visual_theme === 'desire'
      ? data.visual_theme
      : 'desire') as VisualThemeId
    setAdultMode(mode)
    setAdultUnlocked(!!data.adult_unlocked)
    setAdultUnlockKeyMasked(data.adult_unlock_key_masked || '')
    setAdultProfile(data.adult_profile)
    setAdultProfileOptions(data.adult_profile_options)
    setAdultProfileLabels(data.adult_profile_labels)
    setAdultProfileDescriptions(data.adult_profile_descriptions)
    setAdultTheme(themeId)
    setAdultThemeOptions(data.adult_theme_options)
    setAdultThemeLabels(data.adult_theme_labels)
    setVisualTheme(visual)
    setVisualThemeOptions(data.visual_theme_options?.length ? data.visual_theme_options : [...VISUAL_THEME_OPTIONS])
    setVisualThemeLabels({ ...VISUAL_THEME_LABELS, ...(data.visual_theme_labels ?? {}) })
    setExpressionStyle(data.expression_style)
    setExpressionStyleOptions(data.expression_style_options)
    setExpressionStyleLabels(data.expression_style_labels)
    setContentWeights(data.content_weights)
    setPresetWeights(data.preset_weights)
    if (mode) {
      applyUiTheme(visual, themeId)
      dispatchAdultThemeChange(themeId)
      dispatchVisualThemeChange(visual)
    } else {
      applyUiTheme('normal')
    }
    dispatchAdultModeChange(mode)
  }, [])

  useEffect(() => {
    getGameGenSettings()
      .then(applySettings)
      .catch(() => applyUiTheme('normal'))
      .finally(() => setLoading(false))
  }, [applySettings])

  const activeAdultProfile = useMemo(
    () => detectActiveProfile(contentWeights, presetWeights),
    [contentWeights, presetWeights],
  )

  const flushSave = useCallback(async () => {
    const pending = pendingRef.current
    pendingRef.current = {}
    if (!Object.keys(pending).length) return
    setSaving(true)
    try {
      const saved = await updateGameGenSettings(pending)
      applySettings(saved)
      dispatchContentPreferencesSaved({
        options: saved.options,
        options_regenerated: saved.options_regenerated,
      })
    } finally {
      setSaving(false)
    }
  }, [applySettings])

  const savePreferences = useCallback((patch: ContentPreferencesPatch, immediate = false) => {
    const next = { ...patch }
    if (next.adultMode != null) {
      setAdultMode(next.adultMode)
      dispatchAdultModeChange(next.adultMode)
      if (next.adultMode) applyUiTheme(visualTheme, adultTheme)
      else applyUiTheme('normal')
    }
    if (next.adultProfile != null) {
      setAdultProfile(next.adultProfile)
      const preset = presetWeights[next.adultProfile]
      if (preset) {
        setContentWeights({ ...preset })
        next.contentWeights = { ...preset }
      }
    }
    if (next.adultTheme != null) {
      const themeId = next.adultTheme as AdultThemeId
      setAdultTheme(themeId)
      dispatchAdultThemeChange(themeId)
      if (adultMode) applyUiTheme(visualTheme, themeId)
    }
    if (next.visualTheme != null) {
      const visualId = next.visualTheme as VisualThemeId
      setVisualTheme(visualId)
      dispatchVisualThemeChange(visualId)
      if (adultMode) applyUiTheme(visualId, adultTheme)
    }
    if (next.expressionStyle != null) setExpressionStyle(next.expressionStyle)
    if (next.contentWeights != null) setContentWeights({ ...next.contentWeights })

    pendingRef.current = { ...pendingRef.current, ...next }
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    if (immediate) {
      void flushSave()
      return
    }
    saveTimerRef.current = setTimeout(() => void flushSave(), 400)
  }, [adultMode, adultTheme, visualTheme, presetWeights, flushSave])

  const unlockAndEnableAdult = useCallback(async (key: string) => {
    setSaving(true)
    try {
      const saved = await updateGameGenSettings({
        adultUnlockKey: key,
        adultMode: true,
      })
      applySettings(saved)
      dispatchContentPreferencesSaved({
        options: saved.options,
        options_regenerated: saved.options_regenerated,
      })
    } finally {
      setSaving(false)
    }
  }, [applySettings])

  return {
    loading,
    saving,
    adultMode,
    adultUnlocked,
    adultUnlockKeyMasked,
    adultProfile,
    adultProfileOptions,
    adultProfileLabels,
    adultProfileDescriptions,
    adultTheme,
    adultThemeOptions,
    adultThemeLabels,
    visualTheme,
    visualThemeOptions,
    visualThemeLabels,
    expressionStyle,
    expressionStyleOptions,
    expressionStyleLabels,
    contentWeights,
    activeAdultProfile,
    savePreferences,
    unlockAndEnableAdult,
  }
}
