import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useAppSettings } from '@/hooks/useAppSettings'
import { NeuralShellProvider } from '@/components/layout/NeuralShellContext'
import { NeuralShell } from '@/components/layout/NeuralShell'
import { AdultThemeProvider } from '@/contexts/AdultThemeContext'
import { ApiKeyPrompt } from '@/components/ApiKeyPrompt'
import { DocumentTitle } from '@/components/DocumentTitle'
import NewStory from './pages/NewStory'
import Game from './pages/Game'
import NPCs from './pages/NPCs'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'
import VisualWorld from './pages/VisualWorld'

function AppRoutes() {
  const location = useLocation()
  const { animations } = useAppSettings()

  const routes = (
    <Routes>
      <Route path="/new" element={<NewStory />} />
      <Route path="/game" element={<Game />} />
      <Route path="/npcs" element={<NPCs />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/visual" element={<VisualWorld />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/" element={<NewStory />} />
    </Routes>
  )

  if (animations) {
    return (
      <AnimatePresence mode="wait">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="h-full"
        >
          <ErrorBoundary>{routes}</ErrorBoundary>
        </motion.div>
      </AnimatePresence>
    )
  }

  return <ErrorBoundary>{routes}</ErrorBoundary>
}

function App() {
  return (
    <AdultThemeProvider>
      <NeuralShellProvider>
        <div className="h-screen overflow-hidden bg-neural-void text-game-text">
          <DocumentTitle />
          <ApiKeyPrompt />
          <NeuralShell>
            <AppRoutes />
          </NeuralShell>
        </div>
      </NeuralShellProvider>
    </AdultThemeProvider>
  )
}

export default function AppWrapper() {
  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  )
}
