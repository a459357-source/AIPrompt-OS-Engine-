/** Deduplicate character rows by display name (later entries win). */
export function dedupeCharactersByName<T extends { name?: string }>(chars: T[]): T[] {
  const map = new Map<string, T>()
  for (const c of chars) {
    const name = (c.name || '').trim()
    if (name) map.set(name, c)
  }
  return Array.from(map.values())
}
