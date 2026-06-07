import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { getGameGenSettings } from '@/lib/api'
import {
  applyUiTheme,
  dispatchAdultModeChange,
  dispatchVisualThemeChange,
  ADULT_MODE_EVENT,
  ADULT_THEME_EVENT,
  VISUAL_THEME_EVENT,
  type UiTheme,
  type AdultThemeId,
  type VisualThemeId,
} from '@/lib/theme'

interface AdultThemeContextValue {
  adultMode: boolean
  adultTheme: AdultThemeId
  visualTheme: VisualThemeId
  uiTheme: UiTheme
  setAdultMode: (v: boolean) => void
  setAdultTheme: (v: AdultThemeId) => void
  setVisualTheme: (v: VisualThemeId) => void
  loading: boolean
}

const AdultThemeContext = createContext<AdultThemeContextValue | null>(null)

export function AdultThemeProvider({ children }: { children: ReactNode }) {
  const [adultMode, setAdultModeState] = useState(false)
  const [adultTheme, setAdultThemeState] = useState<AdultThemeId>('deep_purple')
  const [visualTheme, setVisualThemeState] = useState<VisualThemeId>('desire')
  const [loading, setLoading] = useState(true)
  const adultThemeRef = useRef(adultTheme)
  adultThemeRef.current = adultTheme
  const visualThemeRef = useRef(visualTheme)
  visualThemeRef.current = visualTheme
  const adultModeRef = useRef(adultMode)
  adultModeRef.current = adultMode

  const applyTheme = useCallback((mode: boolean, visual: VisualThemeId, themePack: AdultThemeId) => {
    applyUiTheme(mode ? visual : 'normal', mode ? themePack : null)
  }, [])

  const setAdultMode = useCallback((v: boolean) => {
    setAdultModeState(v)
    applyTheme(v, visualThemeRef.current, adultThemeRef.current)
    dispatchAdultModeChange(v)
  }, [applyTheme])

  const setAdultTheme = useCallback((v: AdultThemeId) => {
    setAdultThemeState(v)
    adultThemeRef.current = v
    if (adultMode) applyTheme(true, visualThemeRef.current, v)
  }, [adultMode, applyTheme])

  const setVisualTheme = useCallback((v: VisualThemeId) => {
    setVisualThemeState(v)
    visualThemeRef.current = v
    if (adultMode) applyTheme(true, v, adultThemeRef.current)
    dispatchVisualThemeChange(v)
  }, [adultMode, applyTheme])

  useEffect(() => {
    getGameGenSettings()
      .then((data) => {
        const mode = !!data.adult_mode
        const theme = (data.adult_theme || 'deep_purple') as AdultThemeId
        const visual = (data.visual_theme || 'desire') as VisualThemeId
        setAdultModeState(mode)
        setAdultThemeState(theme)
        setVisualThemeState(visual)
        adultThemeRef.current = theme
        visualThemeRef.current = visual
        applyTheme(mode, visual, theme)
      })
      .catch(() => applyUiTheme('normal'))
      .finally(() => setLoading(false))
  }, [applyTheme])

  useEffect(() => {
    const onModeChange = (e: Event) => {
      const mode = !!(e as CustomEvent<{ adultMode: boolean }>).detail?.adultMode
      setAdultModeState((prev) => (prev === mode ? prev : mode))
      applyTheme(mode, visualThemeRef.current, adultThemeRef.current)
    }
    const onThemeChange = (e: Event) => {
      const theme = (e as CustomEvent<{ adultTheme: AdultThemeId }>).detail?.adultTheme
      if (!theme) return
      setAdultThemeState((prev) => (prev === theme ? prev : theme))
      adultThemeRef.current = theme
      if (adultModeRef.current) applyTheme(true, visualThemeRef.current, theme)
    }
    const onVisualChange = (e: Event) => {
      const visual = (e as CustomEvent<{ visualTheme: VisualThemeId }>).detail?.visualTheme
      if (!visual) return
      setVisualThemeState((prev) => (prev === visual ? prev : visual))
      visualThemeRef.current = visual
      if (adultModeRef.current) applyTheme(true, visual, adultThemeRef.current)
    }
    window.addEventListener(ADULT_MODE_EVENT, onModeChange)
    window.addEventListener(ADULT_THEME_EVENT, onThemeChange)
    window.addEventListener(VISUAL_THEME_EVENT, onVisualChange)
    return () => {
      window.removeEventListener(ADULT_MODE_EVENT, onModeChange)
      window.removeEventListener(ADULT_THEME_EVENT, onThemeChange)
      window.removeEventListener(VISUAL_THEME_EVENT, onVisualChange)
    }
  }, [applyTheme])

  const value = useMemo(
    () => ({
      adultMode,
      adultTheme,
      visualTheme,
      uiTheme: (adultMode ? visualTheme : 'normal') as UiTheme,
      setAdultMode,
      setAdultTheme,
      setVisualTheme,
      loading,
    }),
    [adultMode, adultTheme, visualTheme, setAdultMode, setAdultTheme, setVisualTheme, loading],
  )

  return (
    <AdultThemeContext.Provider value={value}>
      {children}
    </AdultThemeContext.Provider>
  )
}

export function useAdultTheme() {
  const ctx = useContext(AdultThemeContext)
  if (!ctx) throw new Error('useAdultTheme must be used within AdultThemeProvider')
  return ctx
}

export function useAdultThemeOptional() {
  return useContext(AdultThemeContext)
}
