# PromptOS Architecture Review — V4.x Closure Decision

Status: **Approved**  
Review Date: 2026-06-08  
Review Result: **V4.x Complete**

---

## 一、最终评审结论

经 Phase 3A（Prompt Unified Regression）与 Phase 3B（Prompt Weight Calibration）评审：

**V4.x 架构目标已完成。**

| 维度 | 结果 |
|------|------|
| Prompt Unified | 成功 |
| Objective System | 成功 |
| Character Brain | 成功 |
| Shared Context | 成功 |
| Cost Optimization | 成功（Unified 成本约 -8.7%） |
| Relationship Recovery | 未达校准目标（≥95% Legacy） |

**Relationship Recovery 不归因于 Prompt Architecture**，而归因于 **Relationship System 缺失**（无 Relationship Dynamics Engine）。继续调 Prompt Weight 收益边际递减。

证据文档：

- [`PROMPT_UNIFIED_REGRESSION_REPORT.md`](PROMPT_UNIFIED_REGRESSION_REPORT.md) — Phase 3A，Architecture PASS / Weight FAIL
- [`PROMPT_WEIGHT_CALIBRATION_REPORT.md`](PROMPT_WEIGHT_CALIBRATION_REPORT.md) — Phase 3B，校准 FAIL；推荐组 B (40/30/30) 未达 95% 恢复门槛

---

## 二、V4.x 正式关闭 — 批准项

| 项 | 状态 |
|----|------|
| V4.0 Prompt Unified Architecture | **Stable** |
| `PromptStrategy` 作为唯一 Prompt 架构 | 批准 |
| Builder Unified Path（`_build_prompt_unified`）为默认 | 批准 |
| `prompt_template_adult_extreme.yaml` | 继续 **deprecated**（紧急回退仅 `PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE=1`） |

## 三、V4.x 正式关闭 — 禁止项

- 恢复双 Prompt 架构
- 恢复 Builder → `adult_mode` 散布逻辑
- 继续进行 V4.x Weight Calibration 实验（含 `PROMPTOS_CALIBRATION_WEIGHTS` 生产化调参）
- 为 Relationship Recovery 继续堆 Prompt Weight 实验

---

## 四、Relationship 问题归因（评审）

Prompt 无法替代：

- 关系图谱
- 关系记忆与持久化
- 社交传播
- NPC↔NPC 网络
- Relationship Event

关系推进当前为 **Prompt Emergent Behavior**；下一阶段需升级为 **Engine Driven System**。

---

## 五、下一阶段入口

**批准启动：V5.1 Relationship Dynamics System（设计阶段）**

### V5.1 必须优先解决（来自回归报告）

1. Relationship Activity
2. Relationship Persistence
3. Relationship Recall

### V5.1 开发顺序

| Phase | 内容 |
|-------|------|
| A | Relationship Core |
| B | Relationship Memory |
| C | Relationship Graph |
| D | Character Brain Integration |
| E | Objective Integration |
| F | Plot Director Integration |
| 最后 | Dashboard / Analytics |

### V5.1 禁止优先项

- Dashboard
- 可视化 / Theme
- Experience UI

必须先完成 **Relationship Core Engine**。

---

## 六、版本生命周期

| 版本 | 名称 | Status |
|------|------|--------|
| V4.0 | Prompt Unified Architecture | **Stable** |
| V4.1 | Prompt Weight Calibration | **Closed** |
| V5.1 | Relationship Dynamics System | **Design Approved** |

---

## 七、工程现状快照（关闭时）

- 默认 Prompt：`prompt_template.yaml` + `PromptStrategy.build_mode_context()`
- Legacy 回退：环境变量 `PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE=1`（仅应急）
- Adult Mode Context 权重（代码默认）：World 20% / Plot 25% / Relationship 55%
- Story Mode Context 权重（代码默认）：World 45% / Plot 35% / Relationship 20%
- Phase 3B 实验推荐组 B (40/30/30) **未写入默认常量**（校准未 PASS，V4.1 已关闭）
