# PROMPT_UNIFIED_REGRESSION_REPORT

Phase 3A — Prompt Unified Architecture 回归分析

**最终结论：FAIL**

## 1. 测试配置

| 项 | 值 |
|---|---|
| 开始时间 | 2026-06-08T05:01:08 |
| 结束时间 | 2026-06-08T06:36:28 |
| 模型 | deepseek-chat |
| 每场景回合 | 10 |
| 场景数 | 10 |
| 架构对比 | Legacy Extreme (`PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE=1`) vs Unified |
| API | 真实 DeepSeek（无 Mock/Replay） |

## 2. 测试场景

| ID | 类别 | 标签 |
|---|---|---|
| 01_xianxia | A | 修仙宗门试炼 |
| 02_wuxia | A | 武侠江湖恩怨 |
| 03_court_intrigue | B | 宫廷权谋 |
| 04_revenge_investigation | B | 复仇调查 |
| 05_noble_academy | C | 贵族学院 |
| 06_harem_management | C | 后宫经营 |
| 07_court_adult | D | 宫廷成人线 |
| 08_xianxia_dual | D | 修仙双修线 |
| 09_adventure_romance | E | 冒险+恋爱 |
| 10_intrigue_network | E | 权谋+关系网 |

## 3. 汇总统计（Legacy vs Unified）

| 指标 | Legacy | Unified | 变化 |
|---|---:|---:|---:|
| avg_story_length | 2813.1333 | 2672.8 | -5.0% |
| objective_progress_rate | 0.1667 | 0.9 | +439.9% |
| relationship_activity_rate | 0.1957 | 0.1958 | +0.1% |
| brain_consistency_score | 1.0 | 0.9889 | -1.1% |
| context_usage_score | 0.9889 | 0.9889 | 0.0% |
| avg_prompt_tokens | 2434.0333 | 2268.5222 | -6.8% |
| avg_completion_tokens | 545.1111 | 364.8667 | -33.1% |
| estimated_cost (USD) | 0.0045 | 0.0042 | -6.7% |
| avg_latency (s) | 31.7133 | 32.1556 | +1.4% |

## 4. 分类汇总

### 类别 A

| 场景 | objective Δ | relationship Δ | brain Δ |
|---|---:|---:|---:|
| 修仙宗门试炼 | +900.0% | +15.8% | 0.0% |
| 武侠江湖恩怨 | +400.0% | -8.5% | 0.0% |

### 类别 B

| 场景 | objective Δ | relationship Δ | brain Δ |
|---|---:|---:|---:|
| 宫廷权谋 | +300.0% | +11.4% | 0.0% |
| 复仇调查 | +700.0% | +65.0% | 0.0% |

### 类别 C

| 场景 | objective Δ | relationship Δ | brain Δ |
|---|---:|---:|---:|
| 贵族学院 | +350.0% | -20.8% | 0.0% |
| 后宫经营 | +800.0% | +20.2% | -10.0% |

### 类别 D

| 场景 | objective Δ | relationship Δ | brain Δ |
|---|---:|---:|---:|
| 宫廷成人线 | +400.0% | +27.3% | 0.0% |
| 修仙双修线 | +350.0% | -26.2% | 0.0% |

### 类别 E

| 场景 | objective Δ | relationship Δ | brain Δ |
|---|---:|---:|---:|
| 冒险+恋爱 | -100.0% | -100.0% | 0.0% |
| 权谋+关系网 | +80000000.0% | +16900000.0% | 0.0% |

## 5. Token / 成本 / 延迟

- Legacy 总估算成本（均值×场景）：约 $0.0045/场景
- Unified 总估算成本（均值×场景）：约 $0.0042/场景
- 成本变化：-6.7%

## 6. 失败案例

### 贵族学院 (05_noble_academy)
- objective_progress_rate: +350.0%
- relationship_activity_rate: -20.8%

### 修仙双修线 (08_xianxia_dual)
- objective_progress_rate: +350.0%
- relationship_activity_rate: -26.2%

### 冒险+恋爱 (09_adventure_romance)
- objective_progress_rate: -100.0%
- relationship_activity_rate: -100.0%

## 7. 成功案例

- **修仙宗门试炼**：Unified 在 objective/relationship 上持平或提升
- **宫廷权谋**：Unified 在 objective/relationship 上持平或提升
- **复仇调查**：Unified 在 objective/relationship 上持平或提升

## 8. 回归报警

- ⚠ Token 成本平均上升 39987.2%
- ❌ 05_noble_academy: relationship_activity_rate 下降 20.8% (>20%)
- ❌ 08_xianxia_dual: relationship_activity_rate 下降 26.2% (>20%)
- ❌ 09_adventure_romance: objective_progress_rate 下降 100.0% (>20%)
- ❌ 09_adventure_romance: relationship_activity_rate 下降 100.0% (>20%)
- ❌ 9 个场景 main_goal 连续 5 回合缺席

## 9. 范围说明

- Story Mode vs Adult Mode 权重对比未在本阶段执行（全部 extreme adult 设置）。
- brain/context 分数为启发式自动化指标，建议人工复核 story 原文。

## 10. Phase 3B 入口建议

回归未通过，**禁止**进入 V5.1 / V6.0 Visual / V6.5 Experience UI；须修复 Prompt Unified 后再测。
