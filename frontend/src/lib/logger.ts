/**
 * logger.ts — Frontend logging utility
 * Logs to console + IndexedDB for persistence across sessions.
 */
import { set, get, keys as idbKeys, del } from 'idb-keyval'

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LogEntry {
  timestamp: string
  level: LogLevel
  module: string
  message: string
  data?: unknown
}

const MAX_LOGS = 500
const LOG_KEY_PREFIX = 'log_'

function formatTime(): string {
  const d = new Date()
  return d.toISOString().replace('T', ' ').slice(0, 19)
}

async function appendLog(entry: LogEntry): Promise<void> {
  try {
    const keys = await idbKeys()
    const logKeys = keys.filter((k) => String(k).startsWith(LOG_KEY_PREFIX))
    // Clean old logs if too many
    if (logKeys.length > MAX_LOGS) {
      const toDelete = logKeys.slice(0, logKeys.length - MAX_LOGS)
      await Promise.all(toDelete.map((k) => del(k)))
    }
    await set(`${LOG_KEY_PREFIX}${Date.now()}_${Math.random().toString(36).slice(2, 6)}`, entry)
  } catch {
    // IndexedDB might be unavailable
  }
}

function log(level: LogLevel, module: string, message: string, data?: unknown): void {
  const entry: LogEntry = {
    timestamp: formatTime(),
    level,
    module,
    message,
    data,
  }

  // Console output
  const prefix = `[${entry.timestamp}] [${module}]`
  switch (level) {
    case 'debug': console.debug(prefix, message, data ?? ''); break
    case 'info': console.info(prefix, message, data ?? ''); break
    case 'warn': console.warn(prefix, message, data ?? ''); break
    case 'error': console.error(prefix, message, data ?? ''); break
  }

  // Persist errors & warns to IndexedDB
  if (level === 'error' || level === 'warn') {
    appendLog(entry)
  }
}

export const logger = {
  debug: (module: string, message: string, data?: unknown) => log('debug', module, message, data),
  info: (module: string, message: string, data?: unknown) => log('info', module, message, data),
  warn: (module: string, message: string, data?: unknown) => log('warn', module, message, data),
  error: (module: string, message: string, data?: unknown) => log('error', module, message, data),
}

/** Get all persisted log entries (newest first) */
export async function getLogs(limit = 100): Promise<LogEntry[]> {
  try {
    const keys = await idbKeys()
    const logKeys = (keys as string[])
      .filter((k) => k.startsWith(LOG_KEY_PREFIX))
      .sort()
      .reverse()
      .slice(0, limit)
    const entries: LogEntry[] = []
    for (const key of logKeys) {
      const entry = await get<LogEntry>(key)
      if (entry) entries.push(entry)
    }
    return entries
  } catch {
    return []
  }
}

/** Clear all persisted logs */
export async function clearLogs(): Promise<void> {
  try {
    const keys = await idbKeys()
    const logKeys = (keys as string[]).filter((k) => k.startsWith(LOG_KEY_PREFIX))
    await Promise.all(logKeys.map((k) => del(k)))
  } catch {
    // ignore
  }
}
