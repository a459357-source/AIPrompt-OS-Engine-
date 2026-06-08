import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import type { IncomingMessage } from 'http'

const API = 'http://localhost:8000'

/** Browser refresh on SPA routes must serve index.html from Vite, not :8000. */
function spaPageBypass(req: IncomingMessage | undefined) {
  const accept = req?.headers?.accept || ''
  if (req?.method === 'GET' && accept.includes('text/html')) {
    return '/index.html'
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    open: 'http://127.0.0.1:5173/',
    proxy: {
      '/api': { target: API, changeOrigin: true },

      // AI / form POST endpoints
      '/generate-world': API,
      '/generate-field': API,
      '/generate-rules': API,
      '/new': { target: API, changeOrigin: true, bypass: spaPageBypass },
      '/visual': { target: API, changeOrigin: true, bypass: spaPageBypass },
      '/game': { target: API, changeOrigin: true, bypass: spaPageBypass },
      '/npcs': { target: API, changeOrigin: true, bypass: spaPageBypass },
      '/dashboard': { target: API, changeOrigin: true, bypass: spaPageBypass },
      '/settings': { target: API, changeOrigin: true, bypass: spaPageBypass },

      // Backend utilities (no React route conflict)
      '/health': API,
      '/save': API,
      '/load': API,
      '/saves': API,
      '/reset': API,
      '/export': API,
      '/shutdown': API,
    },
  },
})
