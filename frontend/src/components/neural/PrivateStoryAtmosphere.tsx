import { useAdultThemeOptional } from '@/contexts/AdultThemeContext'

/** Soft-focus red/pink bokeh — Desire+ atmosphere */
export function PrivateStoryAtmosphere() {  const adultMode = useAdultThemeOptional()?.adultMode ?? false
  if (!adultMode) return null

  return (
    <div className="private-story-atmosphere fixed inset-0 pointer-events-none z-[1]" aria-hidden>
      <div className="private-orb private-orb-1" />
      <div className="private-orb private-orb-2" />
      <div className="private-orb private-orb-3" />
    </div>
  )
}
