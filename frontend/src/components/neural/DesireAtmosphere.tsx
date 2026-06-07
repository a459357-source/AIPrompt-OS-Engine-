import { useAdultThemeOptional } from '@/contexts/AdultThemeContext'

/** Soft-focus red/pink bokeh layer for Desire+ theme */
export function DesireAtmosphere() {
  const adultMode = useAdultThemeOptional()?.adultMode ?? false
  if (!adultMode) return null

  return (
    <div className="desire-atmosphere fixed inset-0 pointer-events-none z-[1]" aria-hidden>
      <div className="desire-orb desire-orb-1" />
      <div className="desire-orb desire-orb-2" />
      <div className="desire-orb desire-orb-3" />
    </div>
  )
}
