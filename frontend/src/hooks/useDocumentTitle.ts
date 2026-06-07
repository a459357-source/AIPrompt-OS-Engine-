import { useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { getWorldMeta } from '@/lib/api'

const WORLD_CHANGED = 'promptos:world-changed'
const DRAFT_TITLE = 'promptos:draft-title'
const APP_NAME = 'World Builder'

function formatDocumentTitle(storyTitle: string, draftTitle?: string, useDraft?: boolean): string {
  const title = (useDraft ? draftTitle?.trim() : '') || storyTitle.trim()
  return title ? `${title} — ${APP_NAME}` : APP_NAME
}

/** Sync browser tab title with story title (world_pack) or NewStory draft on /new. */
export function useDocumentTitle() {
  const location = useLocation()
  const [worldTitle, setWorldTitle] = useState('')
  const [draftTitle, setDraftTitle] = useState('')
  const onWorldPage = location.pathname === '/new' || location.pathname === '/'

  const refreshWorldTitle = useCallback(async () => {
    try {
      const data = await getWorldMeta()
      setWorldTitle(data.world_title || '')
    } catch {
      /* keep previous title on transient API errors */
    }
  }, [])

  useEffect(() => {
    refreshWorldTitle()
    const onWorldChanged = () => {
      refreshWorldTitle()
    }
    const onDraft = (event: Event) => {
      const detail = (event as CustomEvent<{ title?: string }>).detail
      setDraftTitle(typeof detail?.title === 'string' ? detail.title : '')
    }
    window.addEventListener(WORLD_CHANGED, onWorldChanged)
    window.addEventListener(DRAFT_TITLE, onDraft)
    return () => {
      window.removeEventListener(WORLD_CHANGED, onWorldChanged)
      window.removeEventListener(DRAFT_TITLE, onDraft)
    }
  }, [refreshWorldTitle])

  useEffect(() => {
    if (!onWorldPage) {
      setDraftTitle('')
    }
  }, [onWorldPage])

  useEffect(() => {
    document.title = formatDocumentTitle(worldTitle, draftTitle, onWorldPage)
  }, [worldTitle, draftTitle, onWorldPage, location.pathname])
}

export function notifyWorldTitleChanged(): void {
  window.dispatchEvent(new Event(WORLD_CHANGED))
}

export function notifyDraftTitle(title: string): void {
  window.dispatchEvent(new CustomEvent(DRAFT_TITLE, { detail: { title } }))
}
