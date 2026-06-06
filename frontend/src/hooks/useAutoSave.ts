import { useEffect, useRef, useCallback } from 'react'
import { get, set } from 'idb-keyval'

export function useAutoSave<T>(
  key: string,
  data: T,
  options: { debounceMs?: number } = {}
) {
  const { debounceMs = 2000 } = options
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const isRestoredRef = useRef(false)
  const restoredDataRef = useRef<T | null>(null)

  // Restore on mount
  useEffect(() => {
    get<T>(key).then((saved) => {
      if (saved !== undefined && saved !== null) {
        restoredDataRef.current = saved
        isRestoredRef.current = true
      }
    })
  }, [key])

  // Auto-save with debounce
  useEffect(() => {
    if (!isRestoredRef.current) return // Don't save before restore check
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      set(key, data).catch(console.error)
    }, debounceMs)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [key, data, debounceMs])

  const clearSaved = useCallback(() => {
    set(key, null).catch(console.error)
  }, [key])

  return {
    restoredData: restoredDataRef.current,
    isRestored: isRestoredRef.current,
    clearSaved,
  }
}
