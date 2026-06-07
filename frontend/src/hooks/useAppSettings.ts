import { useEffect, useState } from 'react'
import { getSettings, type AppSettings } from '@/lib/settings'

export function useAppSettings(): AppSettings {
  const [settings, setSettings] = useState<AppSettings>(() => getSettings())

  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<AppSettings>).detail
      if (detail) setSettings({ ...detail })
      else setSettings(getSettings())
    }
    window.addEventListener('app-settings-changed', onChange)
    return () => window.removeEventListener('app-settings-changed', onChange)
  }, [])

  return settings
}
