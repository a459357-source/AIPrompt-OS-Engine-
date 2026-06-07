# Architecture Classification Template

复制本模板，为每个新功能填写一份分类文档。

---

## Feature

（功能名称，例如 Date System / Visual Scene Generator）

## Classification

Shared System | Mode Layer

（二选一；若两者均涉及，分别说明 Shared 部分与 Mode Layer 部分）

## Affected Modules

（受影响的模块列表，例如 RelationshipDynamics, PromptStrategy, Game.tsx）

## Notes

（设计说明、数据一致性约束、模式切换是否修改 Shared 数据）

---

### 示例

## Feature

Relationship Stage Display

## Classification

Mode Layer

## Affected Modules

ThemeStrategy, Game.tsx CharacterPanel, i18n

## Notes

底层 affection/trust 数值来自 Shared memory；Adult Mode 仅改变阶段标签映射，不写入新字段。
