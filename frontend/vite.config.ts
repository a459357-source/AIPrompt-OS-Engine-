import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import type { IncomingMessage } from 'http'

const API = 'http://localhost:8000'

/** Browser refresh on SPA routes must not hit legacy HTML on :8000. */
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
    port: 5173,
    proxy: {
      '/api': { target: API, changeOrigin: true },

      // AI / form POST endpoints (legacy paths, no React route conflict on GET)
      '/generate-world': API,
      '/generate-field': API,
      '/generate-rules': API,

      // React routes that also exist on backend — only proxy non-page requests
      '/new': { target: API, changeOrigin: true, bypass: spaPageBypass },
      '/settings': { target: API, changeOrigin: true, bypass: spaPageBypass },

      // Backend-only utilities (no matching React Router paths)
      '/health': API,
      '/save': API,
      '/load': API,
      '/saves': API,
      '/reset': API,
      '/export': API,
      '/graph': API,
      '/shutdown': API,
      '/next': API,
      '/legacy': API,
    },
  },
})
