import { useDocumentTitle } from '@/hooks/useDocumentTitle'

/** Mount once at app root — updates document.title from world_pack. */
export function DocumentTitle() {
  useDocumentTitle()
  return null
}
