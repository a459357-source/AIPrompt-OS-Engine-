import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getSettingsStatus, saveApiKey } from '@/lib/api'

/** Block first use until DeepSeek API Key is saved locally. */
export function ApiKeyPrompt() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [key, setKey] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const checkStatus = useCallback(async () => {
    const data = await getSettingsStatus()
    setOpen(!data.configured)
  }, [])

  useEffect(() => {
    checkStatus()
  }, [checkStatus])

  const handleSave = async () => {
    const trimmed = key.trim()
    if (!trimmed) {
      setError('请输入 DeepSeek API Key')
      return
    }
    setSaving(true)
    setError('')
    const result = await saveApiKey(trimmed)
    setSaving(false)
    if (result.error) {
      setError(result.error)
      return
    }
    setKey('')
    setOpen(false)
  }

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent
        className="sm:max-w-md [&>button]:hidden"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>🔑 请先配置 DeepSeek API Key</DialogTitle>
          <DialogDescription>
            首次使用需要填写 API Key 才能生成故事。Key 仅保存在本机
            <code className="mx-1 text-game-dim">data/apikey.json</code>
            ，不会上传。
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <Label htmlFor="first-run-api-key">DeepSeek API Key</Label>
          <Input
            id="first-run-api-key"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="sk-xxxxxxxxxxxxxxxx"
            className="font-mono"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave()
            }}
          />
          {error && <p className="text-xs text-game-danger">{error}</p>}
          <p className="text-xs text-game-dim">
            可在{' '}
            <a
              href="https://platform.deepseek.com/"
              target="_blank"
              rel="noreferrer"
              className="text-game-primary hover:underline"
            >
              DeepSeek 开放平台
            </a>
            {' '}申请 Key
          </p>
        </div>
        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            variant="outline"
            className="w-full sm:w-auto"
            onClick={() => navigate('/settings')}
          >
            打开完整设置
          </Button>
          <Button
            variant="accent"
            className="w-full sm:w-auto"
            disabled={saving || !key.trim()}
            onClick={handleSave}
          >
            {saving ? '保存中…' : '保存并开始'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
