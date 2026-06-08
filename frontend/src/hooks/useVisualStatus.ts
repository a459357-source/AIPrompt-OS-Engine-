import { useEffect, useState } from 'react'
import { getVisualStatus, type VisualStatus } from '@/lib/api'

export function useVisualStatus() {
  const [status, setStatus] = useState<VisualStatus | null>(null)
  useEffect(() => {
    getVisualStatus().then(setStatus).catch(() => setStatus(null))
  }, [])
  return status
}
