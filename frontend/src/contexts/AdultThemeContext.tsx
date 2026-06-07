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
} from '@/lib/theme'

interface AdultThemeContextValue {
  adultMode: boolean
  uiTheme: UiTheme
  setAdultMode: (v: boolean) => void
  loading: boolean
}

const AdultThemeContext = createContext<AdultThemeContextValue | null>(null)

export function AdultThemeProvider({ children }: { children: ReactNode }) {
  const [adultMode, setAdultModeState] = useState(false)
  const [loading, setLoading] = useState(true)

  const setAdultMode = useCallback((v: boolean) => {
    setAdultModeState(v)
    applyUiTheme(v ? 'adult' : 'normal')
    dispatchAdultModeChange(v)
  }, [])

  useEffect(() => {
    getGameGenSettings()
      .then((data) => {
        const mode = !!data.adult_mode
        setAdultModeState(mode)
        applyUiTheme(mode ? 'adult' : 'normal')
      })
      .catch(() => applyUiTheme('normal'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const handler = (e: Event) => {
      const mode = !!(e as CustomEvent<{ adultMode: boolean }>).detail?.adultMode
      setAdultModeState(mode)
      applyUiTheme(mode ? 'adult' : 'normal')
    }
    window.addEventListener(ADULT_MODE_EVENT, handler)
    return () => window.removeEventListener(ADULT_MODE_EVENT, handler)
  }, [])

  return (
    <AdultThemeContext.Provider
      value={{
        adultMode,
        uiTheme: adultMode ? 'adult' : 'normal',
        setAdultMode,
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
