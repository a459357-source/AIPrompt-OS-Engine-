import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'

const FONT_SIZES = [
  { value: 14, label: '小' },
  { value: 17, label: '默认' },
  { value: 20, label: '大' },
  { value: 24, label: '超大' },
  { value: 28, label: '特大' },
]

function getFontSize(): number {
  try {
    const v = localStorage.getItem('story-font-size')
    return v ? parseInt(v, 10) : 17
  } catch {
    return 17
  }
}

function setFontSize(v: number) {
  localStorage.setItem('story-font-size', String(v))
  document.documentElement.style.setProperty('--story-font-size', `${v}px`)
}

// Apply on load
if (typeof window !== 'undefined') {
  document.documentElement.style.setProperty('--story-font-size', `${getFontSize()}px`)
}

export { getFontSize, setFontSize }

export default function Settings() {
  const [fontSize, setFontSizeState] = useState(getFontSize)
  const [saved, setSaved] = useState(false)

  const handleFontSize = useCallback((v: number) => {
    setFontSizeState(v)
    setFontSize(v)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }, [])

  // API key state
  const [apiKey, setApiKey] = useState('')
  const [apiKeyMasked, setApiKeyMasked] = useState('')
  const [model, setModel] = useState('deepseek-chat')
  const [storyLength, setStoryLength] = useState(1000)

  useEffect(() => {
    // Fetch current settings from backend
    fetch('/settings')
      .then((r) => r.text())
      .then((html) => {
        // Extract current key from HTML
        const keyMatch = html.match(/value="(sk-[^"]*)"/)
        if (keyMatch) setApiKey(keyMatch[1])
        const maskedMatch = html.match(/已配置 \((sk[^)]+)\)/)
        if (maskedMatch) setApiKeyMasked(maskedMatch[1])
        const modelMatch = html.match(/当前: ([^<]+)</)
        if (modelMatch) setModel(modelMatch[1].includes('Flash') ? 'deepseek-chat' : 'deepseek-reasoner')
        const lenMatch = html.match(/value="(\d{3,4})"/)
        if (lenMatch) setStoryLength(parseInt(lenMatch[1]))
      })
      .catch(() => {})
  }, [])

  const handleSave = useCallback(async () => {
    const fd = new FormData()
    if (apiKey) fd.append('api_key', apiKey)
    fd.append('model', model)
    fd.append('story_length', String(storyLength))
    await fetch('/settings', { method: 'POST', body: fd })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }, [apiKey, model, storyLength])

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-game-card border border-game-border rounded-lg p-6 space-y-4"
      >
        <h2 className="text-game-accent font-bold text-lg flex items-center gap-2">
          <span>🔤</span> 正文字体大小
        </h2>
        <p className="text-xs text-game-dim">调整游戏故事正文的阅读字体大小</p>

        <div className="flex items-center gap-3">
          {FONT_SIZES.map((fs) => (
            <button
              key={fs.value}
              onClick={() => handleFontSize(fs.value)}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${
                fontSize === fs.value
                  ? 'bg-game-primary/20 text-game-primary border border-game-primary/40'
                  : 'bg-game-surface text-game-muted border border-game-border hover:text-game-text'
              }`}
            >
              {fs.label}
              <div className="text-[11px] opacity-60">{fs.value}px</div>
            </button>
          ))}
        </div>

        {/* Preview */}
        <div
          className="bg-game-bg border border-game-border rounded-md p-4 text-game-text leading-relaxed"
          style={{ fontSize: `${fontSize}px` }}
        >
          「有时候，一个选择就足以改变一切。」
          <br />
          少女微微一笑，伸手拨开了被风吹乱的刘海，目光穿过窗外的樱花，仿佛在凝视遥远的记忆。
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-game-card border border-game-border rounded-lg p-6 space-y-4"
      >
        <h2 className="text-game-accent font-bold text-lg flex items-center gap-2">
          <span>🔑</span> API 设置
        </h2>

        <div>
          <label className="text-xs text-game-muted font-medium">DeepSeek API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-xxxxxxxxxxxxxxxx"
            className="w-full mt-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-game-primary"
          />
          {apiKeyMasked && (
            <p className="text-xs text-game-success mt-1">✅ 已配置 ({apiKeyMasked})</p>
          )}
          <p className="text-xs text-game-dim mt-1">Key 仅存储在本地，不会上传</p>
        </div>

        <div>
          <label className="text-xs text-game-muted font-medium">模型选择</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full mt-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-game-primary"
          >
            <option value="deepseek-chat">V4-Flash（快速）</option>
            <option value="deepseek-reasoner">V4-Pro（深度思考）</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-game-muted font-medium">每轮字数</label>
          <input
            type="number"
            min={300}
            max={3000}
            step={100}
            value={storyLength}
            onChange={(e) => setStoryLength(parseInt(e.target.value) || 1000)}
            className="w-32 mt-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-game-primary"
          />
          <span className="text-xs text-game-dim ml-2">300–3000，默认 1000</span>
        </div>

        <button
          onClick={handleSave}
          className="w-full py-2.5 bg-game-success/20 text-game-success border border-game-success/30 rounded-md font-bold hover:bg-game-success/30 transition-colors"
        >
          {saved ? '✅ 已保存' : '💾 保存设置'}
        </button>
      </motion.div>
    </div>
  )
}
