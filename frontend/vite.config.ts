import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

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
      '/api/game-state': 'http://localhost:8000',
      '/api/next': 'http://localhost:8000',
      '/generate-world': 'http://localhost:8000',
      '/generate-field': 'http://localhost:8000',
      '/generate-rules': 'http://localhost:8000',
      '/new': 'http://localhost:8000',
      '/next': 'http://localhost:8000',
      '/npcs': 'http://localhost:8000',
      '/settings': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/save': 'http://localhost:8000',
      '/load': 'http://localhost:8000',
      '/saves': 'http://localhost:8000',
      '/reset': 'http://localhost:8000',
      '/export': 'http://localhost:8000',
      '/dashboard': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
    },
  },
})
