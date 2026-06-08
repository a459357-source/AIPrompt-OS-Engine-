# PromptOS Architecture Classification

本目录用于 **ADR-001 Experience Mode Architecture** 强制执行。

## 最高优先级

任何新功能开发前，必须先完成 **Architecture Classification**（架构分类）。

权威文档：[`doc/# ADR-001 — Experience Mode Archite.txt`](../doc/#%20ADR-001%20—%20Experience%20Mode%20Archite.txt)

## 流程

1. 复制 [`CLASSIFICATION_TEMPLATE.md`](CLASSIFICATION_TEMPLATE.md)
2. 填写 Feature / Classification / Affected Modules
3. 对照 [`REGISTRY.md`](REGISTRY.md) 确认不违反 Shared System 唯一性
4. 将分类文档随功能设计一并提交评审

## 禁止

- 未分类功能禁止开发（ADR §十四）
- Shared System 禁止双实现（StoryWorld / AdultMemory 等）
- 禁止在未分类情况下新增 `if adult_mode` 散布逻辑

## PR / Commit 检查清单

- [ ] 是否已完成 Architecture Classification？
- [ ] Classification 是 Shared System 还是 Mode Layer？
- [ ] 是否修改了 Memory / StoryGraph / CharacterBrain 等 Shared 数据分叉？
- [ ] 模式差异是否应进入 `engine/experience/` Strategy 而非业务模块？
- [ ] 模式切换是否保证 World / Memory / Timeline 数据不变？

## 版本状态（V4.x 已关闭）

| 版本 | 文档 | Status |
|------|------|--------|
| V4.0 | [`PROMPT_UNIFIED_DESIGN.md`](PROMPT_UNIFIED_DESIGN.md) | **Stable** |
| V4.1 | [`PROMPT_WEIGHT_CALIBRATION_REPORT.md`](PROMPT_WEIGHT_CALIBRATION_REPORT.md) | **Closed** |
| V5.1 | （待设计）Relationship Dynamics | **Design Approved** |

评审结论：[`V4_CLOSURE_DECISION.md`](V4_CLOSURE_DECISION.md)

## 交付归档

- [`ADR_FOUNDATION_REPORT.md`](ADR_FOUNDATION_REPORT.md) — Phase 1 experience_mode 兼容层
- [`PROMPT_UNIFIED_DESIGN.md`](PROMPT_UNIFIED_DESIGN.md) — V4.0 统一 Prompt 架构（Stable）
- [`PROMPT_UNIFIED_REGRESSION_REPORT.md`](PROMPT_UNIFIED_REGRESSION_REPORT.md) — Phase 3A
- [`PROMPT_WEIGHT_CALIBRATION_REPORT.md`](PROMPT_WEIGHT_CALIBRATION_REPORT.md) — Phase 3B
