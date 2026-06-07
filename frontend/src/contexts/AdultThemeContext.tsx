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
  ADULT_MODE_EVENT,
  ADULT_THEME_EVENT,
  type UiTheme,
  type AdultThemeId,
} from '@/lib/theme'

interface AdultThemeContextValue {
  adultMode: boolean
  adultTheme: AdultThemeId
  uiTheme: UiTheme
  setAdultMode: (v: boolean) => void
  setAdultTheme: (v: AdultThemeId) => void
  loading: boolean
}

const AdultThemeContext = createContext<AdultThemeContextValue | null>(null)

export function AdultThemeProvider({ children }: { children: ReactNode }) {
  const [adultMode, setAdultModeState] = useState(false)
  const [adultTheme, setAdultThemeState] = useState<AdultThemeId>('deep_purple')
  const [loading, setLoading] = useState(true)
  const adultThemeRef = useRef(adultTheme)
  adultThemeRef.current = adultTheme
  const adultModeRef = useRef(adultMode)
  adultModeRef.current = adultMode

  const applyTheme = useCallback((mode: boolean, themePack: AdultThemeId) => {
    applyUiTheme(mode ? 'adult' : 'normal', mode ? themePack : null)
  }, [])

  const setAdultMode = useCallback((v: boolean) => {
    setAdultModeState(v)
    applyTheme(v, adultThemeRef.current)
    dispatchAdultModeChange(v)
  }, [applyTheme])

  const setAdultTheme = useCallback((v: AdultThemeId) => {
    setAdultThemeState(v)
    adultThemeRef.current = v
    if (adultMode) applyTheme(true, v)
  }, [adultMode, applyTheme])

  useEffect(() => {
    getGameGenSettings()
      .then((data) => {
        const mode = !!data.adult_mode
        const theme = (data.adult_theme || 'deep_purple') as AdultThemeId
        setAdultModeState(mode)
        setAdultThemeState(theme)
        adultThemeRef.current = theme
        applyTheme(mode, theme)
      })
      .catch(() => applyUiTheme('normal'))
      .finally(() => setLoading(false))
  }, [applyTheme])

  useEffect(() => {
    const onModeChange = (e: Event) => {
      const mode = !!(e as CustomEvent<{ adultMode: boolean }>).detail?.adultMode
      setAdultModeState((prev) => (prev === mode ? prev : mode))
      applyTheme(mode, adultThemeRef.current)
    }
    const onThemeChange = (e: Event) => {
      const theme = (e as CustomEvent<{ adultTheme: AdultThemeId }>).detail?.adultTheme
      if (!theme) return
      setAdultThemeState((prev) => (prev === theme ? prev : theme))
      adultThemeRef.current = theme
      if (adultModeRef.current) applyTheme(true, theme)
    }
    window.addEventListener(ADULT_MODE_EVENT, onModeChange)
    window.addEventListener(ADULT_THEME_EVENT, onThemeChange)
    return () => {
      window.removeEventListener(ADULT_MODE_EVENT, onModeChange)
      window.removeEventListener(ADULT_THEME_EVENT, onThemeChange)
    }
  }, [applyTheme])

  const value = useMemo(
    () => ({
      adultMode,
      adultTheme,
      uiTheme: (adultMode ? 'adult' : 'normal') as UiTheme,
      setAdultMode,
      setAdultTheme,
      loading,
    }),
    [adultMode, adultTheme, setAdultMode, setAdultTheme, loading],
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
