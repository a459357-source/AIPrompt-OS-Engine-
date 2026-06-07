export interface StoryPresetCharacter {
  name: string
  isMain: boolean
  faction?: string
  role_tags: string[]
  personality_tags: string[]
  appearance: string
  relationship: string[]
  goal: string
  secret: string
  background: string
  special_ability: string
}

export interface StoryPreset {
  id: string
  label: string
  keywords: string
  form: {
    title: string
    world: string
    genre: string[]
    scene: string
    main_goal: string
    characters: StoryPresetCharacter[]
    rel_stages: string[]
    rel_affection: number
  }
  stats: { key: string; label: string; max: number }[]
}

export const STORY_PRESETS: StoryPreset[] = [
  {
    id: 'scifi',
    label: '🚀 星痕纪元',
    keywords: '科幻 星际 遗迹 星痕 回声号 碎星带',
    form: {
      title: '星痕纪元',
      world: '公元2247年，人类已进入星际殖民时代。在银河系边缘的「碎星带」，一艘名为「回声号」的调查船发现了一处远古外星遗迹。遗迹中封存着名为「星痕」的神秘能量。',
      genre: ['科幻', '冒险', '情感'],
      scene: '回声号 — 舰桥',
      main_goal: '调查星痕遗迹的真相',
      characters: [
        {
          name: '林夜', isMain: true, faction: '', role_tags: ['调查船船长', '退役军人'],
          personality_tags: ['冷静', '理性', '内敛', '有责任感'],
          appearance: '短发，眼神锐利，常穿深色作战服', relationship: [], goal: '寻找星痕背后的真相',
          secret: '', background: '曾参与第七远征舰队', special_ability: '星痕感知',
        },
        {
          name: '艾琳', isMain: false, faction: '', role_tags: ['考古语言学家'],
          personality_tags: ['热情', '好奇', '冲动', '敏锐'],
          appearance: '金色长发，碧绿色眼睛', relationship: ['工作伙伴'], goal: '破解星痕文字',
          secret: '能够听见遗迹中的低语', background: '', special_ability: '',
        },
      ],
      rel_stages: ['陌生', '熟悉', '朋友', '信赖', '暧昧', '恋人'],
      rel_affection: 0,
    },
    stats: [{ key: 'trust', label: '好感度', max: 100 }, { key: 'insight', label: '洞察力', max: 100 }],
  },
  {
    id: 'school',
    label: '🌸 樱之诗',
    keywords: '校园 恋爱 樱花 转学 学生会长',
    form: {
      title: '樱之诗',
      world: '私立樱丘学园，坐落于沿海小城。春天，樱花如雪般飘落。主人公在开学典礼那天，遇见了改变命运的两个人。',
      genre: ['校园', '恋爱', '日常'],
      scene: '樱丘学园 — 校门口樱花道',
      main_goal: '在樱花飘落的季节，找到属于自己的青春答案',
      characters: [
        {
          name: '小樱', isMain: true, faction: '', role_tags: ['转学生'],
          personality_tags: ['开朗', '温柔', '天然呆'],
          appearance: '粉色长发，常穿校服', relationship: [], goal: '融入新学校，交到朋友',
          secret: '', background: '因家庭原因频繁转学', special_ability: '',
        },
        {
          name: '雪乃', isMain: false, faction: '', role_tags: ['学生会长'],
          personality_tags: ['高冷', '完美主义', '外冷内热'],
          appearance: '黑色长发，戴眼镜', relationship: ['同班同学'], goal: '维持学生会权威',
          secret: '私下喜欢画漫画', background: '', special_ability: '',
        },
      ],
      rel_stages: ['陌生', '认识', '朋友', '知己', '暧昧', '恋人'],
      rel_affection: 0,
    },
    stats: [{ key: 'trust', label: '好感度', max: 100 }, { key: 'popularity', label: '人气', max: 100 }],
  },
  {
    id: 'fantasy',
    label: '⚔️ 剑与星辉',
    keywords: '奇幻 冒险 虚空裂隙 骑士 精灵',
    form: {
      title: '剑与星辉',
      world: '艾泽拉大陆，魔法与剑术并存的世界。千年和平被北方出现的「虚空裂隙」打破。王国的冒险者公会正在招募勇者。',
      genre: ['奇幻', '冒险', '史诗'],
      scene: '冒险者公会 — 王都大厅',
      main_goal: '封印虚空裂隙，拯救艾泽拉大陆',
      characters: [
        {
          name: '雷恩', isMain: true, faction: '', role_tags: ['流浪骑士'],
          personality_tags: ['正直', '勇敢', '沉默'],
          appearance: '银白短发，蓝色眼睛，身穿旧铠甲', relationship: [], goal: '找回失去的记忆',
          secret: '', background: '失去记忆的骑士', special_ability: '剑术无双',
        },
        {
          name: '艾莉西亚', isMain: false, faction: '', role_tags: ['精灵弓箭手'],
          personality_tags: ['冷静', '高傲', '忠诚'],
          appearance: '金色长发，尖耳朵，绿色披风', relationship: ['同伴', '救命恩人'], goal: '保护森林族人的安全',
          secret: '拥有预知箭术的能力', background: '', special_ability: '',
        },
      ],
      rel_stages: ['陌路', '同行', '战友', '信赖', '羁绊', '灵魂共鸣'],
      rel_affection: 0,
    },
    stats: [{ key: 'bond', label: '羁绊', max: 100 }, { key: 'power', label: '战力', max: 100 }],
  },
  {
    id: 'mystery',
    label: '🔍 第七日',
    keywords: '悬疑 推理 失踪案 咖啡馆 侦探',
    form: {
      title: '第七日',
      world: '现代都市。一连串离奇的失踪案打破了城市的平静。作为私家侦探的主角，在调查中发现所有线索都指向一家名为「第七日」的神秘咖啡馆。',
      genre: ['悬疑', '都市', '推理'],
      scene: '第七日咖啡馆 — 深夜',
      main_goal: '破解失踪案的真相，揭开第七日的秘密',
      characters: [
        {
          name: '苏晓', isMain: true, faction: '', role_tags: ['私家侦探'],
          personality_tags: ['冷静', '敏锐', '孤僻'],
          appearance: '黑色风衣，常戴墨镜', relationship: [], goal: '查明真相，找回失踪者',
          secret: '', background: '曾是一名刑警', special_ability: '过目不忘的观察力',
        },
        {
          name: '墨言', isMain: false, faction: '', role_tags: ['咖啡馆老板'],
          personality_tags: ['神秘', '优雅', '深不可测'],
          appearance: '黑发，常穿深色西装', relationship: ['线人', '对手'], goal: '守护第七日的秘密',
          secret: '知道所有失踪案的真相', background: '', special_ability: '',
        },
      ],
      rel_stages: ['陌生', '试探', '合作', '信任', '依赖', '命运共同体'],
      rel_affection: 0,
    },
    stats: [{ key: 'trust', label: '信任度', max: 100 }, { key: 'clue', label: '线索进度', max: 100 }],
  },
]
