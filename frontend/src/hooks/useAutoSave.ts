import { useEffect, useRef, useCallback, useState } from 'react'
import { get, set } from 'idb-keyval'

export function useAutoSave<T>(
  key: string,
  data: T,
  options: { debounceMs?: number } = {}
) {
  const { debounceMs = 2000 } = options
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const isRestoredRef = useRef(false)
  const [restoredData, setRestoredData] = useState<T | null>(null)

  // Restore on mount
  useEffect(() => {
    get<T>(key).then((saved) => {
      if (saved !== undefined && saved !== null) {
        setRestoredData(saved)
        isRestoredRef.current = true
      } else {
        isRestoredRef.current = true // mark as checked even if empty
      }
    }).catch(() => {
      isRestoredRef.current = true
    })
  }, [key])

  // Auto-save with debounce
  useEffect(() => {
    if (!isRestoredRef.current) return
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
    restoredData,
    isRestored: isRestoredRef.current,
    clearSaved,
  }
}
