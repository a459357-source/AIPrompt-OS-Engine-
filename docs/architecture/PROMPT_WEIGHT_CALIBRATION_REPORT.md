# PROMPT_WEIGHT_CALIBRATION_REPORT

Phase 3B — Prompt Weight Calibration（V4.1）

**校准结论：FAIL**

## 1. 背景

Phase 3A 判定 **Architecture PASS / Weight Calibration FAIL**。
本阶段仅在 Unified Prompt 上校准 Mode Context 权重（World / Plot / Relationship），禁止回滚双 Prompt。

| 代码 Story 默认 | world 45% / plot 35% / rel 20% |
| 代码 Adult 默认 | world 20% / plot 25% / rel 55% |

## 2. 实验组（A–D）

| 组 | World | Plot | Relationship | 说明 |
|---|---:|---:|---:|---|
| A | 45% | 35% | 20% | 当前版本（ADR Story 基准） |
| B | 40% | 30% | 30% | 关系 +10 |
| C | 35% | 30% | 35% | 关系 +15 |
| D | 30% | 30% | 40% | 关系 +20 |

## 3. Legacy 基线（Phase 3A，05/08/09）

| 场景 | relationship_activity_rate | objective_progress_rate |
|---|---:|---:|
| 05_noble_academy | 0.241 | 0.2 |
| 08_xianxia_dual | 0.233 | 0.2 |
| 09_adventure_romance | 0.251 | 0.1 |

## 4. 四组权重结果

| 组 | 场景 | rel_rate | obj_rate | brain | recovery | cost USD |
|---|---|---:|---:|---:|---:|---:|
| A | 05_noble_academy | 0.186 | 0.9 | 1.0 | 0.7718 | 0.0034 |
| A | 08_xianxia_dual | 0.149 | 0.8 | 1.0 | 0.6395 | 0.0064 |
| A | 09_adventure_romance | 0.192 | 0.8 | 1.0 | 0.7649 | 0.0039 |
| B | 05_noble_academy | 0.198 | 0.7 | 1.0 | 0.8216 | 0.0035 |
| B | 08_xianxia_dual | 0.221 | 1.0 | 1.0 | 0.9485 | 0.0038 |
| B | 09_adventure_romance | 0.208 | 0.6 | 1.0 | 0.8287 | 0.0068 |
| C | 05_noble_academy | 0.195 | 0.7 | 1.0 | 0.8091 | 0.0037 |
| C | 08_xianxia_dual | 0.159 | 0.8 | 1.0 | 0.6824 | 0.0057 |
| C | 09_adventure_romance | 0.207 | 0.9 | 1.0 | 0.8247 | 0.0052 |
| D | 05_noble_academy | 0.199 | 0.9 | 1.0 | 0.8257 | 0.0056 |
| D | 08_xianxia_dual | 0.205 | 0.8 | 1.0 | 0.8798 | 0.004 |
| D | 09_adventure_romance | 0.172 | 1.0 | 1.0 | 0.6853 | 0.0038 |

## 5. Relationship Recovery Score（相对 Legacy）

目标：≥ 0.95（恢复至 Legacy 的 95% 以上）

| 组 | 平均 recovery | 最低场景 |
|---|---:|---|
| A | 0.7254 | 08_xianxia_dual (0.6395) |
| B | 0.8663 | 05_noble_academy (0.8216) |
| C | 0.7721 | 08_xianxia_dual (0.6824) |
| D | 0.7969 | 09_adventure_romance (0.6853) |

## 6. Main Goal 缺失原因分析

**主因分类：C**

Legacy 与 Unified 均高比例触发 heuristic；story 常含角色名/地点但不含 main_goal 前 8 字，属启发式误判（要求字面 substring 过严），非 Unified 独有回归。

- Legacy 触发率：1.0
- Unified 触发率：1.0
- 含关键词但不含 main_goal 前 8 字：58 回合

禁止在本阶段修改 heuristic 规则；评审后可考虑将判定改为 OBJECTIVES 进度或语义匹配，而非 main_goal[:8] 字面包含。

## 7. 推荐权重

**推荐组：B** — 关系 +10

- World 40% / Plot 30% / Relationship 30%
- 理由：平均 recovery 0.8663，最低 0.8216；objective 0.7667；cost 0.0047 USD

## 8. 是否修改 PromptStrategy

暂不改默认常量；优先完成未达标组的根因分析后重测。

## 9. 通过条件核对

- Relationship recovery（最低场景）❌ 0.8216 (需≥0.95)
- Objective 保持 ✅ 0.7667 (需≥0.7200000000000001)
- Brain consistency ✅ 1.0 (需≥0.98)
- Cost ❌ +11.9% vs 3A unified (需≤10%)

## 10. Phase 3B 后建议

校准未通过，**禁止**进入 V5.1 / V6.0 / V6.5；须调整权重或 PromptStrategy 后重测。
