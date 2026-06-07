import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { getGameGenSettings } from '@/lib/api'
import {
  applyUiTheme,
  dispatchAdultModeChange,
  ADULT_MODE_EVENT,
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

  const applyTheme = useCallback((mode: boolean, themePack: AdultThemeId) => {
    applyUiTheme(mode ? 'adult' : 'normal', mode ? themePack : null)
  }, [])

  const setAdultMode = useCallback((v: boolean) => {
    setAdultModeState(v)
    applyTheme(v, adultTheme)
    dispatchAdultModeChange(v)
  }, [adultTheme, applyTheme])

  const setAdultTheme = useCallback((v: AdultThemeId) => {
    setAdultThemeState(v)
    if (adultMode) applyTheme(true, v)
  }, [adultMode, applyTheme])

  useEffect(() => {
    getGameGenSettings()
      .then((data) => {
        const mode = !!data.adult_mode
        const theme = (data.adult_theme || 'deep_purple') as AdultThemeId
        setAdultModeState(mode)
        setAdultThemeState(theme)
        applyTheme(mode, theme)
      })
      .catch(() => applyUiTheme('normal'))
      .finally(() => setLoading(false))
  }, [applyTheme])

  useEffect(() => {
    const handler = (e: Event) => {
      const mode = !!(e as CustomEvent<{ adultMode: boolean }>).detail?.adultMode
      setAdultModeState(mode)
      applyTheme(mode, adultTheme)
    }
    window.addEventListener(ADULT_MODE_EVENT, handler)
    return () => window.removeEventListener(ADULT_MODE_EVENT, handler)
  }, [adultTheme, applyTheme])

  return (
    <AdultThemeContext.Provider
      value={{
        adultMode,
        adultTheme,
        uiTheme: adultMode ? 'adult' : 'normal',
        setAdultMode,
        setAdultTheme,
        loading,
      }}
    >
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
