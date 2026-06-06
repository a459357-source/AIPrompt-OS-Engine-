import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  loadSettings,
  saveSettings,
  DEFAULTS,
  type AppSettings,
  FONT_SIZE_OPTIONS,
  LINE_HEIGHT_OPTIONS,
  MAX_WIDTH_OPTIONS,
  FONT_FAMILY_LABELS,
  BG_THEME_LABELS,
} from '@/lib/settings'

type SectionKey = 'reading' | 'ai' | 'data' | 'ui'

export default function Settings() {
  const [s, setS] = useState<AppSettings>(loadSettings)
  const [saved, setSaved] = useState(false)
  const [collapsed, setCollapsed] = useState<Set<SectionKey>>(new Set())

  const update = useCallback((key: keyof AppSettings, value: unknown) => {
    setS((prev) => {
      const next = { ...prev, [key]: value }
      saveSettings({ [key]: value } as Partial<AppSettings>)
      return next
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 1200)
  }, [])

  const toggle = (k: SectionKey) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      next.has(k) ? next.delete(k) : next.add(k)
      return next
    })
  }

  // API settings (backend)
  const [apiKey, setApiKey] = useState('')
  const [apiKeyMasked, setApiKeyMasked] = useState('')
  const [model, setModel] = useState('deepseek-chat')
  const [storyLength, setStoryLength] = useState(1000)

  useEffect(() => {
    fetch('/settings')
      .then((r) => r.text())
      .then((html) => {
        const keyMatch = html.match(/value="(sk-[^"]*)"/)
        if (keyMatch) setApiKey(keyMatch[1])
        const maskedMatch = html.match(/已配置 \((sk[^)]+)\)/)
        if (maskedMatch) setApiKeyMasked(maskedMatch[1])
      })
      .catch(() => {})
  }, [])

  const saveApiKey = useCallback(async () => {
    const fd = new FormData()
    if (apiKey) fd.append('api_key', apiKey)
    fd.append('model', model)
    fd.append('story_length', String(storyLength))
    await fetch('/settings', { method: 'POST', body: fd })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }, [apiKey, model, storyLength])

  // ── Section component ──
  function Section({ id, icon, title, children }: { id: SectionKey; icon: string; title: string; children: React.ReactNode }) {
    const open = !collapsed.has(id)
    return (
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="bg-game-card border border-game-border rounded-lg overflow-hidden">
        <button type="button" onClick={() => toggle(id)} className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-game-surface/50 transition-colors">
          <span className="font-bold text-sm flex items-center gap-2">
            <span>{icon}</span> {title}
          </span>
          <span className="text-game-dim text-xs">{open ? '▲' : '▼'}</span>
        </button>
        {open && <div className="px-5 pb-5 space-y-4">{children}</div>}
      </motion.div>
    )
  }

  function SelectRow({ label, value, options, onChange, labels }: {
    label: string; value: unknown; options: readonly (number | string | { value: number | string; label: string })[]
    onChange: (v: unknown) => void; labels?: Record<string, string>
  }) {
    return (
      <div className="flex items-center justify-between">
        <span className="text-sm text-game-muted">{label}</span>
        <div className="flex gap-1">
          {(options as any[]).map((opt) => {
            const v = typeof opt === 'number' ? opt : opt.value
            const l = typeof opt === 'number' ? String(opt) : opt.label
            return (
              <button key={v} onClick={() => onChange(v)}
                className={`px-2.5 py-1 text-xs rounded transition-all ${
                  value === v ? 'bg-game-primary/20 text-game-primary border border-game-primary/40' : 'bg-game-surface text-game-muted border border-game-border hover:text-game-text'
                }`}
              >{labels?.[v] ?? l}</button>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-game-accent font-bold text-lg">⚙️ 设置</h1>
        {saved && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs text-game-success">✅ 已保存</motion.span>}
      </div>

      {/* ── Reading ── */}
      <Section id="reading" icon="📖" title="阅读体验">
        <SelectRow label="字体大小" value={s.fontSize} options={FONT_SIZE_OPTIONS} onChange={(v) => update('fontSize', v)} />
        <SelectRow label="行高" value={s.lineHeight} options={LINE_HEIGHT_OPTIONS} onChange={(v) => update('lineHeight', v)} />
        <SelectRow label="正文字体" value={s.fontFamily} options={['system','serif','sans','kai']} onChange={(v) => update('fontFamily', v)} labels={FONT_FAMILY_LABELS} />
        <SelectRow label="最大宽度" value={s.maxWidth} options={MAX_WIDTH_OPTIONS} onChange={(v) => update('maxWidth', v)} />
        <SelectRow label="背景色调" value={s.bgTheme} options={['dark','sepia','gray']} onChange={(v) => update('bgTheme', v)} labels={BG_THEME_LABELS} />
        <SelectRow label="段落间距" value={s.paragraphSpacing} options={['compact','standard','relaxed']} onChange={(v) => update('paragraphSpacing', v)} labels={{compact:'紧凑',standard:'标准',relaxed:'宽松'}} />

        {/* Live preview */}
        <div className="bg-game-bg border border-game-border rounded-md p-4 mt-2" style={{
          fontSize: `var(--story-font-size)`,
          lineHeight: `var(--story-line-height)`,
          fontFamily: `var(--story-font-family)`,
          maxWidth: `var(--story-max-width)`,
        }}>
          <p style={{marginBottom:'var(--story-paragraph-spacing)'}}>「有时候，一个选择就足以改变一切。」</p>
          <p>少女微微一笑，伸手拨开了被风吹乱的刘海，目光穿过窗外的樱花，仿佛在凝视遥远的记忆。</p>
        </div>
      </Section>

      {/* ── AI ── */}
      <Section id="ai" icon="🤖" title="AI 行为">
        <div className="flex items-center justify-between">
          <span className="text-sm text-game-muted">生成温度 <span className="text-game-dim text-xs">({s.temperature.toFixed(1)})</span></span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-game-dim">保守</span>
            <input type="range" min={0.3} max={1.2} step={0.1} value={s.temperature}
              onChange={(e) => update('temperature', parseFloat(e.target.value))}
              className="w-32 accent-game-accent" />
            <span className="text-xs text-game-dim">创意</span>
          </div>
        </div>
        <SelectRow label="选项数量" value={s.optionCount} options={[3,4,5]} onChange={(v) => update('optionCount', v)} />
        <div className="flex items-center justify-between">
          <span className="text-sm text-game-muted">叙事视角</span>
          <div className="flex gap-1">
            {[{v:'first',l:'第一人称'},{v:'third',l:'第三人称'},{v:'auto',l:'自动'}].map(o => (
              <button key={o.v} onClick={() => update('narrativePov', o.v)}
                className={`px-2.5 py-1 text-xs rounded transition-all ${
                  s.narrativePov === o.v ? 'bg-game-primary/20 text-game-primary border border-game-primary/40' : 'bg-game-surface text-game-muted border border-game-border hover:text-game-text'
                }`}>{o.l}</button>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-game-muted">文风偏好</span>
          <div className="flex gap-1 flex-wrap justify-end">
            {[{v:'descriptive',l:'细腻描写'},{v:'fast',l:'快节奏'},{v:'dialogue',l:'对话为主'},{v:'psycho',l:'心理刻画'},{v:'balanced',l:'均衡'}].map(o => (
              <button key={o.v} onClick={() => update('stylePreference', o.v)}
                className={`px-2 py-0.5 text-[11px] rounded transition-all ${
                  s.stylePreference === o.v ? 'bg-game-primary/20 text-game-primary border border-game-primary/40' : 'bg-game-surface text-game-muted border border-game-border hover:text-game-text'
                }`}>{o.l}</button>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-game-muted">自动推进</span>
          <button onClick={() => update('autoAdvance', !s.autoAdvance)}
            className={`px-3 py-1 text-xs rounded transition-all ${
              s.autoAdvance ? 'bg-game-success/20 text-game-success border border-game-success/40' : 'bg-game-surface text-game-dim border border-game-border'
            }`}>{s.autoAdvance ? '开' : '关'}</button>
        </div>
        <SelectRow label="重复检测" value={s.repetitionCheck} options={['strict','standard','loose']} onChange={(v) => update('repetitionCheck', v)} labels={{strict:'严格',standard:'标准',loose:'宽松'}} />
      </Section>

      {/* ── Data ── */}
      <Section id="data" icon="💾" title="数据与存档">
        <SelectRow label="自动保存间隔" value={s.autoSaveInterval} options={[30,60,300,0]} onChange={(v) => update('autoSaveInterval', v)} labels={{30:'30秒',60:'1分钟',300:'5分钟',0:'关闭'}} />
        <SelectRow label="最大存档数" value={s.maxSaveSlots} options={[3,5,10]} onChange={(v) => update('maxSaveSlots', v)} />
        <SelectRow label="导出格式" value={s.exportFormat} options={['markdown','text','html']} onChange={(v) => update('exportFormat', v)} labels={{markdown:'Markdown',text:'纯文本',html:'HTML'}} />
        <SelectRow label="自动导出" value={s.autoExport} options={['off','turn','chapter']} onChange={(v) => update('autoExport', v)} labels={{off:'关闭',turn:'每轮',chapter:'每章'}} />
      </Section>

      {/* ── UI ── */}
      <Section id="ui" icon="🎨" title="UI 偏好">
        <div className="flex items-center justify-between">
          <span className="text-sm text-game-muted">动画效果</span>
          <button onClick={() => update('animations', !s.animations)}
            className={`px-3 py-1 text-xs rounded transition-all ${
              s.animations ? 'bg-game-success/20 text-game-success border border-game-success/40' : 'bg-game-surface text-game-dim border border-game-border'
            }`}>{s.animations ? '开' : '关'}</button>
        </div>
        <SelectRow label="侧栏默认" value={s.sidebarDefault} options={['expanded','collapsed']} onChange={(v) => update('sidebarDefault', v)} labels={{expanded:'展开',collapsed:'折叠'}} />
        <SelectRow label="角色面板位置" value={s.charPanelPosition} options={['right','bottom','hidden']} onChange={(v) => update('charPanelPosition', v)} labels={{right:'右侧',bottom:'底部',hidden:'隐藏'}} />
        <SelectRow label="语言" value={s.language} options={['zh','en','ja']} onChange={(v) => update('language', v)} labels={{zh:'中文',en:'English',ja:'日本語'}} />
      </Section>

      {/* ── API ── */}
      <Section id="reading" icon="🔑" title="API 密钥">
        <div>
          <label className="text-xs text-game-muted font-medium">DeepSeek API Key</label>
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-xxxxxxxxxxxxxxxx"
            className="w-full mt-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:border-game-primary" />
          {apiKeyMasked && <p className="text-xs text-game-success mt-1">✅ 已配置 ({apiKeyMasked})</p>}
        </div>
        <div>
          <label className="text-xs text-game-muted font-medium">模型</label>
          <select value={model} onChange={(e) => setModel(e.target.value)}
            className="w-full mt-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-game-primary">
            <option value="deepseek-chat">V4-Flash（快速）</option>
            <option value="deepseek-reasoner">V4-Pro（深度思考）</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-game-muted font-medium">每轮字数</label>
          <input type="number" min={300} max={3000} step={100} value={storyLength} onChange={(e) => setStoryLength(parseInt(e.target.value)||1000)}
            className="w-32 mt-1 bg-game-bg border border-game-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-game-primary" />
          <span className="text-xs text-game-dim ml-2">300–3000</span>
        </div>
        <button onClick={saveApiKey} className="w-full py-2.5 bg-game-success/20 text-game-success border border-game-success/30 rounded-md font-bold hover:bg-game-success/30 transition-colors">
          💾 保存 API 设置
        </button>
      </Section>

      {/* Reset */}
      <div className="text-center pb-8">
        <button onClick={() => { if (confirm('恢复所有设置为默认值？')) { saveSettings({...DEFAULTS}); setS(loadSettings()) } }}
          className="text-xs text-game-dim hover:text-game-danger transition-colors">
          恢复默认设置
        </button>
      </div>
    </div>
  )
}
