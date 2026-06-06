import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import NewStory from './pages/NewStory'
import Game from './pages/Game'
import NPCs from './pages/NPCs'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'

function NavBar() {
  const location = useLocation()
  const links = [
    { to: '/new', icon: '🆕', label: '新故事' },
    { to: '/game', icon: '🎮', label: '游戏' },
    { to: '/npcs', icon: '👥', label: '角色' },
    { to: '/dashboard', icon: '📊', label: '仪表盘' },
    { to: '/settings', icon: '⚙️', label: '设置' },
  ]

  return (
    <nav className="flex items-center gap-1 px-4 py-2 border-b border-game-border bg-game-bg sticky top-0 z-50">
      <h1 className="text-game-primary font-bold text-lg mr-6">🎮 Prompt OS</h1>
      {links.map((l) => (
        <Link
          key={l.to}
          to={l.to}
          className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
            location.pathname === l.to
              ? 'bg-game-primary/15 text-game-primary'
              : 'text-game-muted hover:text-game-text hover:bg-game-surface'
          }`}
        >
          <span className="mr-1.5">{l.icon}</span>
          {l.label}
        </Link>
      ))}
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-game-bg text-game-text">
        <NavBar />
        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="p-4 md:p-6 max-w-7xl mx-auto"
          >
            <Routes>
              <Route path="/new" element={<NewStory />} />
              <Route path="/game" element={<Game />} />
              <Route path="/npcs" element={<NPCs />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/" element={<NewStory />} />
            </Routes>
          </motion.main>
        </AnimatePresence>
      </div>
    </BrowserRouter>
  )
}

export default App
