# Style Bible v1（最小可用版）

**状态**: Implemented  
**日期**: 2026-06-08

## 定位

确定性 **prompt 约束层**：给所有资产生成注入统一世界视觉语言，不改 V6 架构。

```text
VisualIdentity
  → IdentityPromptBuilder (+ Content Template IP层)
  → StyleBible.apply()          ← v1 注入点
  → normalize_prompt → Provider → Image
  → Style Drift Detector        ← 见 V6_STYLE_DRIFT_DETECTOR.md
```

## 三模块

| 模块 | 实现 |
|------|------|
| Style Token Set | `STYLE_BIBLE_V1`（global / composition / material / tone） |
| Style Injection | `apply_style_bible(prompt, entity_type)` |
| Entity Binding | `ENTITY_STYLE_MAP`（character / location / faction / event） |

## 规则

- 只前置约束 token，不覆盖 identity 语义
- 不修改 registry / provider / UI
- `config.STYLE_BIBLE_V1_ENABLED = True`

## 文件

`engine/templates/style_bible.py`

## 与 Content Template 关系

- **Content Template**：IP  archetype / 世界观造型（`content_templates.json`）
- **Style Bible v1**：全局镜头与材质约束（代码常量，确定性）

二者串联，均在 `build_identity_prompt` 内完成。
