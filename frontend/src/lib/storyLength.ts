/** Keep in sync with config.py story_length_float_margin */

export const STORY_LENGTH_SHORT_THRESHOLD = 1000
export const STORY_LENGTH_SHORT_FLOAT = 200
export const STORY_LENGTH_LONG_RATIO = 0.15
export const STORY_LENGTH_MAX_OVERFLOW = 1000

export function storyLengthFloatMargin(target: number): number {
  if (target < STORY_LENGTH_SHORT_THRESHOLD) return STORY_LENGTH_SHORT_FLOAT
  const pct = Math.floor(target * STORY_LENGTH_LONG_RATIO)
  return Math.min(STORY_LENGTH_MAX_OVERFLOW, Math.max(STORY_LENGTH_SHORT_FLOAT, pct))
}

export function storyTargetBounds(target: number, hardMin: number) {
  const margin = storyLengthFloatMargin(target)
  return {
    min: Math.max(hardMin, target - margin),
    max: target + margin,
  }
}

/** 用户可见的字数允许区间说明（与 config.py 一致） */
export function storyLengthRangeLabel(target: number, hardMin: number = 300): string {
  const { min, max } = storyTargetBounds(target, hardMin)
  const margin = storyLengthFloatMargin(target)
  if (target < STORY_LENGTH_SHORT_THRESHOLD) {
    return `允许 ${min.toLocaleString()}–${max.toLocaleString()} 字（目标 ${target.toLocaleString()}，±${margin}）`
  }
  return `允许 ${min.toLocaleString()}–${max.toLocaleString()} 字（目标 ${target.toLocaleString()}，±${margin}，15% 且最多 ±${STORY_LENGTH_MAX_OVERFLOW.toLocaleString()}）`
}
