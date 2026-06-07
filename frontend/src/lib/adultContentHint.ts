/** Keep in sync with config.py is_clearly_adult_content / suggest_adult_mode_for_options */

const INTIMATE_KEYWORDS = [
  '吻', '亲', '摸', '抱', '脱', '床', '做', '爱', '性', '裸', '胸', '腿', '腰',
  '唇', '舌', '进入', '插入', '高潮', '情欲', '诱惑', '撩', '色', '欲', '肉体',
  '抚摸', '解开', '按在', '扑倒', '缠绵', '欢爱', '做爱', '上床', '侵犯', '占有',
]

const ORGASM_MARKERS = [
  '高潮', '绝顶', '去了', '痉挛', '颤抖着释放', '潮吹', '泄身', '攀上顶峰',
  '身体绷紧', '一阵酥麻', '软倒', '余韵', '瘫软',
]

const EXPLICIT_PHRASES = [
  '做爱', '性交', '性行为', '色情', '裸体', '全裸', '口交', '肛交', '乳交',
  '手淫', '自慰', '淫', '骚', '勃起', '阳具', '阴部', '私处', '春药',
  'AV', '黄片', '援交', '卖淫', '嫖娼',
]

function countIntimateMarkers(text: string): number {
  let n = 0
  for (const kw of INTIMATE_KEYWORDS) {
    if (text.includes(kw)) n += 1
  }
  return n
}

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
  return countIntimateMarkers(t) >= 2
}

export function suggestsAdultModeForOptions(options: string[]): boolean {
  if (!options.length) return false
  return options.some((o) => isClearlyAdultContent(o))
}

export function suggestsAdultModeForText(text: string): boolean {
  return isClearlyAdultContent(text)
}
