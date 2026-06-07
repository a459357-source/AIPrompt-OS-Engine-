/** Keep in sync with config.py is_clearly_adult_content / suggest_adult_mode_for_options */

const ORGASM_MARKERS = [
  '高潮', '绝顶', '去了', '痉挛', '颤抖着释放', '潮吹', '泄身', '攀上顶峰',
  '身体绷紧', '一阵酥麻', '软倒', '余韵', '瘫软',
]

const EXPLICIT_PHRASES = [
  '做爱', '性交', '性行为', '色情', '裸体', '全裸', '口交', '肛交', '乳交',
  '手淫', '自慰', '淫', '骚', '勃起', '阳具', '阴部', '私处', '春药',
  'AV', '黄片', '援交', '卖淫', '嫖娼',
]

/** Unambiguous contextual phrases — stricter than loose intimate keywords. */
const STRONG_PHRASES = [
  '脱光', '脱衣', '裸露', '裸身', '一丝不挂',
  '深吻', '舌吻', '湿吻', '法式吻',
  '爱抚', '揉捏', '揉胸', '捏胸', '探入', '进入她', '进入他', '插入她', '插入他',
  '进入体内', '插入体',
  '解开衣', '解衣', '褪下', '扯下',
  '按在墙', '按在身', '按在床', '压在身', '压在她', '压在他身上',
  '扑倒在床', '扑倒她', '扑倒他',
  '缠绵', '欢爱', '侵犯', '占有', '强暴', '强奸',
  '情欲', '色欲', '肉欲', '发情',
  '抚摸她', '抚摸他', '抚摸身', '抚摸胸', '手探入',
]

function countOrgasmMarkers(text: string): number {
  let n = 0
  for (const kw of ORGASM_MARKERS) {
    if (text.includes(kw)) n += 1
  }
  return n
}

export function isClearlyAdultContent(text: string): boolean {
  const t = String(text || '').trim()
  if (!t) return false
  if (EXPLICIT_PHRASES.some((p) => t.includes(p))) return true
  if (countOrgasmMarkers(t) >= 1) return true
  return STRONG_PHRASES.some((p) => t.includes(p))
}

export function suggestsAdultModeForOptions(options: string[]): boolean {
  if (!options.length) return false
  return options.some((o) => isClearlyAdultContent(o))
}

export function suggestsAdultModeForText(text: string): boolean {
  return isClearlyAdultContent(text)
}
