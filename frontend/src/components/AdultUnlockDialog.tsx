import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type Props = {
  open: boolean
  saving?: boolean
  error?: string
  maskedKey?: string
  onClose: () => void
  onSubmit: (key: string) => void | Promise<void>
}

export function AdultUnlockDialog({
  open,
  saving = false,
  error = '',
  maskedKey = '',
  onClose,
  onSubmit,
}: Props) {
  const [keyInput, setKeyInput] = useState('')

  if (!open) return null

  const handleSubmit = () => {
    const trimmed = keyInput.trim()
    if (!trimmed) return
    void onSubmit(trimmed)
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-md rounded-xl glass-panel-opaque shadow-2xl p-5 space-y-4 border border-pink-500/20"
        role="dialog"
        aria-modal="true"
        aria-labelledby="adult-unlock-title"
      >
        <div className="space-y-1">
          <h2 id="adult-unlock-title" className="text-sm font-semibold text-game-text">
            成人模式解锁
          </h2>
          <p className="text-[11px] text-game-muted leading-relaxed">
            开启成人内容前需输入有效解锁密钥。密钥由本地密钥生成器签发，格式如 POS-A-XXXXXXXX-XXXXXXXXXXXXXXXX。
          </p>
          {maskedKey && (
            <p className="text-[10px] text-game-dim">已保存：{maskedKey}</p>
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="adult-unlock-key" className="text-xs text-game-muted">
            解锁密钥
          </Label>
          <Input
            id="adult-unlock-key"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="POS-A-..."
            className="font-mono text-xs"
            autoComplete="off"
            spellCheck={false}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSubmit()
            }}
          />
          {error && <p className="text-[11px] text-red-400">{error}</p>}
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={saving || !keyInput.trim()}
            onClick={handleSubmit}
          >
            {saving ? '验证中…' : '解锁并开启'}
          </Button>
        </div>
      </div>
    </div>
  )
}
