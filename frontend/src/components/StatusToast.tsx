import { motion, AnimatePresence } from 'framer-motion'

interface StatusToastProps {
  message: string
  type?: 'info' | 'success' | 'error' | 'loading'
}

const typeStyles = {
  info: 'bg-game-primary/10 border-game-primary/30 text-game-primary',
  success: 'bg-game-success/10 border-game-success/30 text-game-success',
  error: 'bg-game-danger/10 border-game-danger/30 text-game-danger',
  loading: 'bg-game-accent/10 border-game-accent/30 text-game-accent',
}

export function StatusToast({ message, type = 'info' }: StatusToastProps) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className={`mb-4 px-4 py-2.5 rounded-lg text-sm border flex items-center gap-2 ${typeStyles[type]}`}
        >
          {type === 'loading' && (
            <span className="inline-block w-3 h-3 border-2 border-game-accent/30 border-t-game-accent rounded-full animate-spin" />
          )}
          {type === 'success' && '✅'}
          {type === 'error' && '❌'}
          {type === 'info' && 'ℹ️'}
          <span>{message}</span>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
