import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import NewStory from './pages/NewStory'
import Game from './pages/Game'
import NPCs from './pages/NPCs'
import Dashboard from './pages/Dashboard'
import Settings from './pages/Settings'

const NAV_LINKS = [
  { to: '/new', icon: '🆕', label: '新故事' },
  { to: '/game', icon: '🎮', label: '游戏' },
  { to: '/npcs', icon: '👥', label: '角色' },
  { to: '/dashboard', icon: '📊', label: '仪表盘' },
  { to: '/settings', icon: '⚙️', label: '设置' },
]

// ── Desktop NavBar ──
function DesktopNav() {
  const location = useLocation()

  return (
    <nav className="hidden md:flex items-center gap-1 px-4 py-2 border-b border-game-border bg-game-bg/95 backdrop-blur-sm sticky top-0 z-50">
      <Link to="/" className="text-game-primary font-bold text-lg mr-6 hover:text-game-accent transition-colors">
        🎮 Prompt OS
      </Link>
      {NAV_LINKS.map((l) => (
        <Link
          key={l.to}
          to={l.to}
          className={`px-3 py-1.5 rounded-md text-sm transition-all duration-200 ${
            location.pathname === l.to || (l.to === '/new' && location.pathname === '/')
              ? 'bg-game-primary/15 text-game-primary shadow-sm'
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

// ── Mobile Bottom Nav ──
function MobileBottomNav() {
  const location = useLocation()

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-game-card/95 backdrop-blur-sm border-t border-game-border">
      <div className="flex items-center justify-around px-2 py-2 safe-area-bottom">
        {NAV_LINKS.map((l) => {
          const active = location.pathname === l.to || (l.to === '/new' && location.pathname === '/')
          return (
            <Link
              key={l.to}
              to={l.to}
              className={`flex flex-col items-center gap-0.5 px-2 py-1 rounded-lg transition-colors min-w-0 ${
                active
                  ? 'text-game-primary'
                  : 'text-game-dim hover:text-game-muted'
              }`}
            >
              <span className="text-lg">{l.icon}</span>
              <span className="text-[10px] leading-none">{l.label}</span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}

// ── Mobile Drawer Menu ──
function MobileDrawer() {
  const location = useLocation()
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger className="md:hidden">
        <Button variant="ghost" size="icon" className="text-game-text">
          <span className="text-xl">☰</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-64">
        <SheetHeader>
          <SheetTitle>🎮 Prompt OS</SheetTitle>
        </SheetHeader>
        <div className="mt-6 flex flex-col gap-1">
          {NAV_LINKS.map((l) => {
            const active = location.pathname === l.to || (l.to === '/new' && location.pathname === '/')
            return (
              <Link
                key={l.to}
                to={l.to}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                  active
                    ? 'bg-game-primary/15 text-game-primary font-medium'
                    : 'text-game-muted hover:text-game-text hover:bg-game-surface'
                }`}
              >
                <span className="text-lg">{l.icon}</span>
                {l.label}
              </Link>
            )
          })}
        </div>
      </SheetContent>
    </Sheet>
  )
}

// ── Mobile Top Bar ──
function MobileTopBar() {
  return (
    <div className="md:hidden flex items-center justify-between px-4 py-2 border-b border-game-border bg-game-bg/95 backdrop-blur-sm sticky top-0 z-40">
      <MobileDrawer />
      <Link to="/" className="text-game-primary font-bold text-base">
        🎮 Prompt OS
      </Link>
      <div className="w-9" /> {/* spacer for symmetry */}
    </div>
  )
}

// ── App ──
function App() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-game-bg text-game-text pb-16 md:pb-0">
      <DesktopNav />
      <MobileTopBar />
      <MobileBottomNav />

      <AnimatePresence mode="wait">
        <motion.main
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          className="p-4 md:p-6"
        >
          <ErrorBoundary>
            <Routes>
              <Route path="/new" element={<NewStory />} />
              <Route path="/game" element={<Game />} />
              <Route path="/npcs" element={<NPCs />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/" element={<NewStory />} />
            </Routes>
          </ErrorBoundary>
        </motion.main>
      </AnimatePresence>
    </div>
  )
}

export default function AppWrapper() {
  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  )
}
