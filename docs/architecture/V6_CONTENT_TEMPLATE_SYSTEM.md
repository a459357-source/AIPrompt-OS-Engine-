# V6 Content Template System（IP 化层）

**状态**: Implemented  
**日期**: 2026-06-08

## 定位

世界内容的**标准化造型规则层**——不改 V6 运行时架构，只约束生成内容的 IP 风格分布。

```text
Content Template Layer（IP 造型）
    ↓
Visual Identity（V6.1 一致性）
    ↓
Style Bible v1（全局视觉 token 约束）→ 见 V6_STYLE_BIBLE_V1.md
    ↓
Prompt Builder → Image
```

## 四类模板

| 类型 | 关键 IP 字段 |
|------|----------------|
| Character | archetype, conflict_vector, visual_keywords |
| Location | function_in_world, atmosphere, dominant_materials |
| Faction | public_image, hidden_goal, visual_identity |
| Event | emotion_tone, visual_focus, conflict |

## 文件

| 路径 | 说明 |
|------|------|
| `engine/templates/` | 解析、注册、prompt 合并 |
| `data/content_templates.json` | 用户运行时（锁定后不变） |
| `packaging/defaults/content_templates.json` | style_bible + 空桶 |

## 核心 API

- `resolve_content_template(entity_type, entity_id, context)` — 首次推断并锁定
- `build_prompt_from_template(template, identity, base_prompt=...)`

## 原则

- template 决定**世界风格**
- identity 决定**实体一致性**
- 无 LLM、无 UI 生成触发

## 配置

`config.CONTENT_TEMPLATE_SYSTEM_ENABLED = True`
