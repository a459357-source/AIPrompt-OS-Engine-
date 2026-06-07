/** Minimal UI strings for zh / en / ja */

export type AppLanguage = 'zh' | 'en' | 'ja'

const MESSAGES: Record<AppLanguage, Record<string, string>> = {
  zh: {
    'nav.new': '新故事',
    'nav.game': '游戏',
    'nav.npcs': '角色',
    'nav.dashboard': '仪表盘',
    'nav.settings': '设置',
    'settings.title': '设置',
    'settings.reading': '阅读体验',
    'settings.ai': 'AI 行为',
    'settings.data': '数据与存档',
    'settings.ui': 'UI 偏好',
    'settings.api': 'API 密钥',
    'game.story': '正文',
    'game.choices': '做出你的选择',
    'game.status': '状态',
    'game.quickSettings': '生成快捷设置',
  },
  en: {
    'nav.new': 'New Story',
    'nav.game': 'Game',
    'nav.npcs': 'Characters',
    'nav.dashboard': 'Dashboard',
    'nav.settings': 'Settings',
    'settings.title': 'Settings',
    'settings.reading': 'Reading',
    'settings.ai': 'AI Behavior',
    'settings.data': 'Data & Saves',
    'settings.ui': 'UI Preferences',
    'settings.api': 'API Key',
    'game.story': 'Story',
    'game.choices': 'Make your choice',
    'game.status': 'Status',
    'game.quickSettings': 'Quick gen settings',
  },
  ja: {
    'nav.new': '新規ストーリー',
    'nav.game': 'ゲーム',
    'nav.npcs': 'キャラ',
    'nav.dashboard': 'ダッシュボード',
    'nav.settings': '設定',
    'settings.title': '設定',
    'settings.reading': '読書体験',
    'settings.ai': 'AI 動作',
    'settings.data': 'データとセーブ',
    'settings.ui': 'UI 設定',
    'settings.api': 'API キー',
    'game.story': '本文',
    'game.choices': '選択してください',
    'game.status': 'ステータス',
    'game.quickSettings': '生成クイック設定',
  },
}

export function t(key: string, lang: AppLanguage = 'zh'): string {
  return MESSAGES[lang]?.[key] ?? MESSAGES.zh[key] ?? key
}

export function applyDocumentLanguage(lang: AppLanguage) {
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : lang
}
