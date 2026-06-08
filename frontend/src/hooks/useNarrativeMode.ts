import { useCallback, useEffect, useState } from 'react'
import { getNarrativeState, setNarrativeMode, type NarrativeState } from '@/lib/api'

export function useNarrativeMode() {
  const [state, setState] = useState<NarrativeState | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      setState(await getNarrativeState())
    } catch {
      setState(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const setMode = useCallback(async (mode: 'explore' | 'narrative') => {
    const next = await setNarrativeMode(mode)
    setState(next)
    return next
  }, [])

  return {
    mode: state?.mode ?? 'explore',
    currentEventId: state?.current_event_id ?? '',
    setMode,
    refresh,
    loading,
  }
}
